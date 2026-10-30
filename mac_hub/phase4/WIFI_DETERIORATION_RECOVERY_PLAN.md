# Proposed experiment DR-1 — manual location A → B → A

**Status: plan only; NOT approved or executed.** Collection code remains commit
`7bd12b0f7872b592e0f2e3ef95078ed87fb2f12e`. This local document does not change
that pushed commit. No prior code, results or evidence is overwritten.

## Proposed action and scope of approval

After explicit approval, manually carry the already USB-connected MacBook and
its iPhone from marked location A (the normal good-Wi-Fi position) to marked
location B (a nearby indoor position farther from the existing access point,
preferably across an existing wall), then return to A. Keep the USB cable
connected, Mac lid open, and both devices uncovered. Use safe, stationary surfaces
and a short, unobstructed route. Do not reposition or alter the router, create
interference, wrap devices, close shielding around them, unplug USB or toggle
Wi-Fi. No induced background congestion or traffic to household devices.

Distance and obstructions are plausible attenuation mechanisms, not a guarantee
of worsened packet-level performance. Vendor background:
https://support.apple.com/en-us/102319 and
https://www.tp-link.com/uk/support/faq/468/ . Actual RTT, loss and bounded download
measurements determine whether deterioration happened; Wi-Fi bars are not data.
This is a spatial intervention with a measured response, not a calibrated RF
attenuator or proof of congestion. If B does not cause deterioration, retain the
run as a negative manipulation check; do not relabel it or keep moving farther
until SmartConnect produces a desired result.

Prefer leaving the iPhone stationary if the existing cable comfortably reaches B
without tension. Otherwise carry it in the same orientation with the Mac. Record
which arrangement was used. Moving the phone can change cellular reception, so
both paths are measured throughout; a cellular change makes the test a joint-path
condition, not isolated Wi-Fi degradation. No new hardware purchase is assumed.
If no safe B exists within a short walk, do not substitute disconnection or
network-setting changes: report the location experiment infeasible.

Approval requested for this manual movement plus the bounded workload below
only. **Privileged capture is separate, unapproved and excluded.** No automated
physical action, system-wide handover or existing-session migration occurs.

## What happens to internet access; stop and recover

The Mac's ordinary Wi-Fi can become slow or temporarily unreachable at B.
Browsers, uploads, calls and other existing sessions on the Mac may stall or
fail. Finish/save work and do not run this during a call or important transfer.
SmartConnect binds only its new test requests: it does not transfer ordinary Mac
traffic to cellular or guarantee macOS's own fallback behavior. Other household
devices are not moved, reconfigured, disconnected or targeted. Small test downloads
still share normal Wi-Fi airtime; stop if household use is affected. The iPhone's
data allowance is used for cellular probes and selected requests.

To stop: press **Ctrl-C in the workload Terminal**, return both devices to A,
keep USB connected, and wait for normal Wi-Fi reception. Do not change routes,
DNS, firewall, network priority or router settings as a recovery step. The existing
client aborts its active socket on cancellation; ping monitoring can take up to
nine seconds to finish. Already written data and a cancellation manifest remain.
Also stop the read-only observer with Ctrl-C. Close no privileged process because
none is started. If connectivity does not recover at A, end the test and report
it; do not automatically try configuration changes. Stop early for tether loss,
device heat, cable tension, unacceptable household impact or any safety concern.

## Design fixed before looking at outcomes

Use the existing runner unchanged, four trials, both profiles, 12 cycles per
profile, 64 KiB calibration/download bodies, 16 KiB Video Call responsiveness
bodies, and a 10-second pause between completed cycles. This gives:

- Eight separate profile blocks; fresh controller per block. Each block follows
  A → B → A; never restart the controller between those three stages.
- Cycles 0–3 at A, 4–7 at B, 8–11 back at A (cycle numbers are zero-based).
- 96 planned decision rounds, up to 384 fresh HTTPS requests, 576 ICMP echo
  attempts. Up to 24 MiB requested body budget; if every slot requests/completes its
  planned body, delivered bodies total 19.5 MiB. Wire bytes and unrelated traffic
  are extra; neither number is a cellular billing cap. Failures/no-path slots may
  reduce actual requests/completed bytes.
- Usually roughly 20–30 minutes; failure deadlines can make it considerably longer.
  Stop rather than waiting indefinitely. Do not increase load, timeout or trial
  length during the experiment to obtain a favorable switch.

