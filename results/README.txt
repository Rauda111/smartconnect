SmartConnect final Testing & Data Analysis

Controlled simulation results using realistic assumed Wi-Fi and 5G-like network conditions.

Source: https://github.com/Rauda111/smartconnect
Finalized main commit: ac860776ba1d168cfa2e1dea8a496c9fa086d7d9
Experiment date: 10 October 2026 (Asia/Dubai).
Nine original unit tests must pass before experiments run. See verification/unit_tests.log.

Design
Four scenarios: leaving_wifi, congested_wifi, large_download, recovery.
Ten seeds: 0,1,2,3,4,5,6,7,8,9.
For each scenario and seed: baseline once, SmartConnect/video_call once,
SmartConnect/file_download once. Total: 120 executions, each with 100 steps.
Each baseline is reused in the two application comparisons; this does not double
the baseline sample size. Every mean and sample standard deviation uses n=10.

Package contents
raw_csv/: all 120 native generated CSV files, copied unchanged.
code/: experiment runner, analysis, plotting, and independent audit scripts.
tables/: per-run results, mean/SD, paired differences, handover events, switching
behavior, and paired-input verification. Original full precision is retained.
figures/: repeated-seed Baseline vs SmartConnect figures (PNG and SVG; dashboard PDF).
summary_tables.html: direct comparison tables for every scenario/application.
findings.html: main findings, including slide-ready figures and methodological limits.
source_snapshot/: exact finalized Python source, original tests and pinned requirements.
verification/: all run logs, unit-test log, dependency versions, experiment and
raw checksums, and independent numeric audit. The analysis manifest is at the
package root (analysis_manifest.json).

Metric definitions
Select wifi_* or g5_* values according to selected_network at each CSV row.
Average selected-network latency and jitter: ms. Packet loss: percent (not fraction).
Throughput: simulated available path capacity in Mbps, not achieved download goodput.
Handovers: selected_network transitions; initial attachment is excluded.
Occupancy: count of the 100 equal-duration abstract steps and percentage of those steps.
The source defines no seconds-per-step conversion, physical duration, handover delay,
outage, or handover cost. No seconds, real-world speed, or download-time claims are made.

QoE guardrails are prototype assumptions from finalized smartconnect.LIMITS.
Video call: latency >60 ms, packet loss >2%, or jitter >20 ms.
File download: packet loss >3% or throughput <20 Mbps.
A sample violating any applicable guardrail counts once in the combined rate.
The same application's thresholds evaluate both baseline and SmartConnect.
Threshold equality is allowed. These are not validated service guarantees.

Summary statistics
Calculate each metric separately for each seed, then report the ten-seed arithmetic
mean and sample SD (denominator n-1=9). Error bars show that SD, not confidence intervals.
Paired differences equal SmartConnect minus baseline for identical scenario/seed.
Baseline results may repeat in application panels intentionally.
All 11 network trace columns (time and both paths' five metrics) must match exactly
across the three configurations for every scenario/seed.

Reproduce from a new clone (choose empty raw output directories)
git clone https://github.com/Rauda111/smartconnect.git smartconnect
cd smartconnect
git checkout ac860776ba1d168cfa2e1dea8a496c9fa086d7d9
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m unittest -v

Use absolute paths below, replacing PACKAGE with this extracted package directory,
REPO with the new SmartConnect repository, and NEW_RESULTS with a fresh directory:
python PACKAGE/code/run_experiments.py --repo REPO --results-dir NEW_RESULTS
python PACKAGE/code/analyze_results.py --repo REPO --raw-dir NEW_RESULTS/raw_csv --output-dir NEW_RESULTS
python PACKAGE/code/plot_results.py --results-dir NEW_RESULTS
python PACKAGE/code/audit_results.py --repo REPO --results-dir NEW_RESULTS
python PACKAGE/code/build_report.py --results-dir NEW_RESULTS

The runner invokes the original simulate.py CLI, preserves generated CSV bytes,
refuses stale results, and checks source hashes before and after the experiments.
It does not alter the simulator, RSSI baseline, or SmartConnect logic.
To analyze this package without rerunning experiments, use its existing raw_csv
and an unchanged matching source repo. Generated comparison tables and plots are
derived outputs; original native raw CSV files remain unchanged.

Interpretation
These are controlled synthetic scenarios with realistic assumed conditions, not
measurements from a physical Wi-Fi or 5G network. Small independent Gaussian noise
perturbs fixed scenario curves. Ten seeds measure sensitivity to that modeled noise;
they do not establish real-world generalization. Both paths are observable at each
step. Illustrative Wi-Fi and 5G-like RSSI values are assumed comparable within this
simulator. The model does not calibrate Wi-Fi RSSI against cellular RSRP.
