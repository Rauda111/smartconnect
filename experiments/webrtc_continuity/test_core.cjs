'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {Call,Metrics,Progress}=require('./core.js');
class PC {
  constructor(config){this.config=config;this.connectionState='new';this.iceConnectionState='new';this.iceGatheringState='complete';this.signalingState='stable';this.senders=[];this.receivers=[];this.restarts=0;this.stats=new Map();}
  addTrack(track){this.senders.push({track});}
  getSenders(){return this.senders;}
  getReceivers(){return this.receivers;}
  restartIce(){this.restarts++;}
  async createOffer(){return {type:'offer',sdp:'v=0\na=fixture-offer-'+this.restarts};}
  async createAnswer(){return {type:'answer',sdp:'v=0\na=fixture-answer'};}
  async setLocalDescription(d){this.localDescription=d;this.signalingState=d.type==='offer'?'have-local-offer':'stable';}
  async setRemoteDescription(d){this.remoteDescription=d;this.signalingState=d.type==='offer'?'have-remote-offer':'stable';}
  async getStats(){return this.stats;}
  close(){this.connectionState='closed';}
}
function fixture(mode='smartconnect',role='A'){
  let now=0,created=0;
  const messages=[],tracks=[{kind:'video',stop(){this.stopped=true;}},{kind:'audio',stop(){this.stopped=true;}}];
  const stream={getTracks:()=>tracks};
  const call=new Call({mode,role,pcFactory:c=>{created++;return new PC(c);},send:async m=>messages.push(structuredClone(m)),clock:()=>now,gather:async()=>{}});
  return {call,stream,tracks,messages,get created(){return created;},set now(v){now=v;},async start(){await call.start(stream,{iceServers:[]},{approved:true});},async answer(){await call.receive({mode,revision:call.revision,description:{type:'answer',sdp:'v=0\na=fixture-answer'}});}};
}
const policy=(window,recommended,age_seconds=0)=>({status:'fresh',application:'video_call',window,recommended,age_seconds});
const stats=(frames,packets,pair='pair-fixture',extra={})=>new Map([
 ['v',{id:'v',type:'inbound-rtp',kind:'video',framesDecoded:frames,packetsReceived:frames,packetsLost:0,framesDropped:0,...extra}],
 ['a',{id:'a',type:'inbound-rtp',kind:'audio',packetsReceived:packets,packetsLost:0,totalSamplesReceived:packets*160,concealedSamples:0}],
 ['t',{id:'t',type:'transport',selectedCandidatePairId:pair}],
 [pair,{id:pair,type:'candidate-pair',localCandidateId:'l',remoteCandidateId:'r',currentRoundTripTime:.03}],
 ['l',{id:'l',type:'local-candidate',candidateType:'host',protocol:'udp',address:'PRIVATE-ADDRESS',port:12345}],
 ['r',{id:'r',type:'remote-candidate',candidateType:'relay',address:'PRIVATE-REMOTE',port:23456}]
]);

