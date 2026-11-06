# Offline validation and delivery — 6 November 2026

Feature branch: codex/webrtc-continuity-poc.
Base: d273c2d14afe474637fc9dc8b5794381560b100a, the latest local frozen competition
branch tip. codex/dashboard-finalization remains at that commit. No other branch
was rewritten, merged or pushed; no GitHub backup was modified.

## Results

- Node v24.13.0: **27 tests passed**, 0 failed, 0 skipped.
  `node --test experiments/webrtc_continuity/test_core.cjs experiments/webrtc_continuity/test_app.cjs`
- Python 3.13.5: **8 new server/policy tests passed**; **42 existing focused
  competition/dashboard tests passed**, 0 failures/errors, 0 skipped.
  `/opt/anaconda3/bin/python -m unittest experiments.webrtc_continuity.test_server test_dashboard_ux test_dashboard_finalization test_download_decision_display test_competition_demo`
- Total: **77 offline tests passed**. This is not a full-repository suite claim.
- `node --check` passes for core.js and app.js; `git diff --check` passes.
- Frozen mac_hub code, dashboard, policy, thresholds, evidence, original application
  and dependency files compare unchanged against the base. Only this new isolated
  directory is added. No packages were installed.

## What the tests establish

Tests use fake peer connections/media tracks and supplied stats fixtures; no real
RTP or camera/audio capture occurs. They verify a single connection/track identity
across an ICE-restart offer/answer exchange; rejection of implicit new sessions;
signaling failure/retry/ordering; queued signaling while recovery is busy; assisted
versus ordinary baseline intervention; Wi-Fi→cellular recommendations; no eligible
path and later recovery; stale/wrong-profile input; rapid changes, cooldown and
attempt ceiling; selected candidate-pair generations without egress claims;
missing stats, independent audio/video stalls, counter reset and right censoring;
receiver-track changes; explicit end and the independent duration timer.

Application wiring tests verify zero fetch/getUserMedia/RTCPeerConnection/timer
activity on page boot or denied approval; invalid config rejected before I/O;
approved startup invokes genuine browser API interfaces; baseline recovery is
disabled; manual mode creates signaling without broker traffic; private setup is
hidden after Start. These are mocks, not a live-browser media proof.

Server tests forbid sockets/DNS, verify the CLI gate before listener creation,
authorization/role conflicts, queue bounds/TTL, origin/Host checks, safe errors,
read-only fresh/stale/finished/profile policy handling and privacy filtering.
Neither SDP nor source IP/port nor credentials appear in sanitized observation
exports. Signaling necessarily contains private SDP in memory; it is not evidence
for public release. Do not project private control fields or URLs.

## Demonstrated versus unproven

Demonstrated offline: the software contracts above and byte-preservation of the
frozen competition implementation. Implemented: actual WebRTC media API wiring,
not a visual placeholder or prerecorded outcome.

**Not demonstrated:** a successful real call, camera/microphone permissions,
a live ICE restart, physical en0/en6 traffic paths, continuity under Wi-Fi loss,
measured interruption/packet/frame/audio loss, TURN interoperability, persistent
remote signaling, perceptual seamlessness, or improvement over ordinary WebRTC.
No listener was started, no camera/microphone activated, no media/probe/HTTPS/capture
traffic was run, and no network/system configuration was changed. Technical
reference lookup was documentation research, not an experimental network run.

## Exact new files

- experiments/webrtc_continuity/__init__.py
- experiments/webrtc_continuity/server.py
- experiments/webrtc_continuity/core.js
- experiments/webrtc_continuity/app.js
- experiments/webrtc_continuity/index.html
- experiments/webrtc_continuity/style.css
- experiments/webrtc_continuity/test_core.cjs
- experiments/webrtc_continuity/test_app.cjs
- experiments/webrtc_continuity/test_server.py
- experiments/webrtc_continuity/FEASIBILITY.md
- experiments/webrtc_continuity/README.md
- experiments/webrtc_continuity/PROTOCOL.md
- experiments/webrtc_continuity/VALIDATION.md

## Remaining blockers and EDGE recommendation

Browser JavaScript has no named-interface binding API. A recovery request does
not enforce the SmartConnect recommendation. The automatic broker is loopback
only, so two local tabs cannot establish carrier-path continuity. Manual remote
signaling is supported but is operator-assisted, not seamless. Remote automatic
recovery needs an approved resilient signaling service; NAT/firewall conditions
may require approved TURN. Actual permissions, interface state and peer reachability
remain unverified. See FEASIBILITY.md and PROTOCOL.md for sources and promotion
gates. **Recommendation: research-only; keep the frozen new-request dashboard as
the EDGE demonstration until approved live evidence supports a narrower claim.**
