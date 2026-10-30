# Location pilot P-1 — prepared only, not executed

Purpose: check whether a fixed location B actually worsens en0 Wi-Fi relative to
A, while en6 remains a usable, reasonably stable comparison path. This is an
active diagnostic with read-only network operation, not policy benchmarking.
It does not execute the full 384-request workload, change network settings,
apply recommendations, or run packet capture. Existing Phase 4 files are untouched.

## Scope and manual sequence

Three stationary stages: **A_before → B → A_return**. At each stage collect four
10-packet ICMP windows per interface and eight small HTTPS requests, four per
interface. Total: **240 ICMP echo attempts, 24 fresh HTTPS requests, at most
1.5 MiB requested response bodies**, plus normal protocol/retransmission overhead.
All HTTPS requests use the same pinned public IPv4 and 64 KiB object. No retries.
Normally around 3–4 minutes including movement/settling; failures may take longer.
Five-second HTTPS deadlines bound each request. Preparation and offline
analysis do not create application traffic; each `pilot_https` call explicitly
opts in to eight requests. No router/device stress traffic.

Choose A at your normal good-Wi-Fi position. Mark B at one nearby, safe indoor
position farther from the router or across an existing wall. Keep the Mac lid
open and USB cable connected. Do not wrap equipment or switch Wi-Fi off. Prefer
a stationary iPhone if the existing cable comfortably reaches; otherwise carry
it in the same orientation. Record which arrangement you used. Moving the phone
can change cellular conditions; the pilot explicitly screens for that confounder.

Stay still throughout each stage. Move only after its command has finished.
After each move, wait 10 seconds for settling, then start the next stage manually.
Do not keep searching farther away during a stage. Your Mac's ordinary internet
may slow/stall at B; the test client will not move other apps/sessions to cellular.
No other household device is moved, reconfigured, disconnected or targeted.
Stop if household use is affected by the small shared-network test traffic.

To stop: Ctrl-C in the active Terminal; return to A and keep USB attached. Do not
issue the next stage command after cancellation. The ICMP monitor can take up to
16 seconds for its in-flight 10-packet subprocesses to finish; the HTTPS client
has active request cancellation. Save partial logs and report the cancellation.
If ordinary connectivity does not recover at A, stop rather than changing settings.

## Exact commands — for you to run manually when ready; not run by the assistant

One Terminal, kept open for all three stages:

```sh
cd ~/smartconnect
source venv/bin/activate
pilot_dir="$PWD/mac_hub/logs/location-pilot-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$pilot_dir"
pilot_address="$(python -c 'import threading; from mac_hub.phase4.run import resolve; addresses=resolve(threading.Event()); assert addresses, "No public IPv4 endpoint resolved"; print(addresses[0])')"
printf 'Pilot directory: %s\nPinned HTTPS IPv4: %s\n' "$pilot_dir" "$pilot_address"
printf '%s\n' "$pilot_address" > "$pilot_dir/endpoint-ipv4.txt"
```

`mac_hub/logs` already exists in this installation. If directory creation or DNS
resolution fails, stop; do not run further commands or substitute an unrelated
address. DNS is an ordinary bounded lookup, not a DNS configuration change.

Define these two helpers; neither changes network configuration. Run each stage
command separately, proceeding to HTTPS only after ICMP completes normally:

```sh
pilot_icmp () {
    python -m mac_hub.run --wifi en0 --cellular en6 --target 1.1.1.1 --count 10 --cycles 4 --pause 2 --output "$pilot_dir/${1}-icmp.csv"
}
pilot_https () {
    python -m mac_hub.traffic.run_stage_a --execute --interfaces en0 en6 en6 en0 en6 en0 en0 en6 --address "$pilot_address" --server-name speed.cloudflare.com --path '/__down?bytes=65536' --timeout 5 --pause 1 --output-dir "$pilot_dir/${1}-https"
}
```

The ICMP CLI prints recommendations but **only logs them**. The HTTPS sequence
is fixed manually, unrelated to any recommendation. It alternates pair order
AB/BA/BA/AB, four attempts on each path. ICMP and HTTPS collection happen
sequentially within each stationary stage; they are not simultaneous measurements
of the same instant. All stages use the same endpoint/sequence/settings.

1. At A, remain stationary and execute:

```sh
pilot_icmp A_before
```

After normal completion (not cancellation), run separately:

```sh
pilot_https A_before
```

2. When it finishes normally, manually move to B, keep USB attached, wait 10
seconds while stationary, then execute:

```sh
pilot_icmp B
```

After normal completion (not cancellation), run separately:

```sh
pilot_https B
```

3. When it finishes normally, manually return to A, wait 10 seconds while
stationary, then execute:

```sh
pilot_icmp A_return
```

After normal completion (not cancellation), run separately:

```sh
pilot_https A_return
```

New CSVs and request directories are exclusively created; existing evidence is
not overwritten. Write a short `notes.txt` in this pilot directory recording A/B
locations, phone stationary/moved, approximate move times and any unusual activity.
Do not run a cancelled stage again with the same label or overwrite it; retain
partial evidence and use a new pilot directory for a separately agreed repeat.

## Offline numerical summary (no traffic)

After all three stages complete, run this in the same Terminal. It saves
`pilot_summary.csv` with counts and medians. A successful HTTP response counts as
a valid goodput observation only if exactly 65,536 body bytes were received.
Missing/error values remain blank, never zero. HTTPS goodput includes full fresh
TCP/TLS/server/request duration; it is not sustained link capacity. The requested
path is not independently packet-confirmed.

