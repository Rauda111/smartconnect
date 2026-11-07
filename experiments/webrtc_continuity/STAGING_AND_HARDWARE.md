# Two-laptop staging and hardware runbook

This is the next-action procedure following integration commit `4b5e878` on
`codex/prototype-integration-demo`. It supersedes scattered launch instructions
for the next hardware trial. It does not authorize deployment or live experiments.

## Preparation completed

- The isolated checkout was clean at `4b5e878`; that commit was pushed to GitHub.
- The integration branch remains separate from `codex/webrtc-render-signaling`.
- [render.staging.yaml](../../render.staging.yaml) defines a separate staging
  service. The user approved this separate free deployment, which is now live;
  production has not been changed.
- Distinct URL-safe staging signal/writer credentials were generated privately in
  the ignored `.env.staging` file in the isolated checkout, with mode `0600`.
  Their values were imported privately into the separate staging service through
  Render’s `.env` file chooser. They were not displayed, committed or reused from
  production.
- Source configuration validation accepts these credentials. The server/cloud
  tests also pass with Python site-packages disabled: deployment needs no pip
  install of the simulation/dashboard dependencies.
- A real ephemeral loopback HTTP check passed: bridge → HTTP handler → broker →
  authenticated A/B reads; retained-until-ACK signaling, unauthorized rejection,
  and room teardown. Measurements and SDP in that check were fixtures; it used no
  external probes, browser, camera, microphone or ICE.
- Read-only local inventory found `en0` active but **`en6` absent** at preparation
  time. This is not a reachability test; the iPhone USB link must be connected and
  rechecked before a trial.
- Render sign-in and deployment completed on 2026-11-07. Read-only billing showed
  Hobby, no card on file, 3.03/750 free hours, 6 MB/5 GB bandwidth, and 1/500
  pipeline minutes used before creation. No paid resource or billing change was
  enabled. No Render API credential was needed.

The only call-code addition after `4b5e878` is automatic **sanitized** evidence
download at explicit end, time limit or shared-session expiry. It uses peer role
and UTC start time in the filename. No candidate addresses, SDP, tokens or media
are automatically downloaded. Browser blocking remains possible; the explicit
download button is retained. Closing/reloading the tab is not a reliable save.

## Smallest staging deployment

Reuse the existing GitHub repository, Render account, native Python runtime and
HTTPS broker architecture. Create one separate service; do not clone production
environment groups or change its branch/settings.

| Setting | Prepared value |
| --- | --- |
| Blueprint file | `render.staging.yaml` (explicit selection; not auto-discovered `render.yaml`) |
| Proposed service name | `smartconnect-prototype2-staging-4b5e878`; verify unused first |
| Repository / branch | `Rauda111/smartconnect` / `codex/prototype-integration-demo` |
| Runtime | Python 3.13.5, matching the existing validated environment |
| Build | `python -m compileall -q experiments/webrtc_continuity` |
| Start | `python -m experiments.webrtc_continuity.cloud_server` |
| Health | `/healthz` |
| Compute | Explicit `free`, exactly one instance/process; no disk/database |
| Auto-deploy | Off; deploy the reviewed branch head explicitly |
| Proposed region | Frankfurt; inspect account availability before creation |

