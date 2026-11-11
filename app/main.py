import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import db, security, tools, providers
from .agents import run_job
from . import governance
from .models import Inspection, Login, Decision, Question, UserCreate, Rule

async def worker():
    while True:
        jobs=db.rows("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1")
        if jobs:
            job=jobs[0]
            if db.execute("UPDATE jobs SET status='processing' WHERE id=? AND status='queued'",(job['id'],)):
                try:
                    await asyncio.wait_for(run_job(job),120)
                except Exception as exc:
                    db.execute("UPDATE jobs SET status='failed',error=? WHERE id=?",('Workflow failed: '+type(exc).__name__,job['id']))
                    db.audit('agent-runtime','workflow.failed',{'job_id':job['id'],'type':type(exc).__name__})
        await asyncio.sleep(.5)

@asynccontextmanager
async def lifespan(app):
    db.init()
    initial_password = os.getenv('INITIAL_ADMIN_PASSWORD', '')
    if initial_password and not db.rows('SELECT username FROM users LIMIT 1'):
        initial_username = os.getenv('INITIAL_ADMIN_USERNAME', 'admin')
        if len(initial_password) < 16:
            raise RuntimeError('INITIAL_ADMIN_PASSWORD must be at least 16 characters')
        db.execute('INSERT INTO users VALUES(?,?,?)',
                   (initial_username, security.hash_password(initial_password), 'admin'))
        db.audit(initial_username, 'auth.bootstrap', {'role': 'admin'})
    # Single-process service: unfinished durable jobs resume after restart.
    db.execute("UPDATE jobs SET status='queued' WHERE status='processing'")
    task=asyncio.create_task(worker())
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass

app=FastAPI(title='MineGuard compliance API',version='1.0.0',lifespan=lifespan)
app.include_router(governance.router)
STATIC=Path(__file__).resolve().parent.parent/'static'
app.mount('/static',StaticFiles(directory=STATIC),name='static')

@app.middleware('http')
async def protection(request,call_next):
    if int(request.headers.get('content-length','0') or 0)>100000:
        return JSONResponse({'detail':'Request exceeds 100 KB'},413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control']='no-store'
    return response

@app.get('/')
def index(): return FileResponse(STATIC/'index.html')

@app.get('/health')
def health():
    db.rows('SELECT 1')
    return {'status':'ok','service':'mineguard'}

@app.post('/api/login')
def login(body:Login,request:Request,response:Response):
    ip=request.client.host if request.client else 'unknown'
    db.execute('DELETE FROM login_attempts WHERE created<?',(time.time()-900,))
    if len(db.rows('SELECT 1 FROM login_attempts WHERE ip=?',(ip,)))>=10:
        raise HTTPException(429,'Too many sign-in attempts; retry in 15 minutes')
    db.execute('INSERT INTO login_attempts VALUES(?,?)',(ip,time.time()))
    users=db.rows('SELECT * FROM users WHERE username=?',(body.username,))
    if not users or not security.check_password(body.password,users[0]['password']):
        raise HTTPException(401,'Invalid credentials')
    token=secrets.token_urlsafe(32)
    csrf=secrets.token_urlsafe(24)
    db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),body.username,csrf,time.time()+28800))
    response.set_cookie('session',token,httponly=True,secure=os.getenv('COOKIE_SECURE','false')=='true',samesite='strict',max_age=28800)
    db.audit(body.username,'auth.login',{})
    return {'username':body.username,'role':users[0]['role'],'csrf':csrf}

@app.post('/api/logout')
def logout(request:Request,response:Response,user=Depends(security.current)):
    db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies['session'].encode()).hexdigest(),))
    response.delete_cookie('session')
    return {'ok':True}

@app.get('/api/me')
def me(user=Depends(security.current)): return user

