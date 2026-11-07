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
 f.now=10000;await f.call.sample();await f.call.recoveryTask;assert.equal(f.call.pc.restarts,2);await f.answer();
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


test('assisted initiator detects sustained decoded-video stall and requests bounded ICE restart',async()=>{
 const f=fixture();await f.start();await f.answer();f.call.pc.stats=stats(5,10);await f.call.sample();
 f.now=2500;await f.call.sample();assert.equal(f.call.restarts,0);
 f.now=3200;await f.call.sample();assert.equal(f.call.restarts,1);
 assert(f.call.events.some(e=>e.kind==='video_stall_observed'));
 assert(f.call.events.some(e=>e.kind==='recovery_requested' && e.cause==='video_stalled'));
 assert.equal(f.created,1);
});
test('baseline never automatically restarts on stalled video',async()=>{
 const f=fixture('baseline');await f.start();await f.answer();f.call.pc.stats=stats(5,10);await f.call.sample();
 f.now=3500;await f.call.sample();assert.equal(f.call.restarts,0);
});
test('assisted initiator attempts recovery after sustained ICE disconnection',async()=>{
 const f=fixture();await f.start();await f.answer();f.call.pc.iceConnectionState='disconnected';f.call.pc.oniceconnectionstatechange();
 f.now=3000;await f.call.sample();assert.equal(f.call.restarts,1);
 assert(f.call.events.some(e=>e.kind==='recovery_requested' && e.cause==='ice_disconnected'));
});

test('unanswered recovery offer retries after 3 seconds and stops after answer',async()=>{
  const f=fixture();
  await f.start();
  await f.answer();
  await f.call.requestRestart('manual');
  assert.equal(f.messages.length,2);

  f.now=2999;
  await f.call.sample();
  assert.equal(f.messages.length,2);

  f.now=3000;
  await f.call.sample();
  assert.equal(f.messages.length,3);
  assert.equal(f.messages[2].revision,2);
  assert(f.call.events.some(e=>e.kind==='signaling_retried'));

  await f.answer();
  f.now=6500;
  await f.call.sample();
  assert.equal(f.messages.length,3);
});

test('integrated policy and signaling require current call session scope',async()=>{
 const f=fixture();f.call.sessionId='session-current';await f.start();
 assert.equal(await f.call.receive({session_id:'other',mode:'smartconnect',revision:1,description:{type:'answer',sdp:'v=0\nwrong'}}),false);
 await f.call.receive({session_id:'session-current',mode:'smartconnect',revision:1,description:{type:'answer',sdp:'v=0\nanswer'}});
 await f.call.applyPolicy({...policy(1,'wifi'),session_id:'session-current'});
 await f.call.applyPolicy({...policy(2,'cellular'),session_id:'other'});assert.equal(f.call.restarts,0);
 await f.call.applyPolicy({...policy(2,'cellular'),session_id:'session-current'});assert.equal(f.call.restarts,1);
});
test('same revision same offer resends cached answer boundedly without a new PC or negotiation',async()=>{
 const f=fixture('baseline','B');await f.start();const offer={mode:'baseline',revision:1,description:{type:'offer',sdp:'v=0\noffer'}};
 assert.equal(await f.call.receive(offer),true);const answer=f.messages[0];
 for(let i=0;i<3;i++)assert.equal(await f.call.receive(offer),true);
 assert.equal(await f.call.receive(offer),false);assert.equal(f.messages.length,4);assert.deepEqual(f.messages[3],answer);assert.equal(f.created,1);
 assert.equal(await f.call.receive({...offer,description:{type:'offer',sdp:'v=0\nchanged'}}),false);
});
test('unanswered offer retries have the same finite budget in both conditions',async()=>{
 for(const mode of ['baseline','smartconnect']){const f=fixture(mode);await f.start();for(let i=1;i<9;i++){f.now=i*4000;await f.call.sample();}assert.equal(f.messages.length,4);assert.equal(f.created,1);assert.equal(f.call.restarts,0);}
});
test('policy reversal cancels a pending restart before cooldown elapses',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));
 f.call.lastRestart=0;f.now=1000;await f.call.applyPolicy(policy(2,'cellular'));assert.equal(f.call.pending,'policy_change');
 await f.call.applyPolicy(policy(3,'wifi'));assert.equal(f.call.pending,null);
 f.now=11000;await f.call.sample();assert.equal(f.call.restarts,0);
});