Both policies share each real concurrent en0/en6 three-packet ICMP window and the
same two completed pre-decision calibration probes. One common resolved IPv4 is
pinned for the run, with unchanged TLS hostname verification. SmartConnect uses
its existing application-specific policy; Wi-Fi-first uses shared ICMP
reachability, with cellular fallback. Preserve the original .05 margin,
three-window hold, five-score trend and 30-second dwell. Real elapsed time governs
stability, not cycle numbers. Failed HTTP probes can cause the documented common
RTT/loss fallback; missing values remain missing. Three-packet loss resolution is
33.3 percentage points; it cannot establish low single-digit loss rates.

The two outcome requests use identical per-profile sizes and endpoint. Their
order alternates by trial+cycle; calibration-interface order also alternates.
Profile order alternates by trial: trial 0 Video then Download, trial 1 Download
then Video, and repeat. Within each of the four-cycle stages each policy is first
twice. They run sequentially on nearby conditions, not simultaneous identical
network states. Report pairing gaps; endpoint variation, motion and probe load
remain possible confounders. Do not compare absolute goodput between the different
body-size profiles. Do not use the earlier 128 KiB stable dataset as an unmatched
causal control for this 64 KiB experiment; each block has its own A-stage control.

### Manual timing — important current-runner limitation

The runner has **no movement barriers, per-cycle prompts or built-in event log**.
The dashboard waits for the final manifest; it is not a live movement cue.
Use the read-only progress observer below. After it reports completion of cycle
3 for the current trial/profile, move A → B during the following 10-second pause.
After completion of cycle 7, return B → A in the next pause. Stay at A after
cycle 11: the next block starts immediately, with no inter-block pause.
Repeat those two moves in every profile block (eight outward and eight return
moves total). Do not move at a policy's intermediate request boundary.

Record departure and arrival in a paper/phone note or a separate event file with
UTC time, trial, profile, origin/destination and any USB/household issues. The
observer prints UTC and epoch times for cues. Cues are NOT actual movement or
arrival timestamps. Missed/late cues make timing inconclusive; do not speed up
movement or secretly restart a block to repair the result. In the observer's separate Terminal tab, the event-marker
command below records UTC/epoch labels with trial/profile; press Enter immediately
before leaving and immediately after arriving. If you cannot safely do that,
record an honest time interval instead; do not invent precision.

If a move overlaps measurement/probe/outcome activity, retain that round but tag
it `transition/mixed`, not pure B or pure recovery. Decide that classification
from event/measurement timestamps, never from which policy performed better.
Complete means all scheduled slots are recorded, not that all requests succeeded.
Do not exclude failed requests to make a stationary stage look better. For a
metric-specific stage estimate, require at least three valid stationary
observations; failed slots still count in failure comparisons. At least three
complete stationary rounds per stage/profile/trial are needed for
the planned stage analysis. Otherwise label that stage timing-inconclusive.
A pair with a movement overlapping either request or between requests is mixed,
not a clean policy comparison. Keep all rounds in the overall report as well.

## Commands — prepared only; do not execute until approval

Terminal 1, after approval, at A with en0 and en6 already connected:

```sh
cd ~/smartconnect
git switch codex/mac-hub-phase4
source venv/bin/activate
phase4_dr_dir="$PWD/mac_hub/logs/phase4-dr1-$(date -u +%Y%m%dT%H%M%SZ)"
printf '%s\n' "$phase4_dr_dir"
python -m mac_hub.phase4.run --execute --output "$phase4_dr_dir" --trials 4 --cycles 12 --bytes 65536 --interval 10 --condition planned_manual_A_B_A
```

The runner creates a new directory and refuses to overwrite existing evidence.
Copy its printed absolute directory for Terminal 2. Start the observer promptly:
first movement is not needed until after four cycles, about 40 seconds or more.
This observer only reads local CSVs; it neither starts traffic nor moves devices.
It may miss a cue if started late; do not replay stale cues as physical actions.

Terminal 2 (replace only the directory with the one printed above):

