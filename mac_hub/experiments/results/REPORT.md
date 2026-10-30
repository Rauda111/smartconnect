# SmartConnect Phase 2 experimental results

Decision-only evaluation against Wi-Fi-first. No routes or network settings changed. All selected-path results are counterfactual selection proxies, not actual handovers or achieved application QoE.

## Design

Six synthetic scenarios × 10 seeds × two profiles × two policies. Each synthetic trace has 90 timestamped windows at five-second spacing. Both policies receive identical observations; each profile is replayed with a fresh causal engine. Synthetic noise seeds measure sensitivity to assumed conditions, not real-world generalization.

RTT/loss weights renormalize to 50%/50% in both profiles (60% original weight coverage for Video Call, 30% for File Download). Different observed guardrails may produce different choices. Throughput, RSSI and application jitter are absent. RTT variation is evaluated diagnostically and never substituted for application jitter.

## Synthetic outcomes

| Scenario / profile | RTT: Wi-Fi-first → SmartConnect (ms) | Loss: baseline → SmartConnect (%) | Recommended path changes: baseline → SmartConnect |
|---|---:|---:|---:|
| cellular_degradation / video_call | 47.98 ± 0.09 → 44.68 ± 0.07 | 0.05 ± 0.01 → 0.15 ± 0.02 | 0.00 ± 0.00 → 2.00 ± 0.00 |
| cellular_degradation / file_download | 47.98 ± 0.09 → 44.68 ± 0.07 | 0.05 ± 0.01 → 0.15 ± 0.02 | 0.00 ± 0.00 → 2.00 ± 0.00 |
| congested_wifi / video_call | 78.76 ± 0.09 → 35.79 ± 0.12 | 3.13 ± 0.02 → 0.14 ± 0.01 | 0.00 ± 0.00 → 1.00 ± 0.00 |
| congested_wifi / file_download | 78.76 ± 0.09 → 35.79 ± 0.12 | 3.13 ± 0.02 → 0.14 ± 0.01 | 0.00 ± 0.00 → 1.00 ± 0.00 |
| deteriorating_wifi / video_call | 87.43 ± 0.09 → 34.27 ± 0.15 | 4.15 ± 0.02 → 0.08 ± 0.02 | 0.00 ± 0.00 → 1.00 ± 0.00 |
| deteriorating_wifi / file_download | 87.43 ± 0.09 → 34.27 ± 0.15 | 4.15 ± 0.02 → 0.08 ± 0.02 | 0.00 ± 0.00 → 1.00 ± 0.00 |
| network_unavailability / video_call | 25.22 ± 0.09 → 25.22 ± 0.09 | 0.05 ± 0.01 → 0.05 ± 0.01 | 1.00 ± 0.00 → 1.00 ± 0.00 |
| network_unavailability / file_download | 25.22 ± 0.09 → 25.22 ± 0.09 | 0.05 ± 0.01 → 0.05 ± 0.01 | 1.00 ± 0.00 → 1.00 ± 0.00 |
| stable / video_call | 21.98 ± 0.09 → 21.98 ± 0.09 | 0.05 ± 0.01 → 0.05 ± 0.01 | 0.00 ± 0.00 → 0.00 ± 0.00 |
| stable / file_download | 21.98 ± 0.09 → 21.98 ± 0.09 | 0.05 ± 0.01 → 0.05 ± 0.01 | 0.00 ± 0.00 → 0.00 ± 0.00 |
| wifi_recovery / video_call | 56.29 ± 0.09 → 30.55 ± 0.68 | 2.19 ± 0.02 → 0.08 ± 0.02 | 0.00 ± 0.00 → 2.00 ± 0.00 |
| wifi_recovery / file_download | 56.29 ± 0.09 → 30.55 ± 0.68 | 2.19 ± 0.02 → 0.08 ± 0.02 | 0.00 ± 0.00 → 2.00 ± 0.00 |

## Synthetic event response

| Scenario / profile / event | Wi-Fi-first: observed/n, mean delay (s) | SmartConnect: observed/n, mean delay (s) |
|---|---:|---:|
| cellular_degradation / file_download / cellular_degradation_onset | 10/10, 0.00 (already on target: 10) | 10/10, 10.00 (already on target: 0) |
| cellular_degradation / video_call / cellular_degradation_onset | 10/10, 0.00 (already on target: 10) | 10/10, 10.00 (already on target: 0) |
| congested_wifi / file_download / wifi_degradation_onset | 0/10, unobserved (already on target: 0) | 10/10, 10.00 (already on target: 0) |
| congested_wifi / video_call / wifi_degradation_onset | 0/10, unobserved (already on target: 0) | 10/10, 10.00 (already on target: 0) |
| deteriorating_wifi / file_download / wifi_degradation_onset | 0/10, unobserved (already on target: 0) | 10/10, 21.50 (already on target: 0) |
| deteriorating_wifi / video_call / wifi_degradation_onset | 0/10, unobserved (already on target: 0) | 10/10, 21.50 (already on target: 0) |
| network_unavailability / file_download / both_unavailable | 10/10, 0.00 (already on target: 0) | 10/10, 0.00 (already on target: 0) |
| network_unavailability / file_download / wifi_no_reply | 10/10, 0.00 (already on target: 0) | 10/10, 0.00 (already on target: 0) |
| network_unavailability / file_download / wifi_returns | 10/10, 0.00 (already on target: 0) | 10/10, 0.00 (already on target: 0) |
| network_unavailability / video_call / both_unavailable | 10/10, 0.00 (already on target: 0) | 10/10, 0.00 (already on target: 0) |
| network_unavailability / video_call / wifi_no_reply | 10/10, 0.00 (already on target: 0) | 10/10, 0.00 (already on target: 0) |
| network_unavailability / video_call / wifi_returns | 10/10, 0.00 (already on target: 0) | 10/10, 0.00 (already on target: 0) |
| wifi_recovery / file_download / wifi_degradation_onset | 0/10, unobserved (already on target: 0) | 10/10, 21.50 (already on target: 0) |
| wifi_recovery / file_download / wifi_recovery_onset | 10/10, 0.00 (already on target: 10) | 10/10, 70.50 (already on target: 0) |
| wifi_recovery / video_call / wifi_degradation_onset | 0/10, unobserved (already on target: 0) | 10/10, 21.50 (already on target: 0) |
| wifi_recovery / video_call / wifi_recovery_onset | 10/10, 0.00 (already on target: 10) | 10/10, 70.50 (already on target: 0) |