test('approval gate creates no peer connection or tracks/transports',async()=>{
 const f=fixture();await assert.rejects(()=>f.call.start(f.stream,{}),/approval_required/);assert.equal(f.created,0);assert.equal(f.messages.length,0);
});
test('initial call and ICE restart preserve one PC and the actual local track objects',async()=>{
 const f=fixture();await f.start();await f.answer();const pc=f.call.pc;
 await f.call.applyPolicy(policy(1,'wifi'));await f.call.applyPolicy(policy(2,'cellular'));
 assert.equal(f.created,1);assert.equal(f.call.pc,pc);assert.equal(pc.restarts,1);assert.deepEqual(pc.getSenders().map(x=>x.track),f.tracks);
 assert.equal(f.messages.length,2);assert.equal(f.messages[1].revision,2);assert.equal(f.messages[1].description.type,'offer');
 assert.equal(f.tracks.some(t=>t.stopped),false);assert.equal(f.call.export().physical_egress_verified,false);
});
test('offer/answer restart keeps both controlled clients, never silently replaces either',async()=>{
 const a=fixture(),b=fixture('smartconnect','B');await a.start();await b.start();
 assert.equal(await b.call.receive(a.messages[0]),true);assert.equal(await a.call.receive(b.messages[0]),true);
 const pa=a.call.pc,pb=b.call.pc;await a.call.requestRestart('manual');
 assert.equal(await b.call.receive(a.messages[1]),true);assert.equal(await a.call.receive(b.messages[1]),true);
 assert.equal(a.call.pc,pa);assert.equal(b.call.pc,pb);assert.equal(a.created,1);assert.equal(b.created,1);
});
test('ordinary WebRTC baseline observes identical policy inputs without application ICE restart',async()=>{
 const f=fixture('baseline');await f.start();await f.answer();
 await f.call.applyPolicy(policy(1,'wifi'));await f.call.applyPolicy(policy(2,'cellular'));
 f.call.pc.iceConnectionState='failed';f.call.pc.oniceconnectionstatechange();
 await f.call.requestRestart('manual');assert.equal(f.call.pc.restarts,0);assert.equal(f.created,1);
});
test('signaling send failure and explicit retry do not create a new call or new offer',async()=>{
 const f=fixture();await f.start();await f.answer();const original=f.call.pc;
 let sent=0;f.call.send=async()=>{sent++;throw new Error('PRIVATE-EXCEPTION');};
 assert.equal(await f.call.requestRestart('manual'),false);const revision=f.call.revision;
 assert.equal(await f.call.retrySignal(),false);assert.equal(f.call.pc,original);assert.equal(f.created,1);assert.equal(f.call.revision,revision);
 assert.equal(JSON.stringify(f.call.export()).includes('PRIVATE-EXCEPTION'),false);
 f.call.send=async()=>{sent++;};assert.equal(await f.call.retrySignal(),true);assert.equal(f.call.revision,revision);
});
test('bad, mismatched, duplicate and stale signaling is rejected without recreating session',async()=>{
 const f=fixture();await f.start();
 for(const m of [{},{mode:'baseline',revision:1,description:{type:'answer',sdp:'v=0'}},{mode:'smartconnect',revision:99,description:{type:'answer',sdp:'v=0'}}])assert.equal(await f.call.receive(m),false);
 await f.answer();assert.equal(await f.call.receive({mode:'smartconnect',revision:1,description:{type:'answer',sdp:'v=0'}}),false);assert.equal(f.created,1);
});
test('Wi-Fi unavailable recommendation can request recovery, but cannot claim interface binding',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));
 await f.call.applyPolicy(policy(2,'cellular'));const e=f.call.events.find(e=>e.kind==='recovery_requested');
 assert.equal(e.interface_control,'not_available');assert.equal(f.call.recommended,'cellular');
 assert.equal(f.call.export().interface_control,'unavailable_in_browser');
});
test('cellular also unavailable does not invent a working path; later restoration can trigger recovery',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));
 await f.call.applyPolicy(policy(2,'none'));assert.equal(f.call.pc.restarts,0);
 await f.call.applyPolicy(policy(3,'cellular'));assert.equal(f.call.pc.restarts,1);
});
test('stale, wrong-profile, duplicate and regressed policy records do not trigger recovery',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(2,'wifi'));
 for(const p of [policy(1,'cellular'),policy(2,'cellular'),policy(3,'cellular',46),{...policy(4,'cellular'),application:'file_download'},{status:'stale'}])await f.call.applyPolicy(p);
 assert.equal(f.call.pc.restarts,0);assert.equal(f.call.recommended,'wifi');
});
test('rapid fluctuations are bounded by recovery cooldown and an explicit attempt ceiling',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));await f.call.applyPolicy(policy(2,'cellular'));await f.answer();
 f.now=100;await f.call.applyPolicy(policy(3,'wifi'));assert.equal(f.call.pc.restarts,1);
 f.now=10000;await f.call.sample();assert.equal(f.call.pc.restarts,2);await f.answer();
 f.now=20000;await f.call.applyPolicy(policy(4,'cellular'));await f.answer();
 f.now=30000;await f.call.applyPolicy(policy(5,'wifi'));assert.equal(f.call.pc.restarts,3);assert.equal(f.created,1);
 assert(f.call.events.some(e=>e.kind==='recovery_limit_reached'));
});
test('pending recommendation expiry does not cause late recovery on stale inputs',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));await f.call.applyPolicy(policy(2,'cellular'));await f.answer();
 f.now=10;await f.call.applyPolicy(policy(3,'wifi',44));f.now=2000;await f.call.sample();assert.equal(f.call.pc.restarts,1);assert.equal(f.call.pending,null);
});
test('browser failed-ICE callback requests recovery only on the initiator in assisted mode',async()=>{
 const f=fixture();await f.start();await f.answer();f.call.pc.iceConnectionState='failed';f.call.pc.oniceconnectionstatechange();
 await Promise.resolve();assert.equal(f.call.restarts,1);
 const b=fixture('smartconnect','B');await b.start();b.call.pc.iceConnectionState='failed';b.call.pc.oniceconnectionstatechange();assert.equal(b.call.restarts,0);
});
test('export contains real supplied numeric counters, not raw candidate IDs, addresses, SDP or SSRC',async()=>{
 const f=fixture();await f.start();await f.answer();f.call.pc.stats=stats(20,50,'PRIVATE-PAIR',{ssrc:'PRIVATE-SSRC'});
 const sample=await f.call.sample();assert.equal(sample.frames_decoded,20);assert.equal(sample.audio_packets_received,50);assert.equal(sample.same_peer_connection,true);assert.equal(sample.same_local_tracks,true);
 const out=JSON.stringify(f.call.export());for(const privateText of ['PRIVATE-ADDRESS','PRIVATE-REMOTE','PRIVATE-PAIR','PRIVATE-SSRC','fixture-offer'])assert.equal(out.includes(privateText),false);
});
test('candidate-pair changes are counted but never treated as verified physical interface change',()=>{
 const m=new Metrics();assert.equal(m.ingest(stats(1,1,'one'),0).candidate_pair_generation,1);
 const sample=m.ingest(stats(2,2,'two'),500);assert.equal(sample.candidate_pair_generation,2);assert.equal(sample.physical_interface,'unverified');assert.equal(sample.physical_egress_verified,false);
});
test('missing stats remain null and partial counters are not silently zero-filled',()=>{
 const m=new Metrics();const empty=m.ingest(new Map(),0);assert.equal(empty.frames_decoded,null);assert.equal(empty.audio_packets_received,null);assert.equal(empty.candidate_pair_generation,null);
 const partial=stats(2,2);partial.set('v2',{id:'v2',type:'inbound-rtp',kind:'video'});assert.equal(m.ingest(partial,500).frames_decoded,null);
});
test('video and audio stalls have separate intervals and recovery preserves observations',()=>{
 const p=new Progress();p.update('video',1,0);p.update('audio',1,0);p.update('video',1,1000);p.update('audio',3,1000);
 assert.equal(p.snapshot(1000).open_gaps.length,1);p.update('video',2,1500);
 assert.deepEqual(p.snapshot(1500).closed_gaps,[{kind:'video',last_progress_to_recovery_ms:1500,right_censored:false}]);
});
test('counter reset, unknown samples and final open gaps are right-censored, not fake recovery',()=>{
 const p=new Progress();p.update('video',10,0);p.update('video',10,1000);p.update('video',0,1200);
 assert.equal(p.gaps[0].right_censored,true);p.update('audio',2,1500);p.update('audio',null,3000);assert.equal(p.gaps[1].right_censored,true);
 p.update('video',2,3000);p.close(5000);assert.equal(p.gaps[2].right_censored,true);
});
test('explicit end stops tracks and transport; samples and restarts cannot resurrect the call',async()=>{
 const f=fixture();await f.start();f.call.close();assert(f.tracks.every(t=>t.stopped));assert.equal(await f.call.sample(),null);assert.equal(await f.call.requestRestart('manual'),false);
 await assert.rejects(()=>f.call.start(f.stream,{}, {approved:true}),/explicit_new_session_required/);assert.equal(f.created,1);
});
test('unobserved receiver identity and expired policy remain explicitly unknown/stale',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));
 let sample=await f.call.sample();assert.equal(sample.same_observed_receiver_tracks,null);assert.equal(sample.policy_input_status,'fresh');
 f.now=45001;sample=await f.call.sample();assert.equal(sample.policy_input_status,'stale');
 await f.call.applyPolicy({...policy(2,'cellular'),application:'file_download'});assert.equal(f.call.policyStatus,'wrong_profile');
});
test('receiver-track replacement is disclosed rather than passed as preserved',async()=>{
 const f=fixture();await f.start();await f.answer();const remoteTrack={kind:'video'};f.call.pc.receivers=[{track:remoteTrack}];
 assert.equal((await f.call.sample()).same_observed_receiver_tracks,true);
 f.call.pc.receivers=[{track:{kind:'video'}}];assert.equal((await f.call.sample()).same_observed_receiver_tracks,false);
});
