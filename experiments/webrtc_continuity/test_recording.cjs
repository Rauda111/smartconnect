'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function setup(surface='browser',captureHandle='fixture-handle'){
 const elements=new Map(),effects={display:0,recorder:0,audio:0,stop:0,downloads:[],timeouts:[],notices:[],entered:0};
 const element=id=>{if(!elements.has(id))elements.set(id,{checked:true,disabled:false,textContent:'',handlers:{},addEventListener(t,f){this.handlers[t]=f;}});return elements.get(id);};
 const track={kind:'video',getSettings:()=>({displaySurface:surface}),getCaptureHandle:()=>({handle:captureHandle}),stop(){effects.stop++;},addEventListener(){}};
 class Stream{constructor(tracks=[]){this.tracks=tracks;}getTracks(){return this.tracks;}getAudioTracks(){return this.tracks.filter(t=>t.kind==='audio');}getVideoTracks(){return this.tracks.filter(t=>t.kind==='video');}}
 class Recorder{static isTypeSupported(){return true;}constructor(stream,options){effects.recorder++;this.state='inactive';this.mimeType=options.mimeType;this.listeners={};}start(){this.state='recording';}addEventListener(name,fn){this.listeners[name]=fn;}stop(){this.state='inactive';queueMicrotask(()=>{this.ondataavailable({data:new Blob(['TEST FIXTURE, NOT CAMERA FOOTAGE'])});this.listeners.stop?.();});}}
 class Audio{resume(){return Promise.resolve();}close(){return Promise.resolve();}createMediaStreamDestination(){return{stream:new Stream([{kind:'audio'}])};}createMediaStreamSource(){effects.audio++;return{connect:n=>n,disconnect(){}};}createGain(){return{gain:{value:1},connect:n=>n};}}
 const doc={body:{classList:{toggle(){}}},getElementById:element,createElement(tag){if(tag==='video')return{videoWidth:0,videoHeight:0,play:async()=>{}};return{click(){effects.downloads.push(this.download);}};}};
 const local={kind:'audio'},remote={kind:'audio'};
 const context={TextEncoder,Blob,Uint8Array,DataView,Map,Date,Math,Number,Array,Promise,JSON,MediaStream:Stream,MediaRecorder:Recorder,AudioContext:Audio,crypto:{randomUUID:()=> 'fixture-handle'},location:{origin:'https://fixture.example'},performance:{now:()=>1000},navigator:{mediaDevices:{setCaptureHandleConfig(){},async getDisplayMedia(){effects.display++;return new Stream([track]);}}},URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL(){}},setTimeout(fn,ms){effects.timeouts.push({fn,ms});return 1;},clearTimeout(){},setInterval(){return 1;},clearInterval(){}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/recording.js','utf8'),context);
 const recorder=context.SmartConnectRecording.create({document:doc,getRole:()=> 'A',getEvidence:async()=>({call:{role:'A'},session_fingerprint_sha256:'fixture-only'}),getStreams:()=>[new Stream([local]),new Stream([remote])],enter:()=>effects.entered++,announce:s=>effects.notices.push(s)});
 return {element,effects,recorder};
}
test('permission request is gated by separate recording approval',async()=>{const f=setup();f.element('recordApproval').checked=false;await f.element('recordStart').handlers.click();assert.equal(f.effects.display,0);assert.equal(f.effects.recorder,0);});
test('wrong tab stops the captured track before MediaRecorder starts',async()=>{const f=setup('browser','wrong');await f.element('recordStart').handlers.click();assert.equal(f.effects.display,1);assert.equal(f.effects.recorder,0);assert.equal(f.recorder.hasRecording,false);assert(f.effects.stop>0);});
test('desktop/window capture cannot become a recording',async()=>{for(const surface of ['monitor','window']){const f=setup(surface);await f.element('recordStart').handlers.click();assert.equal(f.effects.recorder,0);assert(f.effects.stop>0);}});
test('approved same-tab recording mixes only existing call audio and saves once',async()=>{
 const f=setup();assert.equal(f.effects.display,0);await f.element('recordStart').handlers.click();assert.equal(f.recorder.active,true);assert.equal(f.effects.audio,2);f.recorder.attachAudio();assert.equal(f.effects.audio,2);assert(f.effects.timeouts.some(t=>t.ms===420000));
 const archive=await f.recorder.finish();await f.recorder.finish();assert.equal(f.recorder.active,false);assert.equal(f.effects.downloads.length,1);assert.equal(archive.type,'application/zip');assert(f.effects.stop>0);
});
