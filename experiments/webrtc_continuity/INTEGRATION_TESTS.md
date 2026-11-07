# Integration validation · 7 November 2026

Follow-up staging preparation is recorded at the end of this report. The table
below records the original `4b5e878` integration result.

Base revision: `22c401b`. Delivery branch: `codex/prototype-integration-demo`.
All results below are software tests with mocked probe/media transports or offline
recorded/synthetic regression inputs. **No physical handover result is claimed.**

## Final results

| Suite | Result |
| --- | --- |
| Existing repository Python regression | 109 run: 103 passed, 6 pre-existing private-evidence skips |
| WebRTC server / cloud / channel / bridge / path verifier Python | 70 passed |
| Browser core / application / Python-to-JavaScript integration | 74 passed |
| Python compilation, JS syntax and Git whitespace checks | Passed |
| Total automated cases | **247 passed, 6 skipped, 0 failed** |

Python runtime: `/opt/anaconda3/bin/python` 3.13.5. Node: v24.13.0.
Existing regression environment: NumPy 2.1.3, pandas 2.3.1, Streamlit 1.45.1,
Matplotlib 3.10.0. No dependencies were installed or upgraded. The installed
versions differ from the repository-wide pins. The default `python3` lacks
NumPy, so use the stated existing environment for the bridge and contract test.

The initial broad run exposed an existing Streamlit API mismatch and an existing
test's chart-element naming assumption. The branch carries the original local
two-line dashboard compatibility fix and a test accepting either supported
element name while still requiring five charts. The full regression then passed.
Six tests require intentionally withheld private historical artifacts; those
skips were retained, not bypassed or replaced with invented evidence.

## Reproduce offline

Run from the integrated checkout root:

```sh
MPLCONFIGDIR=/private/tmp/smartconnect-prototype-mpl /opt/anaconda3/bin/python -m unittest discover -s . -p 'test_*.py'
/opt/anaconda3/bin/python -m unittest discover -s experiments/webrtc_continuity -p 'test_*.py'
SMARTCONNECT_TEST_PYTHON=/opt/anaconda3/bin/python node --test experiments/webrtc_continuity/test_core.cjs experiments/webrtc_continuity/test_app.cjs experiments/webrtc_continuity/test_integration.cjs
/opt/anaconda3/bin/python -m compileall -q experiments/webrtc_continuity
node --check experiments/webrtc_continuity/core.js
node --check experiments/webrtc_continuity/app.js
git diff --check
```

These commands do not launch a signaling listener or a media trial. Do not run
unrelated hardware-routing scripts as part of offline discovery. Existing tests
may print simulated/mocked request outcomes; their stdout is not live evidence.

## What is exercised

- Real existing `Session → Controller → Engine` behavior with mocked interface
  measurements: normalization, trend history, three-observation hold, 30-second
  dwell, outage exception and unavailable cellular/both-path inputs.
- The actual Python bridge and broker together: fresh scope, separate reader and
  writer authentication, exact engine explanation, window-start timestamps,
  monotonic expiry, duplicate/replayed timestamp/sequence rejection, wrong
  profile/session, schema/body bounds and invalid cloud configuration.
- Bridge approval gate before HTTP/probe/file activity; finite probe/runtime
  budgets; session lease; bounded transient GET retries; lost POST response
  reconciliation without replay; old-window discard and state preservation.
- Strict origin checks, HTTP handler read bounds, bounded acknowledged signaling
  delivery, duplicate coalescing, queue expiry and shared session teardown.
- JavaScript call behavior under initial/recovery send and gathering failures,
  cached duplicate offers/answers, delayed responses, cooldowns, exhausted limits,
  stale policy, rollback failure and end-during-gathering transitions.
- One real Python policy stream passed directly to the actual JS coordinator:
  the original hold/dwell produces `wifi, wifi, wifi, cellular`, causing exactly
  one recommendation-driven recovery on the original peer/track objects.
- Browser application wiring through VM stubs: inert page boot, approval gates,
  private ICE configuration validation, session/ACK polling, media-duration timer,
  visibility/network hints and honest unavailable/closed UI reporting.
- Sanitized exports exclude addresses, SDP, credentials and raw exceptions;
  explicit private candidate snapshots are separate. Offline IPv4/IPv6 exact
  matching leaves relay, reflexive, mDNS, ambiguous, disconnected or stale evidence
  unverified and never claims physical egress or same-session migration.

## Evidence boundary

The browser APIs and HTTP transports are mocked in automated tests; the
cross-language contract test uses the production controller/relay/coordinator,
but its probe values and peer transports remain fixtures. Real Chrome/Windows
media, microphone/camera permissions, carrier NAT/TURN reachability, actual
en0/en6 measurement behavior, physical switching, packet correlation and
perceptual continuity were not exercised. No approved hardware trial has run.

Private Render configuration and the actively deployed revision were not
independently inspected. Public root/health-page access through the browsing
tool failed; that does not diagnose an outage. Production was not changed.

The shortest remaining path is: review this commit, approve the matching hosted
deployment and separate writer secret, then execute the staged procedure in
[HARDWARE_VALIDATION.md](HARDWARE_VALIDATION.md). Use
[DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) for the competition presentation.

## Follow-up: staging and evidence preparation

The original commit was confirmed clean and pushed to the dedicated GitHub branch.
The readiness follow-up adds a separate-service Render Blueprint, one sequential
hardware runbook, automatic sanitized downloads at call end/expiry, and an opt-in
loopback HTTP smoke checker. No algorithm or recovery policy was changed.

Relevant follow-up suites: **72 Python cases and 77 JavaScript/contract cases
passed (149 total, zero failures)**. The added cases cover automatic end/expiry
downloads, private-data exclusion, blocked-download fallback, and rejection of
unapproved loopback-listener startup. Python compilation, JavaScript syntax,
YAML parsing/explicit free-plan/single-instance/no-secret assertions and Git
whitespace checks also pass. The prior broader repository regression remains
applicable; its source was not changed or rerun unnecessarily.

The actual loopback HTTP smoke check passed with an ephemeral listener on
`127.0.0.1`, private temporary test credentials and fixture measurements/SDP.
It exercised the production bridge `Writer`, HTTP handler, broker scope, policy
delivery, signaling acknowledgements, unauthorized requests and room teardown.
The listener was shut down afterward. This is additional transport evidence,
not a browser/media or physical-network test. No external probes or routes were
used. An initial sandbox bind restriction was resolved through the approved
loopback-only execution; no application defect or external network was involved.

The server and cloud tests additionally pass under `python3 -S`, demonstrating
that the proposed Render service does not need the dashboard's pip dependencies.
Prepared staging credential values were checked with the real configuration
validator without displaying them or creating a listener.

Render account inspection is blocked by sign-in. No staging service has been
created, secrets uploaded or production configuration changed. Read-only local
inventory found `en6` absent, so USB hardware preparation is also required.
See [STAGING_AND_HARDWARE.md](STAGING_AND_HARDWARE.md) for exact next actions.
