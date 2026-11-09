/* Dedicated authenticated navigation response. No media, signaling or probes. */
(function(){
  'use strict';
  const node=document.getElementById('privateLaunch');
  try{
    const data=JSON.parse(node.textContent);node.remove();
    if(!/^[A-Za-z0-9_-]{40,256}$/.test(data.reader)||!['A','B'].includes(data.role))throw Error();
    sessionStorage.setItem('smartconnect.reader',data.reader);
    sessionStorage.setItem('smartconnect.settings',JSON.stringify({role:data.role,mode:'smartconnect',signaling:'broker',policy:data.role==='A',duration:300,ice:'{"iceServers":[],"iceTransportPolicy":"all"}'}));
    location.replace('/');
  }catch(_){if(node?.isConnected)node.remove();document.getElementById('launchStatus').textContent='Private tab storage is unavailable. Allow site storage in this browser, then reopen the private launcher. No media started.';}
})();