```sh
cd ~/smartconnect
source venv/bin/activate
phase4_dr_dir='/PASTE/THE/ABSOLUTE/EXPERIMENT/DIRECTORY'
python -u - "$phase4_dr_dir" <<'PY'
import csv, sys, time
from pathlib import Path
from datetime import datetime, timezone
root = Path(sys.argv[1])
last_rank = -1
while True:
    try:
        with (root/'rounds.csv').open(newline='') as f:
            rows = list(csv.DictReader(f))
        row = rows[-1] if rows else None
        if row and all(row.get(k) is not None for k in ('trial','application','cycle')):
            key = (row['trial'], row['application'], row['cycle'])
            trial, application, cycle = int(row['trial']), row['application'], int(row['cycle'])
            order = ['video_call','file_download'] if trial % 2 == 0 else ['file_download','video_call']
            rank = trial * 24 + order.index(application) * 12 + cycle
            if rank > last_rank:
                last_rank = rank
                cue = {3:'MOVE A -> B now; log departure/arrival',
                       7:'RETURN B -> A now; log departure/arrival',
                       11:'Stay at A; next block starts immediately'}.get(cycle,'Stay at the current planned location')
                age = time.time() - (root/'rounds.csv').stat().st_mtime
                if cycle in (3,7) and age >= 8:
                    cue = 'LATE cue: pause may be over; do not assume a clean transition; retain timing-inconclusive data'
                print(datetime.now(timezone.utc).isoformat(), time.time(),
                      'completed trial/profile/cycle:', *key, cue, flush=True)
        if (root/'manifest.json').exists():
            print('Run ended; inspect manifest for cancellation/error.'); break
    except (FileNotFoundError, csv.Error, ValueError, KeyError, IndexError):
        pass  # CSVs are rewritten during collection; retry partial reads.
    time.sleep(.25)
PY
```

In a third Terminal tab, use the same absolute directory and one command per
event. Replace the sample label with the actual trial/profile/event; never paste
these examples as if the movements already occurred. This writes only a new
sidecar in `mac_hub/logs`, not the runner's source CSVs or manifest:

```sh
cd ~/smartconnect
source venv/bin/activate
phase4_dr_dir='/PASTE/THE/ABSOLUTE/EXPERIMENT/DIRECTORY'
python -c 'import json,sys,time; from datetime import datetime,timezone; from pathlib import Path; record={"epoch":time.time(),"utc":datetime.now(timezone.utc).isoformat(),"event":sys.argv[2]}; f=(Path(sys.argv[1])/"operator_events.jsonl").open("a"); f.write(json.dumps(record)+"\n"); f.close(); print(record)' "$phase4_dr_dir" 'trial=0 profile=video_call depart_A_for_B'
```

Use labels `depart_A_for_B`, `arrive_B`, `depart_B_for_A`, `arrive_A`, always with
the actual trial and profile. These are operator observations with reaction-time
uncertainty, not instrument-verified network event times.

After completion or Ctrl-C, in Terminal 1 (where its variable is still set):

```sh
python -m mac_hub.phase4.report "$phase4_dr_dir"
python -m mac_hub.phase4.report "$phase4_dr_dir" --audit-only
streamlit run mac_hub/phase4/dashboard.py
```

Choose Custom completed experiment and paste the new directory. Existing reports
produce whole-run/per-profile summaries, not automatic A/B/recovery summaries.
Stage annotation and the predeclared stage analysis below are a separate offline
step after collection; no nonexistent stage-report CLI is implied. Store derived
stage tables separately and keep all original collection files immutable. The
operator sidecar is not covered by the runner's manifest hashes; preserve/hash it
separately with the final derived evidence bundle.

## Predeclared interpretation and success criteria

These are exploratory protocol thresholds, not service standards or guarantees:

1. **Manipulation check:** on stationary B rounds, compared with that same block's
   stationary A rounds, Wi-Fi median RTT rises by at least 20 ms AND 50%, OR median
   equal-sized calibration goodput falls by at least 40%. Require at least three
   complete stationary rounds per stage. Report measured loss and RTT variation
   separately, including missingness; do not substitute zero for unavailable RTT.
   Reachable Wi-Fi in at least three B rounds allows a proactive-selection test.
   If Wi-Fi instead becomes unavailable, classify it as outage/fallback evidence;
   Wi-Fi-first can also fall back, so that is not automatically a unique benefit.
2. **Cellular control check:** no cellular calibration failures in the stationary
   stages; B and recovered-A median cellular RTT stay within max(20 ms, 30% of
   baseline-A RTT), and median cellular calibration goodput within +/-30% of
   baseline A. Otherwise report a joint-path change/confounded Wi-Fi-only test.
   Retain every such run, not only runs passing this check. These tolerances are
   screening assumptions; small sequential probes cannot prove cellular stationarity.
3. **Recovery check:** for the metric that deteriorated, recovered-A median Wi-Fi
   RTT returns within max(10 ms, 25% of baseline-A RTT), or goodput recovers to at
   least 80% of baseline A, respectively. If both deterioration criteria applied,
   check both. Report loss/reachability too. Missing or non-recovered data is
   inconclusive/failed recovery, not interpolated success.
