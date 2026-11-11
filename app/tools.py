"""Narrow, read-only agent tools. No shell, arbitrary URLs or database SQL from models."""
import json
import re
from . import db

INJECTION = re.compile(r'ignore\s+(all\s+)?(previous|prior|system)|system\s*prompt|reveal.*(key|secret)|<\|im_start\|>|override.*instructions', re.I)

def search_rules(query: str, limit: int = 5):
    """Lexical RAG over the administrator-curated, version-snapshotted rule corpus."""
    terms = set(re.findall(r'[a-z0-9]+', query.lower()))
    rules = [json.loads(r['body']) for r in db.rows('SELECT body FROM rules')]
    scored = [(len(terms & set(re.findall(r'[a-z0-9]+',json.dumps(r).lower()))), r) for r in rules]
    return [r for score,r in sorted(scored,key=lambda x:x[0],reverse=True)[:limit] if score > 0]

def get_evidence(evidence_id):
    found = db.rows('SELECT body FROM evidence WHERE id=?',(evidence_id,))
    if not found:
        raise ValueError('Evidence record not found')
    return json.loads(found[0]['body'])

def evaluate(evidence, rules):
    findings = []
    for r in rules:
        value = evidence.get(r['metric'])
        missing = value is None
        exceeded = not missing and ((r.get('minimum') is not None and value < r['minimum']) or (r.get('maximum') is not None and value > r['maximum']))
        status = 'missing' if missing else 'breach' if exceeded else 'pass'
        findings.append({'rule_id':r['id'],'title':r['title'],'status':status,'value':value,'unit':r['unit'],'metric':r['metric'],'source_quote':r['text'],'rule_snapshot':r})
    return findings

def validate_claims(data, rules, evidence_text):
    """A citation gate, not proof of semantic truth. Unsupported claims are suppressed."""
    sources = {r['id']:r['text'] for r in rules}
    valid, rejected = [], []
    for claim in data.get('claims',[])[:12]:
        if not isinstance(claim,dict):
            rejected.append('Malformed claim'); continue
        quote = claim.get('quote','')
        evidence_quote = claim.get('evidence_quote','')
        if (not isinstance(claim.get('rule_id'),str) or not isinstance(quote,str) or len(quote)<15 or quote not in sources.get(claim.get('rule_id'),'')
            or not isinstance(evidence_quote,str) or len(evidence_quote)<5 or evidence_quote not in evidence_text):
            rejected.append('Unverifiable source or evidence quote'); continue
        valid.append({k:str(claim.get(k,''))[:2000] for k in ('rule_id','quote','evidence_quote','explanation')})
    return {'claims':valid,'rejected':rejected,'disclaimer':'Citations verified; interpretation still requires human review.'}
