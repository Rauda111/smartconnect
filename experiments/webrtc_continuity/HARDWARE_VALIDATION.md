# One-session Mac–Windows hardware validation

Status: **prepared, not run by this implementation**. The participant reports separate working Wi-Fi and cellular sessions; successful recovery inside one existing session is not yet demonstrated. Treat offline test fixtures as software tests only.

## Approval and scope

Obtain explicit approval for each live stage before performing it. Approval must name the two participants, camera/microphone use, media/signaling and ICE/TURN destinations, Mac ICMP target, duration/cellular usage, and sanitized policy uploads. Packet capture, recording people, disabling Wi-Fi, changing a network setting or physically perturbing connectivity each require their own explicit approval. Do not alter routes, DNS, firewall, service order or other applications. Do not run unapproved preparatory internet tests.

The default bridge is six cycles of ten probes per interface: at most 120 ICMP echo sends total to the fixed public target `1.1.1.1`. It measures the two paths concurrently, preserves Video Call state across cycles, and pauses five seconds between cycles. Each measurement has a count+6-second timeout; HTTPS requests have bounded timeouts and add to elapsed duration. Approve the displayed limits rather than assuming a fixed completion time. Browser call duration is separately bounded by its configured 30–300-second limit. Stop the bridge and both calls if an approved limit is reached.

Use the launch commands and separate credential setup in [INTEGRATION.md](INTEGRATION.md). Match the bridge's `--duration` to the remaining approved call interval. Both peers must join within the shared room's absolute 360-second lifetime; either peer leaving ends that scope. Do not accidentally start a replacement call when collecting the before/after evidence.

## Stage 1: stationary baseline

1. Confirm the Mac has `en0` and the current USB interface; confirm Windows has stable internet. Do not assume a remembered interface number or address. Local interface inspection is read-only; keep addresses private.
2. Confirm the integrated code is deployed only after approval, both clients use the same revision, and policy-writer and signaling credentials are distinct. If using the existing deployment, do not assume new policy endpoints exist.
3. Select ordinary WebRTC baseline on both clients, identical approved ICE configuration and a 120-second limit. Keep both laptops awake and browser tabs visible; use headphones and moving video/audio with a reproducible reference.
4. Start Windows B and Mac A. Confirm increasing inbound video frames and audio sample/packet counters on both sides, and audible/visible two-way media. A connected ICE label alone is insufficient.
5. If approved, launch the Mac bridge. Confirm a fresh real Video Call recommendation appears. The baseline may display policy but must not request application ICE recovery.
6. Download sanitized observations from both peers and explicitly end both. Report inability to connect as a failed trial; do not hide it by starting another call inside the same trial.

## Stage 2: independent path preparation

Before a transition trial, establish that the initial call media actually uses Wi-Fi and that USB cellular internet is independently usable. Successful separate cellular calls already reported are useful feasibility evidence, but do not prove the new trial's path.

Inspect the selected ICE pair and local candidate privately, using browser diagnostics if necessary. Compare its local address with the contemporaneous interface address list. Candidates may use mDNS names, NAT mappings, relay addresses or IPv6 privacy addresses, so direct address equality may be impossible. An unmatched or obscured candidate remains **unverified**, not Wi-Fi or cellular by guesswork.

The integrated private path download and `media_path capture-interfaces` / `compare` commands make an exact host-address comparison reproducible. Keep snapshots within 30 seconds, retain their original timestamps, and use separate before/after files. The comparison itself is offline; the inventory command only reads local interface state. An exact address match is candidate/interface evidence, not packet egress or handover proof. The report explicitly keeps those stronger claims false. Never infer en6 from an address prefix, a recommendation, a pair generation change, or a TURN address.

For stronger evidence, separately approve narrowly scoped interface-correlated packet observation on `en0` and the USB interface. Correlate the selected media transport's tuple, timing and sustained packet/byte progression with that interface; account for TURN relay transport when used. Distinguish SRTP/DTLS media transport from ICMP probes, HTTPS signaling and other application traffic. This guide deliberately does not execute or automatically invoke capture commands. Have the exact filters, duration, storage and deletion plan reviewed before capture. Keep raw addresses, ports, identifiers, credentials and captures private; publish only sanitized findings. Encrypted transport correlation verifies path, not decoded media content.

Independent cellular reachability may require a separately approved bound connectivity check or an approved temporary Wi-Fi-loss stage. An ICMP response alone is not proof that media/TURN can traverse that path. A successful cellular-only new call is still not a same-session handover result.

## Stage 3: one continuous assisted call