4. **Functional adaptation:** where logged policy inputs actually justify a
   cellular recommendation for the sustained hold/dwell window, inspect whether
   SmartConnect applies that recommendation to subsequent outcome requests.
   Similarly examine return to Wi-Fi only if its guardrails, advantage, hold and
   dwell justify it. Use unchanged Engine replay, not an assumed fixed deadline.
   No justified advantage means a hold can be correct. Failure to change despite
   eligible conditions is an adverse finding. Record initial attachment, direct
   recommended changes and availability transitions separately.
5. **Comparative benefit:** primary outcome for File Download is B-stage actual
   end-to-end bounded-object goodput; for Video Call it is B-stage fresh-request
   completion time, explicitly a responsiveness proxy. Summarize paired differences
   within trial, then across four trials; use the existing seed-2026 trial-cluster
   bootstrap convention on stage-specific complete-success pairs. Favorable point
   estimates alone are preliminary. A directional interval excluding zero AND no
   increase in failed/no-eligible slots is stronger exploratory evidence, provided
   the pairs actually select different paths. Same-path pairs are timing controls.
   Report failures/paired attrition and all unfavorable effects; no QoE claim.
   If fewer than four trials have clean pairs for a stage, suppress that stage's
   interval. These adjacent trials are not independent population replications.

The run has a fixed sample budget. Do not alter thresholds, drop unfavorable
rounds, continue only until significance, or force a switch during analysis.
Report transition/mixed rounds and overall results alongside stationary-stage
results, including timing/missing-data exclusions and their counts.

## Timing and physical-egress evidence

Separate: (a) operator movement interval, (b) last non-deteriorated to first
measured-deteriorated monitor window (onset is interval-censored), (c) monitor end
to decision including calibration, (d) decision compute duration, (e) decision to
new request initiation/TCP connection/observed completion or failure. First
observed degraded input is a detection time, not exact physical onset. A failure
bracket includes scheduled pauses, probes and the other policy's traffic; it is
not existing-session downtime. No failures observed means no such failure gap
was observed, not zero interruption or seamless continuity. Return not seen
before block end is censored; do not extend the block opportunistically.

Without fresh capture all Phase 4 rows remain `egress_status=unverified`.
Source-IP selection, socket binding readback and HTTP success are insufficient
physical proof. For a **confirmed new-request path change**, independently match
SmartConnect outcome flows before and after the recommendation change against
simultaneous en0/en6 captures: request ID plus source IP/local port, common pinned
IPv4/443, time interval, SYN/SYN-ACK sequence/ACK, TCP timestamps where present,
and outbound TLS payload on the expected interface, with no corresponding
outbound flow on the other capture. Probe flows are not policy outcomes. Require
capture readiness covering both flows, clean flush/termination, kernel-drop
counts, supported PCAP format, hashes and per-request confirmed/unverified reasons.
TCP timestamps are supporting evidence where present, not a fabricated requirement
if the capture lacks them. Failed or absent connections cannot be confirmed as
successful path transitions. Even confirming these new flows does not prove
migration of an existing connection.

Optional future capture proposal: after separate approval and endpoint pinning,
capture only TCP to that exact public IPv4 port 443 on en0/en6, promiscuous mode
disabled, 96-byte snapshots, a hard 240-second scope around one agreed profile
block, Python/workload unprivileged and only capture processes elevated. Save
stderr/readiness/drop counts and both PCAPs; any flow outside the valid interval
stays unverified. If a block overruns, stop capture at the limit, not extend it.
A safe bounded supervisor and exact pinned-IP command must be reviewed before
execution; the existing Phase 3 fixed-1.1.1.1 helper is NOT suitable for this
Cloudflare endpoint or for a 240-second session. Existing Phase 4 report/dashboard
cannot import confirmed flows: preserve any new verification as a separate report
until reviewed tooling supports it, and do not edit old unverified rows to claim
confirmation. No privileged command is executed or required by this plan.

## Approval boundary

Await explicit approval for DR-1: the marked-location A → B → A movements,
four-trial/two-profile/12-cycle/64-KiB/10-second workload above (24 MiB maximum
requested payload), normal Mac internet possibly impaired at B, Ctrl-C plus
return-to-A recovery, **no privileged capture and no networking changes**.
Location feasibility, lack of deterioration, timing contamination or cellular
variation can make this experiment inconclusive; all evidence must be retained.
