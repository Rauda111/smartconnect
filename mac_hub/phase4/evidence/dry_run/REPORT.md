# Phase 4 paired application evidence

Mode: dry_run; operator condition label: stable_observation.
No contemporaneous capture: all requested interfaces remain physically unverified.
Body goodput = delivered body bits / full fresh HTTPS duration, including TCP/TLS/server time. Not capacity.
Response metric is successful full-request duration, not video latency or QoE.
Paired difference = SmartConnect minus Wi-Fi-first; lower response time / higher goodput is favorable.
Contrasts require both successes; inspect failure and no-eligible counts for survivor bias.
Same-requested-path pairs are timing controls: differences there cannot establish a network-selection benefit, even if a small exploratory interval excludes zero.
95% percentile bootstrap resamples trial means (seed 2026); suppressed below four trials. Trials on one host are not independent populations.
Failure gap spans successful completions bracketing failed slots, includes cadence/other traffic; absent gap means unknown disruption, not zero interruption.
Direct recommended path changes exclude initial attachment and unavailable transitions; no confirmed handover or existing-session metric.

```
  application       policy  slots  actual_attempts  successes  failures  no_eligible_slots  mean_success_response_ms  mean_success_goodput_mbps  recommended_path_changes  availability_transitions  max_failed_slot_streak max_bracketed_failure_gap_ms  packet_confirmed_requests
file_download smartconnect      4                0          0         0                  4                       NaN                        NaN                         0                         0                       0                         None                          0
file_download   wifi_first      4                0          0         0                  4                       NaN                        NaN                         0                         0                       0                         None                          0
   video_call smartconnect      4                0          0         0                  4                       NaN                        NaN                         0                         0                       0                         None                          0
   video_call   wifi_first      4                0          0         0                  4                       NaN                        NaN                         0                         0                       0                         None                          0
```

```
 same_requested_path_pairs  different_requested_path_pairs   application              metric  paired_successes  trials  smart_minus_wifi_mean cluster_bootstrap_low cluster_bootstrap_high
                         0                               0 file_download request_duration_ms                 0       0                    NaN                  None                   None
                         0                               0 file_download        goodput_mbps                 0       0                    NaN                  None                   None
                         0                               0    video_call request_duration_ms                 0       0                    NaN                  None                   None
                         0                               0    video_call        goodput_mbps                 0       0                    NaN                  None                   None
```

No missing values are replaced with zero. No achieved QoE improvement is asserted. Favorable and unfavorable signed contrasts are retained.