Response delays are conditional on an observed response. Failed responses remain explicitly counted; already-on-target cases are not switching-speed evidence.


Synthetic QoS table values are mean ± sample SD across seed-level summaries; SD is not a confidence interval. See aggregate.csv for variation, guardrail, stability and missing-data results, paired_differences.csv for within-trace differences, and event_responses.csv for response times (including failures to respond).

The cellular-degradation fixture illustrates a trade-off: SmartConnect may temporarily select higher loss and variation while waiting for sustained superiority. Stable and unavailable-path conditions may show no advantage over the baseline. Quiet-region changes can include legitimate initial policy adaptation or recovery; they are not automatically unnecessary switches.

## Measured-input replay

- measured_0_live_smoke_20261030: 1 observed window(s), replayed for both profiles. No synthetic replication or SD is assigned to this capture. Measured inputs are real; selected-path outcomes and policy recommendations remain counterfactual. A one-window smoke capture cannot establish switching delay, stability or performance improvement.
- measured_1_quiet_capture_20261030: 6 observed window(s), replayed for both profiles. No synthetic replication or SD is assigned to this capture. Measured inputs are real; selected-path outcomes and policy recommendations remain counterfactual. A one-window smoke capture cannot establish switching delay, stability or performance improvement.

| Measured capture / profile / policy | RTT mean (ms) | Loss mean (%) | RTT variation mean (ms) | Observed RTT windows |
|---|---:|---:|---:|---:|
| measured_0_live_smoke_20261030 / video_call / wifi_first | 22.498 | 0.000 | 29.265 | 1 |
| measured_0_live_smoke_20261030 / video_call / smartconnect | 22.498 | 0.000 | 29.265 | 1 |
| measured_0_live_smoke_20261030 / file_download / wifi_first | 22.498 | 0.000 | 29.265 | 1 |
| measured_0_live_smoke_20261030 / file_download / smartconnect | 22.498 | 0.000 | 29.265 | 1 |
| measured_1_quiet_capture_20261030 / video_call / wifi_first | 16.228 | 0.000 | 7.506 | 6 |
| measured_1_quiet_capture_20261030 / video_call / smartconnect | 16.228 | 0.000 | 7.506 | 6 |
| measured_1_quiet_capture_20261030 / file_download / wifi_first | 16.228 | 0.000 | 7.506 | 6 |
| measured_1_quiet_capture_20261030 / file_download / smartconnect | 16.228 | 0.000 | 7.506 | 6 |

## Definitions and poster-safe interpretation

- Selected-path RTT, loss and variation are arithmetic means over observed windows; each metric has its own denominator. No-path windows and unknown values are counted separately, never replaced with zero. All-loss measurements remain present in observations even if neither policy recommends that path.
- Recommended handovers count direct Wi-Fi↔cellular transitions only; initial attachment, transitions to none and reattachments are separate. None represents no eligible recommendation, not demonstrated internet failure.
- Response time is from a predefined synthetic event onset to the first observation recommending its expected path, before the next event. Already-on-target cases are flagged; blank delay means no observed response, not zero. These are sampled decision delays, not switching or session-restoration times. Real traces have no event labels and no reported response-time estimate.
- Observed guardrail violations, unknown-guardrail windows and no-path windows are separate. Video Call RTT >60 ms or loss >2%; File Download loss >3%. Application jitter and capacity guardrails are unknown, so no full QoE pass rate is reported.
- Quiet-region path changes (both adjacent observations in a predefined stable region) and A→B→A reversals within 30 seconds are stability proxies. They do not prove a switch was unnecessary. Real traces lack stable-region truth, so that assessment is unavailable.
- Window means and counts are not time-weighted. Correlated windows are not independent experimental replicates. Synthetic five-second cadence and assumed probe counts differ from real monitor windows.

## Conclusion and limits

The framework demonstrates reproducible application-profile-aware recommendations and paired evaluation. Examine all scenarios and both profiles, including recovery delays, unavailable periods and unfavorable trade-offs; there is no universal improvement claim. Phase 1 policy is retained for complete inputs; incomplete RTT/loss replay observations are explicitly ineligible for SmartConnect rather than scored on an accidental subset.

For a poster: “SmartConnect was compared with Wi-Fi-first on identical timestamped traces using partial RTT/loss scoring, trends, guardrails, hold and dwell. Results quantify counterfactual selected-probe quality and recommendation stability under controlled synthetic conditions; real application QoE and switching continuity remain unverified.”

Next: repeated naturally varying real captures, independently verified interface binding, held-out threshold calibration and authorized application goodput/call-quality experiments. No automatic switching, seamless connectivity or verified 5G radio access is claimed.