Render's Blueprint supports these controls, but matching an existing service name
can modify that service. Confirm the proposed staging name is unused before
applying it. [Render Blueprint reference](https://render.com/docs/blueprint-spec).

Free services share workspace allowances, can sleep/restart and are not a
continuity guarantee. Inspect remaining hours/bandwidth and any billing settings
after sign-in. Do not create or upgrade anything if it requires a paid resource
or unapproved charge. Warm staging with a single readiness request shortly before
the trial; do not add a recurring keepalive. [Render free-service limits](https://render.com/docs/free).

`PYTHON_VERSION` is pinned explicitly so a new service does not inherit a different
default. [Render Python version configuration](https://render.com/docs/python-version).

### Credentials and startup requirements

The server requires Render-provided `RENDER=true`, `RENDER_EXTERNAL_HOSTNAME`
and a valid `PORT` (normally `10000`). Do not invent or override the hostname;
its exact value drives Host/Origin checks. Use Render's native HTTPS URL.

Set **both** `SMARTCONNECT_SIGNAL_TOKEN` and `SMARTCONNECT_POLICY_TOKEN` on staging
from the prepared private file. Both are distinct 64-character URL-safe random
values. Do not reuse production credentials. The writer token goes only to the
Mac bridge and staging server; never into browser URLs or configuration.

The Blueprint uses `sync: false` for these secrets. Do not replace it with
`generateValue: true`: Render documents standard base64 output that may contain
`+`, `/` or `=`, which this application's deliberate URL-safe validation rejects.
The prepared credentials avoid changing the validated security contract.

The user approved deployment and completed Render sign-in. The agent performed
service setup and private secret transfer through Render’s `.env` file chooser. No secret
values should be pasted into chat, command arguments, screenshots, public logs,
PRs or source. Keep `.env.staging` private; never use `git add -f`. The agent can
load its values into a subprocess environment without printing them. No user
code copying or file editing is needed.

### Deployment acceptance before any live call

Completed at 2026-11-07 18:10:20 UTC: 27 staging HTTPS checks passed. The browser
was separately observed idle, with no media, ICE or signaling polling started.
The test used synthetic measurements and synthetic SDP in a temporary staging
room, then ended it and verified the writer again saw no active session. No live
probe, camera/microphone session, packet capture or Wi-Fi interruption occurred.

| Verified deployed setting | Actual value |
| --- | --- |
| Staging URL | https://smartconnect-prototype2-staging-4b5e878.onrender.com |
| Render service | `srv-dbnmiae7bikc73cviig0` |
| Deployment | `dep-dbnmib67bikc73cvikb0` — Live |
| Application commit | `dd6c3722768f5000288b8b0fb4ce3a7449ded076` |
| Plan / region | Free ($0/month) / Frankfurt |
| Project assignment | None; separate from the existing Production project |
| Runtime | Python 3.13.5, one process |
| Auto-deploy / PR previews | Off / Off |
| Health check | `/healthz`, HTTP 200 |

Acceptance covered byte-for-byte matching HTML, JavaScript and CSS; no-store
headers; cross-origin rejection; unauthenticated rejection; reader/writer
credential separation; four fixture policy windows through the actual bridge;
policy reads by both roles; retained-until-ACK offer delivery; answer delivery;
and room cleanup. Physical interface remained explicitly unverified. Sanitized
JSON was saved locally at
`/private/tmp/smartconnect-staging-evidence/acceptance-20261107T181020Z.json`.
The application remains at the commit above; a later documentation-only commit
does not trigger deployment because auto-deploy is off.

Production service `smartconnect` (`srv-dbn0al0n74is73fhd6b0`, Singapore) was
viewed read-only. Its service, branch, credentials and deployment were not
modified. Free staging can still sleep or restart; readiness must be checked
again before an approved hardware trial.

## Accepted baseline and assisted-trial readiness

The user accepted the 2026-11-07 two-laptop baseline. **Do not repeat it.**
Both saved peer logs and the operator observation establish bidirectional live
video/audio. The 120-second call limit included setup; connected media lasted
approximately 65 seconds. The selected Mac host candidate matched `en6`, while
`en0` remained active. This establishes a candidate/interface association, not
independent packet egress or Wi-Fi-to-cellular handover. Missing Windows private
endpoint evidence is a recorded limitation, not a reason to repeat the baseline.
All 19 baseline/staging preparation evidence files were hash-verified into the
owner-only durable archive `~/SmartConnectEvidence/accepted-baseline-20261107T184453Z`;
archived files are owner-read-only and originals remain unchanged.

The machine-readable companion is [assisted_trial_plan.json](assisted_trial_plan.json).
No assisted media, probes, captures, interface changes or deployment were started
for this preparation. Existing production and staging runtime settings are unchanged.

### Blocking requirement: reliable Wi-Fi-first selection

The deployed browser cannot bind a peer connection or ICE socket to `en0`.
`RTCConfiguration` exposes candidate policy `all`/`relay`, not an interface selector;
ICE restart negotiates new ICE credentials/connectivity checks. Neither selects
Wi-Fi by name. See the [WebRTC configuration specification](https://www.w3.org/TR/webrtc/#rtcconfiguration-dictionary)
and [ICE restart definition](https://www.w3.org/TR/webrtc/#dom-rtcofferoptions-icerestart).

Editing only the candidates sent in SDP is not a reliable interface restriction:
the local ICE agent still owns its gathered sockets and can learn peer-reflexive
paths through connectivity checks. A TURN relay also does not identify or bind
its physical underlay. See [RFC 8445, sections 7.2.5.3.1 and 7.3.1.3](https://www.rfc-editor.org/rfc/rfc8445).
Do not implement cosmetic candidate ordering or mark Wi-Fi verified from the
engine's recommendation. The accepted baseline is direct evidence that active
Wi-Fi alone does not establish the desired starting path.

The smallest robust architectural change under the strict two-interface
requirement is **Mac-side, per-call interface control in the native ICE/socket
layer**, retaining the existing engine, scoped signaling/policy service and
Windows browser. Merely wrapping the existing page in a native window is not
sufficient. This component is **specified, not implemented or hardware-validated**.
Native WebRTC exposes network enumeration and socket-factory integration points;
those must be adapted to actual macOS interface binding, with `en0`-or-fail setup,
then admission of `en6` without replacing the peer connection or tracks.
[Native network-manager interface](https://webrtc.googlesource.com/src/+/main/rtc_base/network.h)
and [native packet socket factory](https://webrtc.googlesource.com/src/+/refs/heads/main/p2p/base/basic_packet_socket_factory.cc).

A temporary USB disconnect during setup would be operationally smaller but would
relax the requirement that both interfaces remain available. A host firewall or
routing workaround adds separate network manipulation and isolation risks. Neither
is silently authorized by this plan. No additional account, paid resource, global
route change, firewall modification or modified recommendation is proposed as a
hidden part of the trial.

### Native component acceptance contract

- Leave `en0` and `en6` up; real ICMP observations on both remain unmodified.
- Restrict this new trial's initial **media sockets** to `en0`, or fail visibly.
  Do not claim that binding a source address alone independently proves egress.
- Preserve one native peer-connection identity, call scope and original media
  track identities across enabling `en6` and subsequent ICE recovery. Log private
  identifiers separately and publish only preservation results.
- After the initial path is independently confirmed, make `en6` eligible for that
  same peer connection. Confirm that media remains on `en0` with both interfaces
  available before any degradation stage; if it moves early, retain the outcome
  and stop qualification rather than declaring a handover.
- Reuse the actual policy envelopes and original engine explanations. No alternate
  scorer, changed hold/dwell/margin, fabricated loss, forced recommendation, or
  replacement call is permitted.
- Save sanitized counters/events automatically. Retain bounded private selected-pair
  history throughout the call so its final export remains available after closure;
  no Windows live-download timing dependency should be needed for the trial's
  essential Mac pre/post path proof.

### Prepared 300-second trial gates (not permission to execute)

1. **Transport readiness:** the native interface-control component must be built,
   checked offline, then deployed/installed only within approved scope. An ordinary
   browser call that happens to choose Wi-Fi is not a substitute for this control.
2. **Session approval and coordinated start:** one new integrated assisted session,
   at most 300 seconds from the first peer's Start action; both cameras/microphones,
   staging HTTPS signaling, configured ICE/media and cellular usage must be approved.
   Coordinate both laptops before starting the timer. Do not repeat the baseline.
3. **Real engine:** start exactly one persistent `Session('video_call')` through
   the existing bridge. Fixed target `1.1.1.1`, `en0` and `en6`, at most 18 windows
   × 10 ICMP echoes × 2 interfaces = 360 echoes, 5-second pauses, at most 270 seconds.
   Reduce that ceiling to the remaining global 300-second budget minus a shutdown
   margin. No parallel collector or reset of hold/dwell state in the same call.
   The bridge's session lease and per-request/probe bounds still apply.
4. **Arm only on evidence:** require fresh engine output genuinely recommending
   Wi-Fi, moving audio/video on both peers, the selected Mac candidate matching
   `en0`, and independently corroborated media egress on `en0`. Both interfaces
   must still be available. Failure of any condition is an honest stop condition.
5. **Capture approval:** before each capture, derive the exact IPv4/IPv6 media
   tuple from current private stats and present the actual interface/filter. Proposed
   ceiling: 20 seconds, 2,000 packets, 96-byte snap length, non-promiscuous capture,
   owner-only local storage. Exclude ICMP probes and staging HTTPS; account for
   STUN/DTLS packets on the same tuple when interpreting media traffic. No capture
   is run from an old baseline tuple or without its separate approval.
6. **Perturbation approval:** only after arming may a separately approved, bounded
   physical Wi-Fi degradation/interruption occur. Never fabricate its measurements.
   If the user requires both interfaces to stay available throughout, use a real
   approved degradation while keeping them up; an actual Wi-Fi outage needs an
   explicit exception at that stage. No default route, service order or other app
   steering is included.
7. **Record the genuine transition:** require an accepted, current bridge window
   with `wifi → cellular`, measured RTT/loss and the original explanation. Normal
   superiority requires the unchanged 3-window hold / 30-second dwell / 0.05 margin;
   a measured outage may legitimately use the existing availability exception.
   If conditions do not produce a change, record that result; never manufacture one.
8. **Verify the same session:** correlate private pre/post call identity, original
   PC/tracks, the transition and request timeline, fresh `en6` selected-path evidence,
   independent egress corroboration, and at least 15 seconds of resumed audio **and**
   video on both peers. For an outage trial, `en0` must remain unavailable during
   that observation. Counter gaps are sampled bounds, not exact perceptual freeze
   or handover latency. A new ICE pair or restart alone is insufficient.
9. **End and preserve:** stop within the global deadline, save both sanitized logs,
   private path history, interface snapshots, bridge journal and any approved
   captures. Preserve failures and incomplete/censored gaps. Restore only changes
   specifically authorized by the perturbation approval.

### Recovery attribution

The current implementation logs `recovery_requested.cause` separately as
`policy_change`, `ice_failed`, `ice_disconnected`, `video_stalled` or `manual`.
Only `policy_change` is an engine-triggered application request. The other three
automatic causes are application failure fallbacks, not engine decisions. Ordinary
browser ICE recovery can also occur without an application restart request.

Correlate the accepted bridge window and browser `policy_recommendation` with each
request and the subsequent media/path observations. If media/path recovery precedes
the policy request, report ordinary/fallback recovery. If a failure request precedes
or overlaps the policy request, label the attribution mixed/indeterminate. A policy
request followed by recovery is temporally associated with the engine intervention;
one such trial does not prove that the intervention alone caused recovery. Record
cooldown, stale-window, queue and retry-limit effects rather than relabeling them.
A policy-only application-restart mode would improve a later causal comparison but
cannot disable the browser's internal ICE behavior and is not currently implemented.

### Exact next approval / scope decision

The 300-second live trial is **not ready for approval** while reliable Wi-Fi-first
transport control is absent. The next scope decision is:

> Approve a Mac-only native interface-control adaptation for the assisted trial,
> keeping both interfaces up, the existing recommendation engine, staging service
> and Windows browser. Authorize software implementation/offline validation only;
> camera/microphone, live probes, captures and interface interruption remain
> subject to separate approval. Production stays unchanged and no paid resources
> are enabled. The existing separate free-staging authorization remains in force.

This changes the Mac client architecture beyond the current browser implementation;
it is not another baseline run or a request to repeat evidence transfers. Once a
concrete native build passes the acceptance contract, request the bounded live
session/probe approval in steps 2–3. Request the actual capture and physical
interruption approvals at steps 5–6, with their concrete scope.

Focused preparation verification: 33 Python bridge tests and 50 JavaScript core /
Python-to-JavaScript contract tests passed. Probe sockets/media were mocks in these
checks; they are software evidence only and did not repeat the accepted baseline.

## One sequential hardware-validation procedure

The agent performs software commands and evidence processing. The operator handles
the two devices, permissions and expressly approved physical network actions.
Do not proceed past a numbered approval boundary until it is granted.

1. **Staging deployment — completed.** The approved separate free service is live
   and passed the acceptance checks above, with distinct staging credentials and
   auto-deploy disabled. This approval does not include probes, media, Wi-Fi
   interruption or capture. **The current next step is step 2.**

2. **Prepare devices.** Connect the iPhone by USB, enable its Personal Hotspot and
   complete any device trust prompt yourself. Keep Mac Wi-Fi and Windows home
   Wi-Fi connected. Use headphones, power and visible foreground browser tabs.
   The agent reads interface state privately and verifies `en0` plus `en6`. If the
   USB interface has a different name, confirm it physically and use that name
   consistently; do not silently label another interface `en6`.

3. **Approve a bounded reachability check.** The agent runs the existing bound
   monitor for 10 ICMP echoes each on `en0` and `en6` to `1.1.1.1` (20 total),
   with no default-route fallback or HTTP workload. Save only sanitized numeric
   results. If cellular has no valid replies, stop and resolve USB/hotspot service.
   Replies establish bound ICMP reachability, not WebRTC/TURN reachability.

4. **Approve a 120-second stationary two-laptop call.** Approval covers both
   participants' camera/microphone, staging HTTPS signaling, browser ICE/media
   checks and cellular data use. Use automatic broker signaling, Windows B then
   Mac A, ordinary baseline on both. Start with the already approved ICE config;
   do not silently add public STUN/TURN. Both peers must show increasing decoded
   frames and audio counters plus visible/audible media. End explicitly and retain
   each peer's automatically requested sanitized download. If the cross-network
   path needs TURN, stop for approval of an authenticated service and its cost
   limits; enter temporary credentials privately and repeat the smoke call.

5. **Approve the assisted trial and bridge budget.** Use a fresh shared session,
   SmartConnect-assisted mode on both, Mac A's policy checkbox enabled, and a
   300-second browser limit. Approve up to 18 windows × 10 echoes × two interfaces
   = **360 ICMP sends** to `1.1.1.1`, pauses of 5 seconds, and a **270-second**
   bridge runtime ceiling, plus authenticated policy HTTPS requests and media.
   The agent starts the bridge immediately after both peers join, using the private
   writer credential and `--cycles 18 --count 10 --pause 5 --duration 270 --output`
   with a new owner-only journal path. Session/remaining-time limits can end it
   sooner; never restart its policy state inside the same trial.

6. **Establish the Wi-Fi starting path.** While video/audio counters increase,
   download the Mac's explicit private selected-path snapshot and collect a local
   interface snapshot within 30 seconds. The agent runs the existing offline
   matcher. Require a selected host-address match to `en0` before labeling the
   start Wi-Fi. If mDNS/NAT/TURN obscures it, leave the path unverified and obtain
   separately approved packet corroboration before continuing a physical-path
   claim. Record the private session ID and pair generation for later comparison.

7. **Approve packet observation if physical-path proof is required.** The agent
   first prepares a reviewable filter from the observed private media tuple
   (or TURN transport), never from guesswork. Proposed bounds: a maximum of
   20 seconds and 2,000 packets per pre/post capture, snap length 96 bytes,
   non-promiscuous capture on the relevant interface, owner-only private storage.
   This may need OS administrator authorization. The filter must exclude ICMP
   probes and staging HTTPS traffic and account for any changed tuple after
   recovery. No capture starts without approval of the actual filter, interface,
   duration and storage. Do not call captured encrypted packet prefixes media
   recordings or publish raw captures.

8. **Approve Mac Wi-Fi interruption at that step.** Once pre-transition evidence
   and fresh policy are present, turn off **only Mac Wi-Fi** for up to 60 seconds
   (or the shorter remaining approved interval). Do not change the router,
   Windows network, USB link, routes or service order. The agent timestamps the
   action and records read-only interface state. Keep `en0` unavailable until
   post-recovery evidence is complete. Never reload, press Start again, reacquire
   the camera, or create another call to obtain a successful-looking result.

9. **Observe and verify the same call.** Record recommendation transitions and
   exact explanations, recovery causes/attempts, ICE state, counter gaps and
   preservation flags. Require resumed video **and** audio progress on both peers
   for at least 15 seconds while `en0` remains unavailable. Collect another private
   selected-path snapshot and contemporary interface inventory; compare the same
   private session ID, original PC/tracks and a uniquely matched `en6` host address.
   Add the approved tuple/interface packet evidence, especially for relay or
   obscured candidates. A new pair, connected label, recommendation or separate
   cellular call alone is insufficient. If there is no recovery or insufficient
   proof before the limit, retain a failed/unverified trial.

10. **End, save and restore.** End both peers explicitly before closing their tabs.
    Each attempts one sanitized evidence download; if absent, use the existing
    download button on that device. The bridge journal is already written as it
    runs. Stop remaining capture/bridge processes, then restore Mac Wi-Fi under
    the approved perturbation plan. The agent collects the authorized local files,
    compares both peers' gaps, preserves failed attempts, and creates a sanitized
    trial summary. Windows needs no repository, Python, code editing or test run.
    Its operator only uses the browser and retains the downloaded evidence.

## Evidence and success boundary

Automatically collected: per-peer numeric counters/events every approximately
500 ms during the call, gap/censoring observations, recovery reasons, and the
Mac's decision/delivery journal. Automatic browser downloads occur at explicit
end, time limit or room expiry; confirm their presence before closing. No raw
camera/microphone recording or telemetry upload is introduced.

Explicit/private: pre/post candidate snapshots, local interface snapshots,
device/perturbation timestamps and any separately approved packet captures.
Keep them separate from sanitized jury material. The agent runs the existing
`media_path compare` command against each snapshot pair and records unavailable
evidence honestly. That matcher always leaves physical egress and handover flags
false; it reports an address association only.

**Do not report physical handover success unless the original call demonstrably
resumes over the cellular-backed interface while Wi-Fi remains unavailable.**
Record interruption duration as a sampled counter-progress interval, not exact
perceptual freeze time. Verify the before/after path independently and record
which recovery cause acted. An unverified path means an unverified handover even
if the video starts moving again. No 5G radio or seamlessness claim is supported.

## Checks for this preparation

The original 247 passed / 6 skipped result remains documented in
[INTEGRATION_TESTS.md](INTEGRATION_TESTS.md). This follow-up reruns the relevant
Python and JS integration suites, validates the staging YAML locally, verifies
credential format without revealing values, and adds the opt-in real loopback
transport check. Run it only with local-listener authorization:

```sh
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.transport_smoke --approved-loopback-check
```

The default offline test suites do not start this listener. Deployment used the
Render service form with the prepared Blueprint-equivalent settings; no Blueprint
sync was applied. Hosted HTTP/browser acceptance is recorded above. Hardware
validation remains pending, and no physical handover success is claimed.
