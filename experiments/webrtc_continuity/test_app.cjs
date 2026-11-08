'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const api=require('./core.js');
const source=fs.readFileSync(__dirname+'/app.js','utf8');
function setup(){
 const elements=new Map(),calls={fetch:[],media:0,pc:0,timers:[],stopped:0,incoming:[],responseStatus:200,policy:null,now:0,listeners:{},downloads:[],downloadFailure:false,lease:360,mediaDelay:0,policyDelay:0};
 const defaults={role:'A',mode:'baseline',signaling:'broker',ice:'{"iceServers":[],"iceTransportPolicy":"all"}',duration:'120'};
 function element(id){if(!elements.has(id))elements.set(id,{value:defaults[id] || '',checked:false,disabled:false,textContent:'',handlers:{},addEventListener(type,fn){this.handlers[type]=fn;},async click(){if(this.handlers.click)return this.handlers.click();},play:async()=>{}});return elements.get(id);}
 const tracks=[{kind:'video',stop(){calls.stopped++;}},{kind:'audio',stop(){calls.stopped++;}}];
 class FakePC{
  constructor(config){calls.pc++;calls.config=config;this.signalingState='stable';this.iceGatheringState='complete';this.senders=[];}
  addTrack(track){this.senders.push({track});}
  async createOffer(){return{type:'offer',sdp:'v=0\nfixture'};}
  async setLocalDescription(d){this.localDescription=d;this.signalingState='have-local-offer';}
  async getStats(){return new Map();}
  async setRemoteDescription(d){this.remoteDescription=d;this.signalingState='stable';}
  getSenders(){return this.senders;}getReceivers(){return [];}close(){}
 }
 class MediaStream{constructor(){this.tracks=[];}getTracks(){return this.tracks;}addTrack(t){this.tracks.push(t);}}
 const sandbox={document:{getElementById:element,createElement:()=>({click(){if(calls.downloadFailure)throw new Error('download blocked');calls.downloads.push(this);}}),visibilityState:'visible',addEventListener(type,fn){calls.listeners[type]=fn;}},location:{hash:'#role=A&token=test-only-token',pathname:'/'},history:{replaceState(){}},URLSearchParams,
  navigator:{mediaDevices:{async getUserMedia(constraints){calls.media++;calls.now+=calls.mediaDelay;calls.constraints=constraints;return{getTracks:()=>tracks};}},clipboard:{writeText:async()=>{}}},MediaStream,RTCPeerConnection:FakePC,
  SmartConnectContinuity:{...api,Call:class extends api.Call{constructor(options){super(options);calls.instance=this;}}},crypto:{randomUUID:()=> 'fixture-client-AAAA'},performance:{now:()=>calls.now},AbortController,
  fetch:async(path,options)=>{calls.fetch.push({path,options});if(path.startsWith('/policy'))calls.now+=calls.policyDelay;return{ok:calls.responseStatus===200,status:calls.responseStatus,json:async()=>path.startsWith('/signal?')?{session_id:'fixture-session',messages:calls.incoming.splice(0)}:path==='/join'?{joined:true,session_id:'fixture-session',absolute_expires_in_seconds:calls.lease}:path.startsWith('/policy')?(calls.policy || {status:'not_configured'}):{accepted:true}};},
  setTimeout(fn,ms){calls.timers.push({fn,ms});return calls.timers.length;},clearTimeout(){},clearInterval(){},addEventListener(type,fn){calls.listeners[type]=fn;},Blob,URL,TextEncoder,console};
 vm.runInNewContext(fs.readFileSync(__dirname+'/recording.js','utf8'),sandbox,{filename:'recording.js'});
 vm.runInNewContext(fs.readFileSync(__dirname+'/jury.js','utf8'),sandbox,{filename:'jury.js'});
 vm.runInNewContext(source,sandbox,{filename:'app.js'});
 return{element,calls};
}
test('page boot is inert: no network, media permission, peer connection or timers',()=>{
 const f=setup();assert.equal(f.calls.fetch.length,0);assert.equal(f.calls.media,0);assert.equal(f.calls.pc,0);assert.equal(f.calls.timers.length,0);
});
test('Start without explicit operator approval stays inert',async()=>{
 const f=setup();await f.element('start').click();assert.equal(f.calls.fetch.length,0);assert.equal(f.calls.media,0);assert.equal(f.calls.pc,0);assert.match(f.element('status').textContent,/Approval is required/);
});
test('invalid ICE config is rejected before media, signaling and peer creation',async()=>{
 const f=setup();f.element('approval').checked=true;f.element('ice').value='{"iceServers":[],"iceTransportPolicy":"relay"}';await f.element('start').click();assert.equal(f.calls.fetch.length,0);assert.equal(f.calls.media,0);assert.equal(f.calls.pc,0);
});
test('approved start wires actual WebRTC APIs and camera/microphone, baseline disables custom recovery',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();
 assert.equal(f.calls.media,1);assert.equal(f.calls.constraints.audio,true);assert.equal(f.calls.pc,1);assert.equal(f.element('configuration').hidden,true);
 assert.equal(f.calls.config.iceServers.length,0);assert.equal(f.element('restart').disabled,true);
 assert(f.calls.fetch.some(x=>x.path==='/join'));assert(f.calls.fetch.some(x=>x.path==='/signal' && JSON.parse(x.options.body).message.description.type==='offer'));
 await f.element('stop').click();assert(f.calls.stopped>=2);assert(f.calls.fetch.some(x=>x.path==='/leave'));
});
test('manual exchange creates SDP without contacting the local broker or external signaling',async()=>{
 const f=setup();f.element('approval').checked=true;f.element('signaling').value='manual';await f.element('start').click();assert.equal(f.calls.fetch.length,0);assert.equal(JSON.parse(f.element('outgoing').value).description.type,'offer');assert.equal(f.calls.pc,1);
 await f.element('start').click();assert.equal(f.calls.pc,1);await f.element('stop').click();
});