test('unresolved ICE gathering never blocks repeated media samples or duplicates recovery',async()=>{
 const f=fixture();await f.start();await f.answer();let release;
 f.call.gather=()=>new Promise(resolve=>{release=resolve;});f.call.pending='manual';
 f.call.pc.stats=stats(5,8);const first=await f.call.sample();assert.equal(first.frames_decoded,5);
 await Promise.resolve();f.now=500;f.call.pc.stats=stats(6,9);const second=await f.call.sample();
 assert.equal(second.frames_decoded,6);assert.equal(f.call.pc.restarts,1);assert.equal(f.call.samples.length,2);
 release();await f.call.recoveryTask;assert.equal(f.created,1);
});
test('unsent gather failure rolls back on same PC and clears obsolete retry offer',async()=>{
 const f=fixture();await f.start();await f.answer();const pc=f.call.pc;
 f.call.gather=async()=>{throw new Error('private gather failure');};
 assert.equal(await f.call.requestRestart('manual'),false);assert.equal(pc.signalingState,'stable');
 assert.equal(pc.localDescription.type,'rollback');assert.equal(f.call.lastSignal,null);
 assert.equal(await f.call.retrySignal(),false);assert.equal(f.created,1);assert.equal(f.messages.length,1);
 assert(f.call.events.some(e=>e.kind==='unsent_offer_rolled_back'));
});
test('policy observation can be enabled with policy recovery disabled and preserves safe measured history',async()=>{
 const f=fixture();f.call.policyRecoveryEnabled=false;await f.start();await f.answer();
 await f.call.applyPolicy(policy(1,'wifi'));
 await f.call.applyPolicy({...policy(2,'cellular'),reason_code:'availability',private:'PRIVATE',measurements:{wifi:{status:'no_reply',trend:'Unavailable',latency_ms:null,loss_percent:100,sent:10,received:0,score:null,adjusted_score:null,raw:'PRIVATE'},cellular:{status:'reachable',trend:'Stable',latency_ms:20,loss_percent:0,sent:10,received:10,score:.9,adjusted_score:.9}},stability:{hold_count:0,hold_required:3,dwell_seconds:30,margin:.05,private:'PRIVATE'}});
 assert.equal(f.call.restarts,0);assert.equal(f.call.recommended,'cellular');
 const e=f.call.events.filter(x=>x.kind==='policy_recommendation').at(-1);
 assert.equal(e.reason_code,'availability');assert.equal(e.measurements.wifi.latency_ms,null);assert.equal(e.measurements.cellular.score,.9);assert.equal(e.stability.hold_required,3);
 assert(!JSON.stringify(f.call.export()).includes('PRIVATE'));
});

