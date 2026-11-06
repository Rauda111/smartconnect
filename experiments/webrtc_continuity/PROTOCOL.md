# Safe validation protocol — pending explicit approval

## 0. Approve exact scope before any traffic

No step below has been run. Agree the two controlled clients, locations, operating
systems, browser versions, camera/microphone consent, headphones, destinations,
ICE/STUN/TURN configuration, signaling mechanism, trial count, duration and data
budget first. Do not include unrelated applications. Each call defaults to a
120-second maximum; media byte volume is browser-controlled. Approve any existing
Video collector separately, including its ICMP/HTTPS destinations and counts.
Capture requires separate explicit approval and privacy/storage scope.

Never change default routes, DNS, firewall, service order, VPN profiles, Wi-Fi
settings, interface state, other applications or iPhone settings under this plan.
If controlled loss of Wi-Fi coverage or any configuration change is desired,
obtain approval for that exact action first. Use safe indoor conditions; do not
improvise movement or infrastructure impairment during judging.

## 1. Functional same-Mac smoke (not a path/continuity experiment)

After approval, start the loopback server with its approval flag. Use two local
browser clients, no external ICE servers initially, one A and one B, same
condition. Start real camera/audio on both, allow permissions, press Play remote
media when required and use headphones. Verify recognizable motion/audio,
increasing received packets/decoded frames and the same connection/track objects.
A same-Mac call can be entirely loopback; label it as such. No en0/en6 claim.

Test initial signaling failure and explicit retry, then an assisted manual ICE
restart. Confirm that no new RTCPeerConnection or camera tracks are created and
that both endpoints complete offer/answer on the existing session. If media never
arrives, treat the trial as failed; do not show empty/fixture counters as success.

## 2. Establish the real two-machine topology

Use the MacBook as mobile peer A and a separately controlled, stationary remote
peer B reachable through both approved Wi-Fi and cellular-backed paths. Confirm
the iPhone tether is usable; USB presence alone does not prove carrier radio
access. Use only approved STUN/TURN servers with short-lived credentials when
required by NAT/firewalls. Record which transport/candidate type actually works.

The included manual signaling can establish/recover the call privately on separate
machines, but operator exchange time is part of recovery delay. It cannot support
a claim of automatic seamless recovery. Before an automatic cross-network trial,
provide and review resilient authenticated HTTPS/WSS signaling reachable through
both paths, then adapt the injected send/receive interface without changing the
call lifecycle. Do not expose the included loopback broker as a public service.
Until that infrastructure exists, automatic remote continuity is blocked.

## 3. Verify intended paths independently, with separate approval

Agree an owner-only capture/correlation plan limited to this call on en0 and en6,
plus remote observations if needed. Avoid collecting unrelated traffic. Correlate
selected transport tuples/packet timing privately with the same ongoing session.
A change in ICE-pair generation, a public-IP lookup or a recommendation label is
not physical path verification. If raw correlation is unavailable, report path
as **unverified**, even if media resumes.

Do not commit/upload packet captures, SDP, candidates, credentials, private tuples
or raw browser-internals dumps. Use an owner-only directory outside the repo and
prepare a separately reviewed sanitized summary. No capture command is authorized
or executed by this document.

## 4. Paired baseline and assisted trials

Keep browser versions, media constraints, peer location, ICE servers, signaling,
call duration and interference/movement conditions as identical as practical.
Randomize or alternate baseline/assisted order. Pre-approve at least three repeats
per condition if bandwidth/time permit; report all failures and censored trials.
Do not compare different endpoints, codecs or signaling procedures as if only the
policy differed. The two conditions use the same genuine call implementation:

- Baseline: ordinary browser WebRTC behavior; no application-requested ICE restart.
- Assisted: fresh unchanged Video-policy recommendations may request ICE recovery;
  failed ICE may also request it. Log which cause actually triggered intervention.

Use an independently approved existing collector only when evaluating the policy
bridge. Record its observation cadence. Current ICMP windows and hold/dwell may
lag a media problem; distinguish this from negotiation and transport delays.
There is no guaranteed advantage over the ordinary browser baseline.

Approved scenarios: stable Wi-Fi, loss/recovery of Wi-Fi coverage with cellular
available, cellular unavailable too, both becoming usable again, rapid but safe
fluctuations, signaling outage and TURN failure where that infrastructure exists.
Do not manufacture successful outcomes, silently replace the peer connection,
replace camera media with a success clip or exclude failed attempts.

## 5. Measure and report actual observations

Sample the receiver's getStats counters every approximately 500 ms. Preserve
monotonic local elapsed times and UTC start anchors; record timer delays and
clock synchronization uncertainty before cross-device alignment. Report:

- Peer-connection and original sender/receiver-track identity preservation.
- Connection/ICE-state transitions, signaling failures, ICE-restart offers and
  completed renegotiations; baseline spontaneous recovery separately.
- Last progressing receiver video-decode counter → next progressing observation;
  and audio received-packet counter gaps separately. The 1000 ms marker is a
  detection/instrumentation threshold. Durations include polling uncertainty,
  not exact radio handover or guaranteed perceptual interruption.
- Open intervals at end, missing statistics, counter resets/stream changes and
  background-tab throttling as censored/unknown, never zero interruption.
- RTP packet loss, frames decoded/dropped/freeze counters, encoded frames, audio
  samples/concealed samples and payload bytes where supported. Packet loss is not
  identical to missing video frames or intelligible audio loss. Missing fields
  remain unavailable. Concealment may keep audio samples progressing during loss.

For exact frame delivery and perceptual audio interruption, obtain separate consent
for sender/receiver reference recording or a synchronized frame/audio marker
source. Compare like-for-like intervals and account for encoder changes, buffering,
clock skew and dropped captures. Browser packet/frame counters alone cannot prove
"no noticeable disconnection." Collect observer reports separately from counters.

## 6. Promotion gate for EDGE

Keep this as research until a real remote call is repeatably established, actual
en0→en6 path use is independently verified, the same application session/tracks
survive, interruption/quality is quantified under approved conditions, and paired
baseline results support the exact claim. State failures and setup limits.
Do not infer verified 5G, system-wide steering, migration of Zoom/Teams/FaceTime,
seamlessness or universal superiority. If any gate fails, use the frozen, verified
new-HTTPS-request dashboard for EDGE and describe continuity as future work.
