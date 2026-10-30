# Phase 3 Stage A request outcomes

Fresh IPv4 HTTPS requests only. Confirmed egress requires independent dual-interface packet evidence. A requested interface, bound-index readback or successful HTTP response alone is not proof of egress.

| Interface | Actual attempts | Success | Failed | Timeout (subset of failed) | Cancelled | Capture-confirmed success | Mean successful request duration (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| en0 | 2 | 2 | 0 | 0 | 0 | 0 | 186.814 |
| en6 | 2 | 2 | 0 | 0 | 0 | 0 | 228.689 |

Request duration includes client setup, TCP, TLS, HTTP headers and bounded response body receipt; it is not ICMP RTT or throughput. Failed attempts are reported separately, not replaced with zero latency. No application was migrated, no policy comparison was performed, and no existing TCP/video session continuity was tested.
