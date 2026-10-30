# P-1: downstairs location unsuitable — retained negative result

Classification: **unsuitable_location**. Independent offline audit reproduced all
six `raw/pilot_summary.csv` rows from stored ping text and request records. Every
ping window had 10 unique echo replies, giving 240/240 overall; all 24 HTTPS
records show HTTP 200 and exactly 65,536 completed body bytes (1.5 MiB total).
No actual new-traffic egress is packet-confirmed. Recorded binding indexes and
source tuples are socket evidence only. Response-body digests are recorded but
cannot be independently recomputed because bodies were not retained.

| Median metric | A before | Downstairs B | A return |
|---|---:|---:|---:|
| Wi-Fi mean-window RTT, ms | 15.27935 | 14.66875 | 21.05350 |
| Wi-Fi bounded-object goodput, Mbps | 2.329828 | 1.904179 | 1.908061 |
| Cellular mean-window RTT, ms | 67.28045 | 42.85205 | 82.28170 |
| Cellular bounded-object goodput, Mbps | 1.618779 | 1.637357 | 1.442199 |
| Observed loss, either path | 0% | 0% | 0% |

Predeclared checks, without changing thresholds:

- Wi-Fi RTT change at B: **−0.61060 ms**, rather than ≥20 ms and ≥50% worse. Fail.
- Wi-Fi goodput change: **−18.26955%**, rather than ≥40% worse. Fail.
- Cellular B RTT shift: **−24.42840 ms**, outside ±20.184135 ms. Cellular stability
  screen fails even though its RTT improved. Cellular goodput and return RTT
  remain inside their specified tolerances; all reachability/success checks pass.
- Wi-Fi return RTT is within 10 ms and return goodput is **81.89710%** of baseline,
  satisfying the original ≥80% recovery tolerance. This does not establish recovery
  from an induced degradation: the manipulation check itself failed.

The timestamps span 789.96 seconds from initial ICMP creation to final HTTPS
completion, rather than a tightly timed 3–4-minute sequence. The gap from initial
HTTPS end to B ICMP creation is 434.23 seconds; from B HTTPS end to return ICMP
creation is 171.87 seconds. These are recorded gaps, not measured walking times.
ICMP and HTTPS also ran sequentially within each stage. No notes file documents
phone movement, exact locations, settling or other traffic. Ordinary temporal and
cellular variability therefore remain confounders. Four samples per path/stage
are screening data, not population estimates. Zero observed loss is not proof of
zero underlying loss; RTT variation is not application jitter.

This pilot used a fixed manual HTTPS interface sequence, not decision-driven
application selection. ICMP-only recommendations do not turn it into a paired
SmartConnect/Wi-Fi-first workload or demonstrate a handover/QoE benefit.

## Preservation and reproduction

`raw/` is a byte-for-byte copy of all 14 original files from
`mac_hub/logs/location-pilot-20261030T175502Z`. Originals were not edited.
`preservation.json` records their SHA-256 digests. Hashes were established during
this audit, not signed at collection. Collection manifests reference commit
`7bd12b0f7872b592e0f2e3ef95078ed87fb2f12e`; recorded source hashes match the
corresponding Git objects. The recorded Python platform string is an x86_64
compatibility report; it does not independently attest native M1 execution or
the actual macOS marketing version.

`audit.json` contains full-precision numerical checks and stage timestamps.
The auditor uses independent stdlib ping-text parsing, packet-count checks,
adjacent-sequence RTT differences, request timing/body-size/order validation and
recorded-duration goodput calculations. It checks every numeric summary column,
all preserved hashes, and source provenance. It establishes consistency of saved
measurements, not independent network observation or authenticated body content.

```sh
cd ~/smartconnect
source venv/bin/activate
python -m mac_hub.phase4.pilot_audit mac_hub/phase4/evidence/location_pilot_20261030T175502Z
```

The original pilot protocol is preserved at `../../PILOT_LOCATION_CHECK.md`.
Retain this unfavorable manipulation result in the competition evidence. Do not
run the full downstairs-location workload or relabel these data as deterioration.
The proposed replacement is in `../../CONTROLLED_AP_EXPERIMENT_PLAN.md` and has
not been executed or approved for network configuration/capture.
