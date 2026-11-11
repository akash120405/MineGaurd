import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

def connect():
    path = os.getenv('DATABASE_PATH', 'data/mineguard.db')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
    return c

def rows(sql, args=()):
    with connect() as c:
        return [dict(x) for x in c.execute(sql, args).fetchall()]

def execute(sql, args=()):
    with connect() as c:
        return c.execute(sql, args).rowcount

def audit(actor, action, detail):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        append_audit(c, actor, action, detail)

def append_audit(c, actor, action, detail):
    prev = c.execute('SELECT digest FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
    previous = prev[0] if prev else 'GENESIS'
    payload = json.dumps({'at': time.time(), 'actor': actor, 'action': action, 'detail': detail}, sort_keys=True)
    digest = hashlib.sha256((previous + payload).encode()).hexdigest()
    c.execute('INSERT INTO audit(payload,previous,digest) VALUES(?,?,?)', (payload, previous, digest))

def verify_audit():
    previous = 'GENESIS'
    for row in rows('SELECT * FROM audit ORDER BY seq'):
        if row['previous'] != previous or hashlib.sha256((previous + row['payload']).encode()).hexdigest() != row['digest']:
            return False
        previous = row['digest']
    return True

DEMO_RULES = [
 {'id':'DEMO-VENT-01','title':'Ventilation inspection record','category':'Ventilation','text':'Demonstration policy: each submitted inspection must record ventilation airflow and inspector identity. Missing evidence requires review. This is not a statutory threshold.','metric':'airflow_m3_s','minimum':5,'unit':'m³/s'},
 {'id':'DEMO-GAS-02','title':'Methane monitoring','category':'Gas safety','text':'Demonstration policy: a methane observation above 1.0 percent creates a high-priority review. Missing measurements require review. The threshold is illustrative, not a legal limit.','metric':'methane_pct','maximum':1,'unit':'%'},
 {'id':'DEMO-DUST-03','title':'Dust control inspection','category':'Occupational health','text':'Demonstration policy: a dust observation above 2.0 mg/m³ creates a high-priority review. Missing measurements require review. The threshold is illustrative, not a legal limit.','metric':'dust_mg_m3','maximum':2,'unit':'mg/m³'}
]

def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,password TEXT NOT NULL,role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,username TEXT NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS rules(id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,body TEXT NOT NULL,actor TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,evidence_id TEXT UNIQUE NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,result TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS decisions(job_id TEXT PRIMARY KEY,decision TEXT NOT NULL,note TEXT NOT NULL,actor TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS traces(id INTEGER PRIMARY KEY,job_id TEXT,agent TEXT,tool TEXT,duration_ms REAL,detail TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,payload TEXT NOT NULL,previous TEXT NOT NULL,digest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,username TEXT NOT NULL,question TEXT,answer TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS login_attempts(ip TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS mine_access(username TEXT PRIMARY KEY REFERENCES users(username),mine TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS corrective_actions(
            job_id TEXT NOT NULL REFERENCES jobs(id), rule_id TEXT NOT NULL,
            mine TEXT NOT NULL, owner TEXT NOT NULL REFERENCES users(username),
            description TEXT NOT NULL, due_date TEXT NOT NULL,
            status TEXT NOT NULL, evidence TEXT, reviewer TEXT, review_note TEXT,
            PRIMARY KEY(job_id,rule_id)
        );
        ''')
        for rule in DEMO_RULES:
            c.execute('INSERT OR IGNORE INTO rules VALUES(?,?)', (rule['id'], json.dumps(rule)))

def identifier():
    return uuid.uuid4().hex
