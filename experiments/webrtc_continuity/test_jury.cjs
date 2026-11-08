'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const jury=require('./jury.js'),recording=require('./recording.js');
const now=Date.parse('2026-11-08T12:00:00Z');
function fixture(){return{snapshot:{role:'A',captured_at:new Date(now).toISOString(),connection_state:'connected',ice_state:'connected',candidate_pair_generation:1,selected_pair:{state:'succeeded',nominated:true},local_candidate:{candidate_type:'host',address:'192.0.2.20'}},inventory:{schema:1,kind:'interface_inventory',platform:'macos',role:'A',captured_at:new Date(now).toISOString(),interfaces:[{id:'en0',active:true,addresses:['192.0.2.20']},{id:'en6',active:true,addresses:['192.0.2.21']}]}};}
test('exact fresh Mac association is never physical egress or handover proof',()=>{const f=fixture(),r=jury.match(f.snapshot,f.inventory,'A',now);assert.equal(r.interface,'en0');assert.equal(r.status,'candidate_interface_match');assert.equal(r.physical_egress_verified,false);assert.equal(r.same_session_handover_verified,false);assert(!JSON.stringify(r).includes('192.0.2'));});
test('cellular association requires an exact current address match',()=>{const f=fixture();f.snapshot.local_candidate.address='192.0.2.21';assert.equal(jury.match(f.snapshot,f.inventory,'A',now).interface,'en6');});
for(const [name,mutate] of [
 ['stale inventory',f=>{f.inventory.captured_at=new Date(now-31000).toISOString();}],
 ['future inventory',f=>{f.inventory.captured_at=new Date(now+3000).toISOString();}],
 ['stale stats',f=>{f.snapshot.captured_at=new Date(now-6000).toISOString();}],
 ['wrong peer',f=>{f.inventory.role='B';}],
 ['wrong platform',f=>{f.inventory.platform='windows';}],
 ['inactive interface',f=>{f.inventory.interfaces[0].active=false;}],
 ['mDNS hidden candidate',f=>{f.snapshot.local_candidate.address='private-host.local';}],
 ['relay address',f=>{f.snapshot.local_candidate.candidate_type='relay';}],
 ['reflexive address',f=>{f.snapshot.local_candidate.candidate_type='srflx';}],
 ['ambiguous match',f=>{f.inventory.interfaces[1].addresses=['192.0.2.20'];}],
 ['not connected',f=>{f.snapshot.connection_state='disconnected';}],
 ['not selected',f=>{f.snapshot.selected_pair.nominated=false;}],
 ['unknown pair generation',f=>{f.snapshot.candidate_pair_generation=null;}],
 ['unmatched address',f=>{f.snapshot.local_candidate.address='198.51.100.42';}],
 ['injected interface name',f=>{f.inventory.interfaces[0].id='192.0.2.20-secret';}],
])test(name+' stays unverified',()=>{const f=fixture();mutate(f);assert.equal(jury.match(f.snapshot,f.inventory,'A',now).status,'unverified');});
test('IPv6 textual normalization and scope work without DNS',()=>{const f=fixture();f.snapshot.local_candidate.address='fe80::1234%en0';f.inventory.interfaces[0].addresses=['fe80:0:0:0:0:0:0:1234'];assert.equal(jury.match(f.snapshot,f.inventory,'A',now).interface,'en0');f.snapshot.local_candidate.address='fe80::1234%en6';assert.equal(jury.match(f.snapshot,f.inventory,'A',now).status,'unverified');});
test('Windows reports its own adapter and remote recommendation label',()=>{const f=fixture();f.snapshot.role='B';f.inventory.role='B';f.inventory.platform='windows';f.inventory.interfaces=[{id:'adapter-7',index:7,active:true,network:'wifi',addresses:['192.0.2.20']}];const r=jury.match(f.snapshot,f.inventory,'B',now);assert.equal(r.interface,'adapter-7');assert.equal(r.network,'wifi');assert.match(jury.recommendationLabel('B'),/^REMOTE MAC/);assert(!jury.recommendationLabel('A').includes('REMOTE'));});
test('loopback, multicast, malformed and names are never matched',()=>{for(const address of ['localhost','127.0.0.1','0.0.0.0','224.0.0.2','192.0.2.999','01.2.3.4','::1','ff02::1','<script>'])assert.equal(jury.ip(address),null);});
test('capture rejects desktop, window, unrelated tab and missing handle',()=>{for(const type of ['window','monitor','browser'])assert.equal(recording.correctSurface({getSettings:()=>({displaySurface:type}),getCaptureHandle:()=>({handle:'different'})},'expected'),false);assert.equal(recording.correctSurface({getSettings:()=>({displaySurface:'browser'}),getCaptureHandle:()=>({handle:'expected'})},'expected'),true);});
test('stored ZIP has correct CRC and rejects unsafe archive paths',async()=>{assert.equal(recording.crc32(new TextEncoder().encode('123456789')),0xcbf43926);const blob=await recording.zip([{name:'sanitized.json',blob:new Blob(['{"test_fixture":true}'])}]);const bytes=new Uint8Array(await blob.arrayBuffer());assert.equal(new DataView(bytes.buffer).getUint32(0,true),0x04034b50);await assert.rejects(recording.zip([{name:'../escape',blob:new Blob(['x'])}]));});
test('recording module is inert and approval gate precedes capture',async()=>{
 const elements=new Map();const doc={getElementById(id){if(!elements.has(id))elements.set(id,{checked:false,handlers:{},addEventListener(t,f){this.handlers[t]=f;}});return elements.get(id);}};
 let notices=[];const rec=recording.create({document:doc,getRole:()=> 'A',getEvidence:()=>({}),getStreams:()=>[],enter:()=>assert.fail('entered before approval'),announce:s=>notices.push(s)});
 assert.equal(rec.active,false);assert.equal(rec.hasRecording,false);await doc.getElementById('recordStart').handlers.click();assert.match(notices[0],/approval/);assert.equal(rec.hasRecording,false);
});
