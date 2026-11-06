# Mac + Windows: first genuine call and continuity validation

Status: implemented browser media/signaling wiring; offline-tested only. No real
call or physical migration has been demonstrated. This is separate from the
frozen competition dashboard. All launch instructions below are for a future,
explicitly approved experiment; none were executed during development.

## Feasibility and the shortest path

Confirmed by the participant: MacBook Pro M1, Wi-Fi en0, iPhone USB cellular-backed
connection previously en6, and Windows laptop with stable internet. Both Mac
connections are available. Reconfirm the USB interface name privately before a
path-validation trial; availability does not establish where browser media flows.

A genuine two-party call is feasible using one local page on each laptop and
private manual offer/answer exchange. There is no dependency installation for
the Python server. Direct connectivity across the two networks is not guaranteed:
carrier NAT/firewalls may require an approved TURN service. No STUN/TURN server
or credentials are bundled. An empty ICE configuration is appropriate only when
host candidates can reach each other; it is not a reliable internet setup.

Critical limitation: standard browser WebRTC cannot bind media to en0/en6.
SmartConnect can request ICE renegotiation on the existing peer connection, but
cannot enforce which interface wins. An ICE restart is an intervention, not proof
of migration. Ordinary browser recovery can happen before or without it.
Automatic cross-laptop recovery additionally needs resilient authenticated
remote signaling; this prototype deliberately has only a loopback broker and
manual remote exchange. Manual exchange cannot demonstrate seamless recovery.

If policy-enforced physical interface selection is mandatory, this browser-only
implementation is blocked. A native WebRTC transport with audited interface-bound
sockets or an explicitly approved tunnel/overlay is a separate development
project. A macOS Network Extension/VPN also requires native packaging,
entitlements, user consent and infrastructure; it may affect other applications.
It is not a safe quick addition to the frozen competition code.

## Software and private setup

Mac: existing Python at /opt/anaconda3/bin/python, Chrome, camera/microphone
permissions in browser and macOS, headphones. Node is only needed for offline
unit tests. The server uses Python standard library only.

Windows: Python 3.10+ with the `py` launcher, current Chrome or Edge, permitted
camera/microphone, headphones. These Windows prerequisites have not been checked
on the participant's machine. No Node, Streamlit, Python media package, Git or
administrator access is needed to run the call page.

Privately transfer ONLY these six runtime files from this directory to
C:\SmartConnectCall on Windows, after approval for that transfer:
server.py, index.html, core.js, app.js, style.css, __init__.py.
Do not transfer logs, .git, evidence or credentials. Provision approved STUN/TURN
separately if required; use temporary credentials and keep them off projection.
No dependency downloads, hosted service provisioning or file transfers were run.

## Exact future launch commands

Mac Terminal, after local-listener approval:

```sh
cd /Users/raudaalshaeili/smartconnect
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.server --approved-local-traffic
```

Windows PowerShell, after the six files exist and local-listener approval:

```powershell
cd C:\SmartConnectCall
py -3 server.py --approved-local-traffic
```

Open the Mac server's printed PRIVATE Client A URL on the Mac. Open the Windows
server's printed PRIVATE Client B URL on Windows. Both are locally hosted
http://127.0.0.1:8766/ URLs with their own temporary access tokens. The Mac URL
cannot be opened from Windows to reach the Mac. There is no public join URL.
Do not expose the server, forward ports or disable firewalls.

On BOTH pages choose Private manual SDP exchange and the SAME condition and
approved ICE settings. Mac is A, Windows is B. With separately approved media
traffic, start B then A. Expand Private signaling controls: copy A's entire
outgoing JSON privately to B's incoming field, apply it; then copy B's entire
outgoing JSON privately to A and apply. Wait for live remote video/audio and
increasing receiver counters. No media recording occurs automatically. Each ICE
restart requires another such offer/answer exchange, without pressing End,
Start, or reloading either page. Raw signaling contains private addresses and
credentials; never publish it. Stop buttons and Ctrl+C end the call and servers.

For policy-input trials only, add `--policy-log` followed by the private path to
an approved, current Video-profile events.jsonl on the Mac. Enable the local
policy checkbox on Mac A. This also works with manual remote signaling. It never
starts the collector. A finished historical run cannot drive a live trial; if no
approved current collector exists, automatic policy-driven trials remain blocked.
Starting a collector/probes requires separate approval. Windows needs no policy
log. A manual ICE-recovery button tests the recovery mechanism, not the policy.