test('signaling received while offer generation is busy is retained until the same PC is ready',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();await new Promise(setImmediate);
 const pc=f.calls.instance.pc;f.calls.instance.busy=true;
 f.calls.incoming.push({delivery_id:1,session_id:'fixture-session',mode:'baseline',revision:1,description:{type:'answer',sdp:'v=0\nfixture-answer'}});
 await f.calls.timers.filter(t=>t.fn.name==='polling').at(-1).fn();
 assert.equal(pc.remoteDescription,undefined);
 f.calls.instance.busy=false;
 await f.calls.timers.filter(t=>t.fn.name==='polling').at(-1).fn();
 assert.equal(pc.remoteDescription.type,'answer');assert.equal(f.calls.pc,1);
 await f.element('stop').click();
});
test('approved duration uses an independent end timer, not only stats polling',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();
 const limit=f.calls.timers.find(t=>t.ms===120000);assert(limit);limit.fn();await new Promise(setImmediate);
 assert.equal(f.calls.instance.closed,true);assert(f.calls.stopped>=2);assert.equal(f.calls.pc,1);
 assert(f.calls.instance.events.some(e=>e.kind==='approved_time_limit_reached'));
});


test('Mac manual signaling can read local policy without joining or polling remote signaling',async()=>{
 const f=setup();f.element('approval').checked=true;f.element('signaling').value='manual';f.element('policy').checked=true;
 await f.element('start').click();await new Promise(setImmediate);
 assert.deepEqual(f.calls.fetch.map(x=>x.path),['/policy']);assert.equal(f.calls.pc,1);
 await f.element('stop').click();assert(!f.calls.fetch.some(x=>x.path==='/leave'));
});
test('Windows answerer never polls Mac policy even when its checkbox is checked',async()=>{
 const f=setup();f.element('approval').checked=true;f.element('role').value='B';f.element('signaling').value='manual';f.element('policy').checked=true;
 await f.element('start').click();await new Promise(setImmediate);
 assert.equal(f.calls.fetch.length,0);await f.element('stop').click();
});
test('policy checkbox cannot bypass approval in manual mode',async()=>{
 const f=setup();f.element('signaling').value='manual';f.element('policy').checked=true;
 await f.element('start').click();assert.equal(f.calls.fetch.length,0);assert.equal(f.calls.media,0);
});