```sh
python - "$pilot_dir" <<'PY'
from pathlib import Path
import sys
import pandas as pd
from mac_hub.phase4.policy import goodput
root = Path(sys.argv[1])
results = []
for stage in ('A_before', 'B', 'A_return'):
    icmp = pd.read_csv(root/f'{stage}-icmp.csv')
    requests = pd.read_csv(root/f'{stage}-https'/'requests.csv')
    for network, interface in (('wifi','en0'), ('cellular','en6')):
        probe = requests[requests.requested_interface.eq(interface)].copy()
        if not probe.source.eq('actual_https').all():
            raise ValueError('Expected real pilot requests, not a dry-run dataset')
        valid = probe.status.eq('success') & probe.bytes_received.eq(65536)
        successful = probe[valid]
        goodputs = [goodput(row) for row in successful.to_dict('records')]
        sent, received = icmp[f'{network}_sent'], icmp[f'{network}_received']
        summaries_complete = len(icmp) == 4 and sent.eq(10).all() and received.between(0,10).all()
        results.append(dict(stage=stage, network=network, icmp_windows=len(icmp),
            reachable_windows=int(icmp[f'{network}_status'].eq('reachable').sum()),
            valid_rtt_windows=int(icmp[f'{network}_latency'].notna().sum()),
            median_window_rtt_ms=icmp[f'{network}_latency'].median(),
            median_window_rtt_variation_ms=icmp[f'{network}_rtt_variation'].median(),
            sent=int(sent.sum()) if summaries_complete else None,
            received=int(received.sum()) if summaries_complete else None,
            pooled_loss_pct=100*(sent.sum()-received.sum())/sent.sum() if summaries_complete else None,
            http_attempts=len(probe), valid_64k_successes=int(valid.sum()),
            http_failed_or_wrong_length=int((~valid).sum()),
            median_success_response_ms=successful.request_duration_ms.median(),
            median_bounded_goodput_mbps=pd.Series(goodputs,dtype=float).median(),
            egress_status='unverified'))
summary = pd.DataFrame(results)
with (root/'pilot_summary.csv').open('x') as stream:
    summary.to_csv(stream,index=False)
print(summary.to_string(index=False))
print('Pilot only. Apply the predeclared suitability criteria; no QoE or physical-egress claim.')
PY
```

The summary uses observed failures, not success-only interpretations: inspect
counts before comparing medians. The summary intentionally refuses to overwrite
an earlier summary. Raw ICMP output, request tuples/timestamps, response hashes
and existing CLI manifests remain available beside it.

## Objective suitability criteria, fixed before collection

Use A_before as the same-pilot reference, not the older Phase 4 stable run with a
different body size. Interpret each metric only when it has sufficient valid data.
These screening tolerances are experimental choices, not service standards or
statistical proof. Do not tune them after seeing B.

**1. Adequate baseline and data:** A_before and A_return have four completed
windows and four HTTPS attempts per path; all four baseline-A windows are
reachable and all four baseline-A requests per path succeed with the expected
length. For the gradual-deterioration pilot, require all four B Wi-Fi windows
reachable and at least three valid B RTT windows and three valid Wi-Fi downloads
to use the corresponding medians. Retain every failure; missing data does not
mean good performance. Lack of valid downloads makes the download-based screen
inconclusive; sufficient RTT data can still support an RTT-based screen.

**2. Meaningful Wi-Fi deterioration at B:** either

- Median ICMP window RTT is **at least 20 ms higher AND at least 1.5×** the
  baseline-A median; or
- Median same-size end-to-end download goodput is **at most 60%** of baseline A,
  with at least three valid B downloads.

Report observed packet loss and RTT variation as supporting measurements. Four
10-packet windows give 40 attempted echoes/path/stage and pooled loss resolution
2.5 percentage points when all summaries exist; a single window resolves only
10 points. Zero observed loss is not proof of a zero-loss path. RTT variation is
not application/RTP jitter. Do not use Wi-Fi bars, fabricated RSSI or throughput.

**3. Cellular stays stable enough to be a control:** in all three stages, en6
has four reachable ICMP windows, 40/40 received echoes, and 4/4 valid 64-KiB HTTPS
successes. Both B and A_return median cellular RTT are within
`max(20 ms, 30% of A_before cellular RTT)` of baseline, AND cellular goodput
medians lie between **70% and 130%** of baseline. Failure of this screen means
joint-path variation or unavailable control; do not claim isolated Wi-Fi effects.
The small samples cannot prove stationarity even if this check passes.

**4. Wi-Fi recovers at A:** all four A_return Wi-Fi windows are reachable and
all four requests succeed; median RTT is within
`max(10 ms, 25% of A_before Wi-Fi RTT)` of baseline, AND median goodput is at
least **80%** of baseline. If not, do not assume the original condition returned.

**Decision:** B is provisionally suitable for the full gradual deterioration/
recovery protocol only if checks 1–4 pass. If only goodput deteriorates, it is
principally a File Download condition; Video Call's RTT/loss policy may correctly
hold. If only RTT deteriorates, report that distinction. Even a suitable B does
not ensure cellular wins SmartConnect's actual scoring, guardrails and dwell.
No selection advantage is established by this pilot.

If Wi-Fi becomes unreachable, retain and label it **outage/mixed-condition**
evidence, not clean gradual deterioration; it may motivate a separately approved
availability experiment. If B does not differ, cellular varies too much, recovery
fails, or samples are insufficient, mark this pilot **unsuitable/inconclusive**.
Do not run the full workload automatically, cherry-pick a subset, or silently
repeat locations until a favorable result appears. Review all raw logs before
requesting approval for the full experiment.

## Approval boundary and next step

These are prepared commands for the short pilot only. The assistant has not run
them. No full experiment or privileged capture is authorized by this document.
After you run the pilot, provide the new directory for offline review. Independent
physical egress remains unverified for these new requests; earlier Phase 3 capture
cannot be transferred to them. Preserve the pilot regardless of outcome.
