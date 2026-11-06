/* No fetch, getUserMedia, RTCPeerConnection, timer, or ICE work before Start. */
(function () {
  'use strict';
  const $=id=>document.getElementById(id);
  const fragment=new URLSearchParams(location.hash.slice(1));
  const token=fragment.get('token') || '';
  if(['A','B'].includes(fragment.get('role'))) $('role').value=fragment.get('role');
  // Remove access credentials from the visible URL/history entry, keep only in memory.
  if(location.hash) history.replaceState(null,'',location.pathname);
  let call=null,stream=null,client=null,stopped=true,signalTimer=null,sampleTimer=null,limitTimer=null;
  let active=null,started=0,sampleBusy=false;
  const inbox=[]; // Preserve messages if media recovery is still generating its offer.
  const remoteStream=new MediaStream();
  $('remote').srcObject=remoteStream;
  const status=text=>{$('status').textContent=text;};
  const showEvent=()=>{
    $('events').textContent=call ? JSON.stringify(call.export().events,null,2) : 'No events.';
    $('retry').disabled=!call || !call.lastSignal || stopped;
  };
  async function api(path, method='GET', data=null) {
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
    try {
      const response=await fetch(path,{method,cache:'no-store',signal:controller.signal,
        headers:{Authorization:'Bearer '+token,...(data ? {'Content-Type':'application/json'} : {})},
        body:data ? JSON.stringify(data) : undefined});
      if(!response.ok)throw new Error('signaling_unavailable');
      return await response.json();
    } finally {clearTimeout(timeout);}
  }
  const peerData=()=>({role:active.role,client});
  async function send(message) {
    if(stopped)throw new Error('session_ended');
    if(active.signaling==='manual') {
      $('outgoing').value=JSON.stringify(message);
      status('Private outgoing signaling is ready. Exchange it with the other client; the call has not been recreated.');
    } else await api('/signal','POST',{...peerData(),message});
  }
  function configuration() {
    const config=JSON.parse($('ice').value);
    if(!config || typeof config!=='object' || !Array.isArray(config.iceServers) || !['all','relay'].includes(config.iceTransportPolicy))throw new Error('invalid_configuration');
    if(config.iceServers.length>4)throw new Error('too_many_servers');
    for(const server of config.iceServers) {
      const urls=typeof server.urls==='string' ? [server.urls] : server.urls;
      if(!Array.isArray(urls) || !urls.length || urls.some(u=>typeof u!=='string' || !/^(stun|stuns|turn|turns):[^\s]+$/.test(u)))throw new Error('invalid_ice_server');
    }
    if(config.iceTransportPolicy==='relay' && !config.iceServers.some(s=>(Array.isArray(s.urls)?s.urls:[s.urls]).some(u=>/^turns?:/.test(u))))throw new Error('turn_required');
    const duration=Number($('duration').value);
    if(!Number.isInteger(duration) || duration<30 || duration>300)throw new Error('invalid_duration');
    return {rtc:{iceServers:config.iceServers,iceTransportPolicy:config.iceTransportPolicy,iceCandidatePoolSize:0},duration};
  }
  async function polling() {
    if(stopped)return;
    try {
      if(active.signaling==='broker') {
      const result=await api('/signal?role='+active.role+'&client='+encodeURIComponent(client));
      if(stopped)return;
      if(!Array.isArray(result.messages) || inbox.length+result.messages.length>64)throw new Error('invalid_signaling_batch');
      inbox.push(...result.messages);
      while(inbox.length && !call.busy && !stopped)await call.receive(inbox.shift());
      }
      if(active.policy && active.role==='A')await call.applyPolicy(await api('/policy'));
    } catch (_) {if(!stopped){call.event(active.signaling==='broker'?'signaling_poll_failure':'policy_poll_failure');status('Local signaling or policy input unavailable. No call was recreated; inspect events and restore the approved input.');}}
    if(!stopped)signalTimer=setTimeout(polling,500);
  }
  async function sampling() {
    if(stopped || sampleBusy)return;
    sampleBusy=true;
    try {
      if(performance.now()-started>=active.duration*1000) {call.event('approved_time_limit_reached');await stop();return;}
      const sample=await call.sample();
      if(sample && !stopped)$('metrics').textContent=JSON.stringify({latest:sample,progress:call.export().progress},null,2);
      showEvent();
    } finally {sampleBusy=false;if(!stopped)sampleTimer=setTimeout(sampling,500);}
  }
  async function stop() {
    stopped=true;inbox.length=0;clearTimeout(signalTimer);clearTimeout(sampleTimer);clearTimeout(limitTimer);
    if(call)call.close();
    if(stream)for(const track of stream.getTracks())track.stop();
    if(active && active.signaling==='broker' && client) {try{await api('/leave','POST',peerData());}catch(_){/* Fixed status below, no raw exception. */}}
    for(const id of ['stop','restart','retry','receive','applyPolicy'])$(id).disabled=true;
    $('export').disabled=!call;
    status('Session ended explicitly or at its approved time limit. Reload for a new, separately approved session. No automatic restart.');
    showEvent();
  }
  $('start').addEventListener('click',async()=>{
    if(!$('approval').checked){status('Approval is required before camera, microphone, ICE or signaling traffic.');return;}
    if(call){status('A session already exists. End it and reload explicitly for another run.');return;}
    let configured;
    try {configured=configuration();}catch(_){status('Invalid private configuration. Check ICE servers, TURN requirement and duration locally.');return;}
    active={role:$('role').value,mode:$('mode').value,signaling:$('signaling').value,policy:$('policy').checked,duration:configured.duration};
    if((active.signaling==='broker' || (active.policy && active.role==='A')) && !token){status('No local access token. Open this server’s private URL; manual signaling without policy reading can run without a token.');return;}
    $('start').disabled=true;$('configuration').disabled=true;$('configuration').hidden=true;
    $('condition').textContent=(active.mode==='baseline' ? 'Ordinary WebRTC baseline' : 'SmartConnect-assisted ICE recovery only')+' · Peer '+active.role+' · Physical interface unverified.';
    try {
      client=crypto.randomUUID();
      if(active.signaling==='broker')await api('/join','POST',peerData());
      stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:360},frameRate:{ideal:15,max:15}},audio:true});
      $('local').srcObject=stream;stopped=false;started=performance.now();
      call=new SmartConnectContinuity.Call({role:active.role,mode:active.mode,pcFactory:config=>new RTCPeerConnection(config),send,
        onEvent:e=>{showEvent();if(e.kind==='recovery_requested')status(active.signaling==='manual' ? 'Recovery offer requested. MANUAL signaling: exchange the NEW offer/answer between laptops; automatic end-to-end recovery is unavailable.' : 'ICE recovery requested. Verify signaling delivery and actual media counters.');if(['signaling_failure','recovery_limit_reached'].includes(e.kind))status('Recovery/signaling needs attention. No new call was created; inspect sanitized events.');},
        onTrack:event=>{if(!remoteStream.getTracks().includes(event.track))remoteStream.addTrack(event.track);$('remote').play().catch(()=>status('Remote playback needs a user gesture: press Play remote audio/video.'));}});
      $('stop').disabled=false;$('receive').disabled=false;$('export').disabled=false;
      $('restart').disabled=active.mode!=='smartconnect' || active.role!=='A';
      $('applyPolicy').disabled=active.signaling!=='manual' || active.role!=='A';
      limitTimer=setTimeout(()=>{if(!stopped){call.event('approved_time_limit_reached');void stop();}},active.duration*1000);
      const ready=await call.start(stream,configured.rtc,{approved:true});
      if(stopped)return;
      status(ready===false ? 'Initial signaling failed. The same peer connection is retained; retry signaling or end explicitly. No continuity is claimed.' : 'Approved peer started. Awaiting signaling/media; no Wi-Fi/cellular path or continuity has been verified.');
      if(active.signaling==='broker' || (active.policy && active.role==='A'))void polling();
      void sampling();showEvent();
    } catch (_) {
      stopped=true;if(call)call.close();if(stream)for(const t of stream.getTracks())t.stop();
      if(active.signaling==='broker'){try{await api('/leave','POST',peerData());}catch(_){}}
      status('Peer could not start. Check browser/macOS media permission, secure context and signaling privately. Reload explicitly to retry.');
    }
  });
  $('stop').addEventListener('click',()=>void stop());
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
    try {await call.applyPolicy(JSON.parse($('policyInput').value));status('Policy input inspected. Fresh changes may request ICE recovery; actual interface remains unverified.');}
    catch(_){status('Invalid policy input. No raw details are displayed.');}
  });
  $('copy').addEventListener('click',async()=>{
    if(!$('outgoing').value){status('No outgoing private signaling is available.');return;}
    try{await navigator.clipboard.writeText($('outgoing').value);status('Private signaling copied. Share only with the approved controlled peer.');}
    catch(_){status('Clipboard unavailable. Select the private text manually.');}
  });
  $('play').addEventListener('click',()=>{$('remote').play().catch(()=>status('No playable remote media yet, or playback permission is unavailable.'));});
  $('export').addEventListener('click',()=>{
    if(!call)return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(call.export(),null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='controlled-call-observations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  addEventListener('pagehide',()=>{stopped=true;if(call)call.close();if(stream)for(const t of stream.getTracks())t.stop();});
})();