@app.get('/api/state')
def state(user=Depends(security.current)):
    mine=governance.scope(user)
    jobs=db.rows("""SELECT jobs.*,decisions.decision,decisions.note,decisions.actor AS reviewer
                    FROM jobs JOIN evidence ON evidence.id=jobs.evidence_id
                    LEFT JOIN decisions ON decisions.job_id=jobs.id
                    WHERE (? IS NULL OR json_extract(evidence.body,'$.mine')=?)
                    ORDER BY jobs.created DESC LIMIT 200""",(mine,mine))
    for j in jobs:
        j['result']=json.loads(j['result']) if j['result'] else None
    traces=db.rows("""SELECT traces.* FROM traces JOIN jobs ON jobs.id=traces.job_id
                      JOIN evidence ON evidence.id=jobs.evidence_id
                      WHERE (? IS NULL OR json_extract(evidence.body,'$.mine')=?)
                      ORDER BY traces.id DESC LIMIT 100""",(mine,mine))
    return {'jobs':jobs,'rules':[json.loads(r['body']) for r in db.rows('SELECT body FROM rules')],'providers':{'groq':bool(os.getenv('GROQ_API_KEY')),'gemini':bool(os.getenv('GEMINI_API_KEY'))},'ai_enabled':os.getenv('AI_ENABLED','true')=='true','audit_valid':db.verify_audit(),'traces':traces,'mine':mine}

@app.post('/api/inspections',status_code=202)
def inspection(body:Inspection,user=Depends(security.current)):
    security.require(user,'inspector','admin')
    mine=governance.scope(user)
    if mine is not None and body.mine!=mine:
        raise HTTPException(403,'Submit inspections only for your assigned mine')
    try:
        observed=datetime.fromisoformat(body.observed_at.replace('Z','+00:00'))
        if observed.tzinfo is None: raise ValueError()
        if observed.timestamp()>time.time()+300: raise ValueError()
    except ValueError:
        raise HTTPException(422,'Observation time must include timezone and cannot be in the future')
    eid,jid=db.identifier(),db.identifier()
    with db.connect() as c:
        c.execute('INSERT INTO evidence VALUES(?,?,?,?)',(eid,body.model_dump_json(),user['username'],time.time()))
        c.execute('INSERT INTO jobs VALUES(?,?,?,?,NULL,NULL)',(jid,eid,'queued',time.time()))
    db.audit(user['username'],'inspection.submitted',{'evidence_id':eid,'job_id':jid})
    return {'job_id':jid,'status':'queued'}

@app.post('/api/jobs/{job_id}/decision')
def decide(job_id:str,body:Decision,user=Depends(security.current)):
    security.require(user,'reviewer','admin')
    mine=governance.scope(user)
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        job=c.execute("""SELECT jobs.*,evidence.actor FROM jobs JOIN evidence ON evidence.id=jobs.evidence_id
                         WHERE jobs.id=? AND (? IS NULL OR json_extract(evidence.body,'$.mine')=?)""",(job_id,mine,mine)).fetchone()
        if not job: raise HTTPException(404,'Job not found')
        if job['actor']==user['username']: raise HTTPException(403,'A different reviewer must decide your submission')
        if job['status']!='awaiting_review': raise HTTPException(409,'Job is not awaiting review')
        c.execute('INSERT INTO decisions VALUES(?,?,?,?,?)',(job_id,body.decision,body.note,user['username'],time.time()))
        c.execute('UPDATE jobs SET status=? WHERE id=?',(body.decision,job_id))
    db.audit(user['username'],'review.'+body.decision,{'job_id':job_id,'note':body.note})
    return {'status':body.decision}

@app.post('/api/jobs/{job_id}/retry')
def retry(job_id:str,user=Depends(security.current)):
    security.require(user,'admin')
    if not db.execute("UPDATE jobs SET status='queued',error=NULL WHERE id=? AND status='failed'",(job_id,)):
        raise HTTPException(409,'Only failed jobs can be retried')
    db.audit(user['username'],'workflow.retry',{'job_id':job_id})
    return {'status':'queued'}

@app.get('/api/audit')
def audit(user=Depends(security.current)):
    events=db.rows('SELECT * FROM audit ORDER BY seq DESC LIMIT 1000')
    if governance.scope(user) is not None:
        jobs={row['id'] for row in governance.visible_jobs(user)}
        events=[event for event in events if json.loads(event['payload'])['detail'].get('job_id') in jobs]
        events=[{key: value for key, value in event.items() if key == 'payload'} for event in events]
    return {'valid':db.verify_audit(),'events':events}

