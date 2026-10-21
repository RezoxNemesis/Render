"""Regressions established red→green with real SQLite ordering and HTTP requests."""
import base64
import hashlib
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from fastapi.testclient import TestClient
from app import create_app
from core import Relay

ORIGIN='https://render-test.example'
REDIRECT='https://chatgpt.com/connector_platform_oauth_redirect'
SECRET='test-only-enrollment-secret-with-at-least-32-characters'
CAPS=[{'id':'engine.status','available':True,'api_version':1,
       'input_schema':{'type':'object','properties':{},'additionalProperties':False}}]

class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app(str(Path(self.tmp.name)/'relay.sqlite'),ORIGIN,SECRET)
        self.r=self.app.state.relay
        self.r.clock=lambda:100000.0
        self.phone=self.r.enroll(SECRET,'Test phone')
        self.client=self.r.register([REDIRECT])['client_id']
        self.verifier='A'*64
        self.challenge=base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')
        code=self.r.authorize(self.client,REDIRECT,self.challenge,self.phone['link_code'],self.r.resource,'render')
        self.access=self.r.exchange(self.client,code,self.verifier,REDIRECT,self.r.resource)['access_token']
        self.r.poll(self.phone['device_token'],True,CAPS,None)
        self.http=TestClient(self.app,base_url=ORIGIN)
    def tearDown(self):self.http.close();self.tmp.cleanup()
    def test_fifo_uses_submission_order_when_timestamps_tie(self):
        receipts=[self.r.submit(self.access,'fifo-'+str(i),'engine.status',{}) for i in range(20)]
        for receipt in receipts:
            item=self.r.poll(self.phone['device_token'],True,CAPS,None)['job']
            self.assertEqual(receipt['job_id'],item['job_id'])
            self.r.result(self.phone['device_token'],item['job_id'],item['digest'],'succeeded',{'ok':True})
    def test_duplicate_json_keys_rejected(self):
        x=self.http.post('/v1/device/enroll',headers={'Content-Type':'application/json'},
                         content='{"name":"a","name":"b","enrollment_code":"x"}')
        self.assertEqual(400,x.status_code)
        self.assertEqual('INVALID_REQUEST_BODY',x.json()['error'])
    def test_full_browser_oauth_pkce_round_trip(self):
        link=self.r.link_code(self.phone['device_token'])['link_code']
        params={'response_type':'code','code_challenge_method':'S256','client_id':self.client,
                'redirect_uri':REDIRECT,'code_challenge':self.challenge,'resource':self.r.resource,
                'scope':'render','state':'owner-state'}
        page=self.http.get('/oauth/authorize',params=params)
        self.assertEqual(200,page.status_code)
        form=re.search(r'name="form_id" value="([^"]+)"',page.text).group(1)
        approve=self.http.post('/oauth/approve',headers={'Origin':ORIGIN},
                               data={'form_id':form,'link_code':link},follow_redirects=False)
        self.assertEqual(303,approve.status_code)
        returned=parse_qs(urlsplit(approve.headers['location']).query)
        self.assertEqual(['owner-state'],returned['state'])
        token=self.http.post('/oauth/token',data={'grant_type':'authorization_code','client_id':self.client,
            'code':returned['code'][0],'code_verifier':self.verifier,'redirect_uri':REDIRECT,'resource':self.r.resource})
        self.assertEqual(200,token.status_code)
        self.assertTrue(self.r.status(token.json()['access_token']))

if __name__=='__main__':unittest.main()