## Safe first test: connectivity before handover

1. Obtain approval for both local listeners, camera/microphone, private signaling
   channel, specific ICE/TURN destinations and cellular usage. Agree a 120-second
   limit. Do not approve capture or system changes implicitly.
2. Launch the two servers, configure baseline, manual signaling and 120 seconds.
   Keep both Mac links available and do not disturb Wi-Fi. Permissions must be
   granted normally; do not bypass warnings.
3. Start B and A and exchange signaling as above. Speak and move in front of the
   cameras. Confirm both directions; use Play remote if autoplay is blocked.
4. If no connection forms, stop. Review ICE/NAT/TURN privately; do not change
   routes, DNS, service order or firewall. Failed connectivity is a result.
5. Download sanitized observations locally on both clients and End; stop servers.
   Report success only if actual remote media/counters were observed. This first
   test establishes connectivity, not baseline Wi-Fi egress or handover.

## Physical path and interruption measurement: separate approval

Before a transition trial, approve interface-scoped packet capture and private
handling of raw endpoint identifiers, or another independently reviewed means of
attributing browser media to physical interfaces. No capture command is run by
this prototype. Neither a Wi-Fi icon nor an ICE-pair change proves egress.

With capture approval, correlate the active browser ICE transport's private
endpoint tuple/protocol and timing to packets on en0 before, and the currently
identified USB interface after. Track the actual SRTP/DTLS flow (or TURN transport
if relayed); distinguish media from probes, signaling and unrelated traffic.
Corroborate with remote selected transport and increasing received media counters.
Retain raw tuples/captures privately; publish only reviewed summaries. If the
initial media already uses USB or both paths cannot be attributed, classify the
trial as inconclusive for Wi-Fi-to-cellular migration. Public IP change alone is
insufficient. TURN does not itself force an interface.

Only after a separately approved, reproducible Wi-Fi loss/degradation procedure,
observe recovery without replacing either peer connection or its sender tracks.
Do not modify system settings or routes under the existing authorization.
An approved loss procedure is still needed; this document does not authorize
Wi-Fi disabling, unplugging hardware or disrupting other applications.

Export both clients' sanitized observations. They include monotonic elapsed time,
UTC start, session/track identity checks, ICE state/pair generation, received
packets/loss, decoded frames, audio sample/concealment counters where supported,
and counter-progress gaps. Sampling is 500 ms; the stall marker is 1000 ms.
Report last-progress-to-first-resumed-progress intervals with polling uncertainty,
separately for audio/video, including missing/right-censored intervals. They are
not exact perceptual outages or exact lost-frame counts. Codec frame drops,
packet loss and audio concealment have different meanings. Use separately
consented reference audio/video recording for perceptual measurements. Cross-host
event alignment requires clock-offset/uncertainty accounting; each host's local
monotonic gap avoids assuming synchronized clocks.

## Fair comparison and attribution

Use the identical two laptops, ICE/TURN, signaling method, media settings,
approved loss procedure and duration for baseline and assisted trials. Alternate
or randomize order and repeat at least three times per condition when approved.
Reload between trials, never within a measured session. Baseline disables all
application-requested recovery while retaining the browser's normal behavior.
Feed the same type/cadence of approved real policy input in both conditions.

Assisted events distinguish policy_change, ice_failed and manual restart causes.
Only a policy_change-triggered intervention supports a policy-assisted result.
An ice_failed-triggered restart tests the prototype's separate failure-recovery
handler; a manual restart is operator assisted. Neither demonstrates a policy
advantage. A path change before any application restart is ordinary WebRTC
recovery. Report all causes and failed/censored trials, do not select successes.
With manual signaling, operator delay is part of recovery and must be reported;
it cannot support a seamlessness comparison or predict automatic signaling gains.

Promotion requires successful real calls, independently verified en0→USB media
migration with the same application session, measured bidirectional interruption,
resilient automatic signaling and fair baseline evidence. Until then: research
prototype only, not an EDGE claim of SmartConnect-controlled seamless handover.

References: [WebRTC API](https://www.w3.org/TR/webrtc/),
[WebRTC statistics](https://www.w3.org/TR/webrtc-stats/),
[TURN guidance](https://webrtc.org/getting-started/turn-server).
