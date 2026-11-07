'use strict';
// Real Python bridge/controller/broker envelopes cross into the actual JS call
// coordinator. Only the ICMP hardware and browser transport/media are mocked.
const test=require('node:test'),assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process'),path=require('node:path');
const {Call}=require('./core.js');

test('Python live-policy contract drives same-PC JS recovery after frozen hold/dwell',async()=>{
  const producer=String.raw`
import json
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from experiments.webrtc_continuity.server import Broker
from experiments.webrtc_continuity.policy_bridge import run
from mac_hub.monitor import Measurement
elapsed=0.
base=datetime(2026,11,7,tzinfo=timezone.utc)
reader='R'*48; writer='W'*48
broker=Broker(reader,policy_token=writer,clock=lambda:elapsed,utcnow=lambda:base+timedelta(seconds=elapsed))
client='offline-contract-client-A'
code,joined=broker.dispatch('POST','/join','Bearer '+reader,json.dumps(dict(role='A',client=client)).encode())
assert code==200
session=joined['session_id']; snapshots=[]
def send(route,payload=None):
    code,result=broker.dispatch('POST' if payload else 'GET',route,'Bearer '+writer,json.dumps(payload).encode() if payload else b'')
    assert code==200,(code,result)
    if payload:
        code,item=broker.dispatch('GET','/policy?role=A&client='+client+'&session_id='+session,'Bearer '+reader)
        assert code==200
        snapshots.append(item)
    return result
def probe(interface,target,count):
    return Measurement(interface,'reachable',latency=50 if interface=='en0' else 5,loss=0,sent=count,received=count)
def sleep(seconds):
    global elapsed
    elapsed+=10
with patch('socket.socket',side_effect=AssertionError('network forbidden')),patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')),patch('subprocess.run',side_effect=AssertionError('probe forbidden')):
    run(execute=True,send=send,cycles=4,probe=probe,clock=lambda:elapsed,sleep=sleep,utc=lambda:(base+timedelta(seconds=elapsed)).isoformat(),emit=lambda _:None)
print(json.dumps(dict(session=session,snapshots=snapshots)))
`;
  const python=process.env.SMARTCONNECT_TEST_PYTHON || 'python3';
  const result=spawnSync(python,['-c',producer],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8',timeout:20000,maxBuffer:1024*1024});
  assert.equal(result.status,0,result.stderr || String(result.error));
  const data=JSON.parse(result.stdout);
  assert.deepEqual(data.snapshots.map(p=>p.recommended),['wifi','wifi','wifi','cellular']);
  assert.equal(data.snapshots[3].reason_code,'qualified_change');
  let creations=0,now=0;
  class PC {
    constructor(){creations++;this.signalingState='stable';this.senders=[];this.restarts=0;this.iceGatheringState='complete';}
    addTrack(track){this.senders.push({track});}
    getSenders(){return this.senders;}getReceivers(){return [];}
    restartIce(){this.restarts++;}
    async createOffer(){return {type:'offer',sdp:'v=0\nfixture'};}
    async setLocalDescription(d){this.localDescription=d;this.signalingState='have-local-offer';}
    async setRemoteDescription(){this.signalingState='stable';}
    async getStats(){return new Map();}close(){}
  }
  const tracks=[{kind:'video',stop(){}},{kind:'audio',stop(){}}],sent=[];
  const call=new Call({role:'A',mode:'smartconnect',sessionId:data.session,
    pcFactory:()=>new PC(),send:async m=>sent.push(m),clock:()=>now,gather:async()=>{}});
  await call.start({getTracks:()=>tracks},{iceServers:[]},{approved:true});
  await call.receive({mode:'smartconnect',session_id:data.session,revision:1,description:{type:'answer',sdp:'v=0\nfixture'}});
  const original=call.pc;
  for(const envelope of data.snapshots){now=(envelope.window-1)*10000;await call.applyPolicy(envelope);}
  assert.equal(creations,1);assert.equal(call.pc,original);assert.equal(call.pc.restarts,1);
  assert.deepEqual(call.pc.getSenders().map(s=>s.track),tracks);
  assert.equal(call.events.filter(e=>e.kind==='policy_recommendation').length,4);
  assert.equal(call.events.find(e=>e.kind==='recovery_requested').cause,'policy_change');
  assert.equal(call.export().physical_egress_verified,false);
  assert.equal(sent.length,2);
  call.close();
});