test('broker sends session scope on all joined operations and exposes no session ID publicly',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();await new Promise(setImmediate);
 const post=f.calls.fetch.find(x=>x.path==='/signal');assert.equal(JSON.parse(post.options.body).session_id,'fixture-session');
 assert(f.calls.fetch.some(x=>x.path.startsWith('/policy?') && x.path.includes('session_id=fixture-session')));
 assert(f.calls.fetch.some(x=>x.path.startsWith('/signal?') && x.path.includes('session_id=fixture-session')));
 assert(!f.element('condition').textContent.includes('fixture-session'));
 await f.element('stop').click();assert.equal(JSON.parse(f.calls.fetch.find(x=>x.path==='/leave').options.body).session_id,'fixture-session');
});
test('broker answerer reads shared policy for display but cannot request a restart',async()=>{
 const f=setup();f.element('approval').checked=true;f.element('role').value='B';f.element('mode').value='smartconnect';
 await f.element('start').click();await new Promise(setImmediate);
 assert(f.calls.fetch.some(x=>x.path.startsWith('/policy?')));assert.equal(f.element('restart').disabled,true);
 assert.equal(await f.calls.instance.requestRestart('policy_change'),false);await f.element('stop').click();
});

test('unchecked broker policy is still observed without enabling policy recovery',async()=>{
 const f=setup();f.element('approval').checked=true;f.element('mode').value='smartconnect';
 f.calls.policy={session_id:'fixture-session',status:'fresh',application:'video_call',window:1,recommended:'wifi',age_seconds:0};
 await f.element('start').click();await new Promise(setImmediate);
 assert.equal(f.calls.instance.recommended,'wifi');assert.equal(f.calls.instance.policyRecoveryEnabled,false);
 f.calls.responseStatus=503;await f.calls.timers.filter(t=>t.fn.name==='polling').at(-1).fn();
 assert.equal(f.calls.instance.policyStatus,'unavailable');assert.equal(f.element('recommendation').textContent,'Unavailable');await f.element('stop').click();
});
test('session expiry closes media and disables actions and clears measured display',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();await new Promise(setImmediate);
 f.calls.responseStatus=409;await f.calls.timers.filter(t=>t.fn.name==='polling').at(-1).fn();
 assert.equal(f.calls.instance.closed,true);assert.match(f.element('connection').textContent,/Closed/);
 for(const id of ['stop','restart','retry','receive','applyPolicy'])assert.equal(f.element(id).disabled,true);
 assert.equal(f.element('recommendation').textContent,'Unavailable');assert.equal(f.calls.pc,1);
});

