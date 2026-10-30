# Phase 3 Stage B controlled request comparison

Input mode: live. Scope: live ICMP with actual HTTPS. Profile: video_call.

Both policies receive the same per-round observation snapshot. Each makes a separate new GET to the same endpoint, alternating request order across rounds. These are actual outcomes, not identical counterfactual outcomes; sequential timing, TLS/endpoint variability and shared-path contention can differ. This is a functional steering test, not a randomized QoE trial. Summaries retain all attempts, including failures; complete paired-round counts expose any cancellation imbalance.

| Policy | Actual attempts | Success | Failed/no path | Requested path changes | Independently confirmed path changes | Mean successful request time (ms) |
|---|---:|---:|---:|---:|---:|---:|
| wifi_first | 4 | 4 | 0 | 0 | unverified | 158.570 |
| smartconnect | 4 | 4 | 0 | 0 | unverified | 155.133 |

Controlled mode uses explicitly synthetic Wi-Fi deterioration at 5 seconds and recovery at 40 seconds to exercise the real request client without changing actual networks. Its assumed QoS values are not measurements. Live mode instead uses concurrent interface-bound ICMP snapshots; those ICMP probes still do not measure application jitter, RSSI or capacity.

Stage A independently validated this client on en0/en6, but does not establish the egress of each later request. No new capture was authorized for this comparison. Confirmed traffic transition delay remains unknown; successful responses alone are not egress confirmation.

rounds.csv separates monitoring-window duration from decision-computation duration. requests.csv records dispatch delay after the decision and decision-to-success duration. A bracketed failure gap is a sampled application interruption proxy only if failures occur between two successful attempts; it includes intentional cadence and workload time and is not network outage duration. With no failures, there is no measured failure gap, rather than proof of zero interruption. No existing connections, downloads or calls were migrated.
