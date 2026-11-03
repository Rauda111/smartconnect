# Evidence and limits for the EDGE demo

## Existing measured capture, not a new live run

Bundled `evidence/dorm-continuous-20261103.csv` is a byte-identical copy of the
original local log; original manifest retained. `provenance.json` hashes these
copies at packaging, not a collection-time signature. Evidence is not independently
authenticated. Local original logs were never overwritten. Six-window location
captures are not needed for this replay and have not been repackaged.

18 paired measured ICMP windows to 1.1.1.1, 30 echoes per interface/window;
en0 Wi-Fi and en6 iPhone USB. All paths reachable, no recorded monitor errors.
Wi-Fi receives 512/540 echoes (28 lost, 5.185185%); cellular receives 540/540
(0 observed losses, not a lossless-service guarantee). Stored parsed Wi-Fi
window-mean RTT average 21.011183 ms, cellular 42.407244 ms.

Historical Video Call policy recommends Wi-Fi windows 1–3, cellular 4–17, Wi-Fi 18.
Wi-Fi-first recommends Wi-Fi throughout. Departure at elapsed 139.736369 s
(November 3 23:56:12.142 UAE); return 632.719390 s (November 4 00:04:25.110 UAE).
Both are sampled recommendation changes, not movement, switching or handover
latencies. Movement timestamps were not recorded; location stages remain unknown.
Three-window hold and 30-second dwell apply without retuning.

Counterfactual selected-probe results on identical windows:

| Metric | Wi-Fi-first | SmartConnect |
|---|---:|---:|
| Mean stored selected-window RTT, ms | 21.011183 | 39.393658 |
| Selected echoes received / attempted | 512/540 | 529/540 |
| Pooled selected ICMP loss, % | 5.185185 | 2.037037 |
| Observed RTT/loss breach windows | 8/18 | 2/18 |
| Missing selected RTT/loss windows | 0 | 0 |
| Unknown application-jitter windows | 18/18 | 18/18 |

Source columns: recommended/baseline select *_latency, *_sent, *_received and
*_breaches. This is a loss/RTT trade-off, not universal improvement. No HTTP
outcomes or physical egress were observed in the capture. Do not manufacture
successful replay requests. ICMP response loss cannot locate outbound vs return
loss and is not application packet loss.

Window 15's raw Wi-Fi ping summary counts 29 received but prints 28 RTT lines;
summary average 53.135 ms and maximum 1025.284 ms, versus stored parsed mean
18.414929 ms. All other windows' parsed reply counts match summary counts.
Mean of rounded Wi-Fi summary averages is approximately 22.940111 ms, rather
than the stored 21.011183 ms. Live/replay UI warns about this measurement
limitation; the existing collector and frozen policy were preserved. Future
collector-method changes need separate tests/evaluation, not rewritten evidence.

## New software validation is not a network experiment

Offline tests verify old and new behavior using mocks, deterministic scenarios,
existing raw evidence and Streamlit AppTest. They establish software contracts,
not current link availability, physical egress, current iPhone radio technology,
application performance, session continuity or competition-day resilience.

No new live DNS/ICMP/HTTPS experiment or privileged capture has been run for this
implementation. Historical Phase3 packet evidence confirms four older flows,
not these new sockets or Phase4 traffic. New packet verification must be approved
and performed for new claims. Stage B's expired gate must not be bypassed.

## Remaining validation blockers

1. User approval for the exact bounded live smoke test in README.
2. Confirm current en0/en6 interface identity and endpoint reachability in that
   approved run; offline tests cannot establish them.
3. Separate approval and contemporary packet validation if physical egress/new-flow
   path changes are claimed. No new-log capture importer is implemented.
4. Repeated naturally adverse and recovery conditions for performance claims.
   No policy divergence or request success is guaranteed by the demo.
5. Real application/video-session experiments before any QoE or continuity claim.

No default routes, DNS configuration, firewall, service order, interface state,
university infrastructure or Linux/Cisco utilities are changed by this package.
