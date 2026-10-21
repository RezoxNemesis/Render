"""Durable phone-owned control plane. No Blender execution or file hosting here."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, ValidationError, SchemaError


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()


def random_token():
    return secrets.token_urlsafe(32)


class Denied(Exception):
    def __init__(self, reason, status=400):
        super().__init__(reason)
        self.reason, self.status = reason, status


class Relay:
    TERMINAL = {'succeeded', 'failed', 'cancelled', 'recovery_required'}

    def __init__(self, database, origin, enrollment_secret, clock=time.time):
        p = urlsplit(origin)
        if p.scheme != 'https' or not p.hostname or p.username or p.query or p.fragment or p.path not in ('', '/'):
            raise ValueError('PUBLIC_URL must be an HTTPS origin')
        if len(enrollment_secret) < 32:
            raise ValueError('Enrollment secret must contain at least 32 random characters')
        self.origin, self.resource = origin.rstrip('/'), origin.rstrip('/') + '/mcp'
        self.database, self.clock, self.bootstrap = str(database), clock, hashed(enrollment_secret)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,token TEXT UNIQUE,name TEXT,
              revoked INTEGER NOT NULL DEFAULT 0,enabled INTEGER NOT NULL DEFAULT 0,heartbeat REAL DEFAULT 0,caps TEXT DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS links(hash TEXT PRIMARY KEY,device TEXT,expires REAL,used INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY,redirects TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS codes(hash TEXT PRIMARY KEY,client TEXT,device TEXT,redirect TEXT,
              challenge TEXT,resource TEXT,scope TEXT,expires REAL,used INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY,kind TEXT,client TEXT,device TEXT,
              resource TEXT,scope TEXT,expires REAL,family TEXT,used INTEGER DEFAULT 0,revoked INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,request TEXT,device TEXT,digest TEXT,
              payload TEXT,state TEXT,result TEXT,updated REAL,UNIQUE(device,request));
            CREATE TABLE IF NOT EXISTS rates(key TEXT PRIMARY KEY,bucket INTEGER,count INTEGER);
            CREATE TABLE IF NOT EXISTS forms(id TEXT PRIMARY KEY,cookie TEXT,payload TEXT,expires REAL,used INTEGER DEFAULT 0);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=20, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=20000')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def rate(self, key, limit=30, window=60):
        bucket = int(self.clock() // window)
        with self.db() as db:
            row = db.execute('SELECT * FROM rates WHERE key=?', (key,)).fetchone()
            count = row['count'] + 1 if row and row['bucket'] == bucket else 1
            if count > limit:
                raise Denied('RATE_LIMITED', 429)
            db.execute('INSERT OR REPLACE INTO rates VALUES(?,?,?)', (key, bucket, count))

    def _device(self, db, token):
        row = db.execute('SELECT * FROM devices WHERE token=? AND revoked=0', (hashed(token),)).fetchone()
        if not row:
            raise Denied('DEVICE_AUTH_REQUIRED', 401)
        return row

    def _access(self, db, token):
        row = db.execute('SELECT t.*,d.enabled,d.heartbeat,d.name,d.caps,d.revoked AS device_revoked FROM tokens t '
                         'JOIN devices d ON t.device=d.id WHERE t.hash=? AND t.kind=\'access\'', (hashed(token),)).fetchone()
        if not row or row['revoked'] or row['device_revoked'] or row['expires'] <= self.clock() or row['resource'] != self.resource or row['scope'] != 'render':
            raise Denied('OAUTH_REQUIRED', 401)
        return row

    def _link(self, db, device):
        db.execute('UPDATE links SET used=1 WHERE device=?', (device,))
        code = secrets.token_hex(8).upper()
        db.execute('INSERT INTO links(hash,device,expires) VALUES(?,?,?)', (hashed(code), device, self.clock()+600))
        return {'link_code': code, 'expires_in': 600}

    def enroll(self, secret, name):
        if not isinstance(secret, str) or not hmac.compare_digest(hashed(secret), self.bootstrap):
            raise Denied('INVALID_ENROLLMENT', 403)
        if not isinstance(name, str) or not 1 <= len(name) <= 80:
            raise Denied('INVALID_DEVICE_NAME')
        with self.db() as db:
            if db.execute('SELECT 1 FROM settings WHERE key=?', ('enrolled:'+self.bootstrap,)).fetchone():
                raise Denied('ENROLLMENT_ALREADY_USED', 409)
            device, token = secrets.token_hex(16), random_token()
            db.execute('INSERT INTO devices(id,token,name) VALUES(?,?,?)', (device, hashed(token), name))
            db.execute('INSERT INTO settings VALUES(?,?)', ('enrolled:'+self.bootstrap,device))
            return {'device_id': device, 'device_token': token, **self._link(db,device)}

    def link_code(self, device_token):
        with self.db() as db:
            device = self._device(db,device_token)
            return self._link(db,device['id'])

    @staticmethod
    def allowed_redirect(uri):
        return isinstance(uri,str) and (uri == 'https://chatgpt.com/connector_platform_oauth_redirect' or
               re.fullmatch(r'https://chatgpt\.com/connector/oauth/[A-Za-z0-9_-]{1,160}',uri) is not None)

    def register(self, redirects):
        if not isinstance(redirects,list) or not 1 <= len(redirects) <= 4 or not all(self.allowed_redirect(x) for x in redirects):
            raise Denied('REDIRECT_NOT_ALLOWED')
        with self.db() as db:
            if db.execute('SELECT COUNT(*) FROM clients').fetchone()[0] >= 200:
                raise Denied('CLIENT_REGISTRATION_LIMIT',429)
            client = 'render_'+secrets.token_hex(16)
            db.execute('INSERT INTO clients VALUES(?,?,?)', (client,canonical(redirects),self.clock()))
        return {'client_id':client,'redirect_uris':redirects,'token_endpoint_auth_method':'none',
                'grant_types':['authorization_code','refresh_token'],'response_types':['code']}

    def _auth_params(self, db, client, redirect, challenge, resource, scope):
        row = db.execute('SELECT * FROM clients WHERE id=?',(client,)).fetchone()
        if not row or redirect not in json.loads(row['redirects']):
            raise Denied('UNREGISTERED_CLIENT_OR_REDIRECT')
        if resource != self.resource or scope != 'render':
            raise Denied('INVALID_RESOURCE_OR_SCOPE')
        if not isinstance(challenge,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',challenge):
            raise Denied('PKCE_S256_REQUIRED')

    def validate_authorize(self, client, redirect, challenge, resource, scope):
        with self.db() as db:
            self._auth_params(db,client,redirect,challenge,resource,scope)

    def authorize(self, client, redirect, challenge, link_code, resource, scope):
        with self.db() as db:
            self._auth_params(db,client,redirect,challenge,resource,scope)
            if not isinstance(link_code,str): raise Denied('INVALID_PHONE_LINK_CODE',403)
            row = db.execute('SELECT l.*,d.revoked FROM links l JOIN devices d ON d.id=l.device WHERE l.hash=?',
                             (hashed(link_code.strip().upper()),)).fetchone()
            if not row or row['used'] or row['revoked'] or row['expires'] <= self.clock():
                raise Denied('INVALID_PHONE_LINK_CODE',403)
            db.execute('UPDATE links SET used=1 WHERE hash=?',(row['hash'],))
            code=random_token()
            db.execute('INSERT INTO codes(hash,client,device,redirect,challenge,resource,scope,expires) VALUES(?,?,?,?,?,?,?,?)',
                       (hashed(code),client,row['device'],redirect,challenge,resource,scope,self.clock()+120))
            return code

    def _issue(self, db, client, device, family=None):
        family=family or secrets.token_hex(16)
        access, refresh=random_token(),random_token()
        for token,kind,ttl in [(access,'access',3600),(refresh,'refresh',2592000)]:
            db.execute('INSERT INTO tokens(hash,kind,client,device,resource,scope,expires,family) VALUES(?,?,?,?,?,?,?,?)',
                       (hashed(token),kind,client,device,self.resource,'render',self.clock()+ttl,family))
        return {'access_token':access,'refresh_token':refresh,'token_type':'Bearer','expires_in':3600,'scope':'render'}

    def exchange(self, client, code, verifier, redirect, resource):
        if not isinstance(verifier,str) or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}',verifier):
            raise Denied('INVALID_GRANT')
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        with self.db() as db:
            row=db.execute('SELECT c.*,d.revoked FROM codes c JOIN devices d ON c.device=d.id WHERE hash=?',(hashed(code),)).fetchone()
            if not row or row['used'] or row['revoked'] or row['expires'] <= self.clock() or row['client']!=client or row['redirect']!=redirect or resource!=self.resource or row['resource']!=resource or not hmac.compare_digest(row['challenge'],challenge):
                raise Denied('INVALID_GRANT')
            db.execute('UPDATE codes SET used=1 WHERE hash=?',(row['hash'],))
            return self._issue(db,client,row['device'])

    def refresh(self, client, refresh_token, resource):
        replay=False; result=None
        with self.db() as db:
            row=db.execute('SELECT t.*,d.revoked AS device_revoked FROM tokens t JOIN devices d ON d.id=t.device WHERE t.hash=? AND kind=\'refresh\'',(hashed(refresh_token),)).fetchone()
            if not row or row['revoked'] or row['device_revoked'] or row['expires'] <= self.clock() or row['client']!=client or resource!=self.resource:
                raise Denied('INVALID_GRANT')
            if row['used']:
                db.execute('UPDATE tokens SET revoked=1 WHERE family=?',(row['family'],)); replay=True
            else:
                db.execute('UPDATE tokens SET used=1 WHERE hash=?',(row['hash'],))
                result=self._issue(db,client,row['device'],row['family'])
        if replay: raise Denied('REFRESH_REUSE_REVOKED')
        return result

    def revoke_token(self, token, client):
        with self.db() as db:
            row=db.execute('SELECT family FROM tokens WHERE hash=? AND client=?',(hashed(token),client)).fetchone()
            if row: db.execute('UPDATE tokens SET revoked=1 WHERE family=?',(row['family'],))
        return {}

    def revoke(self, device_token):
        with self.db() as db:
            d=self._device(db,device_token)
            db.execute('UPDATE devices SET revoked=1,enabled=0 WHERE id=?',(d['id'],))
            db.execute('UPDATE tokens SET revoked=1 WHERE device=?',(d['id'],))
            db.execute("UPDATE jobs SET state='cancelled' WHERE device=? AND state='queued'",(d['id'],))
            db.execute("UPDATE jobs SET state='recovery_required' WHERE device=? AND state IN ('running_on_device','cancel_requested')",(d['id'],))
            return {'revoked':True}

    def status(self, access):
        with self.db() as db:
            a=self._access(db,access)
            return {'device_id':a['device'],'device_name':a['name'],'device_online':0 <= self.clock()-a['heartbeat'] < 30,
                    'last_seen':a['heartbeat'],'autonomous_enabled':bool(a['enabled']),
                    'execution_location':'android-only','relay_only':True}

    def capabilities(self, access):
        with self.db() as db:
            a=self._access(db,access)
            return {'capabilities':json.loads(a['caps']),'last_seen':a['heartbeat']}

    def submit(self, access, request, action, args):
        if not isinstance(request,str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}',request): raise Denied('INVALID_REQUEST_ID')
        if not isinstance(action,str) or not isinstance(args,dict) or len(canonical(args))>65536: raise Denied('INVALID_ACTION_ARGUMENTS')
        with self.db() as db:
            a=self._access(db,access)
            payload=canonical({'request_id':request,'api_version':1,'action':action,'args':args,'device_id':a['device']})
            digest=hashed(payload)
            old=db.execute('SELECT * FROM jobs WHERE device=? AND request=?',(a['device'],request)).fetchone()
            if old:
                if old['digest']!=digest: raise Denied('IDEMPOTENCY_CONFLICT',409)
                return {'job_id':old['id'],'state':old['state'],'duplicate':True}
            if not a['enabled']: raise Denied('AUTONOMOUS_SESSION_STOPPED',409)
            cap=next((c for c in json.loads(a['caps']) if c.get('id')==action),None)
            if not cap or cap.get('available') is not True: raise Denied('NATIVE_ACTION_UNAVAILABLE',409)
            try: Draft202012Validator(cap['input_schema']).validate(args)
            except (ValidationError,SchemaError,KeyError): raise Denied('INVALID_ACTION_ARGUMENTS')
            if db.execute("SELECT COUNT(*) FROM jobs WHERE device=? AND state='queued'",(a['device'],)).fetchone()[0]>=100:
                raise Denied('QUEUE_FULL',429)
            job=secrets.token_hex(16)
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,request,a['device'],digest,payload,'queued',None,self.clock()))
            return {'job_id':job,'state':'queued','duplicate':False}

    def poll(self, device_token, enabled, caps, active_job_id):
        if type(enabled) is not bool or not isinstance(caps,list) or len(caps)>2000 or len(canonical(caps))>196608:
            raise Denied('INVALID_CAPABILITIES')
        ids=set()
        for cap in caps:
            if not isinstance(cap,dict) or not isinstance(cap.get('id'),str) or cap['id'] in ids: raise Denied('INVALID_CAPABILITIES')
            ids.add(cap['id'])
            if cap.get('available') is True:
                schema=cap.get('input_schema')
                if not isinstance(schema,dict) or '$ref' in canonical(schema) or '$dynamicRef' in canonical(schema): raise Denied('REMOTE_SCHEMA_REFERENCES_FORBIDDEN')
                try: Draft202012Validator.check_schema(schema)
                except SchemaError: raise Denied('INVALID_CAPABILITIES')
        with self.db() as db:
            d=self._device(db,device_token)
            db.execute('UPDATE devices SET enabled=?,heartbeat=?,caps=? WHERE id=?',(int(enabled),self.clock(),canonical(caps),d['id']))
            if not enabled:
                db.execute("UPDATE jobs SET state='cancelled',updated=? WHERE device=? AND state='queued'",(self.clock(),d['id']))
                db.execute("UPDATE jobs SET state='cancel_requested',updated=? WHERE device=? AND state='running_on_device'",(self.clock(),d['id']))
            running=db.execute("SELECT * FROM jobs WHERE device=? AND state IN ('running_on_device','cancel_requested') ORDER BY updated LIMIT 1",(d['id'],)).fetchone()
            cancellations=[r[0] for r in db.execute("SELECT id FROM jobs WHERE device=? AND state='cancel_requested'",(d['id'],))]
            delivery=None
            if active_job_id is not None:
                if not isinstance(active_job_id,str) or not running or running['id']!=active_job_id:
                    raise Denied('ACTIVE_JOB_MISMATCH',409)
            elif enabled:
                candidate=running or db.execute("SELECT * FROM jobs WHERE device=? AND state='queued' ORDER BY updated,id LIMIT 1",(d['id'],)).fetchone()
                if candidate:
                    if candidate['state']=='queued': db.execute("UPDATE jobs SET state='running_on_device',updated=? WHERE id=?",(self.clock(),candidate['id']))
                    delivery={'job_id':candidate['id'],'digest':candidate['digest'],'payload':candidate['payload']}
            return {'job':delivery,'cancel_job_ids':cancellations,'device_id':d['id']}

    def result(self, device_token, job, digest, state, result):
        if state not in self.TERMINAL or not isinstance(result,dict) or len(canonical(result))>262144: raise Denied('INVALID_RESULT')
        with self.db() as db:
            d=self._device(db,device_token)
            row=db.execute('SELECT * FROM jobs WHERE id=? AND device=?',(job,d['id'])).fetchone()
            if not row or not hmac.compare_digest(row['digest'],digest): raise Denied('JOB_OR_DIGEST_MISMATCH',409)
            if row['state'] in self.TERMINAL:
                if row['state']==state and row['result']==canonical(result): return {'accepted':True,'duplicate':True}
                raise Denied('TERMINAL_RESULT_CONFLICT',409)
            if row['state'] not in ('running_on_device','cancel_requested'): raise Denied('JOB_NOT_DELIVERED',409)
            db.execute('UPDATE jobs SET state=?,result=?,updated=? WHERE id=?',(state,canonical(result),self.clock(),job))
            return {'accepted':True,'duplicate':False}

    def job(self, access, job):
        with self.db() as db:
            a=self._access(db,access)
            row=db.execute('SELECT * FROM jobs WHERE id=? AND device=?',(job,a['device'])).fetchone()
            if not row: raise Denied('JOB_NOT_FOUND',404)
            return {'job_id':job,'state':row['state'],'updated':row['updated'],'result':json.loads(row['result']) if row['result'] else None}

    def cancel(self, access, job):
        with self.db() as db:
            a=self._access(db,access)
            row=db.execute('SELECT * FROM jobs WHERE id=? AND device=?',(job,a['device'])).fetchone()
            if not row: raise Denied('JOB_NOT_FOUND',404)
            state='cancelled' if row['state']=='queued' else 'cancel_requested' if row['state']=='running_on_device' else row['state']
            db.execute('UPDATE jobs SET state=?,updated=? WHERE id=?',(state,self.clock(),job))
            return {'job_id':job,'state':state}
