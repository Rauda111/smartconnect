# Phase 3 results and limits

Branch: codex/mac-hub-phase3 from 44d202e. Stage A was independently verified before Stage B began. All previous Cisco, simulation and Phase 1/2 code/evidence remain unchanged. No default routes, DNS, priorities, firewall, Internet Sharing or router settings were modified.

## Stage A: physical egress established for four requests

The corrected approved capture had clean exits and zero kernel drops. Each request matched its exact source IP/port, destination IP/port, request time interval, outbound SYN, reverse SYN-ACK (ACK = SYN sequence + 1), TCP timestamp options where present, and outbound payload. There were no matching outbound packets on the other physical interface.

| Request ID | Requested interface | Confirmed physical egress | HTTP |
|---|---|---|---:|
| 23bb1cdbd9d548adb35d8b6471559c8f | en0 | en0 | 200 |
| a9773136e56840e3a08c54b68e4caace | en6 | en6 | 200 |
| cc8273fac9e3430fbb2a007792dfd7bb | en0 | en0 | 200 |
| e2add840b97a4833a3e1a6fac9c230a8 | en6 | en6 | 200 |

See `evidence/stage_a_verification/stage_a.json` for per-packet capture times, TCP TSval/TSecr, sequence/ACK numbers, tuple details and hashes. Raw PCAPs remain in ignored local logs; their manifests/hashes and derived evidence are committed. The packet checks validate the exact frozen client backend hash.

## Stage B: actual fresh-request outcomes

Controlled input is synthetic; HTTP requests are real. The live input run uses real interface-bound ICMP. Both modes use the same snapshot for both policies and alternate request order across rounds. Later requests have no concurrent capture because the user explicitly prohibited more capture. Backend validation from Stage A is not misrepresented as per-request confirmation.

| Run / policy | Actual requests | Success | Failed/no path | Requested changes | Mean successful request time (ms) |
|---|---:|---:|---:|---:|---:|
| controlled_report / wifi_first | 16 | 16 | 0 | 0 | 181.458 |
| controlled_report / smartconnect | 16 | 16 | 0 | 2 | 188.115 |
| live_report / wifi_first | 4 | 4 | 0 | 0 | 158.570 |
| live_report / smartconnect | 4 | 4 | 0 | 0 | 155.133 |

SmartConnect requested en0 → en6 → en0 in the controlled run; Wi-Fi-first stayed on en0. The final return was sampled at approximately 65 seconds because the 60-second observation narrowly preceded completion of the actual 30-second dwell since the first change. This illustrates sampling/dwell timing; it was not relaxed to force a favorable response.

The controlled result does not show lower request latency for SmartConnect, nor is it intended as evidence of QoS optimization: the bad Wi-Fi values were synthetic while the real Wi-Fi remained usable. No field QoE improvement or statistical significance is claimed from these short, unreplicated runs.

No failed requests were observed in the final two workloads, including the two requested-change rounds. There is therefore no bracketed failure-gap measurement, not proof of zero interruption. Confirmed Stage B path changes and physical traffic transition delay remain unknown. Existing TCP/video sessions were never migrated.

## Instrumentation and automated checks

44 automated tests passed, covering existing functionality plus dry-run isolation, interface binding failure/readback, unavailable paths, timeout, reconnection/recovery, cancellation, capture startup failure, corrected concurrent shutdown, PCAP parsing/flow correlation, stage gate checks, profile stability, no-path slots, failure-gap calculations and dashboard unknown-state display. The offline audit independently re-correlated all four Stage A flows, checked current backend provenance, replayed recorded decisions, checked common snapshots/order balancing and reproduced both workload reports.

The executed controller source for each actual workload is preserved as controller_source.txt with its recorded source hash. Later validation-only metadata/no-request-label fixes were unit-tested; the actual bound client remained unchanged after Stage A. All unavailable RSSI, throughput and application jitter remain unknown.

## Safe next steps

Use offline audit and dry-run commands in README.md. Any future capture requires new explicit approval. Repeated field captures, application-specific goodput/call-quality workloads and per-request Stage B egress confirmation are still needed before making performance or continuity claims. This prototype directs only its own new test connections, never production applications or system-wide traffic.
