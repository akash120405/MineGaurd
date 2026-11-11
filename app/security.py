import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException, Request
from . import db

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
    return salt + ':' + digest

def check_password(password, stored):
    salt, expected = stored.split(':')
    actual = hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
    return hmac.compare_digest(expected, actual)

def current(request: Request):
    token = hashlib.sha256(request.cookies.get('session','').encode()).hexdigest()
    users = db.rows('SELECT users.username,users.role,sessions.csrf FROM sessions JOIN users USING(username) WHERE token=? AND expires>?',(token,time.time()))
    if not users:
        raise HTTPException(401,'Sign in to continue')
    user = users[0]
    if request.method not in ('GET','HEAD') and not hmac.compare_digest(request.headers.get('x-csrf-token',''),user['csrf']):
        raise HTTPException(403,'Invalid CSRF token')
    return user

def require(user, *roles):
    if user['role'] not in roles:
        raise HTTPException(403,'Your role cannot perform this action')
