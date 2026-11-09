# Completed summary and one-call measurement preparation

This isolated change follows staging commit `90aaaf9`. It is not deployed and
does not start media or measurements. Existing Mac/Windows launchers, tab access,
End/New Call ownership handling, Prototype 1 engine and WebRTC core are retained.

After End Call, the main dashboard becomes a read-only COMPLETED CALL SUMMARY.
It uses the existing sanitized call export: the last accepted policy event and
last media sample, with their elapsed observation times and actual call duration.
It retains Wi-Fi/cellular RTT, loss and score, recommendation/explanation, local
browser network-type metadata, optional interface correspondence, media counters,
recovery causes/signaling events and peer/track preservation status. Missing
measurements remain UNAVAILABLE. Requests and signaling events never establish
physical handover. A previous interface association cannot be attached to a
different final candidate generation. New Call clears the view through the
existing inert reload; it does not start a camera or collector.

Summary freezing is synchronous after media closes, before potentially slow
broker cleanup. The existing recorder/export and broker cleanup order is retained.
Late callbacks cannot replace the frozen summary. No new network reads occur.

## Minimum operator workflow after separate approvals

1. Approve staging deployment of this change. The assistant handles deployment
   verification. Refresh the existing tabs once; access/settings remain in-tab.
2. Approve one call (both cameras/microphones and direct WebRTC traffic), at most
   300 seconds, plus at most 360 ICMP echoes to 1.1.1.1 across en0/en6 over at most
   270 seconds within the call budget. Keep both links available. No capture,
   interruption, route change or recording is included.
3. The assistant arms the existing Mac bridge. On both current tabs choose New
   Call if needed, then Start Call on Windows B followed by Mac A. No JSON file,
   inventory linking, repeated launcher or technical configuration is required.
4. Wait for measured values/recommendations, explain the real engine decision,
   then End Call. Read the retained completed summary. Do not manufacture a
   recommendation change or infer media handover from an ICE restart.

The bridge already sends session-matched policy through the authenticated staging
channel; both browsers already poll it. Windows labels these REMOTE MAC decisions.
`jury_live_watch.py` now has an assistant-operated arming path independent of
browser launch. It checks prerequisites and an idle room, refuses an active
watcher, writes one expiring approval grant, and starts the existing bounded
collector only when Mac A joins. The existing writer credential stays on Mac.
An absent grant remains completely inert. No new icon, service or engine exists.

Assistant maintenance commands, not presentation steps:

```
python jury_live_watch.py --kit-dir <existing-private-kit> --check-only
# Only AFTER the explicit call/probe approval above:
python jury_live_watch.py --kit-dir <existing-private-kit> --arm-one-call --approved-300s-360echoes
```

The first command imports the existing engine, validates local credential shape
and reads OS interface availability; it sends no HTTP or probes. The second
command performs an authenticated idle-room check and arms one call. No grant has
been installed during preparation.

## Validation

126 JavaScript/core/engine-contract tests and 107 Python continuity/bridge tests
passed. Focused cases cover completed-summary staleness/missing values, frozen
late callbacks, Windows attribution, candidate generations, duration, existing
End/New Call evidence and reset behavior, approval gating, idle-room rejection,
single consumption and failed watcher startup cleanup.

Actual local browser previews used preserved sanitized November 7 experiment
exports for both peers, explicitly labeled OFFLINE PREVIEW. They are historical
evidence, not new calls. Both summaries were visually checked. Local bridge
readiness passed for en0/en6, existing credentials and the unchanged engine.
No deployment, new media, live network measurement or recording was performed.
Live operation of this arming path awaits the separate approval above.
