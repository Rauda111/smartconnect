# SmartConnect controlled-call continuity research

**Isolated prototype, not validated handover. Not recommended as an EDGE Demo Day
continuity claim yet.** Read FEASIBILITY.md and PROTOCOL.md first. The frozen
competition dashboard/engine/evidence are untouched. No live call has been run by
this implementation task; mocks are not experimental results.

## Implemented versus unproven

Implemented: real browser camera/microphone tracks, RTCPeerConnection offer/answer,
DTLS/SRTP media transport APIs, full-SDP ICE renegotiation on the same connection,
local automatic signaling, optional private manual signaling for separate
machines, unchanged Video-policy recommendation input, an ordinary-WebRTC
baseline, sanitized counters/events and bounded recovery attempts. The browser
code does not play a prerecorded success clip or generate fake call counters.

Unproven: an actual successful media exchange in this environment; en0/en6 media
path selection; recovery across real Wi-Fi loss; interruption duration; perceptual
audio/video continuity; TURN behavior; remote signaling persistence; benefits
over ordinary WebRTC. Browser JavaScript cannot bind to the named interfaces.
A policy change requests ICE recovery only; it never sets a route or reports that
an interface was physically selected. Same-Mac media can stay local/loopback.

## Setup and approval gates

No dependencies need installing for the server. It uses Python's standard
library; the clients need a browser with getUserMedia, RTCPeerConnection and
restartIce. Camera/microphone permission, a secure local origin, and potentially
macOS local-network permission must be approved by the operator. Never bypass
privacy prompts or certificate warnings.

The following is a **future operator command, NOT executed here**. Run only after
explicit approval for the local listener and controlled experiment:

```sh
cd /Users/raudaalshaeili/smartconnect
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.server --approved-local-traffic
```

The server binds **127.0.0.1:8766 only** and prints private, temporary client A/B
URLs. The token is in a URL fragment, cleared by the client after reading, and is
not logged. Do not project or publish these control URLs. Open both URLs in two
controlled clients. Choose the same baseline/assisted condition on both, confirm
the approved destinations/duration and press Start on each. Start is the only
entry into camera capture, peer creation, ICE gathering and signaling polling.
Opening the page is inert. Serving the page itself is local traffic and is gated
at the CLI. Runtime acknowledgements do not authorize an agent to run experiments
without the user's explicit prior approval.

Default ICE servers are empty: no public STUN/TURN service is contacted by this
application automatically. Host candidate gathering/connectivity checks can
still produce traffic after Start. Default approved call duration is 120 seconds;
operator may set 30–300. An independent timer ends the session and stops its tracks at the time limit
(subject to browser scheduling), recording the event. No call is restarted silently. The media
bitrate is browser-controlled, not a guaranteed byte budget; approve cellular
usage before starting. RTP payload byte counters are recorded where supported.

## Two-machine option and signaling limitation

Run a separately approved local server on each controlled computer, use A on one
and B on the other, and choose **Private manual SDP exchange** on both. Supply
only approved STUN/TURN configuration when needed. Exchange full outgoing JSON
messages through a private approved channel: A offer → B, then B answer → A.
These messages contain ICE credentials/addresses; never put them in source
control, public evidence, the jury dashboard or sanitized observations.

ICE recovery produces another A offer and B answer on the same peer connections.
Manual exchange is functional signaling, **not automatic or seamless recovery**.
The loopback broker is intentionally not exposed to the LAN/Internet. Automatic
remote recovery needs a separately reviewed/authenticated HTTPS/WSS signaling
service that survives the network change; this prototype does not provision it.
TURN may be necessary across carrier NAT/firewalls. Its availability is not
assumed. Both peers need the same ICE configuration for a fair comparison.

## SmartConnect input, not named-interface steering

To read a separately approved, already-running Video collector, add
`--policy-log /path/to/approved/events.jsonl` to the server command, and enable
its policy checkbox on A. This reads only existing completed observations; it
never starts a collector, probe or HTTPS request. File Download logs, stale
observations (over 45 seconds or future timestamps), malformed files and finished
runs are rejected. Both baseline and assisted trials can read the same input.
For manual signaling, a current sanitized snapshot from `server.policy_snapshot`
may be pasted in the private policy field; it is operator-supplied, not
independently authenticated. Do not use historical/fabricated inputs as a live
policy demonstration.

A fresh recommendation change requests ICE recovery in assisted mode only. The
baseline leaves ordinary browser ICE behavior alone. Browser ICE failure may also
request recovery in assisted mode. Role A alone initiates offers to avoid glare.
Three attempts maximum and a 10-second recovery-request cooldown bound this
experimental coordinator; these are separate from, and do not change, the frozen
SmartConnect engine's margin/three-window hold/30-second dwell. Existing ICMP
window cadence and hold can be too slow for imperceptible call recovery. No
faster application-failure detector was silently added to the frozen policy.

## Observations and privacy

Click Download sanitized observations to save only numeric/enum events and
getStats-derived counters. This is a local download, not an upload. It includes
UTC start and monotonic elapsed times, connection/ICE states, recommendations,
unknown physical interface, ICE-pair generation, RTP packet/frame/sample counters,
identity-preservation checks and counter-progress intervals. Raw stats are never
exported: no candidate addresses, ports, SSRCs, track IDs, SDP, ICE-server URLs,
credentials or private exception strings. Signaling SDP exists only in private
browser memory and bounded server queues; no raw signaling log is written.

Frame/audio counters can be absent and remain null. Decode-counter progress is
not proof of presentation or intelligible audio. Counter resets and stream changes
end intervals as censored observations. A 1000 ms no-progress marker is an
instrumentation choice, not the policy threshold or measured handover time.
Background tabs, muted sources and browser scheduling can affect the measurements.

End this session explicitly before another trial; reload for a new session. Use
Retry last signaling message to resend the same description after a signaling
failure. It does not recreate the call. Local track end/mute/unmute is logged.

## Offline checks (no listener or media)

```sh
/usr/local/bin/node --check experiments/webrtc_continuity/core.js
/usr/local/bin/node --check experiments/webrtc_continuity/app.js
/usr/local/bin/node --test experiments/webrtc_continuity/test_core.cjs experiments/webrtc_continuity/test_app.cjs
/opt/anaconda3/bin/python -m unittest experiments.webrtc_continuity.test_server
```

Node is needed only for these offline tests, not browser runtime. Browser/media
and server transports are mocked in the tests. Test fixtures are not experimental
evidence. See VALIDATION.md for exact results and limits.
