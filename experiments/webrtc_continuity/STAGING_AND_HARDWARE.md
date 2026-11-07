# Two-laptop staging and hardware runbook

This is the next-action procedure following integration commit `4b5e878` on
`codex/prototype-integration-demo`. It supersedes scattered launch instructions
for the next hardware trial. It does not authorize deployment or live experiments.

## Preparation completed

- The isolated checkout was clean at `4b5e878`; that commit was pushed to GitHub.
- The integration branch remains separate from `codex/webrtc-render-signaling`.
- [render.staging.yaml](../../render.staging.yaml) defines a separate staging
  service. No service has been created and production has not been changed.
- Distinct URL-safe staging signal/writer credentials were generated privately in
  the ignored `.env.staging` file in the isolated checkout, with mode `0600`.
  Their values were not displayed, committed, uploaded or used in a live service.
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
- The available Render browser session requires sign-in. Actual account quota,
  production configuration, service region and active revision remain unverified.
  No Render API credential is available in the current process.

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

After deployment approval and Render sign-in, the agent will perform the service
setup and private secret transfer through an authorized interface. No secret
values should be pasted into chat, command arguments, screenshots, public logs,
PRs or source. Keep `.env.staging` private; never use `git add -f`. The agent can
load its values into a subprocess environment without printing them. No user
code copying or file editing is needed.

### Deployment acceptance before any live call

The agent will verify the actual staging URL and deployed commit, healthy startup,
matching client asset content and an inert initial page. It will check that
unauthorized policy calls return 403, the writer sees no active session before
joining, and authenticated test-only signaling/policy scope works. These smoke
checks use fixture data in an isolated room, explicitly end it, and are never
published as live measurements. No media/probe access is part of deployment
approval. If the service lacks the new protocol or the browser assets differ,
stop before a call.

## One sequential hardware-validation procedure

The agent performs software commands and evidence processing. The operator handles
the two devices, permissions and expressly approved physical network actions.
Do not proceed past a numbered approval boundary until it is granted.

1. **Approve staging deployment only.** Authorize one separate free-plan staging
   service from this branch, with the two separate credentials and auto-deploy
   disabled; no production changes or paid resources. Sign in to Render when
   prompted. The agent deploys and completes the acceptance checks above. This
   approval does not include probes, media, Wi-Fi interruption or capture.

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

The default offline test suites do not start this listener. Render-side Blueprint
validation and staged HTTP/browser acceptance still require account access and
deployment approval; they have not been represented as completed.
