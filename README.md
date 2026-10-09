# SmartConnect — Application-Aware Smart Handover Between Wi-Fi and a 5G-like Network

University competition project investigating how network quality and application
needs can improve handover decisions. This Student 1 contribution supplies the
network simulation, reproducible traces, and a Strongest Signal First baseline.
Student 2's application-aware algorithm is not implemented here.

## Simulation assumptions

All values are **realistic simulation assumptions, not measured real-world
results**. This is a synthetic trace generator, not a radio emulator or proof of
real 5G performance. Both paths are assumed available for observation at every
step. Throughput represents assumed available capacity, not achieved application
goodput. No traffic generator, outage model, handover delay, or handover cost is
included. Time is an abstract simulation step (0–99); no physical sampling period
is asserted.

The model adds small, zero-mean Gaussian noise to deterministic scenario curves;
it does not generate unrelated network conditions at each step. Individual samples
can briefly move against the overall trend. The noise is independent per metric
and step, rather than a calibrated model of cross-metric or temporal correlation.
The 5G-like RSSI is an illustrative comparable signal value, not cellular RSRP;
raw real-world Wi-Fi and cellular signal measurements are not interchangeable.

| Scenario | Wi-Fi assumptions before noise | 5G-like assumptions before noise |
| --- | --- | --- |
| `leaving_wifi` | RSSI −45 → −84.6 dBm; latency 20 → 74.45 ms; loss 0.1 → 4.555%; jitter 4 → 25.78 ms; throughput 80 → 20.6 Mbps | Stable around −68 dBm, 35 ms latency, 0.5% loss, 8 ms jitter, 55 Mbps |
| `congested_wifi` | RSSI stays around −52 dBm. Through step 30: latency 22 ms, loss 0.15%, jitter 5 ms, throughput 75 Mbps. Then progressively reaches 91 ms, 4.98%, 29.15 ms, and 23.25 Mbps | Stable around −69 dBm, 36 ms, 0.5%, 8 ms, 52 Mbps |
| `large_download` | Usable path: −58 dBm, 25 ms latency, 0.4% loss, 6 ms jitter, 35 Mbps | Usable path: −66 dBm, 38 ms latency, 0.5% loss, 8 ms jitter, 70 Mbps |
| `recovery` | Starts at −45 dBm, 20 ms, 0.1%, 4 ms, 80 Mbps; deteriorates to −80 dBm, 69 ms, 3.95%, 19.75 ms, 27.5 Mbps at steps 49–50; returns to initial conditions | Stable around −68 dBm, 35 ms, 0.5%, 8 ms, 55 Mbps |

Noise standard deviations across scenarios are 1.2–1.5 dB for RSSI,
2–3 ms for latency, 0.12–0.15 percentage points for loss, 1–1.2 ms for
jitter, and 3–4 Mbps for throughput. Exact per-scenario values are in
`scenarios.py`. Values are clamped to RSSI [−95, −30] dBm, latency [1, 300] ms,
loss [0, 15]%, jitter [0, 100] ms, and throughput [1, 150] Mbps.

Congested Wi-Fi deliberately shows why RSSI alone can mislead: strong signal
persists while latency, loss, and jitter rise and capacity falls. Large download
provides a separate throughput tradeoff: 5G-like capacity is approximately double
Wi-Fi capacity despite weaker signal and higher latency.

## Run on macOS

Use the existing environment; do not create another one:

```sh
cd ~/smartconnect
source venv/bin/activate
python simulate.py --scenario leaving_wifi
python simulate.py --scenario congested_wifi
python simulate.py --scenario large_download
python simulate.py --scenario recovery
python simulate.py --scenario leaving_wifi --seed 43
python -m unittest -v
```

Dependencies are already installed in `venv/` and pinned in `requirements.txt`.
If repairing that existing environment is necessary, use
`python -m pip install -r requirements.txt` after activation.
Default duration is 100 steps and default seed is 42 (`config.py`). Seeds must
be nonnegative integers. The runner prints counts, handover times, and artifact
locations instead of dumping all rows.

## Baseline and artifacts

At each step, `baseline.select_network(wifi_rssi, g5_rssi)` picks the larger RSSI:
−50 dBm is stronger than −70 dBm. Ties choose `WiFi`. Output labels are `WiFi`
and `5G` (the latter means the simulated 5G-like path). There is no quality-based
scoring or switching suppression. Noise near the signal crossing can therefore
cause repeated handovers. Initial attachment is not a handover.

Artifacts are saved relative to the project directory even when the script is
launched from elsewhere:

- `outputs/<scenario>_seed<seed>_baseline.csv`: 100 rows with `time`, both paths'
  five metrics, `selected_network`, and a Boolean `handover` flag.
- Metric columns are `wifi_rssi`, `wifi_latency`, `wifi_loss`, `wifi_jitter`,
  `wifi_throughput` and matching `g5_` columns. Units are dBm, ms, %, ms, Mbps.
- `plots/<scenario>_seed<seed>_<metric>.png`: five Wi-Fi vs 5G-like comparison
  plots per run, including jitter. All are labeled simulated-data verification.
- Rerunning the same scenario and seed overwrites its artifacts. Different
  scenarios or seeds have distinct filenames.

## Reproducibility and Student 2 handoff

```python
from scenarios import generate_scenario
from baseline import apply_baseline

trace = generate_scenario("congested_wifi", seed=42)
baseline_result = apply_baseline(trace)
# Give trace.copy(deep=True) to Student 2's future algorithm.
```

The generator uses a fresh local `numpy.random.default_rng(seed)` on each call.
The same scenario, seed, configuration, and dependency versions yield exactly
the same underlying trace regardless of run order. Baseline selection does not
consume randomness or mutate the input. Plotting likewise does not change it.
For fair comparison, generate once and give each algorithm an independent copy
of the same trace, or load the saved CSV and select its original 11 trace columns.
For exact float round trips use `pandas.read_csv(path, float_precision="round_trip")`.
Preserve dependency versions and generator code with experimental results.
Different seeds change the noise, while the deterministic scenario curves stay
fixed; Gaussian noise is not a guarantee of identical individual-step behavior.

`test_simulation.py` checks settings, finite values and bounds, exact repeatability,
input preservation, selection and handover correctness, and scenario trends over
seven seeds. The four default runs provide the verification CSVs and plots.
Student 2 should add normalization, application-aware weighting, trend scoring,
QoE guardrails, hysteresis, and dwell time separately. None is present in this
Student 1 baseline. Any future handover costs should be applied consistently to
both algorithms and documented separately from these assumed network conditions.
