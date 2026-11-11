import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import db, security

router = APIRouter(prefix='/api')


def scope(user):
    if user['role'] == 'admin':
        return None
    matches = db.rows('SELECT mine FROM mine_access WHERE username=?', (user['username'],))
    return matches[0]['mine'] if matches else None


def visible_jobs(user):
    mine = scope(user)
    return db.rows(
        """SELECT jobs.id FROM jobs JOIN evidence ON evidence.id=jobs.evidence_id
           WHERE (? IS NULL OR json_extract(evidence.body,'$.mine')=?)""", (mine, mine)
    )


class MineAccess(BaseModel):
    mine: str = Field(min_length=2, max_length=100)


@router.put('/users/{username}/mine')
def assign_mine(username: str, body: MineAccess, user=Depends(security.current)):
    security.require(user, 'admin')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        account = conn.execute('SELECT role FROM users WHERE username=?', (username,)).fetchone()
        if not account or account['role'] == 'admin':
            raise HTTPException(422, 'Select an existing non-admin account')
        conn.execute('INSERT INTO mine_access VALUES(?,?) ON CONFLICT(username) DO UPDATE SET mine=excluded.mine',
                     (username, body.mine))
        db.append_audit(conn, user['username'], 'access.mine_assigned', {'username': username, 'mine': body.mine})
    return {'mine': body.mine}


class Assignment(BaseModel):
    owner: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=10, max_length=2000)
    due_date: date


class Closure(BaseModel):
    evidence: str = Field(min_length=10, max_length=12000)


class Verification(BaseModel):
    decision: Literal['verified', 'returned']
    note: str = Field(min_length=10, max_length=2000)


def today():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


@router.get('/actions')
def actions(user=Depends(security.current)):
    mine = scope(user)
    records = db.rows('SELECT * FROM corrective_actions WHERE (? IS NULL OR mine=?) ORDER BY due_date, job_id, rule_id',
                      (mine, mine))
    for record in records:
        record['overdue'] = record['status'] != 'verified' and date.fromisoformat(record['due_date']) < today()
    return records


@router.post('/actions/{job_id}/{rule_id}', status_code=201)
def assign(job_id: str, rule_id: str, body: Assignment, user=Depends(security.current)):
    security.require(user, 'reviewer', 'admin')
    mine_scope = scope(user)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        job = conn.execute("""SELECT jobs.status,jobs.result,json_extract(evidence.body,'$.mine') AS mine
                            FROM jobs JOIN evidence ON evidence.id=jobs.evidence_id WHERE jobs.id=?""",
                           (job_id,)).fetchone()
        if not job or (mine_scope is not None and job['mine'] != mine_scope):
            raise HTTPException(404, 'Inspection not found')
        if job['status'] != 'approved':
            raise HTTPException(409, 'Approve the escalation before assigning actions')
        findings = json.loads(job['result'])['findings']
        if not any(f['rule_id'] == rule_id and f['status'] in ('breach', 'missing') for f in findings):
            raise HTTPException(422, 'Select a flagged finding')
        owner = conn.execute('SELECT role,mine FROM users LEFT JOIN mine_access USING(username) WHERE username=?',
                             (body.owner,)).fetchone()
        if not owner or owner['role'] != 'inspector' or owner['mine'] not in (None, job['mine']):
            raise HTTPException(422, 'Select an inspector with access to this mine')
        if body.due_date < today():
            raise HTTPException(422, 'Choose today or a future due date')
        inserted = conn.execute("""INSERT INTO corrective_actions(job_id,rule_id,mine,owner,description,due_date,status)
                                  VALUES(?,?,?,?,?,?,'assigned') ON CONFLICT(job_id,rule_id) DO NOTHING""",
                                (job_id, rule_id, job['mine'], body.owner, body.description, body.due_date.isoformat()))
        if not inserted.rowcount:
            raise HTTPException(409, 'This finding already has a corrective action')
        db.append_audit(conn, user['username'], 'action.assigned',
                        {'job_id': job_id, 'rule_id': rule_id, 'owner': body.owner})
    return {'status': 'assigned'}


def action_for(conn, job_id, rule_id, mine):
    row = conn.execute('SELECT * FROM corrective_actions WHERE job_id=? AND rule_id=?', (job_id, rule_id)).fetchone()
    if not row or (mine is not None and row['mine'] != mine):
        raise HTTPException(404, 'Corrective action not found')
    return row


@router.post('/actions/{job_id}/{rule_id}/evidence')
def submit_closure(job_id: str, rule_id: str, body: Closure, user=Depends(security.current)):
    mine = scope(user)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = action_for(conn, job_id, rule_id, mine)
        if row['owner'] != user['username']:
            raise HTTPException(403, 'Only the assigned inspector can submit closure evidence')
        if row['status'] not in ('assigned', 'returned'):
            raise HTTPException(409, 'This action is not accepting evidence')
        conn.execute("""UPDATE corrective_actions SET evidence=?,status='submitted',reviewer=NULL,review_note=NULL
                      WHERE job_id=? AND rule_id=?""", (body.evidence, job_id, rule_id))
        db.append_audit(conn, user['username'], 'action.evidence_submitted',
                        {'job_id': job_id, 'rule_id': rule_id, 'evidence': body.evidence})
    return {'status': 'submitted'}


@router.post('/actions/{job_id}/{rule_id}/verify')
def verify(job_id: str, rule_id: str, body: Verification, user=Depends(security.current)):
    security.require(user, 'reviewer', 'admin')
    mine = scope(user)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = action_for(conn, job_id, rule_id, mine)
        if row['owner'] == user['username']:
            raise HTTPException(403, 'A separate reviewer must verify closure')
        if row['status'] != 'submitted':
            raise HTTPException(409, 'This action has no evidence awaiting verification')
        conn.execute("""UPDATE corrective_actions SET status=?,reviewer=?,review_note=?
                      WHERE job_id=? AND rule_id=?""",
                     (body.decision, user['username'], body.note, job_id, rule_id))
        db.append_audit(conn, user['username'], 'action.' + body.decision,
                        {'job_id': job_id, 'rule_id': rule_id, 'note': body.note})
    return {'status': body.decision}
