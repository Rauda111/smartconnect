# Phase 2: reproducible, decision-only experiments

Start: Phase 1 commit `6b1213d`; branch: `codex/mac-hub-phase2`. No merge into main. The Cisco prototype, original simulation, historical results and Phase 1 monitor/decision policy remain unchanged. The Mac dashboard adds an experimental results tab; the existing live workflow remains available.

## Exact reproduction commands

From the existing checkout on the MacBook:

```sh
cd ~/smartconnect
git switch codex/mac-hub-phase2
source venv/bin/activate
# If setting up a new environment first: python3 -m venv venv
python -m pip install -r requirements.txt
python -m unittest -v
```

The committed `results/` contains the completed run. Generate a fresh directory to reproduce it (all 10 seeds are the default):

```sh
python -m mac_hub.experiments.run \
  --measured mac_hub/experiments/measurements/quiet_capture_20261030.csv \
  --output-dir mac_hub/logs/phase2-reproduction
python -m mac_hub.experiments.audit mac_hub/logs/phase2-reproduction
python -m streamlit run mac_hub/dashboard.py
```

In **Phase 2 experiments**, set the experiment results directory to `mac_hub/logs/phase2-reproduction` (or retain `mac_hub/experiments/results` for committed evidence). Select a scenario, application, seed and metric. The live sidebar's CSV path remains separate. Offline evaluation/dashboard/audit do not initiate probes.

For a quick two-seed development run, use a fresh output directory and `--seeds 0 1`. `--no-smoke` omits the Phase 1 one-window capture. Repeat `--measured PATH` to include more independent captures, each reported separately; do not concatenate runs with reset elapsed times. Existing output directories are refused to preserve evidence. Exact numeric CSV reproduction requires the same source, inputs, Python/dependency versions and seed list; plots can vary with rendering libraries/fonts. Manifests record source/input/output SHA-256 hashes and configuration. Compare CSV content, not manifests containing destination/input paths or source revisions.

## Experimental design

The runner generates **six scenarios × ten seeds × two profiles × two policies = 240 synthetic policy-run summaries**, plus four summaries for each measured trace (both policies × both profiles). Each synthetic trace has 90 timestamped observations at five-second spacing. Synthetic timestamps use a fixed UTC epoch to make CSVs deterministic, and do not indicate when real measurements were taken.

| Scenario | Controlled assumed behavior | Annotated event / evaluation |
|---|---|---|
| Stable | Wi-Fi ≈22 ms and cellular ≈38 ms, low loss | No degradation event; quiet-region stability |
| Deteriorating Wi-Fi | RTT, loss and variation gradually rise after 100 s | First cellular recommendation after degradation onset |
| Congested Wi-Fi | Wi-Fi RTT/loss/variation step to ≈95 ms/4%/30 ms at 100 s | Reaction to assumed congestion symptoms, no actual congestion generated |
| Cellular degradation | Initially faster cellular degrades at 100 s | Return recommendation to Wi-Fi; hold-period trade-off |
| Wi-Fi recovery | Gradual degradation, then recovery begins at 275 s | Departure and recovery response, including delayed return |
| Network unavailability | Wi-Fi no-reply at 100 s; cellular probe error at 175 s; Wi-Fi returns at 250 s | Outage exception, no-path periods and reattachment |

Seeded bounded noise varies the assumed metrics; loss is quantized to 0.5 percentage points using **assumed** 200-probe window counts. This synthetic representation is not a packet-level simulation or the real collector's cadence. RSSI, throughput and application jitter remain absent in synthetic inputs too. Scenario `stable_region` labels are predefined evaluation metadata and never given to either policy.

Both policies receive identical timestamps and observations; both profiles start with a fresh Phase 1 engine. No future observations or event labels enter decisions. Wi-Fi-first uses observed probe reachability alone. SmartConnect uses the existing partial RTT/loss profile score, causal five-window trend, guardrails, 0.05 margin, three-window hold and 30-second elapsed dwell. The Phase 1 immediate availability exception remains. No parameters were tuned on these reported outcomes.

Review finding: Phase 1 could score an incomplete reachable pair on a reduced common subset, obscuring missing RTT. The **offline adapter** treats a reachable observation missing RTT or loss as ineligible for SmartConnect, preserving original observations and baseline reachability. It does not change the live Phase 1 engine. Missing application jitter/throughput never becomes an observed pass. Replay validates finite nonnegative metrics, loss ≤100%, known statuses, timezone-bearing timestamps and strictly increasing elapsed time. Real wall-clock/monotonic offsets can differ; policy timing uses elapsed seconds. Clock jumps require splitting or reviewing a trace rather than silently reordering it.

## Metrics and evidence labels

