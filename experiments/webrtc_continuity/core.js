/* Transport-independent controlled-call logic. No I/O occurs on import. */
(function (root) {
  'use strict';
  const MODES = ['baseline', 'smartconnect'];
  const STATES = ['new', 'connecting', 'connected', 'disconnected', 'failed', 'closed', 'checking', 'completed'];
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const sum = (rows, key) => rows.length && rows.every(r => finite(r[key])) ? rows.reduce((n,r) => n+r[key],0) : null;
  const enumValue = (x, allowed) => allowed.includes(x) ? x : 'unknown';

  class Progress {
    constructor(thresholdMs = 1000) { this.thresholdMs=thresholdMs; this.values=new Map(); this.gaps=[]; }
    update(kind, value, now) {
      if (!finite(value)) { this.finish(kind, now, true); this.values.delete(kind); return; }
      const previous=this.values.get(kind);
      if (!previous || value<previous.value) {
        this.finish(kind, now, true);
        this.values.set(kind,{value,lastProgress:now,started:value>0,open:false});
        return;
      }
      if (value>previous.value) {
        if (previous.open) this.gaps.push({kind,last_progress_to_recovery_ms:now-previous.lastProgress,right_censored:false});
        this.values.set(kind,{value,lastProgress:now,started:true,open:false});
      } else if (previous.started && now-previous.lastProgress>=this.thresholdMs) previous.open=true;
    }
    finish(kind, now, censored) {
      const p=this.values.get(kind);
      if (p && p.started && (p.open || now-p.lastProgress>=this.thresholdMs)) {
        this.gaps.push({kind,last_progress_to_recovery_ms:now-p.lastProgress,right_censored:censored});
        p.open=false; p.started=false;
      }
    }
    close(now) { for (const kind of this.values.keys()) this.finish(kind,now,true); }
    snapshot(now) {
      return {threshold_ms:this.thresholdMs,closed_gaps:this.gaps.map(x=>({...x})),
        open_gaps:[...this.values].filter(([,p])=>p.open).map(([kind,p])=>({kind,elapsed_since_last_progress_ms:now-p.lastProgress,right_censored:true}))};
    }
  }

  class Metrics {
    constructor() { this.pair=null; this.generation=0; this.streams=null; this.progress=new Progress(); }
    ingest(report, now) {
      const rows=[...report.values()];
      const inbound=rows.filter(r=>r.type==='inbound-rtp' && !r.isRemote);
      const video=inbound.filter(r=>(r.kind || r.mediaType)==='video');
      const audio=inbound.filter(r=>(r.kind || r.mediaType)==='audio');
      const identity=inbound.map(r=>r.id).sort().join('|'); // private, never exported
      if (this.streams!==null && identity!==this.streams) {
        this.progress.close(now); this.progress.values.clear();
      }
      this.streams=identity;
      const transport=rows.find(r=>r.type==='transport' && r.selectedCandidatePairId);
      const pair=transport ? report.get(transport.selectedCandidatePairId) : null;
      if (pair && pair.id!==this.pair) { this.pair=pair.id; this.generation++; }
      const local=pair ? report.get(pair.localCandidateId) : null;
      const remote=pair ? report.get(pair.remoteCandidateId) : null;
      const outbound=rows.filter(r=>r.type==='outbound-rtp' && !r.isRemote);
      const v=sum(video,'framesDecoded'), a=sum(audio,'packetsReceived');
      this.progress.update('video_decoded_frame_progress',v,now);
      this.progress.update('audio_received_packet_progress',a,now);
      return {
        elapsed_ms:now, candidate_pair_generation:pair ? this.generation : null,
        local_candidate_type:local ? enumValue(local.candidateType,['host','srflx','prflx','relay']) : 'unknown',
        remote_candidate_type:remote ? enumValue(remote.candidateType,['host','srflx','prflx','relay']) : 'unknown',
        protocol:local ? enumValue(local.protocol,['udp','tcp']) : 'unknown',
        pair_rtt_seconds:pair && finite(pair.currentRoundTripTime) ? pair.currentRoundTripTime : null,
        video_packets_received:sum(video,'packetsReceived'), video_packets_lost:sum(video,'packetsLost'),
        frames_decoded:v, frames_dropped:sum(video,'framesDropped'), freezes:sum(video,'freezeCount'),
        freeze_duration_seconds:sum(video,'totalFreezesDuration'),
        audio_packets_received:a, audio_packets_lost:sum(audio,'packetsLost'),
        audio_samples_received:sum(audio,'totalSamplesReceived'), concealed_audio_samples:sum(audio,'concealedSamples'),
        rtp_payload_bytes_sent:sum(outbound,'bytesSent'),
        video_packets_sent:sum(outbound.filter(r=>(r.kind || r.mediaType)==='video'),'packetsSent'),
        audio_packets_sent:sum(outbound.filter(r=>(r.kind || r.mediaType)==='audio'),'packetsSent'),
        video_frames_encoded:sum(rows.filter(r=>r.type==='outbound-rtp' && (r.kind || r.mediaType)==='video'),'framesEncoded'),
        physical_interface:'unverified', physical_egress_verified:false
      };
    }
  }

  function waitForIce(pc, timeoutMs=15000) {
    if (pc.iceGatheringState==='complete') return Promise.resolve();
    return new Promise((resolve,reject)=>{
      const finish=()=>{clearTimeout(timer);pc.removeEventListener('icegatheringstatechange',check);pc.removeEventListener('connectionstatechange',closed);};
      const check=()=>{if(pc.iceGatheringState==='complete'){finish();resolve();}};
      const closed=()=>{if(pc.connectionState==='closed'){finish();reject(new Error('gather_closed'));}};
      const timer=setTimeout(()=>{finish();reject(new Error('gather_timeout'));},timeoutMs);
      pc.addEventListener('icegatheringstatechange',check);pc.addEventListener('connectionstatechange',closed);check();
    });
  }

  class Call {
    constructor({role,mode,pcFactory,send,clock=()=>performance.now(),gather=waitForIce,onEvent=()=>{},onTrack=()=>{}}) {
      if (!['A','B'].includes(role) || !MODES.includes(mode)) throw new Error('configuration_invalid');
      Object.assign(this,{role,mode,pcFactory,send,clock,gather,onEvent,onTrack});
      this.pc=null;this.stream=null;this.originalTracks=[];this.events=[];this.samples=[];
      this.metrics=new Metrics();this.revision=0;this.remoteRevision=0;this.busy=false;
      this.closed=false;this.origin=0;this.restarts=0;this.lastRestart=-Infinity;
      this.pending=null;this.lastSignal=null;this.lastSignalAttempt=-Infinity;this.recommended=null;this.policyWindow=0;
      this.remoteTracks=[];this.remotePreserved=true;
      this.lastVideoFrames=null;this.lastVideoProgress=null;this.stallReported=false;this.disconnectedSince=null;
    }
    event(kind,fields={}) { const e={elapsed_ms:this.clock()-this.origin,kind,...fields};this.events.push(e);this.onEvent(e); }
    async start(stream,configuration,{approved=false}={}) {
      if (!approved) throw new Error('approval_required');
      if (this.pc || this.closed) throw new Error('explicit_new_session_required');
      this.origin=this.clock();this.startedUTC=new Date().toISOString();this.stream=stream;this.originalTracks=[...stream.getTracks()];
      if (!this.originalTracks.length) throw new Error('media_required');
      this.pc=this.pcFactory(configuration);this.originalPC=this.pc;
      for (const track of this.originalTracks) {
        this.pc.addTrack(track,stream);
        if(typeof track.addEventListener==='function')for(const kind of ['ended','mute','unmute'])track.addEventListener(kind,()=>this.event('local_track_'+kind,{media_kind:enumValue(track.kind,['audio','video'])}));
      }
      this.pc.ontrack=event=>{
        if (this.remoteTracks.length && !this.remoteTracks.includes(event.track)) this.event('remote_track_observed');
        if (!this.remoteTracks.includes(event.track)) this.remoteTracks.push(event.track);
        this.onTrack(event);
      };
      this.pc.onconnectionstatechange=()=>this.event('connection_state',{state:enumValue(this.pc.connectionState,STATES)});
      this.pc.oniceconnectionstatechange=()=>{
        this.event('ice_state',{state:enumValue(this.pc.iceConnectionState,STATES)});
        if(this.pc.iceConnectionState==='disconnected' && this.disconnectedSince===null)this.disconnectedSince=this.clock();
        if(['connected','completed'].includes(this.pc.iceConnectionState))this.disconnectedSince=null;
        if(this.pc.iceConnectionState==='failed') void this.requestRestart('ice_failed');
      };
      this.event('session_started',{mode:this.mode,role:this.role});
      if(this.role==='A') return this.offer(false);
      return true;
    }
    async offer(restart) {
      if(this.busy || this.closed || !this.pc || this.pc.signalingState!=='stable') return false;
      this.busy=true;
      try {
        if(restart) this.pc.restartIce();
        const offer=await this.pc.createOffer(restart ? {iceRestart:true} : {});
        if(this.closed) return false;
        await this.pc.setLocalDescription(offer);await this.gather(this.pc);
        if(this.closed) return false;
        this.revision++;
        this.lastSignal={mode:this.mode,revision:this.revision,description:{type:'offer',sdp:this.pc.localDescription.sdp}};
        this.lastSignalAttempt=this.clock();
        await this.send(this.lastSignal);
        this.event(restart?'ice_restart_offer_sent':'initial_offer_sent',{revision:this.revision});
        return true;
      } catch (_) {this.event('signaling_failure',{stage:'offer'});return false;}
      finally {this.busy=false;}
    }
    async receive(message) {
      const d=message && message.description;
      if(!d || !['offer','answer'].includes(d.type) || typeof d.sdp!=='string' || !d.sdp.startsWith('v=0') || d.sdp.length>131072 || message.mode!==this.mode || !Number.isInteger(message.revision) || message.revision<1) {
        this.event('signaling_rejected',{stage:'validation'});return false;
      }
      if(!this.pc || this.closed || this.busy) {this.event('signaling_rejected',{stage:'not_ready'});return false;}
      if(d.type==='offer' && (this.role!=='B' || message.revision<=this.remoteRevision || this.pc.signalingState!=='stable')) return false;
      if(d.type==='answer' && (this.role!=='A' || message.revision!==this.revision || this.pc.signalingState!=='have-local-offer')) return false;
      this.busy=true;
      try {
        await this.pc.setRemoteDescription(d);
        if(d.type==='offer') {
          const answer=await this.pc.createAnswer();await this.pc.setLocalDescription(answer);await this.gather(this.pc);
          if(this.closed) return false;
          this.remoteRevision=message.revision;
          this.lastSignal={mode:this.mode,revision:message.revision,description:{type:'answer',sdp:this.pc.localDescription.sdp}};
          await this.send(this.lastSignal);
        }
        this.event('negotiation_completed',{revision:message.revision});return true;
      } catch (_) {this.event('signaling_failure',{stage:'receive'});return false;}
      finally {this.busy=false;}
    }
    async retrySignal() {
      if(!this.lastSignal || this.closed) return false;
      this.lastSignalAttempt=this.clock();
      try {await this.send(this.lastSignal);this.event('signaling_retried');return true;}
      catch (_) {this.event('signaling_failure',{stage:'retry'});return false;}
    }
    async requestRestart(cause) {
      if(!['policy_change','ice_failed','ice_disconnected','video_stalled','manual'].includes(cause)) return false;
      if(this.mode!=='smartconnect' || this.role!=='A' || !this.pc || this.closed) return false;
      if(this.restarts>=3) {this.pending=null;this.event('recovery_limit_reached');return false;}
      if(this.busy || this.pc.signalingState!=='stable' || this.clock()-this.lastRestart<10000) {
        this.pending=cause;return false;
      }
      this.pending=null;this.lastRestart=this.clock();this.restarts++;
      this.event('recovery_requested',{cause,attempt:this.restarts,interface_control:'not_available'});
      return this.offer(true);
    }
    async applyPolicy(p) {
      let inputStatus=p ? enumValue(p.status,['fresh','stale','unavailable','not_configured','wrong_profile','finished']) : 'unavailable';
      if(inputStatus==='fresh' && p.application!=='video_call')inputStatus='wrong_profile';
      if(inputStatus==='fresh' && (!finite(p.age_seconds) || p.age_seconds<0 || p.age_seconds>45))inputStatus='stale';
      if(inputStatus==='fresh' && (!['wifi','cellular','none'].includes(p.recommended) || !Number.isInteger(p.window) || p.window<1))inputStatus='unavailable';
      if(inputStatus!==this.policyStatus){this.policyStatus=inputStatus;this.event('policy_input_status',{status:inputStatus});}
      if(inputStatus!=='fresh') {
        this.policyValidUntil=0;if(this.pending==='policy_change')this.pending=null;return false;
      }
      if(p.window<=this.policyWindow) return false;
      this.policyWindow=p.window;this.policyValidUntil=this.clock()+(45-p.age_seconds)*1000;
      const previous=this.recommended;this.recommended=p.recommended;
      this.event('policy_recommendation',{recommended:p.recommended,window:p.window});
      if(p.recommended==='none') {if(this.pending==='policy_change')this.pending=null;return false;}
      if(previous && previous!==p.recommended) return this.requestRestart('policy_change');
      return false;
    }
    async sample() {
      if(!this.pc || this.closed) return null;
      try {
        if(this.policyStatus==='fresh' && this.clock()>this.policyValidUntil){this.policyStatus='stale';this.event('policy_input_status',{status:'stale'});}
        if(this.pending==='policy_change' && this.clock()>this.policyValidUntil)this.pending=null;
        if(this.pending) await this.requestRestart(this.pending);
        if(this.mode==='smartconnect' && this.role==='A' &&
           this.pc.signalingState==='have-local-offer' &&
           this.lastSignal && this.lastSignal.description.type==='offer' &&
           this.clock()-this.lastSignalAttempt>=3000)
          await this.retrySignal();
        const report=await this.pc.getStats();
        if(this.closed)return null;
        const now=this.clock();
        const sample=this.metrics.ingest(report,now-this.origin);
        // A stalled frame counter is only actionable after real remote video has progressed.
        // This is a recovery trigger, NOT proof of an interface switch or handover latency.
        if(finite(sample.frames_decoded) && sample.frames_decoded>0) {
          if(this.lastVideoFrames===null || sample.frames_decoded>this.lastVideoFrames || sample.frames_decoded<this.lastVideoFrames) {
            this.lastVideoProgress=now;this.stallReported=false;
          } else if(this.mode==='smartconnect' && this.role==='A' && !this.stallReported && this.lastVideoProgress!==null && now-this.lastVideoProgress>=3000 && this.pc.signalingState==='stable') {
            this.stallReported=true;this.event('video_stall_observed',{threshold_ms:3000});
            await this.requestRestart('video_stalled');
          }
          this.lastVideoFrames=sample.frames_decoded;
        } else {this.lastVideoFrames=null;this.lastVideoProgress=null;this.stallReported=false;}
        if(this.disconnectedSince!==null && now-this.disconnectedSince>=2500 && this.mode==='smartconnect' && this.role==='A') {
          this.disconnectedSince=null;await this.requestRestart('ice_disconnected');
        }
        const senders=this.pc.getSenders();
        const receivers=this.pc.getReceivers().map(r=>r.track).filter(Boolean);
        // Track objects, not IDs, establish identity; nothing private is exported.
        if(!this.receiverBaseline && receivers.length)this.receiverBaseline=[...receivers];
        if(this.receiverBaseline && !this.receiverBaseline.every(t=>receivers.includes(t)))this.remotePreserved=false;
        Object.assign(sample,{same_peer_connection:this.pc===this.originalPC,
          same_local_tracks:this.originalTracks.every(t=>senders.some(s=>s.track===t) && this.stream.getTracks().includes(t)),
          same_observed_receiver_tracks:this.receiverBaseline ? this.remotePreserved : null,
          policy_input_status:this.policyStatus || 'not_configured',
          recommended_interface:({wifi:'en0',cellular:'en6',none:'none'})[this.recommended] || 'unknown',
          connection_state:enumValue(this.pc.connectionState,STATES),ice_state:enumValue(this.pc.iceConnectionState,STATES)});
        this.samples.push(sample);if(this.samples.length>7200)this.samples.shift();return sample;
      } catch (_) {this.event('stats_unavailable');return null;}
    }
    close() {
      if(this.closed)return;
      this.closed=true;this.pending=null;
      this.metrics.progress.close(this.clock()-this.origin);
      if(this.pc)this.pc.close();
      if(this.stream)for(const t of this.stream.getTracks())t.stop();
      this.event('session_explicitly_ended');
    }
    export() {
      return {schema:1,mode:this.mode,role:this.role,started_utc:this.startedUTC || null,experimental:true,physical_egress_verified:false,
        interface_control:'unavailable_in_browser',sample_resolution_ms:500,
        gap_definition:'Intervals since last observed counter progress; not handover latency or exact frame/audio loss.',
        events:this.events.map(x=>({...x})),samples:this.samples.map(x=>({...x})),
        progress:this.metrics.progress.snapshot(this.clock()-this.origin)};
    }
  }
  const api={Call,Metrics,Progress,waitForIce};
  if(typeof module!=='undefined' && module.exports)module.exports=api;
  else root.SmartConnectContinuity=api;
})(typeof globalThis!=='undefined'?globalThis:this);
