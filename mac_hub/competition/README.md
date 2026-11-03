# SmartConnect EDGE competition demo

Scope: automatically select en0 Wi-Fi or en6 cellular-backed iPhone USB for this
prototype's own NEW HTTPS requests. Existing sessions never migrate. Physical
interface egress is unverified for new flows until separately captured. Radio
technology is unverified; no 5G signal values, MOS or application QoE are claimed.

## Entrypoints and isolation

Base: verified Phase4 commit `7fbc00e`. Branch `codex/edge-competition-demo`.
The original checkout and historical logs are untouched. Worktree:
`/private/tmp/smartconnect-edge-demo` (temporary storage; preserve this branch and
move/copy the worktree through normal Git workflows before clearing /tmp).
The existing environment can run it without installing packages:

```sh
cd /private/tmp/smartconnect-edge-demo
# Existing Python environment; no activation/install required:
/Users/raudaalshaeili/Desktop/smartconnect/venv/bin/python -B -m streamlit run mac_hub/competition/dashboard.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Dashboard defaults to historical real-input replay. Select window 1, then 4, then
18; or enable Play. It never launches a collector, requests, DNS or capture.
Application selection in replay changes the offline policy only. Historical
File Download lacks goodput and uses the documented RTT/loss fallback.

CLI historical replay (stdout only; deterministic):

```sh
/Users/raudaalshaeili/Desktop/smartconnect/venv/bin/python -B -m mac_hub.competition.run
```

The bundled capture is a byte-identical copy, with its original manifest and a
new provenance hash file. 18 real ICMP windows; historical video recommendations
change at windows 4 and 18. No HTTP requests/outcomes exist in that dataset.
Movement times were not recorded: do not shade assumed location stages.
Window 15 Wi-Fi has 29 reported replies but 28 printed RTTs; the collector's
parsed RTT excludes a late reply. The dashboard flags this without editing the
original parser or measurements. Summary RTT is diagnostic, not silently
substituted in the frozen policy.

## Future approval request — NOT EXECUTED

Proposed short validation: six windows, ten one-second echoes per interface per
window, five-second pauses, Video Call profile, at most six fresh 64 KiB HTTPS
outcomes. 120 echo attempts and at most 384 KiB response payload, plus network
protocol overhead. Duration usually 1–2 minutes, longer on bounded failures.
There is one ordinary DNS resolution, pinned across requests, no DNS changes.
Endpoint: speed.cloudflare.com HTTPS /__down?bytes=65536; verified TLS. ICMP:
1.1.1.1. Already connected en0/en6 only; ordinary user, no sudo/capture/config.

After explicit approval ONLY:

```sh
networksetup -listallhardwareports
ifconfig en0
ifconfig en6
cd /private/tmp/smartconnect-edge-demo
/Users/raudaalshaeili/Desktop/smartconnect/venv/bin/python -B -m mac_hub.competition.run --execute --application video_call --cycles 6 --count 10 --pause 5 --output /tmp/smartconnect-approved-demo
```

Choose Live collector log in the dashboard, using
`/tmp/smartconnect-approved-demo/events.jsonl`. Run folders must not exist.
Start a new folder for each repeat; never overwrite evidence. Ctrl-C cancels
active HTTPS and stops subsequent requests; in-flight ping can take count+6
seconds. A completed/cancelled manifest and partial request logs are retained.
No fallback retry is made, even after TLS, timeout or binding failure.

A separately approved File Download run uses the same command with
`--application file_download` and a DIFFERENT output directory. It adds two
64 KiB pre-decision calibration requests/window (18 requests maximum; 1.125 MiB
payload maximum), with alternating calibration order. It can influence observed
conditions. This single-policy demonstration is not a paired application-QoE
performance experiment; use the preserved Phase4 runner for paired comparisons.

## Policy, timing and failure assessment

Reuse Phase4 Controller and Phase3 Darwin IP_BOUND_IF client unchanged.
Continuous Session persists trends, hold, dwell, selected path and availability
across windows. Margin .05, three qualifying windows, 30-second dwell and
five-score trend remain unchanged. Video: normalized RTT/loss 50/50. Download:
Phase4 utility (0.8 bounded-goodput/10 Mbps capped + 0.2 RTT quality), then effective
40% goodput utility / 10% RTT / 50% loss. Missing calibration on either path makes
both fall back to RTT/loss; trend/streak reset on metric-basis changes.
Video observed thresholds RTT>60 ms or loss>2%; download loss>3%. Jitter/capacity
requirements remain unknown, not passed. RTT/loss completeness is required.

Availability failures can recommend a surviving eligible path immediately.
Reachable-but-degraded paths still observe hold/dwell. We deliberately did NOT
shorten those thresholds. Historical windows 2–3 retain a loss-breaching Wi-Fi
recommendation while waiting for the third qualifying window. HTTP-only failure
may persist despite successful ICMP; it is displayed/logged, not treated as proof
that the entire interface is down. Faster service-failure handling requires a
separately specified, calibrated and evaluated policy; do not tune to force a
competition switch. Ten probes resolve loss in 10 percentage points, and 30 in
3.33 points: neither precisely measures a 2% limit.

Each outcome is a fresh verified-TLS socket. Count only:
- recommendation change: direct policy Wi-Fi/cellular transition;
- successful bound-request interface change: successive successful requests
  with binding readback used different requested interfaces (failures retained);
- physical new-flow path change: unknown until new packet verification;
- existing-session handover: not implemented or measured.

Request duration includes TCP/TLS/server/body; bounded-object goodput is completed
body bits/full request duration, not capacity. No path fallback, connection reuse,
redirect-following or retry. Existing client timeout five seconds here; endpoint
preparation wait five seconds; 1..30 windows, 2..30 probes/window, pause 1..30s,
16..256 KiB bodies, <=24 MiB requested payload. Requests log immediately; decisions
log before dispatch; outcomes after completion. JSONL tolerates a partial final
append only. Private logs contain raw ping text, socket tuples and error strings;
do not publish them. Public dashboard uses an allowlist and generic errors,
localhost binding, and never displays local addresses/ports or raw errors.

## Packet validation plan — separate approval required

Do NOT reuse the expired Phase3 Stage B gate or its fixed-1.1.1.1 capture helper.
Phase3 gated execution expires 24h after capture; this additive demo uses the
Phase4 explicit-execute mechanism and honestly labels all new flows unverified.

Before any privileged capture, approve exact en0/en6 interfaces, freshly resolved
pinned public endpoint, 60–120s duration, TCP port 443 BPF filter and snaplen.
Use two supervised non-promiscuous captures with numeric addresses and small
snapshots. Never run Python as root or alter BPF permissions. Capture must cover
startup through all requests, exit cleanly and report zero kernel drops.
Preserve local PCAPs and their hashes; do not publish private tuples.

Offline: correlate each requests.jsonl actual_https record by exact source/
destination IP+port and start/end interval, outbound SYN, matching reverse
SYN-ACK, and outbound payload on the requested interface, with no corresponding
outbound flow on the other interface. Reuse mac_hub.traffic.verify.packets and
correlate (takes CSV-like string values), not source-IP/readback alone. Require
all outcomes around changes confirmed on both interfaces. Reuse requires a small
JSONL-to-verifier adapter or documented offline invocation; no importer marks
these new logs confirmed yet. Ambiguity, missing captures/drops => unverified.
Physical transition timing would need its own explicitly defined packet interval;
request duration and first success are not existing-session migration time.

## Judge script and backup

1. Explain Wi-Fi-first vs application-specific selection and unknown dimensions.
2. Show both measured paths, reason, score/trend, hold/dwell and failures.
3. After approval, show NEW HTTPS success and binding readback on the selection.
   A visible change depends on conditions; never promise one or disrupt a network.
4. Show historical replay windows 1/4/18 if real conditions do not diverge.
   Keep HISTORICAL banner visible; no fabricated live requests.
5. Separate historical four packet-confirmed Phase3 flows from today's unverified
   flows. Say "automatic selection for new prototype requests", not "seamless 5G
   handover". No bandwidth, zero-loss or QoE-improvement claim.

Q: Does it move my video call? A: No, it opens its own new sockets only.
Q: Is cellular 5G? A: Not independently verified.
Q: Did the historical policy improve everything? A: No: selected loss fell but
selected RTT increased; application traffic was not moved.
Q: Why not switch instantly? A: Stability trades response delay for less flapping;
only observed unavailability bypasses hold/dwell, not every quality breach.
Q: What if HTTPS fails? A: It stays failed in the log; no silent alternate path.
Q: Does socket readback prove physical egress? A: No; packet correlation is separate.

## Offline verification

```sh
cd /private/tmp/smartconnect-edge-demo
/Users/raudaalshaeili/Desktop/smartconnect/venv/bin/python -B -m unittest test_competition_demo test_mac_hub_traffic test_phase4 -v
/Users/raudaalshaeili/Desktop/smartconnect/venv/bin/python -B -m unittest -v
```

These tests use mock requests/probes and historical local files, never initiate
real traffic. They write only temporary test artifacts. Preserve future actual
live logs outside committed/public demo artifacts; private tuple fields are needed
for approved offline packet correlation but must not appear on the projector.