@app.get('/api/export')
def export(user=Depends(security.current)):
    db.audit(user['username'],'report.exported',{})
    return JSONResponse({'exported_at':datetime.now(timezone.utc).isoformat(),'jobs':state(user)['jobs'],'actions':governance.actions(user),'audit':audit(user)},headers={'Content-Disposition':'attachment; filename="mineguard-report.json"'})

@app.post('/api/rules')
def add_rule(body:Rule,user=Depends(security.current)):
    security.require(user,'admin')
    if body.minimum is None and body.maximum is None: raise HTTPException(422,'A threshold is required')
    if body.minimum is not None and body.maximum is not None and body.minimum>body.maximum: raise HTTPException(422,'Minimum exceeds maximum')
    if tools.INJECTION.search(body.text): raise HTTPException(422,'Suspicious instructions in rule content')
    try: db.execute('INSERT INTO rules VALUES(?,?)',(body.id,body.model_dump_json()))
    except sqlite3.IntegrityError: raise HTTPException(409,'Rule IDs are immutable; use a new version ID')
    db.audit(user['username'],'rule.added',{'id':body.id})
    return {'id':body.id}

@app.post('/api/users')
def add_user(body:UserCreate,user=Depends(security.current)):
    security.require(user,'admin')
    try: db.execute('INSERT INTO users VALUES(?,?,?)',(body.username,security.hash_password(body.password),body.role))
    except sqlite3.IntegrityError: raise HTTPException(409,'Username already exists')
    db.audit(user['username'],'user.created',{'username':body.username,'role':body.role})
    return {'username':body.username,'role':body.role}

@app.get('/api/chat')
def chat_history(user=Depends(security.current)):
    return db.rows('SELECT question,answer FROM messages WHERE username=? ORDER BY id DESC LIMIT 20',(user['username'],))[::-1]

@app.post('/api/chat')
async def chat(body:Question,user=Depends(security.current)):
    if tools.INJECTION.search(body.question): raise HTTPException(422,'Instruction override detected; ask an evidence or policy question')
    recent=db.rows('SELECT created FROM messages WHERE username=? ORDER BY id DESC LIMIT 1',(user['username'],))
    if recent and time.time()-recent[0]['created']<3: raise HTTPException(429,'Please wait a moment before asking again')
    rules=tools.search_rules(body.question)
    history=chat_history(user)[-3:]
    evidence_text=json.dumps({'question':body.question,'history':history},ensure_ascii=False)
    if not rules:
        answer={'claims':[],'rejected':[],'provider':'none','errors':[],'message':'No matching rule was found. Add a verified policy to the rule library before relying on an answer.'}
    else:
        raw,provider,errors=await providers.analyze(json.dumps({'question':body.question,'evidence':evidence_text,'rules':rules},ensure_ascii=False))
        answer=tools.validate_claims(raw,rules,evidence_text)
        answer.update(provider=provider,errors=errors,message='Retrieved policy excerpts are shown below. AI interpretations require review.')
    answer['sources']=[{'id':r['id'],'title':r['title'],'text':r['text']} for r in rules]
    db.execute('INSERT INTO messages(username,question,answer,created) VALUES(?,?,?,?)',(user['username'],body.question,json.dumps(answer),time.time()))
    db.audit(user['username'],'chat.answered',{'provider':answer['provider'],'sources':[r['id'] for r in rules]})
    return answer

@app.get('/api/metrics')
def metrics(user=Depends(security.current)):
    mine=governance.scope(user)
    join=" JOIN evidence ON evidence.id=jobs.evidence_id WHERE (? IS NULL OR json_extract(evidence.body,'$.mine')=?)"
    return {'jobs':db.rows('SELECT status,COUNT(*) AS count FROM jobs'+join+' GROUP BY status',(mine,mine)),
            'agents':db.rows('SELECT agent,COUNT(*) AS calls,ROUND(AVG(duration_ms),2) AS avg_ms FROM traces JOIN jobs ON jobs.id=traces.job_id'+join+' GROUP BY agent',(mine,mine)),
            'audit_valid':db.verify_audit()}