test('broker acknowledges safely buffered deliveries and ignores repeat batches while Call is busy',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();await new Promise(setImmediate);
 const poll=()=>f.calls.timers.filter(t=>t.fn.name==='polling').at(-1).fn();
 const answer={delivery_id:1,session_id:'fixture-session',mode:'baseline',revision:1,description:{type:'answer',sdp:'v=0\nanswer'}};
 f.calls.instance.busy=true;f.calls.incoming.push(answer);await poll();
 f.calls.incoming.push(answer);await poll();assert(f.calls.fetch.at(-2).path.includes('ack=1'));
 f.calls.instance.busy=false;await poll();
 assert.equal(f.calls.instance.events.filter(e=>e.kind==='negotiation_completed').length,1);
 assert.equal(f.calls.instance.pc.remoteDescription.sdp,'v=0\nanswer');await f.element('stop').click();
});
test('raw policy status cannot bypass session, profile, age or replay validation in the display',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();await new Promise(setImmediate);
 const poll=()=>f.calls.timers.filter(t=>t.fn.name==='polling').at(-1).fn();
 const valid={session_id:'fixture-session',status:'fresh',application:'video_call',window:1,recommended:'wifi',age_seconds:0};
 for(const invalid of [{...valid,application:'file_download'},{...valid,age_seconds:46},{...valid,session_id:'wrong'}]){
  f.calls.policy=invalid;await poll();assert.equal(f.element('recommendation').textContent,'Unavailable');
 }
 f.calls.policy=valid;await poll();assert.equal(f.element('recommendation').textContent,'Wi-Fi');
 f.calls.policy={...valid,recommended:'cellular'};await poll();assert.equal(f.element('recommendation').textContent,'Unavailable');
 await f.element('stop').click();
});
test('private candidate download requires an active approved session and uses a separate artifact',async()=>{
 const f=setup();await f.element('privatePath').click();assert.equal(f.calls.downloads.length,0);assert.equal(f.calls.fetch.length,0);
 f.element('approval').checked=true;f.element('signaling').value='manual';await f.element('start').click();
 await f.element('privatePath').click();assert.equal(f.calls.downloads[0].download,'PRIVATE-selected-media-path.json');
 assert.equal(f.calls.fetch.length,0);assert.equal(f.calls.instance.export().physical_egress_verified,false);
 await f.element('stop').click();assert.equal(f.element('privatePath').disabled,true);
});
test('browser hints are recorded without claiming a path; page suspension closes and cannot revive media',async()=>{
 const f=setup();f.calls.listeners.offline();assert.equal(f.calls.fetch.length,0);
 f.element('approval').checked=true;f.element('signaling').value='manual';await f.element('start').click();
 f.calls.listeners.offline();f.calls.listeners.online();f.calls.listeners.visibilitychange();
 assert.equal(f.calls.instance.events.filter(e=>e.kind==='browser_network_hint').length,2);
 assert.equal(f.calls.instance.restarts,0);f.calls.listeners.pagehide();assert.equal(f.calls.instance.closed,true);
 f.calls.listeners.pageshow({persisted:true});assert.match(f.element('status').textContent,/Reload and approve/);
 await f.element('start').click();assert.equal(f.calls.pc,1);assert.equal(f.calls.media,1);
});

test('unavailable media cannot show continuity; explicit stop clears live policy and connection labels',async()=>{
 const f=setup();f.element('approval').checked=true;
 f.calls.policy={session_id:'fixture-session',status:'fresh',application:'video_call',window:1,recommended:'wifi',age_seconds:0};
 await f.element('start').click();await new Promise(setImmediate);
 assert.match(f.element('continuity').textContent,/continuity unavailable/);assert.equal(f.element('recommendation').textContent,'Wi-Fi');
 await f.element('stop').click();assert.equal(f.element('recommendation').textContent,'Unavailable');
 assert.match(f.element('connection').textContent,/Closed/);assert.equal(f.element('delivery').textContent,'Media stopped');
 assert.match(f.element('continuity').textContent,/historical/);
});
test('network transit time is charged to policy freshness before display and recovery',async()=>{
 const f=setup();f.element('approval').checked=true;f.calls.policyDelay=4000;
 f.calls.policy={session_id:'fixture-session',status:'fresh',application:'video_call',window:1,recommended:'wifi',age_seconds:43};
 await f.element('start').click();await new Promise(setImmediate);
 assert.equal(f.calls.instance.policyStatus,'stale');assert.equal(f.element('recommendation').textContent,'Unavailable');await f.element('stop').click();
});
test('session duration is capped by remaining absolute lease after waiting for media permission',async()=>{
 const f=setup();f.element('approval').checked=true;f.calls.lease=90;f.calls.mediaDelay=20000;
 await f.element('start').click();assert(f.calls.timers.some(t=>t.ms===70000));assert.match(f.element('condition').textContent,/limit 70 s/);
 await f.element('stop').click();
});
test('expired lease after media permission never constructs a peer connection or sends an offer',async()=>{
 const f=setup();f.element('approval').checked=true;f.calls.lease=1;f.calls.mediaDelay=2000;
 await f.element('start').click();assert.equal(f.calls.pc,0);assert(f.calls.stopped>=2);
 assert(!f.calls.fetch.some(x=>x.path==='/signal'));
});
test('unbounded ICE destinations or missing TURN credentials are rejected before any approved traffic',async()=>{
 for(const ice of [
  {iceServers:[{urls:Array(5).fill('stun:example.invalid:3478')}],iceTransportPolicy:'all'},
  {iceServers:[{urls:'turn:example.invalid:3478'}],iceTransportPolicy:'all'},
  {iceServers:[{urls:'turn:example.invalid:3478',username:'fixture',credential:'x'.repeat(1025)}],iceTransportPolicy:'relay'},
  {iceServers:[{urls:'stun:'+ 'x'.repeat(1025)}],iceTransportPolicy:'all'}]){
  const f=setup();f.element('approval').checked=true;f.element('ice').value=JSON.stringify(ice);
  await f.element('start').click();assert.equal(f.calls.media,0);assert.equal(f.calls.fetch.length,0);assert.equal(f.calls.pc,0);
 }
});
test('approved private TURN config reaches WebRTC without leaking credentials into observations',async()=>{
 const f=setup();f.element('approval').checked=true;f.element('signaling').value='manual';
 f.element('ice').value=JSON.stringify({iceServers:[{urls:'turns:example.invalid:5349',username:'PRIVATE-USER',credential:'PRIVATE-CREDENTIAL'}],iceTransportPolicy:'relay'});
 await f.element('start').click();assert.equal(f.calls.config.iceTransportPolicy,'relay');assert.equal(f.calls.config.iceServers[0].credential,'PRIVATE-CREDENTIAL');
 assert(!JSON.stringify(f.calls.instance.export()).includes('PRIVATE'));await f.element('stop').click();
});

