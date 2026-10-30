# SmartConnect: poster and presentation notes

**Question:** Can application-profile-aware RTT/loss scoring with trends, guardrails, hold and dwell select better probe-quality paths than Wi-Fi-first without excessive recommendation changes?

**Method:** Six controlled synthetic scenarios, ten noise seeds, both profiles and both policies on identical timestamped observations: 240 policy-run summaries. Also replay two separate measured traces (one and six windows), adding eight summaries. Fixed policy; no actual switching.

**Illustrative result:** In synthetic congested Wi-Fi, Video Call selected-probe RTT was **78.76 ± 0.09 ms** for Wi-Fi-first versus **35.79 ± 0.12 ms** for SmartConnect; selected-probe loss was **3.13 ± 0.02%** versus **0.14 ± 0.01%**. These are mean ± sample SD across ten synthetic seeds and counterfactual selection proxies. SmartConnect recommended one direct path change per run and responded ten seconds after the annotated congestion onset; the baseline never recommended cellular in this fixture.

**Trade-offs:** Stable and unavailable-path scenarios show no selected-probe advantage. Cellular-degradation selected loss rose from 0.05% to 0.15% during the policy's response period, despite lower average RTT. In recovery, SmartConnect's mean return recommendation arrived 70.5 seconds after recovery began; Wi-Fi-first was already on Wi-Fi. Quiet-region changes are not proof of unnecessary switching.

**Measured evidence:** Both policies recommended Wi-Fi throughout the six-window observational capture, with identical selected-probe summaries. This short uncontrolled capture demonstrates collection/replay functionality and does not establish a field improvement.

**Limits:** RTT/loss only; File Download capacity, RSSI and application jitter unavailable. Both profiles share normalized score rankings but have distinct guardrails. No achieved application QoE, seamless continuity, actual handover, automatic switching or verified 5G-radio claim. Next: repeated naturally varying real captures and separately authorized application measurements.

Use `results/plots/comparison_video_call.png` with the source/proxy caption visible. All figures and precise tables are in `results/`; definitions and caveats are in `README.md` and `results/REPORT.md`.
