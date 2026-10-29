import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

// Node does not implement the cloudflare:workers base class. Substitute only
// that constructor; the production request, authorization and parsing code is
// loaded unchanged, then exercised through its actual fetch entry point.
const file=new URL('../cloudflare/render-studio-direct-mcp/src/index.mjs',import.meta.url);
const source=await readFile(file,'utf8');
const platformImport='import { DurableObject } from "cloudflare:workers";';
assert.ok(source.startsWith(platformImport));
const fixtureSource=source.replace(platformImport,
  'class DurableObject { constructor(ctx,env) { this.ctx=ctx; this.env=env; } }');
const {RenderRelayDO}=await import('data:text/javascript;base64,'+Buffer.from(fixtureSource).toString('base64'));

function relay() {
  const ctx={storage:{sql:{exec(){return {toArray:()=>[]};}},transactionSync:fn=>fn()}};
  return new RenderRelayDO(ctx,{ENROLLMENT_SECRET:'test-fixture-enrollment-secret-0000'});
}
function streamRequest(path,parts,headers={}) {
  const observed={produced:0,cancelled:false};
  const body=new ReadableStream({
    pull(controller) {
      if(observed.produced===parts.length)controller.close();
      else controller.enqueue(parts[observed.produced++]);
    },
    cancel(){observed.cancelled=true;}
  });
  const req=new Request('https://render-test.invalid'+path,{method:'POST',body,duplex:'half',
    headers:{'content-type':'application/json',...headers}});
  return {req,observed};
}
async function assertError(req,status,error) {
  const response=await relay().fetch(req);
  assert.equal(response.status,status);
  assert.deepEqual(await response.json(),{error});
}
const encode=text=>new TextEncoder().encode(text);

test('oversized JSON is cancelled before the entire body is buffered',async()=>{
  const chunks=Array.from({length:20},()=>new Uint8Array(65536).fill(32));
  const {req,observed}=streamRequest('/v1/device/enroll',chunks);
  await assertError(req,413,'BODY_TOO_LARGE');
  assert.equal(observed.cancelled,true);
  assert.ok(observed.produced<chunks.length);
});

test('declared oversized bodies are rejected without consuming the stream',async()=>{
  const chunks=Array.from({length:20},()=>new Uint8Array(65536).fill(32));
  const {req,observed}=streamRequest('/v1/device/enroll',chunks,{'content-length':'1310720'});
  await assertError(req,413,'BODY_TOO_LARGE');
  assert.equal(observed.cancelled,true);
  assert.ok(observed.produced<=1);
});

test('OAuth forms enforce a byte limit while streaming',async()=>{
  const chunks=Array.from({length:20},()=>encode('é'.repeat(1024)));
  const {req,observed}=streamRequest('/oauth/token',chunks,
    {'content-type':'application/x-www-form-urlencoded'});
  await assertError(req,413,'BODY_TOO_LARGE');
  assert.equal(observed.cancelled,true);
  assert.ok(observed.produced<chunks.length);
});

test('missing or understated content length cannot bypass the streamed limit',async()=>{
  const chunks=Array.from({length:20},()=>new Uint8Array(65536).fill(32));
  const {req,observed}=streamRequest('/v1/device/enroll',chunks,{'content-length':'1'});
  await assertError(req,413,'BODY_TOO_LARGE');
  assert.equal(observed.cancelled,true);
});

test('a valid UTF-8 request split inside a character still reaches authentication',async()=>{
  const bytes=encode(JSON.stringify({enrollment_code:'incorrect-fixture-code',name:'Studio €'}));
  const split=bytes.indexOf(0xe2)+1;
  const {req}=streamRequest('/v1/device/enroll',[bytes.slice(0,split),bytes.slice(split)]);
  await assertError(req,403,'INVALID_ENROLLMENT');
});

test('exact JSON body limit is accepted for subsequent validation',async()=>{
  const prefix='{"enrollment_code":"incorrect","name":"',suffix='"}';
  const {req}=streamRequest('/v1/device/enroll',[
    encode(prefix+'a'.repeat(524288-prefix.length-suffix.length)+suffix)]);
  await assertError(req,403,'INVALID_ENROLLMENT');
});

test('anonymous MCP and device requests remain denied',async()=>{
  for(const path of ['/mcp','/v1/device/revoke']) {
    const {req}=streamRequest(path,[encode('{}')]);
    await assertError(req,401,'AUTH_REQUIRED');
  }
});

test('foreign-origin OAuth consent remains denied',async()=>{
  const {req}=streamRequest('/oauth/approve',[encode('form_id=fixture&link_code=fixture')],{
    'content-type':'application/x-www-form-urlencoded','origin':'https://untrusted.invalid'});
  await assertError(req,403,'CSRF_ORIGIN');
});