test('failed initial and recovery sends retry cached offers automatically with one PC and a finite budget',async()=>{
 for(const recovery of [false,true]){
  const f=fixture();if(recovery){await f.start();await f.answer();}
  let sends=0;f.call.send=async()=>{sends++;throw new Error('private transport failure');};
  if(recovery)await f.call.requestRestart('manual');else await f.start();
  const revision=f.call.revision,pc=f.call.pc;
  for(let n=1;n<=7;n++){f.now=n*3100;await f.call.sample();await f.call.recoveryTask;}
  assert.equal(sends,4);assert.equal(f.call.revision,revision);assert.equal(f.call.pc,pc);assert.equal(f.created,1);
 }
});
test('failed answer delivery retries automatically; a duplicate offer uses the cached answer',async()=>{
 const f=fixture('smartconnect','B');await f.start();let failures=2,sends=0;
 const delivered=[];f.call.send=async m=>{sends++;if(failures-->0)throw new Error('offline');delivered.push(structuredClone(m));};
 const offer={mode:'smartconnect',revision:1,description:{type:'offer',sdp:'v=0\nfirst'}};
 assert.equal(await f.call.receive(offer),false);const description=f.call.pc.localDescription;
 f.now=3000;await f.call.sample();await f.call.recoveryTask;assert.equal(sends,2);
 f.now=6000;await f.call.sample();await f.call.recoveryTask;assert.equal(sends,3);
 f.now=10000;await f.call.sample();await f.call.recoveryTask;assert.equal(sends,3);
 assert.equal(await f.call.receive(offer),true);assert.deepEqual(delivered[0],delivered[1]);
 assert.equal(f.call.pc.localDescription,description);assert.equal(f.created,1);
});
test('failed answer gathering resumes on the same local answer without new tracks or negotiation',async()=>{
 const f=fixture('smartconnect','B');await f.start();let failures=1;
 f.call.gather=async()=>{if(failures-->0)throw new Error('gather timeout');};
 const offer={mode:'smartconnect',revision:1,description:{type:'offer',sdp:'v=0\nfirst'}};
 assert.equal(await f.call.receive(offer),false);const description=f.call.pc.localDescription;
 f.now=3100;await f.call.sample();await f.call.recoveryTask;
 assert.equal(f.messages.length,1);assert.equal(f.call.pc.localDescription,description);assert.equal(f.created,1);
 assert.equal(f.call.answerPending,false);
});
test('answer construction failures have a finite automatic retry budget',async()=>{
 const f=fixture('smartconnect','B');await f.start();let attempts=0;
 f.call.pc.createAnswer=async()=>{attempts++;throw new Error('unavailable');};
 await f.call.receive({mode:'smartconnect',revision:1,description:{type:'offer',sdp:'v=0\nfirst'}});
 for(let n=1;n<=8;n++){f.now=n*3100;await f.call.sample();await f.call.recoveryTask;}
 assert.equal(attempts,4);assert.equal(f.created,1);assert.equal(f.messages.length,0);
});
test('delayed old answers cannot resolve a later recovery; the matching late answer still succeeds',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.requestRestart('manual');
 assert.equal(await f.call.receive({mode:'smartconnect',revision:1,description:{type:'answer',sdp:'v=0\nold'}}),false);
 assert.equal(f.call.pc.signalingState,'have-local-offer');f.now=10000;await f.call.sample();await f.call.recoveryTask;
 await f.answer();assert.equal(f.call.pc.signalingState,'stable');assert.equal(await f.call.retrySignal(),false);
 assert.equal(f.created,1);
});
test('invalid policies cannot refresh expired policy or retain a queued policy recovery',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));
 f.call.lastRestart=0;f.now=100;await f.call.applyPolicy(policy(2,'cellular'));assert.equal(f.call.pending,'policy_change');
 await f.call.applyPolicy({status:'unavailable'});assert.equal(f.call.pending,null);
 f.now=200;await f.call.applyPolicy(policy(2,'cellular'));assert.equal(f.call.policyStatus,'fresh');assert.equal(f.call.restarts,0);
 const until=f.call.policyValidUntil;f.now=1000;await f.call.applyPolicy(policy(2,'cellular'));assert.equal(f.call.policyValidUntil,until);
 f.now=46000;await f.call.applyPolicy(policy(2,'cellular'));assert.equal(f.call.policyStatus,'stale');
 assert.equal(await f.call.requestRestart('policy_change'),false);assert.equal((await f.call.sample()).recommended_interface,'unavailable');
});
test('reconnected ICE cancels a queued failure recovery before cooldown expires',async()=>{
 const f=fixture();await f.start();await f.answer();f.call.lastRestart=0;f.now=1000;
 f.call.pc.iceConnectionState='failed';f.call.pc.oniceconnectionstatechange();assert.equal(f.call.pending,'ice_failed');
 f.call.pc.iceConnectionState='connected';f.call.pc.oniceconnectionstatechange();f.now=11000;await f.call.sample();
 assert.equal(f.call.restarts,0);assert.equal(f.call.pending,null);
});
test('resumed frames cancel a queued video-stall recovery without restarting',async()=>{
 const f=fixture();await f.start();await f.answer();f.call.lastRestart=0;f.call.pc.stats=stats(1,1);await f.call.sample();
 f.now=3500;await f.call.sample();await f.call.recoveryTask;assert.equal(f.call.pending,'video_stalled');
 f.now=11000;f.call.pc.stats=stats(2,2);await f.call.sample();await f.call.recoveryTask;
 assert.equal(f.call.pending,null);assert.equal(f.call.restarts,0);
});
test('private path snapshot is explicit, current, and excluded from sanitized exports',async()=>{
 const f=fixture();f.call.evidenceSessionId='PRIVATE-SESSION';await f.start();await f.answer();
 f.call.pc.stats=stats(8,10);await f.call.sample();const events=f.call.events.length,samples=f.call.samples.length;
 const snapshot=await f.call.privatePathSnapshot();assert.equal(snapshot.schema,1);assert.equal(snapshot.session_id,'PRIVATE-SESSION');
 assert.equal(snapshot.local_candidate.address,'PRIVATE-ADDRESS');assert.equal(snapshot.frames_decoded,8);assert.equal(snapshot.candidate_pair_generation,1);
 assert.equal(f.call.events.length,events);assert.equal(f.call.samples.length,samples);
 assert(!JSON.stringify(f.call.export()).includes('PRIVATE-'));assert.equal(f.call.export().physical_egress_verified,false);
 f.call.close();await assert.rejects(()=>f.call.privatePathSnapshot(),/active_call_required/);
});
test('receiver preservation includes tracks first observed after the initial sample',async()=>{
 const f=fixture();await f.start();await f.answer();const audio={kind:'audio'},video={kind:'video'};
 f.call.pc.receivers=[{track:audio}];await f.call.sample();f.call.pc.receivers.push({track:video});await f.call.sample();
 f.call.pc.receivers=[{track:audio}];assert.equal((await f.call.sample()).same_observed_receiver_tracks,false);
});

