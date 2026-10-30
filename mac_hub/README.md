# SmartConnect Mac Hub — Phase 1

This separate macOS implementation monitors en0 (home Wi-Fi) and en6 (iPhone USB internet) and recommends a path. It never applies recommendations. There is no route, gateway, DNS, Internet Sharing or firewall modification feature, and no gateway or multi-device functionality. No hardware controller is imported or executed. The iPhone connection is labeled cellular internet; its radio access technology has not been verified.

## Setup and verification on the MacBook

From this checkout (the branch already exists):

```sh
cd ~/smartconnect
git branch --show-current
# Expected: codex/mac-hub-phase1
source venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest test_mac_hub test_simulation test_smartconnect -v
python -m unittest -v
```

For a new environment, run `python3 -m venv venv` before activation. The existing environment here uses Python 3.13.5. Keep the simulation's dependencies and files intact.

Verify interface names and bound connectivity using read-only commands; USB interface numbering may change:

```sh
networksetup -listallhardwareports
ifconfig en0
ifconfig en6
/sbin/ping -n -b en0 -c 30 -W 1000 1.1.1.1
/sbin/ping -n -b en6 -c 30 -W 1000 1.1.1.1
```

Apple ping `-b` binds sending to the named interface. `-I` is not the unicast binding option on macOS; `-m` is not a Linux packet mark here. Do not run the existing Linux hardware route scripts on the Mac. No sudo is expected for Apple ping.

Run a finite verification first, then continuous monitoring in terminal one:

```sh
python -m mac_hub.run --cycles 2 --count 10 --output mac_hub/logs/check.csv
python -m mac_hub.run --wifi en0 --cellular en6 --application video_call --count 10 --output mac_hub/logs/live.csv
```

Output files are exclusively created: use a fresh filename for every run. Ctrl-C stops collection and preserves complete windows. In terminal two:

```sh
cd ~/smartconnect
source venv/bin/activate
python -m streamlit run mac_hub/dashboard.py
```

Open the printed localhost URL. The dashboard refreshes every three seconds and reads completed windows. The default CSV path is `mac_hub/logs/live.csv`; change the sidebar path for another run. It shows both networks, availability, measured RTT/loss, adjacent RTT variation, partial scores, trends, unknown guardrails, explanations and Wi-Fi-first comparison. A stale log triggers a warning. It performs no probes or network configuration itself.

For File Download, stop the monitor and start a fresh run:

```sh
python -m mac_hub.run --application file_download --cycles 30 --count 30 --output mac_hub/logs/download.csv
python -m mac_hub.compare mac_hub/logs/download.csv --output mac_hub/logs/download-comparison.csv
```

## Measurement contract

- Each cycle concurrently starts two `/sbin/ping -n -b INTERFACE` processes to the same IPv4 literal, with one-second probe spacing, a 1000 ms reply-print timeout and a bounded overall timeout. There is no default-interface fallback. The configurable pause is AFTER the measurement windows, not the sampling period.
- Latency means the arithmetic mean of parsed ICMP echo RTTs, not one-way delay. Packet loss is computed from ping's transmitted/received summary, not inferred from process exit alone. Late replies may count in the summary without a printed RTT.
- RTT variation is the mean absolute RTT difference for successfully received **consecutive ICMP sequence numbers within a window**. It excludes gaps and duplicates. Fewer than one adjacent pair means unavailable, never zero-filled. This diagnostic is neither RTP jitter nor one-way IP delay variation, and is not fed into the jitter scoring weight.
- RSSI, application jitter and throughput are null in every real log. They are neither estimated nor simulated. Missing CSV cells mean unknown. `source=measured_icmp` identifies live collection; `source=synthetic_fixture` identifies scenario fixtures.
- A valid all-loss summary is `no_reply` with measured 100% loss and unknown RTT. Missing summary, invalid interface, permission error and subprocess timeout are `error`, with metrics unknown. `no_reply` means no response from this ICMP target during this window; it does not prove internet failure. ICMP can be filtered or deprioritized.
- The per-interface status, counts, adjacent-pair count, command duration, errors, wall-clock UTC completion timestamp, monotonic elapsed time target and raw ping output are logged (CSV readers support quoted multiline fields). Paired probes overlap but are not perfectly simultaneous. A manifest records configuration, revision and source hashes. Keep CSV and manifest together.

## Policy and integration review

Reviewed remote main `5f3d1a0`, including simulation modules, scenario generator, tests, Streamlit app, hardware monitors/controllers, analysis scripts, stored results and documentation. The Packet Tracer binary is preserved; its behavior was not revalidated in Packet Tracer. Existing Cisco hardware and physical switching were not rerun. The historical analysis runner hard-codes a nine-test gate and recorded provenance; it is preserved and is not the Mac Hub experiment runner. The current full suite has 17 tests.

