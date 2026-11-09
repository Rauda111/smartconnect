/* No fetch, getUserMedia, RTCPeerConnection, timer, or ICE work before Start. */
(function () {
  'use strict';
  const $=id=>document.getElementById(id);
  const simpleDemo=document.body?.dataset?.juryDemo==='true';
  const tabStore={get:key=>{try{return sessionStorage.getItem('smartconnect.'+key);}catch(_){return null;}},set:(key,value)=>{try{sessionStorage.setItem('smartconnect.'+key,value);return true;}catch(_){return false;}},remove:key=>{try{sessionStorage.removeItem('smartconnect.'+key);}catch(_){}}};
  const fragment=new URLSearchParams(location.hash.slice(1));
  const token=fragment.get('token') || tabStore.get('reader') || '';
  if(token)tabStore.set('reader',token);
  try{
    const saved=JSON.parse(tabStore.get('settings') || '{}');
    for(const [id,allowed] of Object.entries({role:['A','B'],mode:['baseline','smartconnect'],signaling:['broker','manual']}))if(allowed.includes(saved[id]))$(id).value=saved[id];
    if(Number.isInteger(saved.duration)&&saved.duration>=30&&saved.duration<=300)$('duration').value=String(saved.duration);
    if(typeof saved.ice==='string'&&saved.ice.length<=8192)$('ice').value=saved.ice;
    if(typeof saved.policy==='boolean')$('policy').checked=saved.policy;
  }catch(_){}
  if(['A','B'].includes(fragment.get('role'))) $('role').value=fragment.get('role');
  // Legacy links are supported, but new launchers never put credentials in URLs.
  if(location.hash) history.replaceState(null,'',location.pathname);
  function saveSettings(){return tabStore.set('settings',JSON.stringify({role:$('role').value,mode:$('mode').value,signaling:$('signaling').value,policy:$('policy').checked,duration:Number($('duration').value),ice:$('ice').value}));}
  for(const id of ['role','mode','signaling','policy','duration','ice'])$(id).addEventListener('change',saveSettings);
  saveSettings();
  let call=null,stream=null,client=null,stopped=true,signalTimer=null,sampleTimer=null,limitTimer=null;
  let active=null,sessionId=null,started=0,sampleBusy=false,signalCursor=0,lifecycleEnded=false,leaseUntil=Infinity;
  let automaticEvidenceAttempted=false,stopPromise=null,ownedReleased=false,starting=false,joinPending=null;
  const inbox=[]; // Preserve messages if media recovery is still generating its offer.
  const remoteStream=new MediaStream();
  $('remote').srcObject=remoteStream;
  const jury=typeof SmartConnectJury==='undefined'?null:SmartConnectJury.create({document,
    getRole:()=>active?.role || $('role').value,getEvidence:()=>call?.export() || null,
    getFingerprint:async()=>{if(!call?.evidenceSessionId)return null;try{return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(call.evidenceSessionId))),b=>b.toString(16).padStart(2,'0')).join('');}catch(_){return null;}},
    getStreams:()=>[stream,remoteStream]});
  const status=text=>{$('status').textContent=text;};
  if(simpleDemo)$('accessStatus').textContent=token?'Private access loaded for this tab':'Open the private launcher to load access';
  const showEvent=()=>{
    if(call?.negotiationBlocked)$('restart').disabled=true;
    $('events').textContent=call ? JSON.stringify(call.export().events,null,2) : 'No events.';
    $('retry').disabled=!call || call.negotiationBlocked || !call.lastSignal || stopped || call.signalRetries>=3 || (call.lastSignal.description.type==='offer' && call.pc.signalingState!=='have-local-offer');
  };
  async function api(path, method='GET', data=null,extra={}) {
    const requestStarted=performance.now(),controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
    try {
      const response=await fetch(path,{method,cache:'no-store',signal:controller.signal,...extra,
        headers:{Authorization:'Bearer '+token,...(data ? {'Content-Type':'application/json'} : {})},
        body:data ? JSON.stringify(data) : undefined});
      if(!response.ok){const error=new Error('signaling_unavailable');error.status=response.status;if([403,409].includes(response.status)&&sessionId)error.sessionExpired=true;throw error;}
      const result=await response.json(),elapsed=Math.max(0,(performance.now()-requestStarted)/1000);
      // Conservatively charge the entire round trip to freshness, including time spent offline.
      if(path.startsWith('/policy') && typeof result.age_seconds==='number')result.age_seconds+=elapsed;
      if(path==='/join' && typeof result.absolute_expires_in_seconds==='number')result.absolute_expires_in_seconds-=elapsed;
      return result;
    } finally {clearTimeout(timeout);}
  }
  const peerData=()=>({role:active.role,client,...(sessionId?{session_id:sessionId}:{})});
  async function releaseOwned(keepalive=false){
    const stored=tabStore.get('owned');let owned;
    try{owned=stored?JSON.parse(stored):null;}catch(_){tabStore.remove('owned');}
    if(!owned && !ownedReleased && active?.signaling==='broker' && client && sessionId)owned=peerData();
    if(!owned)return true;
    if(!['A','B'].includes(owned.role)||!/^[A-Za-z0-9-]{16,64}$/.test(owned.client||'')||!/^[A-Za-z0-9_-]{1,128}$/.test(owned.session_id||'')){tabStore.remove('owned');return true;}
    try{await api('/leave','POST',owned,keepalive?{keepalive:true}:{});}
    catch(error){if(![403,409].includes(error.status))return false;}
    // A late cleanup response must never erase ownership of a newer call.
    if(tabStore.get('owned')===stored)tabStore.remove('owned');
    ownedReleased=true;
    return true;
  }
  const peerQuery=()=>new URLSearchParams(peerData()).toString();
  const value=(v,unit='')=>typeof v==='number' && Number.isFinite(v)?v.toFixed(1)+unit:'Unavailable';
  function renderPolicy() {
    const p=call?.policySnapshot;
    const fresh=p && call.policyStatus==='fresh' && call.clock()<=call.policyValidUntil;
    $('recommendation').textContent=fresh?({wifi:'Wi-Fi',cellular:'Cellular',none:'No eligible path'}[p.recommended] || 'Unavailable'):'Unavailable';
    const reasons={availability:'Availability exception: the policy selected a responding path.',hold:'Normal stability rule: retain the current recommendation.',qualified_change:'A candidate met the normal switching requirements.',no_eligible_path:'Neither path currently qualifies.'};
    $('decision').textContent=fresh?(p.explanation || reasons[p.reason_code] || 'Current measured policy recommendation.'):'No fresh, session-matched measurement is available.';
    $('policyFreshness').textContent=fresh?'Measured ICMP · window '+(Number.isInteger(p.window)?p.window:'Unavailable')+' · age '+value(Math.max(0,45-(call.policyValidUntil-call.clock())/1000),' s'):'Measured ICMP unavailable';
    const stability=fresh && p.stability;
    $('stability').textContent=stability?'Qualifying observations '+value(stability.hold_count)+' / '+value(stability.hold_required)+' · minimum dwell '+value(stability.dwell_seconds,' s'):'Policy stability state unavailable';
    for(const name of ['wifi','cellular']) {const m=fresh && p.measurements && p.measurements[name];$('quality_'+name).textContent=m?({reachable:'Responding',no_reply:'No probe replies',error:'Measurement unavailable'}[m.status] || 'Unavailable')+' · RTT '+value(m.latency_ms,' ms')+' · loss '+value(m.loss_percent,'%')+' · derived score '+value(m.score)+' · derived trend '+m.trend:'Unavailable';}
  }
  function renderSample(s) {
    $('connection').textContent=s.connection_state+' · ICE '+s.ice_state;
    $('transport').textContent=s.local_candidate_type+' / '+s.protocol+' · candidate generation '+(s.candidate_pair_generation ?? 'Unavailable');
    $('delivery').textContent='Decoded frames '+(s.frames_decoded ?? 'Unavailable')+' · audio packets '+(s.audio_packets_received ?? 'Unavailable');
    const progress=call.export().progress,open=progress.open_gaps;
    const observed=(typeof s.frames_decoded==='number' && s.frames_decoded>0) || (typeof s.audio_packets_received==='number' && s.audio_packets_received>0);
    $('continuity').textContent=!observed ? 'Waiting for media progress; continuity unavailable.' : open.length ? open.map(g=>g.kind.replaceAll('_',' ')+' gap '+value(g.elapsed_since_last_progress_ms/1000,' s')).join(' · ') : 'No counter gap currently detected; '+progress.closed_gaps.length+' recorded interval(s).';
    $('preservation').textContent='Same peer connection: '+(s.same_peer_connection?'yes':'no')+' · same local tracks: '+(s.same_local_tracks?'yes':'no')+' · same observed remote tracks: '+(s.same_observed_receiver_tracks===null?'unavailable':s.same_observed_receiver_tracks?'yes':'no');
  }
  async function send(message) {
    if(stopped)throw new Error('session_ended');
    if(active.signaling==='manual') {
      $('outgoing').value=JSON.stringify(message);
      status('Private outgoing signaling is ready. Exchange it with the other client; the call has not been recreated.');
    } else await api('/signal','POST',{...peerData(),message});
  }
  function configuration() {
    if($('ice').value.length>8192)throw new Error('configuration_too_large');
    const config=JSON.parse($('ice').value);
    if(!config || typeof config!=='object' || !Array.isArray(config.iceServers) || !['all','relay'].includes(config.iceTransportPolicy))throw new Error('invalid_configuration');
    if(config.iceServers.length>4)throw new Error('too_many_servers');
    let urlCount=0;const servers=[];
    for(const server of config.iceServers) {
      if(!server || typeof server!=='object')throw new Error('invalid_ice_server');
      const urls=typeof server.urls==='string' ? [server.urls] : server.urls;
      if(!Array.isArray(urls) || !urls.length || urls.length>4 || urls.some(u=>typeof u!=='string' || u.length>1024 || !/^(stun|stuns|turn|turns):[^\s@]+$/.test(u)))throw new Error('invalid_ice_server');
      urlCount+=urls.length;if(urlCount>8)throw new Error('too_many_urls');
      const clean={urls};
      if(urls.some(u=>/^turns?:/.test(u))) {
        if(['username','credential'].some(k=>typeof server[k]!=='string' || !server[k].length || server[k].length>1024 || /[\u0000-\u001f\u007f]/.test(server[k])) || (server.credentialType && server.credentialType!=='password'))throw new Error('private_turn_credentials_required');
        clean.username=server.username;clean.credential=server.credential;
      }
      servers.push(clean);
    }
    if(config.iceTransportPolicy==='relay' && !config.iceServers.some(s=>(Array.isArray(s.urls)?s.urls:[s.urls]).some(u=>/^turns?:/.test(u))))throw new Error('turn_required');
    const duration=Number($('duration').value);
    if(!Number.isInteger(duration) || duration<30 || duration>300)throw new Error('invalid_duration');
    return {rtc:{iceServers:servers,iceTransportPolicy:config.iceTransportPolicy,iceCandidatePoolSize:0},duration};
  }
  async function polling() {
    if(stopped)return;
    try {
      if(active.signaling==='broker') {
      const result=await api('/signal?'+peerQuery()+'&ack='+signalCursor);
      if(stopped)return;
      if(result.session_id!==sessionId || !Array.isArray(result.messages) || result.messages.length>64)throw new Error('invalid_signaling_batch');
      const received=[];let nextCursor=signalCursor;
      for(const message of result.messages) {
        if(!Number.isSafeInteger(message?.delivery_id) || message.delivery_id<1 || message.session_id!==sessionId)throw new Error('invalid_signaling_delivery');
        if(message.delivery_id<=signalCursor)continue;
        if(message.delivery_id<=nextCursor)throw new Error('invalid_signaling_order');
        received.push(message);nextCursor=message.delivery_id;
      }
      if(inbox.length+received.length>64)throw new Error('signaling_buffer_full');
      inbox.push(...received);signalCursor=nextCursor; // ACK only after messages are safely buffered.

      while(inbox.length && !call.busy && !stopped)await call.receive(inbox.shift());
      }
      if((active.policy && active.role==='A') || active.signaling==='broker') {
        const p=await api('/policy'+(sessionId?'?'+peerQuery():''));
        if(stopped)return;await call.applyPolicy(p);renderPolicy();
      }
    } catch (error) {if(error.sessionExpired){await stop();status('Shared session ended or expired. Evidence download requested. Choose New Call on both laptops when ready.');return;}if(!stopped){await call.applyPolicy({status:'unavailable'});renderPolicy();call.event(active.signaling==='broker'?'signaling_poll_failure':'policy_poll_failure');status('Local signaling or policy input unavailable. No call was recreated; inspect events and restore the approved input.');}}
    if(!stopped)signalTimer=setTimeout(polling,500);
  }
  async function sampling() {
    if(stopped || sampleBusy)return;
    sampleBusy=true;
    try {
      if(performance.now()-started>=active.duration*1000) {call.event('approved_time_limit_reached');await stop();return;}
      const sample=await call.sample();
      if(sample && !stopped){renderSample(sample);$('metrics').textContent=JSON.stringify({latest:sample,progress:call.export().progress},null,2);if(sample.policy_input_status==='stale')renderPolicy();void jury?.update(call,sample);}
      else if(!stopped)jury?.unavailable();
      showEvent();
    } finally {sampleBusy=false;if(!stopped)sampleTimer=setTimeout(sampling,500);}
  }
  function renderClosed(reason) {
    renderPolicy();$('connection').textContent='Closed · '+reason;$('delivery').textContent='Media stopped';
    $('continuity').textContent='Session ended; recorded counters and gaps are historical observations.';
    $('transport').textContent='Session ended · see last recorded transport in technical details';
  }
  async function stop() {
    if(stopPromise)return stopPromise;
    stopPromise=(async()=>{
    stopped=true;lifecycleEnded=true;inbox.length=0;clearTimeout(signalTimer);clearTimeout(sampleTimer);clearTimeout(limitTimer);
    if(call)call.close();
    renderClosed('session ended');
    if(stream)for(const track of stream.getTracks())track.stop();
    for(const track of remoteStream.getTracks())track.stop?.();
    $('local').srcObject=null;$('remote').srcObject=null;
    // Freeze the historical display immediately; slow broker cleanup must not
    // erase it or delay it. Recorder and broker shutdown keep their existing order.
    if(call)jury?.complete();
    // A join already on the wire may acquire ownership after End is clicked.
    // Wait for its bounded response before releasing that exact session.
    if(joinPending)try{await joinPending;}catch(_){}
    const released=await releaseOwned();
    await downloadEvidenceAtEnd();
    for(const id of ['stop','restart','retry','receive','applyPolicy','privatePath'])$(id).disabled=true;
    $('export').disabled=!call;
    $('newCall').disabled=false;
    status(released?'Call ended. Evidence download requested; use Technical Details → Download sanitized observations if no file appeared. Choose New Call on both laptops; cameras remain off until Start Call.':'Call ended locally. Broker cleanup is pending; New Call will retry it. Cameras and microphones are off.');
    showEvent();
    })();return stopPromise;
  }
  $('newCall').addEventListener('click',async()=>{
    $('newCall').disabled=true;
    try{
      await stop();
      if(!await releaseOwned()){status('Cannot release the previous session yet. Check staging connectivity, then click New Call again. No new media started.');return;}
      if(!saveSettings() || (token && !tabStore.set('reader',token))){status('Tab storage is unavailable. No new call started; restore browser site storage before continuing.');return;}
      // A clean document resets all counters, old callbacks and optional recorder
      // state. Tab-only auth/settings survive; no media is started by this reload.
      location.reload();
    }finally{$('newCall').disabled=false;}
  });
  $('start').addEventListener('click',async()=>{
    // In the simple dashboard, pressing the clearly labelled Start Call button
    // is the operator's explicit media action. Page load/refresh never do this.
    if(simpleDemo)$('approval').checked=true;
    if(!$('approval').checked){status('Approval is required before camera, microphone, ICE or signaling traffic.');return;}
    if(starting || call || lifecycleEnded){status('A session already exists. Choose New Call to prepare another run.');return;}
    let configured;
    try {configured=configuration();}catch(_){status('Invalid private configuration. Check ICE servers, TURN requirement and duration locally.');return;}
    active={role:$('role').value,mode:$('mode').value,signaling:$('signaling').value,policy:$('policy').checked,duration:configured.duration};
    if((active.signaling==='broker' || (active.policy && active.role==='A')) && !token){status('No local access token. Open this server’s private URL; manual signaling without policy reading can run without a token.');return;}
    starting=true;$('start').disabled=true;$('stop').disabled=false;$('configuration').disabled=true;$('configuration').hidden=true;
    $('condition').textContent=(active.mode==='baseline' ? 'Ordinary WebRTC baseline' : 'SmartConnect-assisted ICE recovery only')+' · Peer '+active.role+' · Physical interface unverified.';
    try {
      saveSettings();
      if(active.signaling==='broker' && !await releaseOwned())throw new Error('cleanup_pending');
      if(lifecycleEnded)throw new Error('session_ended');
      client=tabStore.get('client') || crypto.randomUUID();tabStore.set('client',client);
      if(active.signaling==='broker') {
        joinPending=api('/join','POST',peerData()).then(joined=>{
          if(typeof joined.session_id!=='string' || !joined.session_id)throw new Error('session_unavailable');
          sessionId=joined.session_id;ownedReleased=false;tabStore.set('owned',JSON.stringify(peerData()));
          if(!Number.isFinite(joined.absolute_expires_in_seconds) || joined.absolute_expires_in_seconds<=0 || joined.absolute_expires_in_seconds>360)throw new Error('session_lease_unavailable');
          leaseUntil=performance.now()+joined.absolute_expires_in_seconds*1000;
        });
        try{await joinPending;}finally{joinPending=null;}
      }
      if(lifecycleEnded)throw new Error('session_ended');
      stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:360},frameRate:{ideal:15,max:15}},audio:true});
      if(lifecycleEnded)throw new Error('session_ended');
      active.duration=Math.min(active.duration,(leaseUntil-performance.now())/1000);
      if(active.duration<=0)throw new Error('session_lease_expired');
      $('condition').textContent+=' · session limit '+Math.floor(active.duration)+' s';
      $('local').srcObject=stream;stopped=false;started=performance.now();
      call=new SmartConnectContinuity.Call({role:active.role,mode:active.mode,sessionId,evidenceSessionId:sessionId || crypto.randomUUID(),policyRecoveryEnabled:active.policy,pcFactory:config=>new RTCPeerConnection(config),send,
        onEvent:e=>{showEvent();jury?.event(e);if(e.kind==='recovery_requested')$('recoveryCause').textContent=({policy_change:'SmartConnect policy change',ice_failed:'ICE failure',ice_disconnected:'ICE disconnected',video_stalled:'Video frame progress stalled',manual:'Operator request'})[e.cause] || 'Unavailable';if(e.kind==='recovery_requested')status(active.signaling==='manual' ? 'Recovery offer requested. MANUAL signaling: exchange the NEW offer/answer between laptops; automatic end-to-end recovery is unavailable.' : 'ICE recovery requested. Verify signaling delivery and actual media counters.');if(['signaling_failure','recovery_limit_reached','initial_offer_limit_reached'].includes(e.kind))status(call.negotiationBlocked?'Negotiation could not roll back safely. Automatic attempts stopped; end this session explicitly.':'Recovery/signaling needs attention. Bounded attempts retain the same peer connection; inspect sanitized events.');if(e.kind==='negotiation_blocked')status('Negotiation could not roll back safely. Automatic attempts stopped; end this session explicitly.');},
        onTrack:event=>{if(!remoteStream.getTracks().includes(event.track))remoteStream.addTrack(event.track);jury?.attachAudio();$('remote').play().catch(()=>status('Remote playback needs a user gesture: press Play remote audio/video.'));}});
      jury?.attachAudio();
      $('stop').disabled=false;$('receive').disabled=false;$('export').disabled=false;$('privatePath').disabled=false;
      $('restart').disabled=active.mode!=='smartconnect' || active.role!=='A';
      $('applyPolicy').disabled=active.signaling!=='manual' || active.role!=='A';
      limitTimer=setTimeout(()=>{if(!stopped){call.event('approved_time_limit_reached');void stop();}},active.duration*1000);
      const ready=await call.start(stream,configured.rtc,{approved:true});
      if(stopped)return;
      status(ready===false ? (call.negotiationBlocked ? 'Negotiation could not roll back safely. Automatic attempts stopped; end this session explicitly.' : 'Initial signaling failed. Bounded retries retain the same peer connection; inspect events or end explicitly. No continuity is claimed.') : 'Approved peer started. Awaiting signaling/media; no Wi-Fi/cellular path or continuity has been verified.');
      if(active.signaling==='broker' || (active.policy && active.role==='A'))void polling();
      void sampling();showEvent();
    } catch (_) {
      stopped=true;lifecycleEnded=true;clearTimeout(signalTimer);clearTimeout(sampleTimer);clearTimeout(limitTimer);if(call)call.close();if(stream)for(const t of stream.getTracks())t.stop();
      $('local').srcObject=null;$('remote').srcObject=null;
      for(const id of ['stop','restart','retry','receive','applyPolicy','privatePath'])$(id).disabled=true;
      if(stopPromise){await stopPromise;return;}
      if(active.signaling==='broker')await releaseOwned();
      status('Call could not start. Check camera/microphone permission and staging connectivity. If this peer is open in another tab, end it there. Choose New Call to retry; no automatic restart.');
      await jury?.finish();$('newCall').disabled=false;
    }finally{starting=false;}
  });
  $('stop').addEventListener('click',stop);
  $('restart').addEventListener('click',()=>{if(call)void call.requestRestart('manual');});
  $('retry').addEventListener('click',()=>{if(call)void call.retrySignal();});
  $('receive').addEventListener('click',async()=>{
    if(!call || stopped || active.signaling!=='manual'){status('Manual signaling applies only to an active manually signaled session.');return;}
    try {const accepted=await call.receive(JSON.parse($('incoming').value));status(accepted?'Signaling applied on the same peer connection. Check actual media counters.':'Signaling rejected, stale, or not ready. No call was recreated.');}
    catch(_){status('Invalid private signaling message. No raw details are displayed.');}
    showEvent();
  });
  $('applyPolicy').addEventListener('click',async()=>{
    if(!call || stopped || active.signaling!=='manual')return;
    try {await call.applyPolicy(JSON.parse($('policyInput').value));renderPolicy();status('Policy input inspected. Fresh changes may request ICE recovery; actual interface remains unverified.');}
    catch(_){status('Invalid policy input. No raw details are displayed.');}
  });
  $('copy').addEventListener('click',async()=>{
    if(!$('outgoing').value){status('No outgoing private signaling is available.');return;}
    try{await navigator.clipboard.writeText($('outgoing').value);status('Private signaling copied. Share only with the approved controlled peer.');}
    catch(_){status('Clipboard unavailable. Select the private text manually.');}
  });
  $('play').addEventListener('click',()=>{$('remote').play().catch(()=>status('No playable remote media yet, or playback permission is unavailable.'));});
  function download(data,name) {
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function evidenceFilename() {
    return 'controlled-call-'+call.role+'-'+(call.startedUTC || 'unstarted').replace(/[^0-9TZ-]/g,'-')+'.json';
  }
  async function downloadEvidenceAtEnd() {
    if(!call || automaticEvidenceAttempted)return;
    automaticEvidenceAttempted=true;
    if(jury?.isRecording()){await jury.finish();return;}
    await jury?.finish();
    // Local sanitized data only. Never auto-save SDP, candidates, or media.
    // Browsers may block automatic downloads; the explicit export stays enabled.
    try{download(call.export(),evidenceFilename());}catch(_){/* Explicit export remains available. */}
  }
  $('export').addEventListener('click',()=>{if(call)download(call.export(),evidenceFilename());});
  $('privatePath').addEventListener('click',async()=>{
    if(!call || stopped)return;
    try {download(await call.privatePathSnapshot(),'PRIVATE-selected-media-path.json');status('Private candidate snapshot saved. Match it to fresh interface evidence using the offline verifier; this does not prove packet egress or handover.');}
    catch(_){status('Selected path evidence is unavailable. No verification is claimed.');}
  });
  for(const type of ['online','offline'])addEventListener(type,()=>{
    if(call && !stopped)call.event('browser_network_hint',{state:type}); // A browser hint is not a media-path measurement.
  });
  document.addEventListener('visibilitychange',()=>{
    if(call && !stopped){call.event('browser_visibility',{state:document.visibilityState==='visible'?'visible':'hidden'});renderPolicy();}
  });
  addEventListener('pagehide',()=>{
    saveSettings();
    jury?.suspend();
    stopped=true;lifecycleEnded=true;inbox.length=0;clearTimeout(signalTimer);clearTimeout(sampleTimer);clearTimeout(limitTimer);
    if(call)call.close();if(stream)for(const t of stream.getTracks())t.stop();renderClosed('page suspended');
    if(active?.signaling==='broker' && sessionId)void releaseOwned(true);
    for(const id of ['stop','restart','retry','receive','applyPolicy','privatePath'])$(id).disabled=true;
  });
  addEventListener('pageshow',event=>{if(event.persisted && lifecycleEnded)status('This page was suspended and its session ended. Reload and approve a new session explicitly.');});
})();
