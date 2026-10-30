# Phase 4: bounded paired application experiments

This additive package preserves Phase 1–3, Cisco and simulation implementations.
No command changes routes, DNS settings, priorities, firewall, interfaces or routers.
No command invokes sudo or packet capture. Ordinary execution needs no administrator.
The viewer is read-only. `--execute` is required for actual requests; dry-run uses
no DNS, ping or sockets and **is not a synthetic performance result**.

## MacBook commands

From the repository root:

```sh
git switch codex/mac-hub-phase4
source venv/bin/activate
python -m unittest -v
python -m mac_hub.traffic.audit
python -m mac_hub.experiments.audit mac_hub/experiments/results
python -m mac_hub.phase4.run --output mac_hub/logs/phase4-plan --trials 4 --cycles 4 --bytes 131072
python -m mac_hub.phase4.report mac_hub/logs/phase4-plan
```

Output directories must be new; nothing overwrites earlier evidence. A normal,
non-disruptive real observation, with both interfaces already connected:

```sh
phase4_dir="mac_hub/logs/phase4-stable-$(date +%Y%m%dT%H%M%S)"
python -m mac_hub.phase4.run --execute --output "$phase4_dir" --trials 4 --cycles 4 --bytes 131072 --interval 5 --condition stable_observation
```

In the same Terminal, use that same variable for the reports:

```sh
python -m mac_hub.phase4.report "$phase4_dir"
python -m mac_hub.phase4.report "$phase4_dir" --audit-only
streamlit run mac_hub/phase4/dashboard.py
```

Choose that directory in the dashboard. It refreshes every five seconds; the
manifest appears when a run completes or is cancelled. Request CSVs flush after
each request, but only completed manifests pass the dashboard integrity audit.
Ctrl-C cancels requests through the existing socket-abort watcher, closes sockets
and saves partial evidence. Concurrent ping monitoring may take up to nine seconds
to finish; cancellation never changes the network configuration.

## Predeclared protocol

* Both paths get concurrent three-packet interface-bound ICMP windows to 1.1.1.1.
  Save raw output, means, loss counts and adjacent successful RTT differences.
  Zero of three lost packets is weak evidence, not proof of a zero-loss path;
  resolution is 33.3 percentage points. Neither RTP jitter, RSSI nor capacity is measured.
* Each window then obtains one equal-sized HTTPS calibration download on each path.
  Path order alternates by trial+cycle. Calibration is traffic and can perturb the
  condition: measurements are sequential, not simultaneous matched universes.
* Only completed pre-decision calibration observations and shared ICMP input enter
  decisions. No outcome is fed backwards into its own decision. Failed calibration
  is missing, never zero. One failed calibration disables goodput comparison on
  **both** paths for that window, rather than rewarding the unmeasured path.
* Video Call uses the original Phase 1 RTT/loss Engine. Its actual outcome is a
  fresh 16 KiB HTTPS request: a request-responsiveness proxy, not a video call.
  File Download uses the same stability controller with an explicitly new input
  adapter: utility = 0.8 min(1, bounded_goodput/10 Mbps) + 0.2 normalized RTT quality.
  Utility is mapped into the Engine's latency scoring coordinate, **not recorded as
  measured RTT**. With the original renormalized weights, effective score weights
  are 0.4 bounded-goodput utility, 0.1 RTT quality and 0.5 loss quality. Reference
  10 Mbps and original normalization bounds/margin are fixed heuristics, not fitted
  to these results or service guarantees. Throughput-capacity guardrail remains
  unknown. The observed download guardrail is loss >3%; Video Call also uses RTT
  >60ms and loss >2%. Jitter guardrail remains unknown.
* If calibration is missing, File Download falls back to the original RTT/loss
  adapter; profiles can then have identical scores, but distinct guardrails.
  Reset score trends and superiority streak on a metric-basis change; retain dwell
  and selected path. Missing required RTT/loss makes a SmartConnect path unusable.
  Baseline uses the same raw reachability: Wi-Fi if reachable, else cellular, else
  no eligible path. ICMP reachability does not guarantee HTTP service availability.
