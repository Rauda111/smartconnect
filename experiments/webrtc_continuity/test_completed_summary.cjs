'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const jury=require('./jury.js');
// Synthetic offline fixtures only; never presented as experimental results.
function evidence(){return {role:'A',started_utc:'2026-11-09T12:00:00Z',events:[
 {kind:'policy_recommendation',elapsed_ms:12000,recommended:'wifi',explanation:'Hold: insufficient advantage or candidate breaches observed guardrails',measurements:{wifi:{status:'reachable',latency_ms:20,loss_percent:0,score:.8},cellular:{status:'reachable',latency_ms:42,loss_percent:0,score:.6}}},
 {kind:'recovery_requested',elapsed_ms:15000,cause:'policy_change'},
 {kind:'ice_restart_offer_sent',elapsed_ms:15500,revision:2},
 {kind:'negotiation_completed',elapsed_ms:16000,revision:2},
 {kind:'recovery_requested',elapsed_ms:28000,cause:'ice_failed'},
 {kind:'policy_input_status',elapsed_ms:59000,status:'stale'},
 {kind:'session_explicitly_ended',elapsed_ms:60000}],samples:[{elapsed_ms:59500,candidate_pair_generation:1,local_candidate_type:'host',remote_candidate_type:'host',protocol:'udp',local_network_type:'cellular',connection_state:'connected',ice_state:'connected',frames_decoded:800,video_frames_encoded:850,video_packets_received:900,video_packets_sent:920,audio_packets_received:2000,audio_packets_sent:2010,freezes:0,same_peer_connection:true,same_local_tracks:true,same_observed_receiver_tracks:null}]};}
function view(data){
 const elements=new Map();
 const document={body:{dataset:{juryDemo:'true'},classList:{add(){},remove(){}}},getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,addEventListener(kind,fn){this[kind]=fn;}});return elements.get(id);}};
 const api=jury.create({document,getRole:()=>data?.role || 'A',getEvidence:()=>data,getStreams:()=>[]});
 return {api,el:id=>document.getElementById(id),text:()=>[...elements.values()].map(e=>e.textContent).join('\n')};
}
test('completed view retains last accepted policy after staleness without implying current measurements',()=>{
 const data=evidence(),p=view(data);p.api.finish();
 assert.equal(p.el('completedBanner').hidden,false);assert.equal(p.el('completedDetails').hidden,false);
 assert.equal(p.el('juryRecommendation').textContent,'Wi-Fi');assert.match(p.el('juryRecommendationTitle').textContent,/LAST/);
 assert.match(p.el('juryWifiQuality').textContent,/20.0 ms/);assert.match(p.el('juryCellularQuality').textContent,/42.0 ms/);
 assert.match(p.el('completedTiming').textContent,/60.0 s.*\+12.0 s.*\+59.5 s/);
 assert.match(p.el('completedNetwork').textContent,/cellular.*not interface proof/);
 assert.match(p.el('juryAssociation').textContent,/UNAVAILABLE/);assert.match(p.el('juryVerification').textContent,/no independent/);
 assert.match(p.el('completedCounters').textContent,/Video decoded 800/);assert.match(p.el('completedPreservation').textContent,/remote tracks UNAVAILABLE/);
 assert.match(p.el('completedRecoveryEvents').textContent,/Policy change/);assert.match(p.el('completedRecoveryEvents').textContent,/ICE failure/);
 assert.match(p.el('completedRecovery').textContent,/2 local recovery request/);
 assert.equal(jury.completedSummary(data).physical_handover_verified,false);
});
test('latest missing measurements stay unavailable instead of filling from older successful observations',()=>{
 const data=evidence();data.events.splice(-1,0,{kind:'policy_recommendation',elapsed_ms:59900,recommended:'none',explanation:null,measurements:{wifi:{status:'error',latency_ms:null,loss_percent:null},cellular:{status:'no_reply',latency_ms:null,loss_percent:100}}});
 data.samples.push({elapsed_ms:59950,local_network_type:'unknown',frames_decoded:null,same_local_tracks:null});
 const p=view(data);p.api.finish();assert.equal(p.el('juryWifiAvailability').textContent,'UNAVAILABLE');
 assert.match(p.el('juryWifiQuality').textContent,/RTT UNAVAILABLE.*loss UNAVAILABLE/);
 assert.match(p.el('juryCellularQuality').textContent,/RTT UNAVAILABLE.*100.0%/);
 assert.equal(p.el('juryExplanation').textContent,'UNAVAILABLE');assert.match(p.el('completedCounters').textContent,/decoded UNAVAILABLE/);
 assert.match(p.el('completedPreservation').textContent,/local tracks UNAVAILABLE/);
});
test('summary is frozen despite late callbacks or reopening jury view; next page starts empty',async()=>{
 const data=evidence(),p=view(data);p.api.complete();const before=p.text();
 data.events[0].recommended='cellular';data.samples[0].frames_decoded=999;
 await p.api.update({},{});p.api.event({kind:'recovery_requested',cause:'manual'});p.api.unavailable();p.api.finish();
 assert.equal(p.text(),before);p.el('juryView').click();assert.equal(p.el('juryRecommendation').textContent,'Wi-Fi');
 const fresh=view(null);assert.equal(fresh.el('completedBanner').hidden,true);assert.equal(fresh.el('completedDetails').hidden,true);
});
test('Windows keeps remote Mac decisions separate from its own media metadata',()=>{
 const data=evidence();data.role='B';data.samples[0].local_network_type='ethernet';const p=view(data);p.api.finish();
 assert.equal(p.el('juryRecommendationTitle').textContent,'LAST REMOTE MAC RECOMMENDATION');
 assert.match(p.el('completedNetwork').textContent,/ethernet/);assert.equal(p.el('juryRecommendation').textContent,'Wi-Fi');
});
test('a later signaling answer alone is never labeled a recovery request or successful recovery',()=>{
 const data=evidence();data.role='B';data.events=data.events.filter(e=>!['recovery_requested','ice_restart_offer_sent','negotiation_completed'].includes(e.kind));
 data.events.push({kind:'answer_sent',revision:2,elapsed_ms:2000});const p=view(data);p.api.finish();
 assert.match(p.el('completedRecovery').textContent,/0 local recovery request/);assert.match(p.el('completedRecoveryEvents').textContent,/Signaling answer sent/);
 assert(!p.el('completedRecoveryEvents').textContent.includes('Recovery'));
});
test('no samples or accepted policy do not invent a duration, counters, recommendation or path',()=>{
 const p=view({started_utc:'2026-11-09T12:00:00Z',role:'A',events:[],samples:[]});p.api.finish();
 assert.match(p.el('completedTiming').textContent,/duration UNAVAILABLE/);assert.match(p.el('completedCounters').textContent,/decoded UNAVAILABLE/);
 assert.equal(p.el('juryRecommendation').textContent,'UNAVAILABLE');assert.match(p.el('completedNetwork').textContent,/UNAVAILABLE/);
 assert.equal(jury.completedSummary(null),null);
});
test('historical address correspondence never becomes packet proof or attaches to a different candidate generation',()=>{
 const data=evidence(),a={status:'candidate_interface_match',candidate_pair_generation:1,interface:'en6',network:'cellular'};
 assert.equal(jury.completedSummary(data,a).association.interface,'en6');
 assert.equal(jury.completedSummary(data,a).physical_egress_verified,false);
 data.samples[0].candidate_pair_generation=2;assert.equal(jury.completedSummary(data,a).association,null);
});
