# Final Phase 2 methodological verification

Original commit 0017b0d was pushed before review. Review fixes remain on codex/mac-hub-phase2. No network probes or configuration changes were performed during this review.

## Findings and fixes

- The original per-run audit did not recalculate aggregate, paired or event-response tables and could overlook numeric-to-missing corruption after a checksum update. The expanded audit fixes both gaps and includes an independent standard-library numerical implementation. All original numerical tables passed.
- Undefined sample SD was displayed using zero-length error bars. Undefined SD now remains missing and has no error bar; this does not alter any measured/simulated metric. Measured timelines are labeled observational captures rather than noise seed −1.
- Reports are now rendered from the serialized CSV evidence; loss is shown to three decimal places to avoid hiding small trade-offs. Poster wording distinguishes whole-run averages from the two response-period observations.
- All eight numerical CSV artifacts are byte-identical to 0017b0d. The decision policy, scenario inputs, seeds, measured traces and timing definitions were not retuned.

## Cellular degradation: actual policy limitation

Across all ten seeds and both profiles, SmartConnect recommends cellular at 30 seconds, retains it at 100 and 105 seconds despite degradation beginning at 100, and recommends Wi-Fi at 110 seconds. Guardrail rescue still requires the three-window hold; a reachable degraded path does not trigger the immediate unavailability exception. These are two observed guardrail-violation windows in every SmartConnect run, versus zero for Wi-Fi-first.

Whole-run means: Wi-Fi-first RTT 47.982921 ms versus SmartConnect 44.675321 ms; loss 0.051667% versus 0.155000% (an increase of 0.103333 percentage points); RTT variation 4.002296 versus 4.263561 ms. Lower whole-run RTT reflects earlier use of faster cellular, not improved quality during the degradation interval. This is not an overall QoS improvement and cannot be called an achieved QoE improvement. A future separately evaluated safety-policy change may be warranted; no such change was made to improve these reported results.

## Six-scenario check

Both profiles have identical outcomes on the current evidence. Table cells are cross-seed means for either profile; all six scenarios use the same policy, timestamp cadence and selected-window definitions.

| Scenario | RTT baseline → SmartConnect (ms) | Loss baseline → SmartConnect (%) | Direct recommendation changes baseline → SmartConnect |
|---|---:|---:|---:|
| cellular_degradation | 47.983 → 44.675 | 0.052 → 0.155 | 0 → 2 |
| congested_wifi | 78.761 → 35.785 | 3.131 → 0.137 | 0 → 1 |
| deteriorating_wifi | 87.427 → 34.269 | 4.146 → 0.077 | 0 → 1 |
| network_unavailability | 25.224 → 25.224 | 0.048 → 0.048 | 1 → 1 |
| stable | 21.983 → 21.983 | 0.052 → 0.052 | 0 → 0 |
| wifi_recovery | 56.288 → 30.546 | 2.191 → 0.076 | 0 → 2 |

All selected-metric denominators match between policies within each current trace/profile: 90 synthetic windows except network unavailability (75 observed, 15 no-recommendation windows); the two measured captures have one and six observed windows. There is no quality-only comparison hiding a differential no-path rate in this dataset. Future comparisons must still examine denominators and no-path counts.

## Missingness and profiles

All RSSI, throughput and application-jitter cells are blank, not zero. Missing selected RTT/loss/variation stay missing and have explicit observed-window counts. Guardrail compliance is incomplete for all 248 policy-runs, so no full QoE pass rate is claimed. Unavailability and probe errors are separate states; none is not proof of internet outage.

Video Call RTT/loss weights 0.30/0.30 and File Download 0.15/0.15 both normalize to 50%/50%. Original profile coverage is 60% versus 30%. Scores are therefore identical on identical complete inputs; trends and rankings match. Different guardrails can produce different recommendations, demonstrated by tests, but do not do so in these generated results. File Download cannot assess capacity.

## Timing and transitions

Independent recomputation confirms three five-second observations at onset, onset+5 and onset+10 produce a ten-second hold response, not fifteen seconds. Congestion and cellular degradation respond after 10 s; gradual Wi-Fi deterioration averages 21.5 s; recovery averages 70.5 s from recovery onset. Unavailability responses are zero at the same synthetic observation, not actual instantaneous handovers. Wi-Fi-first already-on-target cases remain flagged, and unobserved responses remain blank/censored before the next event.

Recommended handovers count direct path-to-path transitions only, excluding initial attachment, transitions to none and reattachments. Network unavailability has one direct change, one outage entry and one reattachment per policy/run. Quiet-region changes and short reversals remain stability proxies rather than proof of unnecessary switching.

## Numerical verification and remaining limits

All 248 policy-run summaries, all eight CSV tables, per-run and cross-seed statistics, original input hashes, fairness, causal replay and rendered report have passed audit. The poster values were checked against aggregate.csv and response_summary.csv; review exposes the cellular loss harm rather than omitting it. All 29 automated tests passed, including checksum-consistent corruption tests.

Synthetic assumptions are not calibrated field conditions. Seeds quantify modeled-noise sensitivity rather than independent field trials. The one-window and six-window measured captures remain separate observational samples; both policies recommend Wi-Fi throughout and show no selected-path difference. No measured real-world improvement, session continuity, automatic switching, application QoE or verified 5G radio access has been demonstrated.