* Keep Engine's five-score trend, margin .05, three-window superiority hold and
  30-second dwell; failed current path resets availability immediately. Guardrail
  rescue can still wait for stability. Report harms as well as benefits.
* Two outcome requests per pair use the same workload/endpoint/body size. Policy
  order alternates by trial+cycle, even if both policies choose the same interface.
  No connection reuse, fallback, retries, redirects, proxy or unbound connection.
  Both profiles are evaluated each trial; profile order alternates by trial.
  Controllers reset per profile/trial, all observations included. Trial order is
  balanced, deterministic and auditable, not randomized or blinded. Even trials
  ensure order balance; use >=4 for uncertainty intervals, preferably repeat whole
  sessions on different days. Short trials may never satisfy dwell; do not tune it
  away after seeing results.
* Polling is paced by a pause after each completed cycle, not a fixed-rate sample.
  Record actual elapsed time. Up to 8 trials, 12 cycles, 1 MiB per body, 10-second
  request deadline and 32 MiB requested-payload ceiling per invocation. Headers,
  TLS, ICMP, retransmissions and an oversize-body sentinel add wire bytes; this is
  a requested-payload budget, not an exact cellular billing cap. The recommended
  4x4, 128 KiB protocol requests at most 16 MiB payload and 128 fresh connections;
  actual response payload is lower because Video Call uses 16 KiB outcomes.
* Endpoint is Cloudflare's documented `https://speed.cloudflare.com/__down?bytes=N`:
  https://github.com/cloudflare/speedtest . One ordinary DNS resolution pins the
  same public IPv4 across both interfaces/policies. DNS lookup is not interface-bound.
  The preparation wait is bounded to five seconds and cancellation starts no HTTP traffic; a daemon libc resolver may finish later. TLS hostname verification stays enabled; public address can be supplied with
  `--address`. Endpoint/server/TLS/setup effects are part of the outcome, not
  isolated radio or access-network performance. Endpoint failure ends preparation
  safely; no substitution to an unrelated endpoint.

## Timing, evidence and analysis