test('explicit end automatically downloads sanitized evidence once with peer and start time',async()=>{
 const f=setup();await f.element('stop').click();assert.equal(f.calls.downloads.length,0);
 const g=setup();g.element('approval').checked=true;await g.element('start').click();await new Promise(setImmediate);
 assert.equal(g.calls.downloads.length,0);await g.element('stop').click();await g.element('stop').click();
 assert.equal(g.calls.downloads.length,1);assert.match(g.calls.downloads[0].download,/^controlled-call-A-\d{4}-.*\.json$/);
 const data=await (await fetch(g.calls.downloads[0].href)).json();
 assert(data.events.some(e=>e.kind==='session_explicitly_ended'));assert.equal(data.physical_egress_verified,false);
 const raw=JSON.stringify(data);for(const value of ['fixture-session','test-only-token','fixture-offer','"description":','"local_candidate":'])assert(!raw.includes(value));
});
test('time limit and broker expiry automatically preserve final observations without starting new calls',async()=>{
 for(const expiry of ['timer','broker']){
  const f=setup();f.element('approval').checked=true;f.element('role').value='B';await f.element('start').click();await new Promise(setImmediate);
  if(expiry==='timer')f.calls.timers.find(t=>t.ms===120000).fn();
  else {f.calls.responseStatus=409;await f.calls.timers.filter(t=>t.fn.name==='polling').at(-1).fn();}
  await new Promise(setImmediate);assert.equal(f.calls.downloads.length,1);assert.match(f.calls.downloads[0].download,/^controlled-call-B-/);
  assert.equal(f.calls.instance.closed,true);assert.equal(f.calls.pc,1);assert.equal(f.calls.media,1);
 }
});
test('blocked automatic download does not prevent shutdown and manual export remains available',async()=>{
 const f=setup();f.element('approval').checked=true;await f.element('start').click();f.calls.downloadFailure=true;
 await f.element('stop').click();assert.equal(f.calls.instance.closed,true);assert.equal(f.element('export').disabled,false);
 assert.match(f.element('status').textContent,/if no file appeared/);assert.equal(f.calls.downloads.length,0);
 f.calls.downloadFailure=false;await f.element('export').click();assert.equal(f.calls.downloads.length,1);
});
