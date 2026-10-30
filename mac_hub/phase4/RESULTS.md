# Phase 4 initial observation: what the evidence supports

The non-disruptive stable observation completed on 30 October 2026 using the
already connected en0/en6 interfaces. Collection took 218.31 seconds. It delivered
12.5 MiB of response bodies within the 16 MiB requested-payload ceiling. No sudo,
packet capture, interface disruption or network configuration changes were used.

There are 32 decision rounds (four trials × four cycles × two profiles), 64
pre-decision calibration requests and 64 policy outcome requests. All 128 HTTPS
requests succeeded. Both policies selected Wi-Fi in every round; recommended path
changes were zero. No Phase 4 flow has contemporaneous physical-egress proof.
Successful bound requests are actual application traffic, not synthetic outcomes.
Phase 3's four historical packet-confirmed flows remain separate evidence.

Mean successful response duration (SmartConnect / Wi-Fi-first): File Download
216.98 / 216.90 ms; Video Call responsiveness proxy 187.46 / 192.83 ms. The download
comparison is slightly unfavorable in response duration, while its mean bounded
goodput is slightly favorable (4.885 / 4.864 Mbps). Video Call's signed response
contrast is favorable, but **both requests used the same requested Wi-Fi path**.
These are timing controls, not evidence that network selection improved QoE.

See the reproducibly generated `evidence/stable_observation/REPORT.md`,
`summary.csv` and `contrasts.csv` for all values and exploratory trial-cluster
intervals. Even the Video Call response interval excluding zero cannot establish a
selection benefit on identical selected paths. Four adjacent trials on one host,
sequential requests, endpoint variation and scheduling limit uncertainty estimates.
No post-hoc parameter tuning or exclusion of unfavorable observations was applied.

The initial observation validates collection, paired workload execution and causal
policy integration under these observed conditions. It does **not** experimentally
validate adaptation through Wi-Fi deterioration, unavailability or recovery.
Those behaviors have automated offline tests; additional actual natural-condition
runs are required. There was no observed failed-request sequence from which to
estimate a bracketed disruption gap. Existing-session interruption and physical
transition latency are unmeasured, not zero.

## Practical guidelines supported by this work

* Retain Wi-Fi when it remains the selected path under both policies; same-path
  differences set a noise/control reference before claiming selection gains.
* Use equal-sized, recent, pre-decision probes on both paths. Keep failed probes
  missing and compare like metric coverage. Small-object goodput includes setup;
  it cannot establish sustained access-link capacity.
* Publish failures, unavailable slots and unfavorable response/goodput results
  alongside complete-success averages. Keep stability settings fixed in advance;
  investigate guardrail-versus-dwell tradeoffs using held-out adverse traces.
* Validate physical egress separately for new traffic. Neither socket readback nor
  historical capture confirms a new flow. Maintain strict separation of measured
  ICMP inputs, actual HTTP outcomes, dry runs, synthetic replay and captured flows.
* Before competition claims, repeat natural adverse/recovery conditions and
  independent sessions/days. Require policy-divergent paired outcomes and
  contemporary capture for physical-switch claims. Video-call QoE needs an actual
  application experiment; this HTTPS responsiveness proxy cannot supply it.

## Completion and limits

Implemented: bounded read-only runner, distinct measured-input application adapter,
balanced repeated pairs, raw logs and timing, uncertainty/failure analysis, plots,
read-only dashboard, offline evidence audits and cancellation/recovery tests.
Preserved: all Phase 1–3, simulation and Cisco files/results.

Pending experimental evidence: real adverse-condition and recovery comparisons,
packet-confirmation of these new flows, and actual video/session-level QoE. No
system-wide switching, existing-session migration or router interference is
implemented or claimed. The exact repeat/demo/approval protocol is in README.md.