- **Input source**: `synthetic` means generated assumptions; `measured_icmp` means recorded interface-bound probes. The output's `counterfactual_selection_proxy` label applies to both sources: no application was actually moved between interfaces.
- **Selected-path RTT/loss/RTT variation**: arithmetic window means with per-metric observed-window counts. Unknown/no-selected-path values stay blank; no-path windows are separately counted. Means are neither time-weighted nor pooled packet-loss rates. All-loss raw windows remain in observations, even where a policy chooses no path.
- **Recommended handovers**: direct Wi-Fi↔cellular recommendation transitions only. Initial attachment, outage entries and reattachments are separate. The legacy Phase 1 comparison's broader transition count is unchanged and should not be confused with this definition.
- **Response time**: synthetic event onset to first matching recommendation in the event's interval, using actual trace seconds. Already-on-target cases are flagged; an unobserved response stays blank and is counted in `response_summary.csv`. A five-second sampled decision delay is not actual switching delay. Measured traces lack controlled labels and receive no invented event timings.
- **Guardrails**: observed breach windows, unknown windows and fully assessed windows are separate. Video Call checks RTT >60 ms or loss >2%; File Download loss >3%. Video Call jitter and File Download throughput limits remain unknown, so full QoE compliance cannot be claimed.
- **Stability**: quiet-region changes require both adjacent synthetic observations to have quiet labels. This is unavailable for unlabeled measured traces. A→B→A reversals within 30 seconds exclude intervening no-path states. These are operational proxies; neither proves a switch unnecessary.
- **Aggregation**: run-level means summarized across ten synthetic seeds as mean ± sample SD; SD is not a confidence interval. Paired differences are SmartConnect minus Wi-Fi-first within each identical trace/profile. Measured captures remain separate, without artificial seed replication. No confidence or generalization claim is based on correlated windows.

Both profiles have the same normalized RTT/loss weights (50/50), with original profile coverage 60% Video Call versus 30% File Download. They differ in observed guardrails but may give identical results for these scenarios. File Download selection cannot optimize goodput or verify the 20 Mbps capacity requirement. RTT variation is a diagnostic mean absolute difference of adjacent successful echo RTTs, not application jitter, and is not used in the score.

## Artifacts

`results/REPORT.md` is the poster/presentation-ready experimental report. `observations.csv` preserves every paired input once; `decisions.csv` replays both profiles with both recommendations; `per_run.csv` includes quality, missingness and stability counts. `aggregate.csv` gives method summaries, `paired_differences.csv`/`paired_summary.csv` preserve paired deltas, and `event_responses.csv`/`response_summary.csv` preserve successful and censored responses. `plots/` includes scenario timelines/statuses and comparative charts for both profiles. `manifest.json` hashes the package. The audit verifies artifact integrity and recomputes replay and per-run summaries; hand-calculated unit tests provide independent metric checks.

## Safe collection of additional measured traces

Use passive household conditions: record a quiet period, then a period of naturally occurring normal use. You may move only the MacBook and attached iPhone to a normal working location, recording that change in a separate note. Do not disconnect household infrastructure, change router settings, disable interfaces, saturate the link, force congestion, modify routes/DNS/firewall/Internet Sharing, or run the Cisco routing utilities. Controlled degradation is provided by offline scenarios rather than imposed on household devices.

Read-only identification and collection:

```sh
networksetup -listallhardwareports
ifconfig en0
ifconfig en6
python -m mac_hub.run --wifi en0 --cellular en6 \
  --count 30 --cycles 20 --pause 5 \
  --output mac_hub/logs/natural-observation-01.csv
```

This uses two concurrent interface-bound ICMP streams, each at one packet/second during a window. It adds probe traffic but no configuration changes or deliberate congestion. Stop with Ctrl-C if needed. Use a fresh name per capture. `en6` may change after reconnecting the phone: verify names first. Retain CSV and its `.manifest.json`; record device locations, time, target, carrier if known, power mode and ordinary workload in a separate text note. Do not infer cellular radio technology from tethering. Thirty probes still give coarse 3.33 percentage-point loss increments; longer windows improve resolution while delaying decisions.

Replay the same capture for both profiles; no need to recollect once per policy:

```sh
python -m mac_hub.experiments.run \
  --measured mac_hub/logs/natural-observation-01.csv \
  --output-dir mac_hub/logs/with-natural-observation-01
python -m mac_hub.experiments.audit mac_hub/logs/with-natural-observation-01
```

Collect repeated independent sessions and varied permitted targets before drawing field conclusions. ICMP nonresponse can be filtering rather than access failure. Replaying probes ignores switching costs, application load effects and feedback from real switching. No seamless connectivity, automatic network switching, actual handover success, achieved application QoE or verified 5G radio access has been demonstrated by this framework.

## Pre-Phase-3 methodological review

See [verification/FINAL_REVIEW.md](verification/FINAL_REVIEW.md). The reviewed
results preserve all eight original numeric CSVs and the fixed policy. The audit
now checks original inputs, causal replay, independently recomputed per-run,
aggregate, paired and response statistics, and exact report rendering from CSV.
Checksum-consistent corruption and numeric-to-missing substitutions are tested.
Undefined sample SD remains missing and has no error bar.

The cellular-degradation result is a safety trade-off: whole-run RTT decreases
while loss and variation increase, with two observed guardrail-breaching windows
before the hold condition permits the return recommendation. Neither this case
nor the short measured captures demonstrates an overall QoS/QoE improvement.
No policy was retuned to conceal the adverse result. The reviewed suite has
29 passing tests; no new network measurements or configuration changes were
made during the review.