test('exact Engine explanations survive sanitized history while arbitrary free text is excluded',async()=>{
 const f=fixture();await f.start();await f.answer();
 const explanation='Hold: superiority 2/3; elapsed dwell 22.0/30s';
 await f.call.applyPolicy({...policy(1,'wifi'),reason_code:'hold',explanation});assert.equal(f.call.policySnapshot.explanation,explanation);
 assert.equal(f.call.events.find(e=>e.kind==='policy_recommendation').explanation,explanation);
 await f.call.applyPolicy({...policy(2,'wifi'),explanation:'PRIVATE free text 192.0.2.1'});
 assert.equal(f.call.policySnapshot.explanation,null);assert(!JSON.stringify(f.call.export()).includes('PRIVATE'));
});

test('initial createOffer failures retry on the same PC before publication in both modes',async()=>{
 for(const mode of ['baseline','smartconnect']){
  const f=fixture(mode),factory=f.call.pcFactory;let attempts=0;
  f.call.pcFactory=config=>{const pc=factory(config),create=pc.createOffer.bind(pc);pc.createOffer=async options=>{if(++attempts<3)throw new Error('temporary browser failure');return create(options);};return pc;};
  await f.start();assert.equal(f.call.initialOfferPending,true);assert.equal(f.messages.length,0);
  f.now=2999;await f.call.sample();await f.call.recoveryTask;assert.equal(attempts,1);
  for(const now of [3000,6000]){f.now=now;await f.call.sample();await f.call.recoveryTask;}
  assert.equal(attempts,3);assert.equal(f.call.initialOfferPending,false);assert.equal(f.messages.length,1);
  assert.equal(f.messages[0].revision,1);assert.equal(f.call.pc.restarts,0);assert.equal(f.created,1);
  assert.deepEqual(f.call.pc.getSenders().map(s=>s.track),f.tracks);assert(f.tracks.every(t=>!t.stopped));
 }
});
test('initial gathering rollback retries stop after three retries without consuming recovery budget',async()=>{
 const f=fixture();let attempts=0;f.call.gather=async()=>{attempts++;throw new Error('gather timeout');};
 await f.start();
 for(let n=1;n<=8;n++){f.now=n*3000;await f.call.sample();await f.call.recoveryTask;}
 assert.equal(attempts,4);assert.equal(f.call.initialOfferAttempts,4);assert.equal(f.call.initialOfferPending,false);
 assert.equal(f.call.pc.signalingState,'stable');assert.equal(f.call.restarts,0);assert.equal(f.call.revision,0);assert.equal(f.messages.length,0);
 assert.equal(await f.call.requestRestart('manual'),false);assert.equal(f.created,1);
 assert(f.call.events.some(e=>e.kind==='initial_offer_limit_reached'));
});
test('unpublished stalled-video recovery retries respect ten-second cooldown and three-restart ceiling',async()=>{
 const f=fixture();await f.start();await f.answer();const pc=f.call.pc;let attempts=0;
 f.call.pc.stats=stats(2,4);await f.call.sample();f.call.gather=async()=>{attempts++;throw new Error('gather timeout');};
 f.now=3500;await f.call.sample();await f.call.recoveryTask;assert.equal(f.call.pending,'video_stalled');assert.equal(f.call.stallReported,true);
 f.now=13499;await f.call.sample();await f.call.recoveryTask;assert.equal(attempts,1);
 for(const now of [13500,23500,33500]){f.now=now;await f.call.sample();await f.call.recoveryTask;}
 assert.equal(attempts,3);assert.equal(f.call.restarts,3);assert.equal(f.call.pending,null);assert.equal(f.call.pc,pc);
 assert.equal(f.call.revision,1);assert.equal(f.messages.length,1);assert(f.tracks.every(t=>!t.stopped));
});
test('expired recommendation cancels retry of its unpublished recovery offer',async()=>{
 const f=fixture();await f.start();await f.answer();await f.call.applyPolicy(policy(1,'wifi'));
 f.call.gather=async()=>{throw new Error('gather timeout');};await f.call.applyPolicy(policy(2,'cellular',44));
 assert.equal(f.call.pending,'policy_change');f.now=11000;await f.call.sample();await f.call.recoveryTask;
 assert.equal(f.call.restarts,1);assert.equal(f.call.pending,null);assert.equal(f.call.policyStatus,'stale');
});
test('ending while initial or recovery offer retry is pending prevents every future attempt',async()=>{
 for(const recovery of [false,true]){
  const f=fixture();if(recovery){await f.start();await f.answer();}
  let attempts=0;f.call.gather=async()=>{attempts++;throw new Error('gather timeout');};
  if(recovery)await f.call.requestRestart('manual');else await f.start();
  assert(recovery?f.call.pending:f.call.initialOfferPending);f.call.close();f.now=60000;
  assert.equal(await f.call.sample(),null);assert.equal(f.call.pending,null);assert.equal(f.call.initialOfferPending,false);
  assert.equal(attempts,1);assert.equal(f.created,1);assert(f.tracks.every(t=>t.stopped));
 }
});
test('rollback failure blocks negotiation and rejects delayed old answers without replacing tracks',async()=>{
 const f=fixture();await f.start();await f.answer();const pc=f.call.pc,setLocal=pc.setLocalDescription.bind(pc);
 pc.setLocalDescription=async d=>{if(d.type==='rollback')throw new Error('rollback unsupported');return setLocal(d);};
 f.call.gather=async()=>{throw new Error('gather timeout');};await f.call.requestRestart('manual');
 assert.equal(f.call.negotiationBlocked,true);assert.equal(f.call.lastSignal,null);assert.equal(f.call.pending,null);
 assert.equal(await f.call.receive({mode:'smartconnect',revision:1,description:{type:'answer',sdp:'v=0\nold answer'}}),false);
 f.now=60000;await f.call.sample();assert.equal(await f.call.requestRestart('manual'),false);assert.equal(await f.call.retrySignal(),false);
 assert.equal(f.call.restarts,1);assert.equal(f.call.pc,pc);assert(f.tracks.every(t=>!t.stopped));
 assert(f.call.events.some(e=>e.kind==='negotiation_blocked'));f.call.close();assert(f.tracks.every(t=>t.stopped));
});
test('ending during unpublished gathering cannot schedule another offer when gathering later resolves',async()=>{
 const f=fixture();let release;f.call.gather=()=>new Promise(resolve=>{release=resolve;});
 const starting=f.start();await new Promise(setImmediate);assert.equal(typeof release,'function');
 f.call.close();release();await starting;f.now=60000;assert.equal(await f.call.sample(),null);
 assert.equal(f.call.initialOfferPending,false);assert.equal(f.messages.length,0);assert.equal(f.created,1);assert(f.tracks.every(t=>t.stopped));
});
