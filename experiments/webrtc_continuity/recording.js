/* Opt-in local tab recording. No capture, permission prompt, or timer on import. */
(function(root){
  'use strict';
  const enc=new TextEncoder();
  function crc32(bytes){let c=0xffffffff;for(const b of bytes){c^=b;for(let i=0;i<8;i++)c=(c>>>1)^((c&1)?0xedb88320:0);}return(c^0xffffffff)>>>0;}
  async function zip(entries){
    const parts=[],central=[];let offset=0,size=0;
    for(const entry of entries){
      if(!/^[a-zA-Z0-9_.-]+$/.test(entry.name))throw new Error('invalid_archive_name');
      const name=enc.encode(entry.name),bytes=new Uint8Array(await entry.blob.arrayBuffer()),crc=crc32(bytes);
      const local=new Uint8Array(30+name.length),v=new DataView(local.buffer);
      v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint32(14,crc,true);v.setUint32(18,bytes.length,true);v.setUint32(22,bytes.length,true);v.setUint16(26,name.length,true);local.set(name,30);
      const directory=new Uint8Array(46+name.length),d=new DataView(directory.buffer);
      d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint32(16,crc,true);d.setUint32(20,bytes.length,true);d.setUint32(24,bytes.length,true);d.setUint16(28,name.length,true);d.setUint32(42,offset,true);directory.set(name,46);
      parts.push(local,bytes);central.push(directory);offset+=local.length+bytes.length;size+=directory.length;
    }
    const end=new Uint8Array(22),v=new DataView(end.buffer);v.setUint32(0,0x06054b50,true);v.setUint16(8,entries.length,true);v.setUint16(10,entries.length,true);v.setUint32(12,size,true);v.setUint32(16,offset,true);
    return new Blob([...parts,...central,end],{type:'application/zip'});
  }
  function correctSurface(track,handle){return track?.getSettings?.().displaySurface==='browser' && track.getCaptureHandle?.()?.handle===handle;}
  function create({document:doc,getRole,getEvidence,getStreams,enter,announce}){
    const $=id=>doc.getElementById(id);let media=null,display=null,context=null,destination=null,preview=null,token=null,startUTC=null,startMono=0,timer=null,limit=null,finishing=null,archive=null,fallback=null,bytes=0,used=false,stopping=false;
    const chunks=[],stills=[],marks=[],sources=new Map();let pendingStills=0;
    const active=()=>!!media && media.state==='recording';
    function download(blob,name){const url=URL.createObjectURL(blob),a=doc.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
    function lock(value){doc.body.classList.toggle('capture-locked',value);for(const id of ['juryBack','juryInventory','recordStart'])$(id).disabled=value;}
    function attachAudio(){
      if(!context || !destination)return;
      for(const stream of getStreams())for(const track of stream?.getAudioTracks?.()||[]){
        if(sources.has(track))continue;
        const source=context.createMediaStreamSource(new MediaStream([track])),gain=context.createGain();gain.gain.value=.45;source.connect(gain).connect(destination);sources.set(track,source);
      }
    }
    async function mark(reason='operator-still'){
      if(!active() || !preview || stills.length+pendingStills>=16)return;
      const safe=['connected','recovery-request','operator-still','recording-start'].includes(reason)?reason:'operator-still';
      const elapsed=Math.max(0,performance.now()-startMono);marks.push({reason:safe,recording_elapsed_ms:elapsed,captured_at:new Date().toISOString()});
      if(!preview.videoWidth || !preview.videoHeight)return;
      pendingStills++;
      try{const canvas=doc.createElement('canvas');canvas.width=preview.videoWidth;canvas.height=preview.videoHeight;canvas.getContext('2d').drawImage(preview,0,0);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(blob)stills.push({name:'still-'+String(stills.length+1).padStart(2,'0')+'-'+safe+'.png',blob});}catch(_){}finally{pendingStills--;}
    }
    async function start(){
      if(used || active())return;
      if(!$('approval').checked || !$('recordApproval').checked){announce('Separate media and screen/audio recording approval must be checked first. No capture started.');return;}
      if(!root.navigator?.mediaDevices?.getDisplayMedia || !root.navigator.mediaDevices.setCaptureHandleConfig || !root.MediaRecorder || !root.AudioContext){announce('This browser cannot verify a safe tab recording. Use current Chrome or Edge; recording has not started.');return;}
      try{
        token=crypto.randomUUID();root.navigator.mediaDevices.setCaptureHandleConfig({handle:token,exposeOrigin:false,permittedOrigins:[location.origin]});
        enter();lock(true);
        // Audio comes only from this call's approved local/remote tracks, never system audio.
        display=await root.navigator.mediaDevices.getDisplayMedia({video:{displaySurface:'browser',frameRate:{ideal:15,max:15}},audio:false,preferCurrentTab:true,selfBrowserSurface:'include',monitorTypeSurfaces:'exclude',surfaceSwitching:'exclude',systemAudio:'exclude'});
        const track=display.getVideoTracks()[0];
        if(!correctSurface(track,token))throw new Error('wrong_surface');
        context=new root.AudioContext();await context.resume();destination=context.createMediaStreamDestination();attachAudio();
        const types=['video/webm;codecs=vp8,opus','video/webm'];const mime=types.find(t=>root.MediaRecorder.isTypeSupported(t));if(!mime)throw new Error('format_unavailable');
        media=new root.MediaRecorder(new MediaStream([track,...destination.stream.getAudioTracks()]),{mimeType:mime,videoBitsPerSecond:2500000,audioBitsPerSecond:128000});
        media.ondataavailable=e=>{if(e.data?.size){chunks.push(e.data);bytes+=e.data.size;if(bytes>220*1024*1024)void finish('size_limit');}};
        media.onerror=()=>void finish('recorder_error');
        preview=doc.createElement('video');preview.muted=true;preview.srcObject=display;await preview.play();
        startUTC=new Date().toISOString();startMono=performance.now();stopping=false;media.start(1000);used=true;
        $('recordStop').disabled=false;$('recordStill').disabled=false;putStatus();
        timer=setInterval(putStatus,250);limit=setTimeout(()=>void finish('420_second_limit'),420000);
        track.addEventListener('ended',()=>void finish('browser_share_ended'));
        track.addEventListener('capturehandlechange',()=>{if(!correctSurface(track,token))void finish('capture_surface_changed');});
        announce('Recording this SmartConnect tab only. Start Windows B, then Mac A. Setup/addresses stay hidden. Screen/audio recording is separate from call media.');
        void mark('recording-start');
      }catch(_){cleanup();lock(false);announce('Recording did not start: permission, current-tab verification or format unavailable. No desktop/window recording is retained.');}
    }
    function putStatus(){const seconds=Math.floor((performance.now()-startMono)/1000);$('recordState').textContent='RECORDING · '+String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')+' · '+new Date().toISOString().slice(11,19)+' UTC';}
    function cleanup(){clearInterval(timer);clearTimeout(limit);for(const t of display?.getTracks?.()||[])t.stop();for(const source of sources.values())try{source.disconnect();}catch(_){}sources.clear();if(context)void context.close().catch(()=>{});context=null;display=null;preview=null;}
    function finish(reason='session_ended'){
      if(!used)return Promise.resolve(null);if(finishing)return finishing;
      finishing=(async()=>{
        stopping=true;clearInterval(timer);clearTimeout(limit);$('recordState').textContent='Saving local recording bundle…';
        if(media && media.state!=='inactive')await new Promise(resolve=>{media.addEventListener('stop',resolve,{once:true});media.stop();});
        const endUTC=new Date().toISOString(),elapsed=performance.now()-startMono;
        cleanup();$('recordStop').disabled=true;$('recordStill').disabled=true;
        const metadata={schema:1,role:getRole(),recording_started_utc:startUTC,recording_ended_utc:endUTC,recording_duration_ms:elapsed,stop_reason:reason,surface:'verified_current_browser_tab',audio_source:'approved_local_and_remote_call_tracks_mixed',raw_recording_unedited:true,screen_clock_is_local_not_cross_device_synchronized:true,markers:marks,physical_handover_verified:false};
        const observations=await getEvidence();fallback=new Blob(chunks,{type:media.mimeType});
        const entries=[{name:'full-unedited-'+getRole()+'.webm',blob:fallback},{name:'recording-manifest.json',blob:new Blob([JSON.stringify(metadata,null,2)],{type:'application/json'})},{name:'sanitized-observations.json',blob:new Blob([JSON.stringify(observations,null,2)],{type:'application/json'})},...stills];
        try{archive=await zip(entries);$('recordSave').disabled=false;download(archive,'SmartConnect-recording-'+getRole()+'-'+startUTC.replace(/[^0-9TZ-]/g,'-')+'.zip');$('recordState').textContent='DOWNLOAD REQUESTED · local recording + sanitized evidence';announce('Bundle download requested. If blocked, click Download recording bundle. Review the complete footage before sharing.');}
        catch(_){$('recordSave').disabled=false;$('recordSave').textContent='Download unedited WebM';$('recordState').textContent='ZIP unavailable · save raw recording';announce('Click Download unedited WebM and Download sanitized observations before closing this page.');}
        // Keep private configuration hidden for the remainder of this recorded session.
        return archive;
      })();return finishing;
    }
    function abort(){if(active())void finish('page_suspended');else cleanup();}
    $('recordStart').addEventListener('click',start);$('recordStop').addEventListener('click',()=>void finish('operator_stop'));
    $('recordStill').addEventListener('click',()=>void mark());$('recordSave').addEventListener('click',()=>{if(archive)download(archive,'SmartConnect-recording-'+getRole()+'-'+startUTC.replace(/[^0-9TZ-]/g,'-')+'.zip');else if(fallback)download(fallback,'SmartConnect-raw-'+getRole()+'.webm');});
    return {get active(){return active();},get hasRecording(){return used;},attachAudio,mark,finish,abort};
  }
  const api={crc32,zip,correctSurface,create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SmartConnectRecording=api;
})(typeof globalThis!=='undefined'?globalThis:this);
