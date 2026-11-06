# SmartConnect WebRTC recovery experiment patch

This patch is for the local `codex/webrtc-continuity-poc` branch. It is **not** a verified seamless handover.

## Changes
- In SmartConnect mode, initiator A observes decoded remote video frame progress; after 3000 ms of no progress (after frames previously arrived), it records `video_stall_observed` and attempts an ICE restart.
- An ICE `disconnected` state held for 2500 ms also attempts recovery. Existing `failed`, policy, and manual triggers are retained.
- Existing 10-second cooldown and 3-attempt ceiling remain. Baseline mode stays unchanged.
- Recovery uses the **same** RTCPeerConnection and local media tracks.
- In manual signaling mode, the interface explicitly warns that the newly generated offer/answer must be exchanged by the operator.

## Critical blocker for unattended handover
The current broker is loopback-only; manual SDP exchange on two laptops is not automatic. ICE restart cannot independently send a new offer to Windows. Fully automatic, cross-interface recovery needs an approved, authenticated signaling channel reachable from *both* Wi-Fi and cellular, and often approved STUN/TURN infrastructure. Do not expose the local broker to the internet.

## Local installation
From `~/smartconnect`, back up the current folder, then overwrite only `core.js`, `app.js`, and `test_core.cjs` from this ZIP in `experiments/webrtc_continuity/`. Do not overwrite your `server.py`, HTML, or configuration.

Run `node --test experiments/webrtc_continuity/test_core.cjs experiments/webrtc_continuity/test_app.cjs` from the repo root.

Keep Wi-Fi available while testing initial logic. Observe `video_stall_observed` and `recovery_requested` events and manually exchange restart offer/answer. Never claim that a physical en0-to-en6 change is verified without a separate owner-approved packet correlation.
