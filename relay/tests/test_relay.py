"""Real SQLite + HTTP tests. Simulated device transport is not a physical phone test."""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from app import create_app
from core import Relay, Denied, canonical, hashed

ORIGIN='https://render-test.example'
REDIRECT='https://chatgpt.com/connector_platform_oauth_redirect'
SECRET='test-only-enrollment-secret-with-at-least-32-characters'
SCHEMA={'type':'object','properties':{},'additionalProperties':False}
CAPS=[{'id':'engine.status','available':True,'api_version':1,'input_schema':SCHEMA},
      {'id':'cycles.render','available':False,'reason':'missing native renderer'}]

class RelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/'test.sqlite')
        self.now=[100000.0]
        self.r=Relay(self.path,ORIGIN,SECRET,clock=lambda:self.now[0])
        self.phone=self.r.enroll(SECRET,'Test phone')
        self.device=self.phone['device_token']
        self.client=self.r.register([REDIRECT])['client_id']
        self.verifier='A'*64
        self.challenge=base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')
        code=self.r.authorize(self.client,REDIRECT,self.challenge,self.phone['link_code'],ORIGIN+'/mcp','render')
        self.tokens=self.r.exchange(self.client,code,self.verifier,REDIRECT,ORIGIN+'/mcp')
        self.access=self.tokens['access_token']
        self.r.poll(self.device,True,CAPS,None)
    def tearDown(self):self.tmp.cleanup()
    def denial(self,reason,call):
        with self.assertRaises(Denied) as caught:call()
        self.assertEqual(reason,caught.exception.reason)
    def submit(self,request='test-1'):
        return self.r.submit(self.access,request,'engine.status',{})
    def deliver(self):return self.r.poll(self.device,True,CAPS,None)['job']
    def test_status_requires_real_device_heartbeat(self):
        self.assertTrue(self.r.status(self.access)['device_online'])
        self.now[0]+=31
        self.assertFalse(self.r.status(self.access)['device_online'])
    def test_enrollment_is_single_use(self):
        self.denial('ENROLLMENT_ALREADY_USED',lambda:self.r.enroll(SECRET,'second'))
    def test_wrong_enrollment_secret_denied(self):
        self.denial('INVALID_ENROLLMENT',lambda:self.r.enroll('wrong','bad'))
    def test_tokens_stored_as_hashes(self):
        with self.r.db() as db:
            stored=db.execute('SELECT token FROM devices').fetchone()[0]
            access=db.execute("SELECT hash FROM tokens WHERE kind='access'").fetchone()[0]
        self.assertNotEqual(stored,self.device);self.assertEqual(stored,hashed(self.device))
        self.assertEqual(access,hashed(self.access))
    def test_redirect_allowlist(self):
        for redirect in ['http://chatgpt.com/connector_platform_oauth_redirect','https://evil.example/callback','https://chatgpt.com.evil.example/connector/oauth/test','https://chatgpt.com/connector/oauth/test?redirect=evil']:
            self.denial('REDIRECT_NOT_ALLOWED',lambda:self.r.register([redirect]))
    def test_link_codes_single_use(self):
        self.denial('INVALID_PHONE_LINK_CODE',lambda:self.r.authorize(self.client,REDIRECT,self.challenge,self.phone['link_code'],self.r.resource,'render'))
    def test_link_rotation_invalidates_previous(self):
        a=self.r.link_code(self.device);b=self.r.link_code(self.device)
        self.denial('INVALID_PHONE_LINK_CODE',lambda:self.r.authorize(self.client,REDIRECT,self.challenge,a['link_code'],self.r.resource,'render'))
        self.assertTrue(self.r.authorize(self.client,REDIRECT,self.challenge,b['link_code'],self.r.resource,'render'))
    def test_link_code_expiry(self):
        link=self.r.link_code(self.device);self.now[0]+=601
        self.denial('INVALID_PHONE_LINK_CODE',lambda:self.r.authorize(self.client,REDIRECT,self.challenge,link['link_code'],self.r.resource,'render'))
    def test_pkce_verifier_and_audience(self):
        link=self.r.link_code(self.device)
        code=self.r.authorize(self.client,REDIRECT,self.challenge,link['link_code'],self.r.resource,'render')
        self.denial('INVALID_GRANT',lambda:self.r.exchange(self.client,code,'B'*64,REDIRECT,self.r.resource))
        self.denial('INVALID_GRANT',lambda:self.r.exchange(self.client,code,self.verifier,REDIRECT,ORIGIN+'/other'))
        token=self.r.exchange(self.client,code,self.verifier,REDIRECT,self.r.resource)
        self.assertTrue(token['access_token'])
        self.denial('INVALID_GRANT',lambda:self.r.exchange(self.client,code,self.verifier,REDIRECT,self.r.resource))
    def test_scope_is_bound(self):
        self.denial('INVALID_RESOURCE_OR_SCOPE',lambda:self.r.authorize(self.client,REDIRECT,self.challenge,'bad',self.r.resource,'admin'))
    def test_access_expiry(self):
        self.now[0]+=3601
        self.denial('OAUTH_REQUIRED',lambda:self.r.status(self.access))
    def test_refresh_rotation_and_reuse_revocation(self):
        token=self.r.refresh(self.client,self.tokens['refresh_token'],self.r.resource)
        self.assertTrue(self.r.status(token['access_token']))
        self.denial('REFRESH_REUSE_REVOKED',lambda:self.r.refresh(self.client,self.tokens['refresh_token'],self.r.resource))
        self.denial('OAUTH_REQUIRED',lambda:self.r.status(token['access_token']))
    def test_revoke_connection_revokes_access(self):
        self.r.revoke(self.device)
        self.denial('OAUTH_REQUIRED',lambda:self.r.status(self.access))
        self.denial('DEVICE_AUTH_REQUIRED',lambda:self.r.poll(self.device,True,CAPS,None))
    def test_submit_is_receipt_not_completion(self):
        job=self.submit();self.assertEqual('queued',job['state'])
        self.assertIsNone(self.r.job(self.access,job['job_id'])['result'])
    def test_unimplemented_engine_is_unavailable(self):
        self.denial('NATIVE_ACTION_UNAVAILABLE',lambda:self.r.submit(self.access,'r','cycles.render',{}))
    def test_unknown_command_and_bad_args(self):
        self.denial('NATIVE_ACTION_UNAVAILABLE',lambda:self.r.submit(self.access,'r','shell.exec',{}))
        self.denial('INVALID_ACTION_ARGUMENTS',lambda:self.r.submit(self.access,'r','engine.status',{'shell':'cmd'}))
    def test_idempotency_receipt_and_conflict(self):
        first=self.submit();second=self.submit()
        self.assertEqual(first['job_id'],second['job_id']);self.assertTrue(second['duplicate'])
        self.denial('IDEMPOTENCY_CONFLICT',lambda:self.r.submit(self.access,'test-1','engine.status',{'x':1}))
    def test_delivery_digest_matches_exact_payload(self):
        self.submit();job=self.deliver()
        self.assertEqual(job['digest'],hashed(job['payload']))
        self.assertEqual(self.phone['device_id'],json.loads(job['payload'])['device_id'])
    def test_redelivery_does_not_create_new_job(self):
        self.submit();a=self.deliver();b=self.deliver();self.assertEqual(a,b)
    def test_no_new_job_during_active_native_call(self):
        a=self.submit('a');self.submit('b');job=self.deliver()
        self.assertEqual(a['job_id'],job['job_id'])
        self.assertIsNone(self.r.poll(self.device,True,CAPS,job['job_id'])['job'])
    def test_result_requires_delivery_and_matching_digest(self):
        receipt=self.submit()
        self.denial('JOB_OR_DIGEST_MISMATCH',lambda:self.r.result(self.device,receipt['job_id'],'wrong','succeeded',{}))
        job=self.deliver()
        self.denial('JOB_OR_DIGEST_MISMATCH',lambda:self.r.result(self.device,job['job_id'],'wrong','succeeded',{}))
    def test_device_result_persisted_and_ack_idempotent(self):
        receipt=self.submit();job=self.deliver();result={'native':'fixture-result'}
        a=self.r.result(self.device,job['job_id'],job['digest'],'succeeded',result)
        b=self.r.result(self.device,job['job_id'],job['digest'],'succeeded',result)
        self.assertTrue(a['accepted']);self.assertTrue(b['duplicate'])
        restarted=Relay(self.path,ORIGIN,SECRET,clock=lambda:self.now[0])
        self.assertEqual(result,restarted.job(self.access,receipt['job_id'])['result'])
    def test_terminal_result_cannot_be_rewritten(self):
        self.submit();job=self.deliver();self.r.result(self.device,job['job_id'],job['digest'],'failed',{'error':'x'})
        self.denial('TERMINAL_RESULT_CONFLICT',lambda:self.r.result(self.device,job['job_id'],job['digest'],'succeeded',{}))
    def test_stop_cancels_queued_and_requests_running_cancel(self):
        a=self.submit('a');b=self.submit('b');self.deliver()
        answer=self.r.poll(self.device,False,CAPS,a['job_id'])
        self.assertIn(a['job_id'],answer['cancel_job_ids'])
        self.assertEqual('cancelled',self.r.job(self.access,b['job_id'])['state'])
        self.denial('AUTONOMOUS_SESSION_STOPPED',lambda:self.submit('c'))
    def test_cancel_queued_job(self):
        job=self.submit();self.assertEqual('cancelled',self.r.cancel(self.access,job['job_id'])['state'])
        self.assertIsNone(self.deliver())
    def test_remote_schema_references_rejected(self):
        bad=[{'id':'engine.status','available':True,'input_schema':{'$ref':'https://evil.example/schema'}}]
        self.denial('REMOTE_SCHEMA_REFERENCES_FORBIDDEN',lambda:self.r.poll(self.device,True,bad,None))
    def test_rate_limit_is_durable(self):
        self.r.rate('trial',2);self.r.rate('trial',2)
        self.denial('RATE_LIMITED',lambda:self.r.rate('trial',2))
        self.now[0]+=61;self.r.rate('trial',2)
    def test_other_device_cannot_read_or_cancel_job(self):
        job=self.submit()
        other=Relay(self.path,ORIGIN,'second-secret-which-is-also-long-enough',clock=lambda:self.now[0])
        phone=other.enroll('second-secret-which-is-also-long-enough','Other')
        code=other.authorize(self.client,REDIRECT,self.challenge,phone['link_code'],self.r.resource,'render')
        access=other.exchange(self.client,code,self.verifier,REDIRECT,self.r.resource)['access_token']
        self.denial('JOB_NOT_FOUND',lambda:other.job(access,job['job_id']))
        self.denial('JOB_NOT_FOUND',lambda:other.cancel(access,job['job_id']))

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app(str(Path(self.tmp.name)/'http.sqlite'),ORIGIN,SECRET)
        self.r=self.app.state.relay
        phone=self.r.enroll(SECRET,'HTTP test');self.phone=phone
        self.client_id=self.r.register([REDIRECT])['client_id']
        verifier='V'*64;challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        code=self.r.authorize(self.client_id,REDIRECT,challenge,phone['link_code'],self.r.resource,'render')
        self.access=self.r.exchange(self.client_id,code,verifier,REDIRECT,self.r.resource)['access_token']
        self.http=TestClient(self.app,base_url=ORIGIN)
        self.headers={'Authorization':'Bearer '+self.access}
    def tearDown(self):self.http.close();self.tmp.cleanup()
    def test_health_is_only_public_status(self):
        self.assertFalse(self.http.get('/health').json()['executes_blender'])
    def test_mcp_requires_oauth(self):
        x=self.http.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
        self.assertEqual(401,x.status_code);self.assertIn('resource_metadata',x.headers['www-authenticate'])
    def test_origin_rejection(self):
        self.assertEqual(403,self.http.get('/health',headers={'Origin':'https://evil.example'}).status_code)
    def test_oauth_metadata_audience(self):
        m=self.http.get('/.well-known/oauth-protected-resource').json()
        self.assertEqual(ORIGIN+'/mcp',m['resource'])
        self.assertIn('S256',self.http.get('/.well-known/oauth-authorization-server').json()['code_challenge_methods_supported'])
    def test_legacy_initialize_and_tool_list(self):
        x=self.http.post('/mcp',headers=self.headers,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}})
        self.assertEqual('2025-11-25',x.json()['result']['protocolVersion'])
        y=self.http.post('/mcp',headers=self.headers,json={'jsonrpc':'2.0','id':2,'method':'tools/list'})
        self.assertEqual(5,len(y.json()['result']['tools']))
    def test_modern_metadata_required(self):
        headers={**self.headers,'mcp-protocol-version':'2026-07-28','mcp-method':'tools/list'}
        body={'jsonrpc':'2.0','id':'x','method':'tools/list','params':{'_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientInfo':{'name':'test','version':'1'},'io.modelcontextprotocol/clientCapabilities':{}}}}
        x=self.http.post('/mcp',headers=headers,json=body)
        self.assertEqual('complete',x.json()['result']['resultType'])
        del body['params']['_meta']
        self.assertEqual(400,self.http.post('/mcp',headers=headers,json=body).status_code)
    def test_payload_limit(self):
        x=self.http.post('/mcp',headers=self.headers,content=b'x'*524289)
        self.assertEqual(413,x.status_code)
    def test_approval_without_csrf_cookie_denied(self):
        x=self.http.post('/oauth/approve',headers={'Origin':ORIGIN},data={'form_id':'bad','link_code':'bad'})
        self.assertEqual(403,x.status_code)
    def test_unknown_tool_never_executes(self):
        x=self.http.post('/mcp',headers=self.headers,json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'shell','arguments':{}}})
        self.assertIn('error',x.json())
    def test_native_unavailable_returns_tool_error(self):
        self.r.poll(self.phone['device_token'],True,CAPS,None)
        x=self.http.post('/mcp',headers=self.headers,json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'render_submit','arguments':{'request_id':'x','action':'cycles.render','args':{}}}})
        self.assertTrue(x.json()['result']['isError'])

if __name__=='__main__':unittest.main()
