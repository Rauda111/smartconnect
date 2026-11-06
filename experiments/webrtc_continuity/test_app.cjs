'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const api=require('./core.js');
const source=fs.readFileSync(__dirname+'/app.js','utf8');
function setup(){
 const elements=new Map(),calls={fetch:[],media:0,pc:0,timers:[],stopped:0,incoming:[]};
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
 const sandbox={document:{getElementById:element,createElement:()=>({click(){}})},location:{hash:'#role=A&token=test-only-token',pathname:'/'},history:{replaceState(){}},URLSearchParams,
  navigator:{mediaDevices:{async getUserMedia(constraints){calls.media++;calls.constraints=constraints;return{getTracks:()=>tracks};}},clipboard:{writeText:async()=>{}}},MediaStream,RTCPeerConnection:FakePC,
  SmartConnectContinuity:{...api,Call:class extends api.Call{constructor(options){super(options);calls.instance=this;}}},crypto:{randomUUID:()=> 'fixture-client-AAAA'},performance:{now:()=>0},AbortController,
  fetch:async(path,options)=>{calls.fetch.push({path,options});return{ok:true,json:async()=>path.startsWith('/signal?')?{messages:calls.incoming.splice(0)}:{accepted:true}};},
  setTimeout(fn,ms){calls.timers.push({fn,ms});return calls.timers.length;},clearTimeout(){},addEventListener(){},Blob,URL,console};
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
 f.calls.incoming.push({mode:'baseline',revision:1,description:{type:'answer',sdp:'v=0\nfixture-answer'}});
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
