'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const jury=require('./jury.js');
const fixed=Date.parse('2026-11-09T12:00:00Z');
function inventory(role='B',stamp=fixed){return {schema:1,kind:'interface_inventory',platform:role==='A'?'macos':'windows',role,captured_at:new Date(stamp).toISOString(),interfaces:[{id:role==='A'?'en0':'adapter-7',active:true,network:'wifi',addresses:['192.0.2.20']}]};}
function page(){
  const elements=new Map(),timers=new Map();let nextTimer=0,now=fixed,data=inventory(),failRead=false,reads=0,pickerCalls=0;
  const doc={body:{classList:{add(){},remove(){}}},getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',handlers:{},addEventListener(t,f){this.handlers[t]=f;}});return elements.get(id);}};
  class Clock extends Date {static now(){return now;}}
  const context={module:{exports:{}},Date:Clock,URL,document:doc,setInterval(f){timers.set(++nextTimer,f);return nextTimer;},clearInterval(id){timers.delete(id);},
    fetch(){assert.fail('No network request is allowed during inventory setup');},
    navigator:{mediaDevices:{getUserMedia(){assert.fail('No media before a call');},getDisplayMedia(){assert.fail('No recording during inventory setup');}}},
    showOpenFilePicker:async()=>{pickerCalls++;return [{getFile:async()=>{reads++;if(failRead)throw Error('private detail must not be shown');return {size:200,text:async()=>JSON.stringify(data)};}}];}};
  vm.runInNewContext(fs.readFileSync(require.resolve('./jury.js'),'utf8'),context);
  const view=context.module.exports.create({document:doc,getRole:()=> 'B',getEvidence:()=>({}),getStreams:()=>[]});
  return {view,doc,elements,timers,setData(v){data=v;},setTime(v){now=v;},failRead(v){failRead=v;},get reads(){return reads;},get pickerCalls(){return pickerCalls;},
    async click(id){await doc.getElementById(id).handlers.click();},async tick(){for(const f of timers.values())f();await new Promise(resolve=>setImmediate(resolve));}};
}
test('link and enter jury view show fresh Windows OS inventory without starting a call',async()=>{
  const p=page();assert.equal(p.reads,0);assert.equal(p.pickerCalls,0);assert.equal(p.timers.size,0);
  await p.click('juryInventory');await p.click('juryView');
  assert.equal(p.view.getReadiness().inventory_linked,true);assert.equal(p.view.getReadiness().inventory_fresh,true);
  assert.equal(p.doc.getElementById('juryInventoryState').textContent,'LINKED · FRESH');
  assert.match(p.doc.getElementById('juryInventoryInterfaces').textContent,/Wi-Fi · adapter-7/);
  assert(![...p.elements.values()].some(e=>e.textContent.includes('192.0.2.20')));
  assert.equal(p.timers.size,1);
});
test('stale linked inventory becomes fresh when the same file is updated, without relinking',async()=>{
  const p=page();p.setData(inventory('B',fixed-31000));await p.click('juryInventory');
  assert.equal(p.doc.getElementById('juryInventoryState').textContent,'LINKED · STALE');
  p.setData(inventory());await p.tick();
  assert.equal(p.doc.getElementById('juryInventoryState').textContent,'LINKED · FRESH');assert.equal(p.pickerCalls,1);
  p.setTime(fixed+31000);await p.tick();assert.equal(p.doc.getElementById('juryInventoryState').textContent,'LINKED · STALE');
});
test('temporarily unreadable file never keeps a fresh claim and recovers without relinking',async()=>{
  const p=page();await p.click('juryInventory');p.failRead(true);await p.tick();
  assert.equal(p.view.getReadiness().inventory_fresh,false);assert.equal(p.doc.getElementById('juryInventoryState').textContent,'LINKED · READ UNAVAILABLE');
  assert(![...p.elements.values()].some(e=>e.textContent.includes('private detail')));
  p.failRead(false);await p.tick();assert.equal(p.view.getReadiness().inventory_fresh,true);assert.equal(p.pickerCalls,1);
});
test('wrong-peer or malformed inventory is rejected at link time',async()=>{
  for(const data of [inventory('A'),{role:'B'},inventory('B',fixed+3000)]){
    const p=page();p.setData(data);await p.click('juryInventory');assert.equal(p.view.getReadiness().inventory_linked,false);assert.equal(p.timers.size,0);
  }
});
test('finishing or suspending stops local file refresh and marks inventory historical',async()=>{
  for(const operation of ['finish','suspend']){
    const p=page();await p.click('juryInventory');p.view[operation]();assert.equal(p.timers.size,0);assert.equal(p.view.getReadiness().inventory_fresh,false);assert.equal(p.doc.getElementById('juryInventoryState').textContent,'STOPPED · HISTORICAL');await p.click('juryInventory');assert.equal(p.timers.size,0);assert.equal(p.pickerCalls,1);
  }
});
test('pre-call summary reports OS inventory only and filters injected interface identifiers',()=>{
  const i=inventory('A');i.interfaces.push({id:'en6',active:true,addresses:['192.0.2.21']},{id:'192.0.2.99-private',active:true,network:'wifi'},{id:'en3',active:false});
  const r=jury.inventoryStatus(i,'A',fixed);assert.deepEqual(r.interfaces,[{id:'en0',network:'wifi'},{id:'en6',network:'cellular'}]);assert(!JSON.stringify(r).includes('192.0.2'));
  assert.equal(jury.match(null,i,'A',fixed).status,'unverified');
});
test('initial media labels wait for call statistics rather than misreporting inventory linkage',()=>{
  const html=fs.readFileSync(require.resolve('./index.html'),'utf8');
  assert.match(html,/id="juryMatchDetail">Media path not checked · call not started/);
  assert.match(html,/id="juryNetworkType">Browser-reported local network type: awaiting call statistics/);
});
