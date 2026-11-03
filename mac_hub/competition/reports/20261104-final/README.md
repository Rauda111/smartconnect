# Sanitized competition evidence — 4 November 2026

Derived offline from retained originals; no new traffic. Raw evidence is privately
archived and is intentionally NOT included in this public report directory.
windows.csv contains 46 window summaries; requests.csv contains 44 actual request
records stripped of source IPs/ports, MACs, request IDs and raw errors. The original
SHA-256 hashes are in provenance.json; the public files cannot authenticate raw
collection or reconstruct omitted private fields. All numbers retain original
units/precision; missing RTT/goodput remains blank rather than zero.

| Run | Windows | Selected HTTPS success/attempts | Recommendation changes |
|---|---:|---:|---:|
| dorm-continuous-20261103 | 18 | Not measured | 2 |
| smartconnect-smoke-20261103T202919Z | 6 | 6/6 | 0 |
| smartconnect-natural-20261103T203950Z | 6 | 6/6 | 0 |
| smartconnect-movement-20261103T205000Z | 8 | 8/8 | 0 |
| smartconnect-download-20261103T211238Z | 8 | 7/8 | 1 |

The natural run is complete and uncancelled. Its six selected requests used en0.
The download run contains 16 calibration attempts (13 successes) and 8 selected
outcomes (7 successes). Windows 1–6 select Wi-Fi; Windows 7–8 select cellular.
Window 6 selected outcome timed out; both cellular-selected outcomes succeeded,
HTTP 200, exactly 65,536 bytes, in 224.694958 ms and 193.062458 ms. All 24 requests
recorded binding readback. Overall: 20/24 completed successes; failed/partial body
bytes remain unknown, not zero. Known completed bodies total 1.25 MiB.

The change at download Window 7 uses the availability exception after Wi-Fi had
0/10 ICMP replies and its calibration connection failed. Goodput comparison had
fallen back to RTT/loss after a calibration timeout at Window 6. It is not a
completed proactive goodput-based hold. Wi-Fi-first makes the identical selections
in this run; no separate baseline HTTPS outcomes were executed.

The movement run's W3/W4 cellular advantage reached 1/3 and 2/3 hold, but W5 Wi-Fi
recovery reset it. Remaining on Wi-Fi is not proof of optimal QoE. Dorm continuous
is historical measured-ICMP decision evidence only; it has no HTTPS outcomes.
Its Wi-Fi W15 ping summary includes a late RTT omitted from individual reply lines;
stored parsed mean undercounts that delay. No original measurements were rewritten.

Plots show measured window samples; connecting lines do not imply observations
between windows or during movement pauses. Missing RTT remains a gap. Location
stages are unassigned because actual movement timestamps were not recorded.
64 KiB object goodput includes full TCP/TLS/server/request time, not link capacity.

Binding readback confirms a socket option, not packet-confirmed physical egress.
No seamless session migration, measured handover time, achieved video QoE, verified
5G radio, or universal selection improvement is claimed.

Reproduction: run analysis/export_competition_backup.py with --archive pointing
at the PRIVATE owner-only archive and --output a NEW destination. Never upload
that archive, raw request/event logs, packet captures or Git bundles containing
unreviewed historical raw data. This exporter does not send network traffic.