Raw client fields preserve UTC request initiation, TCP-established and termination
wall timestamps, monotonic request duration, cumulative TCP/TLS/header-ready
elapsed times and failure phase. Header-ready `ttfb_ms` is when Python has parsed
response headers, **not the instant the first packet or body byte arrived**.
Additional TLS/header UTC estimates add monotonic offsets to request wall start;
these are explicitly estimates. Failure is timestamped at observed termination,
not the unknowable instant the network first failed. Decision, monitor-window,
monitor-to-decision, pre-dispatch and decision-to-observed-completion timing are
separate. Decision-to-start is monotonic controller pre-dispatch delay (a small
Python call overhead precedes the client's recorded initiation). It includes the
other policy request when second. No synchronized one-way or transport-migration
latency is inferred; wall clock adjustment can affect cross-record epoch comparisons.

Goodput = exact delivered body bytes *8 / **whole fresh request duration**. It is
end-to-end bounded-object goodput, not sustained bandwidth, body-transfer-only
speed or video QoE. Invalid lengths/timeouts get no goodput; partial bytes are not
reported as complete delivered objects. Raw partial-byte counters are unavailable
in the preserved Phase 3 client. No application-level jitter measurement exists.

`report` first checks source CSV hashes, exact byte counts, causal common inputs,
policy replay, order and metric arithmetic. It outputs `summary.csv`,
`contrasts.csv`, `outcomes.png`, `REPORT.md`. Complete-success paired differences
are SmartConnect minus baseline. Failures and no-eligible slots are reported
separately; complete-success comparisons can have survivor bias. Report both signs.
Uncertainty is seeded 10,000-resample percentile bootstrap over trial means, not
individual requests; below four complete trials no interval is computed. Four
trials on one host remain exploratory and autocorrelated, not population evidence.

Changes are counts of **recommended new-request** interface changes, per trial,
excluding initial attachment and availability transitions (separately counted).
A bracketed failure gap spans successful completions around failed/no-path slots;
it includes cadence, probes and other requests. Unbracketed failures are censored;
maximum failure streak is also retained. No bracketed gap is unknown, not zero
outage. Captured physical transitions and existing-session interruption remain
unmeasured. Every new Phase 4 flow is `unverified`, including when the binding
socket option reads back correctly. Phase 3's four historical verified requests do
not confirm Phase 4 downloads or subsequent flows.

## Natural conditions, approvals and demonstration

Collect a stable run first. During ordinary use, observe a naturally weaker Wi-Fi
location or naturally occurring temporary path loss; label a separate run
`--condition natural_wifi_deterioration` or `observed_path_unavailability`. Labels
are operator observations, not proof of congestion or causal interventions. Retain
all rounds; annotate timing/context externally without rewriting original CSVs.
For recovery, collect a longer run at the same settings spanning the observed
return. Do not call a stable run a degradation test. Do not generate artificial
load against household devices. No script moves the user, unplugs tethering,
disconnects an interface or changes settings. **Deliberate disconnection, blocking,
reconfiguration or other disruptive action requires a new exact proposal and
explicit approval before execution.** No such action is part of these commands.

Optional physical verification requires **fresh explicit approval** for the exact
interfaces, pinned endpoint, duration, packet filter and snapshot length. Do not
reuse Phase 3 approval or its fixed-1.1.1.1 capture helper for this endpoint. After
approval, a separately supervised capture can correlate each new request's tuple,
TCP handshake and payload on both interfaces using Phase 3's offline PCAP parser.
Until a separately reviewed per-flow verification report exists, leave Phase 4
rows unverified. No capture command is automatically executed or proposed as an
ordinary setup prerequisite.

Demo: open Phase 3's dashboard to explain its four historical confirmed flows;
then open this Phase 4 dashboard, choose a completed actual observation, show raw
inputs/calibration, application scoring basis, outcome status and both signed
contrasts. Explain unavailable metrics and missing contemporaneous capture.
SmartConnect can select a socket for subsequent new traffic; it cannot move an
existing TCP/video session. Selection cannot fix degradation of both paths, server
limits or missing observations. Do not claim improved real application QoE from
this proxy experiment.

## Committed observation and audit commands

The initial non-disruptive run is `mac_hub/phase4/evidence/stable_observation`.
It contains raw measurements, 128 actual request records, 32 decision rounds,
source snapshots as executed, and derived comparison outputs. All physical egress
is unverified. See `RESULTS.md` for findings and scope. The initial dry-run fixture
at `mac_hub/phase4/evidence/dry_run` contains no real measurements or performance
claims. Its creation preceded final source-snapshot instrumentation; its manifest
records code hashes, not a complete source snapshot. The stable observation has
matching snapshots; later runner versions save them automatically. Derived reports
use the final analysis code, which is audited independently of collection snapshots.

```sh
python -m mac_hub.phase4.report mac_hub/phase4/evidence/stable_observation --audit-only
python -m mac_hub.phase4.report mac_hub/phase4/evidence/dry_run --audit-only
```

The audit regenerates numerical tables and REPORT.md in a temporary directory
and compares their bytes, in addition to raw data integrity and causal policy
replay. It does not turn binding intentions into physical-egress confirmation.

The dashboard defaults to `mac_hub/phase4/evidence/stable_observation` (actual
requests, unverified egress). Its dry-run preset selects
`mac_hub/phase4/evidence/final_dry_run` (no traffic, complete source snapshots).
The earlier `dry_run` fixture is retained as preparation evidence, not a live run.

```sh
python -m mac_hub.phase4.report mac_hub/phase4/evidence/final_dry_run --audit-only
```

Calibration failures do not prove the whole interface is down. If ICMP remains
reachable but the endpoint's HTTP service fails, the current controller can still
recommend that path under its fallback policy. These failures remain in outcome
logs; this framework does not supply service-specific failover guarantees.
