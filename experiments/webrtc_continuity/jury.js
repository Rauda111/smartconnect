/* Local-only jury presentation and address matching. No I/O or timers on import. */
(function(root){
  'use strict';
  const finite=x=>typeof x==='number' && Number.isFinite(x);
  const number=(x,n=1)=>finite(x)?x.toFixed(n):'UNAVAILABLE';
  function ip(value){
    if(typeof value!=='string' || value.length>100)return null;
    const [host,scope,...extra]=value.toLowerCase().split('%');if(extra.length)return null;
    if(/^\d+\.\d+\.\d+\.\d+$/.test(host)){
      const a=host.split('.');if(a.some(x=>!/^0$|^[1-9]\d{0,2}$/.test(x)||Number(x)>255)||Number(a[0])===0||Number(a[0])===127||Number(a[0])>=224)return null;
      return {address:a.map(Number).join('.'),scope:scope||null};
    }
    if(!/^[0-9a-f:]+$/.test(host)||!host.includes(':'))return null;
    try{const normalized=new URL('http://['+host+']/').hostname.slice(1,-1);if(['::','::1'].includes(normalized)||normalized.startsWith('ff'))return null;return{address:normalized,scope:scope||null};}catch(_){return null;}
  }
  function match(snapshot,inventory,role,now=Date.now()){
    const base={status:'unverified',interface:null,network:'unknown',reason:'no_fresh_independent_inventory',checked_at:new Date(now).toISOString(),candidate_pair_generation:snapshot?.candidate_pair_generation??null,physical_egress_verified:false,same_session_handover_verified:false};
    const fail=reason=>({...base,reason});
    if(!snapshot || snapshot.role!==role || snapshot.connection_state!=='connected' || !['connected','completed'].includes(snapshot.ice_state) || snapshot.selected_pair?.state!=='succeeded' || snapshot.selected_pair?.nominated!==true || !Number.isInteger(snapshot.candidate_pair_generation) || snapshot.candidate_pair_generation<1)return fail('selected_pair_not_connected');
    if(snapshot.local_candidate?.candidate_type!=='host')return fail('non_host_candidate_not_attributable');
    const selected=ip(snapshot.local_candidate.address);if(!selected)return fail('candidate_address_hidden_or_not_ip');
    if(!inventory || inventory.schema!==1 || inventory.kind!=='interface_inventory' || inventory.role!==role || inventory.platform!==(role==='A'?'macos':'windows') || !Array.isArray(inventory.interfaces) || inventory.interfaces.length>100)return fail('inventory_missing_or_wrong_peer');
    const stamp=Date.parse(inventory.captured_at),captured=Date.parse(snapshot.captured_at);
    if(!finite(stamp)||!finite(captured)||now-stamp< -2000||now-stamp>30000||now-captured< -2000||now-captured>5000||Math.abs(captured-stamp)>30000)return fail('inventory_or_candidate_stale');
    const matches=[];
    for(const item of inventory.interfaces){
      if(item.active!==true || !Array.isArray(item.addresses) || item.addresses.length>100)continue;
      if(!(role==='A'?/^en\d+$/:/^adapter-\d+$/).test(item.id||''))continue;
      if(selected.scope && ![item.id,String(item.index)].includes(selected.scope))continue;
      if(item.addresses.some(a=>ip(a)?.address===selected.address))matches.push(item);
    }
    if(matches.length!==1)return fail(matches.length?'ambiguous_interface_match':'no_active_interface_match');
    const found=matches[0],network=role==='A'?(found.id==='en0'?'wifi':found.id==='en6'?'cellular':'unknown'):['wifi','ethernet','cellular'].includes(found.network)?found.network:'unknown';
    return {...base,status:'candidate_interface_match',interface:found.id,network,reason:'exact_host_address_match',inventory_captured_at:new Date(stamp).toISOString()};
  }
  function recommendationLabel(role){return role==='B'?'REMOTE MAC RECOMMENDATION':'RECOMMENDED NETWORK · THIS MAC';}
  function inventoryStatus(inventory,role,now=Date.now()){
    const invalid={status:'unavailable',age_seconds:null,interfaces:[]};
    if(!inventory || inventory.schema!==1 || inventory.kind!=='interface_inventory' || inventory.role!==role || inventory.platform!==(role==='A'?'macos':'windows') || !Array.isArray(inventory.interfaces) || inventory.interfaces.length>100)return invalid;
    const stamp=Date.parse(inventory.captured_at);
    if(!finite(stamp) || now-stamp< -2000)return invalid;
    const interfaces=inventory.interfaces.filter(item=>item && item.active===true && (role==='A'?/^en\d+$/:/^adapter-\d+$/).test(item.id||''))
      .map(item=>({id:item.id,network:role==='A'?(item.id==='en0'?'wifi':item.id==='en6'?'cellular':'unknown'):['wifi','ethernet','cellular'].includes(item.network)?item.network:'unknown'}));
    return {status:now-stamp<=30000?'fresh':'stale',age_seconds:Math.max(0,(now-stamp)/1000),interfaces};
  }
  function create({document:doc,getRole,getEvidence,getStreams,getFingerprint=async()=>null}){
    const simpleDemo=doc.body?.dataset?.juryDemo==='true';
    const $=id=>doc.getElementById(id);let handle=null,inventory=null,busy=false,inventoryBusy=false,inventoryTimer=null,ended=false,juryMode=false,lastMatch=null;
    const matches=[],readiness={inventory_linked:false};let recorder=null,hasSample=false;
    const put=(id,value)=>{$(id).textContent=value;};
    const announce=text=>put('juryNotice',text);
    function labels(){const b=getRole()==='B';put('juryPeer',b?'WINDOWS · PEER B':'MACBOOK · PEER A');put('juryRecommendationTitle',recommendationLabel(getRole()));put('juryMeasurementsTitle',b?'REMOTE MAC QUALITY · en0 / en6':'LOCAL MAC QUALITY · en0 / en6');put('juryLocalPathTitle',b?'WINDOWS LOCAL CANDIDATE ASSOCIATION':'MAC LOCAL CANDIDATE ASSOCIATION');if(simpleDemo){put('juryWifiTitle',b?'REMOTE MAC WI-FI · en0':'WI-FI · MAC en0');put('juryCellularTitle',b?'REMOTE MAC CELLULAR USB · en6':'CELLULAR USB · MAC en6');}}
    function availability(measurements=null){
      if(!simpleDemo)return;
      const os=inventoryStatus(inventory,getRole());
      for(const [network,iface,prefix] of [['wifi','en0','juryWifi'],['cellular','en6','juryCellular']]){
        const m=measurements?.[network];let text='NOT MEASURED',quality='Waiting for approved measurements';
        if(ended){text='SESSION ENDED';quality='Last measurements are in Technical Details';}
        else if(m){text=({reachable:'RESPONDING · ICMP',no_reply:'NO PROBE REPLIES',error:'MEASUREMENT UNAVAILABLE'}[m.status]||'UNVERIFIED');quality=number(m.latency_ms)+' ms RTT · '+number(m.loss_percent)+'% loss';}
        else if(getRole()==='A'&&os.status==='fresh'){
          const adapter=inventory.interfaces.find(i=>i && i.id===iface);
          text=adapter?.active===true?'AVAILABLE · OS REPORTED':adapter?.active===false?'INACTIVE · OS REPORTED':'NOT REPORTED';
        }
        put(prefix+'Availability',text);put(prefix+'Quality',quality);
      }
    }
    function renderInventory(){
      const s=inventoryStatus(inventory,getRole());readiness.inventory_fresh=!ended && !!handle && s.status==='fresh';
      put('juryInventoryState',ended?'STOPPED · HISTORICAL':!handle?'NOT LINKED':s.status==='fresh'?'LINKED · FRESH':s.status==='stale'?'LINKED · STALE':'LINKED · READ UNAVAILABLE');
      const names={wifi:'Wi-Fi',cellular:getRole()==='A'?'Cellular USB':'Cellular',ethernet:'Ethernet',unknown:'Type unknown'};
      put('juryInventoryInterfaces',!handle?'Link this laptop’s private inventory in setup.':s.status==='unavailable'?'Cannot validate this peer’s inventory. Check its helper; relink only if the file moved or access was lost.':
        (!ended && s.status==='fresh'?'OS-reported active interfaces: ':'Last reported active interfaces: ')+(s.interfaces.map(i=>names[i.network]+' · '+i.id).join(' | ')||'none')+' · snapshot age '+number(s.age_seconds)+' s'+(!ended && s.status==='stale'?' · restart the local inventory helper.':''));
      if(!hasSample || ended)availability();
    }
    function stopInventoryRefresh(){if(inventoryTimer!==null)clearInterval(inventoryTimer);inventoryTimer=null;}
    async function refreshInventory(){
      if(!handle || inventoryBusy || ended)return;inventoryBusy=true;
      try{await read();}catch(_){inventory=null;}finally{inventoryBusy=false;renderInventory();}
    }
    function enter(){labels();renderInventory();juryMode=true;doc.body.classList.add('jury-mode');$('juryPanel').hidden=false;$('jurySetup').hidden=!simpleDemo;if(simpleDemo)$('technicalDetails').open=false;announce('OS inventory, media path and packet-egress proof remain separate.');}
    function leave(){if(recorder?.active)return;if(simpleDemo){$('technicalDetails').open=true;return;}doc.body.classList.remove('jury-mode');juryMode=false;$('juryPanel').hidden=true;$('jurySetup').hidden=false;}
    async function link(){
      if(ended || recorder?.active)return;
      if(typeof root.showOpenFilePicker!=='function'){announce('Live inventory reading is unavailable in this browser. Current path remains UNVERIFIED. Use Chrome or Edge.');return;}
      stopInventoryRefresh();
      try{[handle]=await root.showOpenFilePicker({multiple:false,types:[{description:'Private interface inventory',accept:{'application/json':['.json']}}]});await read();if(inventoryStatus(inventory,getRole()).status==='unavailable')throw new Error();readiness.inventory_linked=true;inventoryTimer=setInterval(()=>{void refreshInventory();},2000);announce('Local inventory linked privately. Addresses stay on this laptop; matching begins only during an approved call.');}
      catch(_){handle=null;inventory=null;readiness.inventory_linked=false;announce('Inventory not linked. Media path stays UNVERIFIED; no addresses are shown.');}
      renderInventory();
    }
    async function read(){const file=await handle.getFile();if(file.size>65536)throw new Error();inventory=JSON.parse(await file.text());}
    function showMatch(m){
      const names={wifi:'Wi-Fi',cellular:'Cellular USB',ethernet:'Ethernet',unknown:'Network type unknown'};
      put('juryAssociation',m.status==='candidate_interface_match'?names[m.network]+' · '+m.interface:'UNKNOWN / UNVERIFIED');
      put('juryVerification',m.status==='candidate_interface_match'?'OS address match · '+m.interface+' · inventory age '+number((Date.now()-Date.parse(m.inventory_captured_at))/1000)+' s · egress NOT VERIFIED':'No fresh independent interface match');
      put('juryMatchDetail',m.reason.replaceAll('_',' '));
      if(m.status==='candidate_interface_match')lastMatch=m;
      put('juryLastMatch',lastMatch?'Last address match: '+lastMatch.interface+' at '+lastMatch.checked_at.slice(11,19)+' UTC · historical if current status is unknown':'No address match recorded for this call');
    }
    async function update(call,sample){
      if(ended)return;hasSample=true;labels();const current=new Date().toISOString();put('juryClock',current.slice(11,23)+' UTC');put('juryElapsed','Call +'+number(sample.elapsed_ms/1000)+' s');
      const p=call.policySnapshot,fresh=p && call.policyStatus==='fresh' && call.clock()<=call.policyValidUntil;
      availability(fresh?p.measurements:null);
      put('juryRecommendation',fresh?({wifi:'Wi-Fi',cellular:'Cellular',none:'No eligible path'}[p.recommended]||'UNAVAILABLE'):'UNAVAILABLE / STALE');
      put('juryExplanation',fresh?(p.explanation||'Explanation unavailable'):'Waiting for fresh measured policy; no recommendation is inferred.');
      put('juryStability',fresh?'Hold '+number(p.stability?.hold_count,0)+' / '+number(p.stability?.hold_required,0)+' · dwell '+number(p.stability?.dwell_seconds,0)+' s · margin '+number(p.stability?.margin,2):'Stability rules unavailable');
      for(const name of ['wifi','cellular']){const m=fresh?p.measurements?.[name]:null;put('jury_'+name,m?({reachable:'RESPONDING',no_reply:'NO REPLY',error:'UNAVAILABLE'}[m.status]||'UNAVAILABLE')+' · '+number(m.latency_ms)+' ms · '+number(m.loss_percent)+'% loss · score '+number(m.score,4)+' · adjusted '+number(m.adjusted_score,4):'UNAVAILABLE');}
      put('juryConnection',sample.connection_state+' · ICE '+sample.ice_state);
      put('juryPair','Pair #'+(sample.candidate_pair_generation??'?')+' · '+sample.local_candidate_type+' → '+sample.remote_candidate_type+' / '+sample.protocol+' · '+(sample.selected_pair_state||'unknown'));
      put('juryNetworkType','Browser-reported local type: '+(sample.local_network_type||'unknown')+' · metadata, not interface proof');
      put('juryRemote','Remote candidate: '+sample.remote_candidate_type+' · remote physical interface UNVERIFIED');
      put('juryProgress','Video frames '+number(sample.frames_decoded,0)+' · received audio packets '+number(sample.audio_packets_received,0));
      put('juryFreezes','Browser freezes '+number(sample.freezes,0)+' / '+number(sample.freeze_duration_seconds)+' s · sampled counter gaps '+call.metrics.progress.snapshot(call.clock()-call.origin).closed_gaps.length);
      put('juryPreservation','Same PC '+(sample.same_peer_connection?'YES':'NO')+' · local tracks '+(sample.same_local_tracks?'YES':'NO')+' · remote tracks '+(sample.same_observed_receiver_tracks===null?'UNKNOWN':sample.same_observed_receiver_tracks?'YES':'NO'));
      if(!handle){showMatch({status:'unverified',reason:'no_local_inventory'});return;}
      if(busy)return;busy=true;
      try{
        // Re-read in-place OS inventory; timestamps are not refreshed by this reader.
        await refreshInventory();
        const snapshot=await call.privatePathSnapshot();if(ended || call.closed)return;
        const m=match(snapshot,inventory,getRole());showMatch(m);matches.push({...m,elapsed_ms:sample.elapsed_ms});if(matches.length>1000)matches.shift();
      }catch(_){if(!ended)showMatch({status:'unverified',reason:'inventory_or_stats_unavailable'});}finally{busy=false;}
    }
    function event(e){
      if(e.kind==='recovery_requested'){put('juryRecovery',({policy_change:'POLICY CHANGE',ice_failed:'ICE FAILURE',ice_disconnected:'ICE DISCONNECTED',video_stalled:'VIDEO STALL',manual:'MANUAL REQUEST'}[e.cause]||'UNKNOWN')+' · +'+number(e.elapsed_ms/1000)+' s');recorder?.mark('recovery-request');}
      if(e.kind==='connection_state' && e.state==='connected')recorder?.mark('connected');
    }
    if(root.SmartConnectRecording)recorder=root.SmartConnectRecording.create({document:doc,getRole,getEvidence:async()=>({call:getEvidence(),session_fingerprint_sha256:await getFingerprint(),interface_associations:matches,physical_egress_verified:false,physical_handover_verified:false}),getStreams,enter,announce});
    $('juryView').addEventListener('click',enter);$('juryBack').addEventListener('click',leave);$('juryInventory').addEventListener('click',link);
    labels();renderInventory();if(simpleDemo)enter();
    return {update,event,unavailable:()=>{showMatch({status:'unverified',reason:'current_stats_unavailable'});put('juryConnection','CURRENT STATS UNAVAILABLE');},attachAudio:()=>recorder?.attachAudio(),
      hasRecording:()=>!!recorder?.hasRecording,
      isRecording:()=>!!recorder?.active,
      finish:()=>{ended=true;stopInventoryRefresh();renderInventory();put('juryElapsed','SESSION ENDED');put('juryConnection','ENDED · CAMERA / MIC OFF');put('juryRecommendation','SESSION ENDED');put('juryExplanation','Last measured decisions remain in Technical Details and the saved evidence.');put('juryAssociation','SESSION ENDED · see historical matches');put('juryVerification','No current media path after session end');return recorder?.finish();},
      suspend:()=>{ended=true;stopInventoryRefresh();renderInventory();recorder?.abort();},getReadiness:()=>({...readiness,juryMode})};
  }
  const api={ip,match,recommendationLabel,inventoryStatus,create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SmartConnectJury=api;
})(typeof globalThis!=='undefined'?globalThis:this);
