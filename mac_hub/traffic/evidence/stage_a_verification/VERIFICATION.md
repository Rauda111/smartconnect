# Stage A independent physical-egress verification

Gate passed: True. Captures completed with clean exits and zero reported kernel drops.

| Request ID | Requested | Confirmed egress | SYN / SYN-ACK / payload packets | Evidence |
|---|---|---|---|---|
| 23bb1cdbd9d548adb35d8b6471559c8f | en0 | en0 | 1 / 1 / 3 | Exact connection tuple and packet timestamps match SYN, SYN-ACK and outbound payload on the requested physical interface; no matching outbound packets on the other interface |
| a9773136e56840e3a08c54b68e4caace | en6 | en6 | 1 / 1 / 3 | Exact connection tuple and packet timestamps match SYN, SYN-ACK and outbound payload on the requested physical interface; no matching outbound packets on the other interface |
| cc8273fac9e3430fbb2a007792dfd7bb | en0 | en0 | 1 / 1 / 3 | Exact connection tuple and packet timestamps match SYN, SYN-ACK and outbound payload on the requested physical interface; no matching outbound packets on the other interface |
| e2add840b97a4833a3e1a6fac9c230a8 | en6 | en6 | 1 / 1 / 3 | Exact connection tuple and packet timestamps match SYN, SYN-ACK and outbound payload on the requested physical interface; no matching outbound packets on the other interface |

stage_a.json contains exact per-interface flow tuples and UTC epoch packet timestamps for each SYN, SYN-ACK and payload observation. Request/capture manifests and SHA-256 hashes bind the evidence. Packet capture times, handshake sequence/ACK numbers and TCP timestamp-option TSval/TSecr values (when present) are recorded separately; missing options remain unknown. No inference is based solely on source IP, requested binding or successful connection.