| Property | Simulation (`smartconnect.py`) | Cisco hardware scripts | Mac adapter |
|---|---|---|---|
| Inputs | Five synthetic metrics on both paths | Gateway or end-to-end ICMP, Linux marked paths | Interface-bound public-target ICMP |
| Score | Higher is better, fixed bounds and application weights | Lower is better: RTT + 2×variation + 10×loss | Reuses simulation weights/bounds for RTT and loss only |
| Trend | Latest five scores, 0.5×slope | None | Latest five consecutive valid scores, 0.5×slope |
| Guardrails | All profile limits | No application guardrails | Only measured dimensions; other limits explicitly unknown |
| Stability | 0.05 margin, three samples, eight steps | 20% relative improvement, three samples, 30 seconds | 0.05 margin, three windows, 30 elapsed seconds |
| Failure | Finite complete traces required | Some monitors discard partial responses or zero-fill single-reply variation | Distinct no-reply/error states, no invented values |
| Action | Simulated selection | Separate route-changing utilities also exist | Recommendation only; no actuator |

The adapter imports the existing constants, leaving the complete-data simulator unchanged. It renormalizes RTT/loss weights: Video Call is 50%/50% (60% original weight coverage); File Download is 50%/50% (30% coverage). **Both profiles therefore have identical score rankings with current measurements**, but retain different observed loss guardrails (2% versus 3%); Video Call additionally observes the 60 ms RTT limit. File Download's 20 Mbps capacity guardrail and Video Call's jitter guardrail remain unknown. A partial score is not a full application-suitability score.

Trends use completed windows, not seconds; monotonic elapsed seconds govern dwell. Histories reset on unavailable observations. Initial recommendation prefers an observed-guardrail-passing Wi-Fi path. A candidate must pass observed guardrails and sustain the score margin (or positive advantage rescuing a breached current path). Normal changes require three windows and dwell. Availability loss bypasses these delays, immediately recommending a surviving path that passes observed guardrails, or `none`. This deliberate outage exception differs from the simulator. A currently reachable but degraded path can remain recommended when neither alternative qualifies; inspect the breach fields. Unknown guardrails never count as passes or observed breaches.

## Reproducible comparative method

Wi-Fi-first chooses Wi-Fi whenever its probe status is reachable, otherwise cellular if reachable, otherwise none. It has no score, application preference, hysteresis or dwell. This observable baseline is justified because RSSI is unavailable; it represents preference for home Wi-Fi rather than an invented signal comparison.

Both methods consume the exact same paired windows. CSV includes both recommendations and both paths' measurements. `compare` computes arithmetic sample means of the hypothetically selected RTT, loss and variation, with per-metric observed-window counts; no-path windows are counted separately, never silently assigned zero latency. Observed breach-or-no-path counts use the same profile for both methods and exclude unknown guardrails. Counts are not time-weighted and should not be interpreted as elapsed outage duration. Recommendation transitions are not actual handovers. Comparison output retains input hash and source labels.

Reproduce the five deterministic tests without network manipulation:

```sh
python -m mac_hub.scenarios --output-dir mac_hub/logs/scenarios
python -m mac_hub.compare mac_hub/logs/scenarios/wifi_recovery_video_call.csv --output mac_hub/logs/recovery-comparison.csv
```

These fixtures cover stable paths, deteriorating Wi-Fi, cellular degradation, Wi-Fi recovery and unavailable paths for both profiles. They test policy behavior, not real network performance. For real evidence, run repeated paired captures under described natural conditions, retain raw logs/manifests, record device locations, carrier, target, time, power mode and workload. Use multiple targets in separate runs to assess endpoint sensitivity. Do not change routes to induce scenarios. Repeat each condition and application; report per-run paired differences and between-run spread rather than treating correlated windows as independent experiments. Report unfavorable outcomes and missing-data rates too.

Short windows have coarse loss resolution (10 packets: 10 percentage points; 30 packets: 3.33). The prototype 2–3% thresholds cannot be estimated precisely from such windows. Longer windows improve loss resolution but delay decisions. Tune and validate this tradeoff on separate development captures, then freeze policy before evaluation. Ping adds light probe traffic and does not establish capacity or achieved application QoE.

## Draft evidence-based QoS/QoE guidelines

1. Use delay and loss evidence alongside signal; stored congestion simulation shows why strong signal alone is insufficient. This is a simulation result, not a Mac field result.
2. Retain hysteresis, hold and dwell to limit recommendation oscillation; measure the resulting recovery delay and sensitivity on held-out captures rather than claiming a universal optimum.
3. Do not certify Video Call readiness when application jitter is unknown. Validate with call freeze time, audio gaps, reconnection events and user ratings in a separately authorized application experiment.
4. Do not promise faster File Downloads from ping. Measure controlled, interface-bound application goodput and completion time in a later experiment before enabling throughput-driven choices.
5. Distinguish target nonresponse, probe errors and missing metrics. Prefer explicit no-eligible-path output over a confident recommendation based on fabricated data.
6. Present paired selection-proxy improvements with missing counts, run-to-run variability and degradation cases. A successful Phase 1 demonstrates monitoring and explainable recommendations; it cannot demonstrate seamless sessions, automatic switching or real 5G access.

Next steps: independently validate binding with packet capture, gather repeated real traces, calibrate thresholds and loss windows, add authorized interface-bound goodput/application measurements, then separately design and verify a switching phase with session-continuity tests. Route control remains outside Phase 1.

## Phase 2 experimental framework

See [experiments/README.md](experiments/README.md) for the six-scenario repeated-seed
comparison, measured-trace replay, response timing, stability definitions, static
plots, dashboard results tab, safe collection protocol and exact reproduction
commands. Phase 1 collection and its historical evidence remain available.