1. Start fresh Mac A and Windows B peers in SmartConnect-assisted mode, with the same media/settings as baseline. Enable hosted policy reading on Mac A and run the approved bridge. No reload, new peer connection, camera reacquisition or new call may be hidden inside this trial.
2. Record pre-transition Wi-Fi path evidence and sustained video/audio progression. Record the original peer-connection and sender/receiver continuity checks available in sanitized observations. Track identity alone does not prove uninterrupted delivery.
3. Mark a common experiment time and introduce exactly the approved Wi-Fi degradation/loss procedure. Do not disable Wi-Fi merely because this protocol describes a loss stage. Record clock uncertainty between laptops and external observations.
4. Observe all events: measurement availability, recommendation and reason, request/suppression of recovery, offer/answer attempts, ICE state, selected pair, media counters and track identity. Keep failures, cooldown suppression, unanswered offers and exhausted attempts in the record.
5. Verify post-change media traffic on the USB interface independently. A cellular recommendation, new candidate pair or ICE `connected` state cannot substitute for this evidence.
6. Observe recovery for the remaining approved interval. Stop and retain the failed result if media never returns. Do not count an explicit new session after failure as continuity. Explicitly stop bridge and both clients at the trial end.

## Interruption calculation

Use each peer's monotonic elapsed timestamps for its local timeline and UTC anchors only with clock uncertainty. Video receiver progress comes from frame-decode counters; audio progress from supported sample/packet counters. Absent metrics remain unavailable. Counter reset, changed stream or ending during a stall makes that interval censored, not a zero-length interruption.

The current 500 ms sampling provides an interval estimate between the last observed progress and first resumed progress, affected by scheduling. Report the polling interval and background-tab effects; do not report this as exact perceptual freeze time. Distinguish audio and video gaps, transport bytes, decoding and user-observed playback. An independently approved timestamped reference audio/video recording can assess perceptual loss and buffering. Never infer exact missing frames from an unchanged counter alone.

Record: condition; software revision; settings; approximate perturbation time; recommendation time/cause; ICE recovery cause and attempts; longest audio/video progress gap; whether media resumed; session/track continuity checks; pre/post physical-path evidence level; failures; sampling/clock uncertainty. Report no-recovery trials and right-censored gaps explicitly. Do not include raw candidate addresses, SDP, socket IDs or credentials in the public report.

## Fair comparison and attribution

Run ordinary WebRTC and assisted trials under the same peer devices, approved ICE/TURN service, media settings, policy observation cadence and reproducible Wi-Fi event. Alternate or randomize order and repeat at least three trials per condition if approved. Keep packet-observation overhead equivalent. Retain all trials, including nonrecoveries.

Classify the intervention cause before interpreting outcomes:

- Ordinary browser recovery: media/path recovered without an application-requested ICE restart.
- Recommendation-driven: a valid fresh policy transition requested ICE recovery.
- Application failure recovery: disconnected/failed ICE or video stall requested recovery.
- Manual recovery: operator requested restart; this is a separate diagnostic condition.

Assisted mode can contain more than one cause. A policy event followed by success is correlation, not proof of benefit. If failure-driven recovery acts first, report that trial accordingly; do not credit the recommendation engine. Never claim proactive goodput switching from ICMP-only measurements. No universal superiority claim follows from a small testbed.

## Acceptance for the jury

A defensible **same-session recovery** claim needs retained peer connection/local tracks, observed resumed audio/video, measured interruption and a complete event record. A **Wi-Fi-to-cellular media migration** claim additionally needs independently verified pre/post physical paths in that same session. A **seamless** claim requires evidence of no perceptible interruption and a declared measurement threshold; the implementation alone does not satisfy it.

Until those criteria are met, present this as implemented integration with hardware validation pending. Keep the frozen Prototype 1 demonstration available. Do not label an unverified path selected, hide a frozen video, fabricate a recovered frame counter or silently restart the call.

## Trial record to complete from actual observations

| Field | Record during the approved trial |
| --- | --- |
| Revision / baseline or assisted / trial number | Exact committed revision and condition |
| Approved interval / start and stop | UTC anchors plus per-peer elapsed time |
| Initial path evidence | Snapshot generation, candidate match, packet corroboration level |
| Cellular preparation | Bound reachability and applicable ICE/TURN feasibility evidence |
| Perturbation | Exact approved action, time and timing uncertainty |
| Recommendation | Previous/current, window, cause and engine explanation |
| Requested recovery | Policy / ICE failure / stall / manual; attempts and failures |
| Observed outcome | Resumed video/audio counters or explicit failure |
| Interruption | Each peer's counter-progress gaps, sampling interval, censoring |
| Same session | Same PC/local/observed remote track results; no hidden reload |
| Final path evidence | Same private session ID, selected generation, interface/packet evidence |
| Claim supported | Recovery only / candidate match / physically corroborated migration / none |

Leave unavailable observations blank or explicitly unavailable. Do not fill this table from unit-test fixtures.
