"""Create unique local demo accounts. Never prints passwords to logs."""
import secrets
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from app import db, security

def setup():
    db.init()
    created=[]
    for username,role in [('admin','admin'),('inspector','inspector'),('reviewer','reviewer'),('viewer','viewer')]:
        if db.rows('SELECT username FROM users WHERE username=?',(username,)): continue
        password=secrets.token_urlsafe(18)
        db.execute('INSERT INTO users VALUES(?,?,?)',(username,security.hash_password(password),role))
        created.append(f'{username}: {password}')
    if created:
        access=Path('.local-access.txt')
        with access.open('a',encoding='utf8') as f:
            f.write('\n'.join(created)+'\n')
        access.chmod(0o600)
        print('Local accounts created. Passwords are in .local-access.txt (excluded from Git and release ZIP).')
    else: print('Accounts already exist; no passwords changed.')

if __name__=='__main__': setup()
