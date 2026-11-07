# Prototype 1 → Prototype 2 integration

For the next real two-laptop trial, follow the single sequential
[staging and hardware runbook](STAGING_AND_HARDWARE.md). It includes the prepared
separate-service configuration, approval boundaries and automatic evidence saving.

This is the current integration guide; older loopback/manual-signaling setup guides describe earlier versions. The frozen competition dashboard, recorded evidence and existing decision engine are retained. The new work connects the Mac's existing Video Call policy to the separate WebRTC application.

## What the demonstration establishes

Real interface-bound ICMP observations on the Mac feed the existing persistent Video Call decision state. A fresh authenticated recommendation reaches the active hosted call. A recommendation change can request ICE recovery on the existing peer connection. Browser statistics observe media progress and selected candidate-pair changes. Physical interface verification is a separate measurement, never inferred from a recommendation or restart.

The participant reports successful Wi-Fi calling and a separate cellular-backed call, including matching a selected IPv6 candidate to the USB interface. These are **participant-reported observations**, not newly reproduced results. Same-session cellular recovery remains unverified. No verified 5G radio claim is made.

## Audit and deployment boundary

The source contains a Python standard-library Render entrypoint, a token-authenticated in-memory signaling broker, strict public Host/Origin checks, and native browser WebRTC media. Render transports signaling; it cannot measure the Mac interfaces. The Mac bridge uses the existing monitor and decision engine rather than introducing another scoring implementation.

The reported deployed revision is `22c401b` at `https://smartconnect-imst.onrender.com`. Read-only attempts to inspect its public root and `/healthz` through the web tool could not access either URL. This does not establish an outage. Private Render settings, deployment revision, compute plan and secrets were not independently inspected. No deployment/configuration change is part of this implementation. Local tests do not update the hosted service.

The repository-wide dependency pins differ from the installed test environment. The server uses only Python's standard library. The bridge also uses the existing NumPy dependency through `smartconnect.py`; `/opt/anaconda3/bin/python` has it, while the default `python3` on this Mac does not. No package was installed. Use the existing environment rather than reinstalling the frozen dashboard environment. A pre-existing two-line Streamlit compatibility fix was copied into this isolated branch; the original uncommitted file remains untouched.

## Setup after deployment and experiment approval

Mac: existing Python 3.10+ environment, the integrated repository, Chrome, camera/microphone permission, headphones, Wi-Fi `en0`, and the currently confirmed USB interface (previously `en6`). Windows: Chrome or Edge, camera/microphone permission, headphones and stable internet. Windows needs no Python when using the approved hosted application. Node is only needed for offline JavaScript tests.

The integrated hosted service must first be explicitly approved for deployment. Its startup entrypoint remains:

```sh
python -m experiments.webrtc_continuity.cloud_server
```

Keep the existing `SMARTCONNECT_SIGNAL_TOKEN`. Configure a separate high-entropy `SMARTCONNECT_POLICY_TOKEN` of 40–256 URL-safe characters in the approved service and privately on the Mac. It must differ from the signaling token. Never put the writer secret in a browser URL, browser input, source file, Git commit, screenshot or public log. No Render settings or paid resources were changed here.

Open private hosted client URLs on the two laptops using the existing signaling token: Mac role A, Windows role B. The base URL is `https://smartconnect-imst.onrender.com/`; private URL fragments carry `role=A` or `role=B` and the signaling token as in the current client. Do not project these URLs. Select the same condition and approved ICE configuration on both. Use automatic broker signaling, not manual exchange, for the integrated recovery experiment. Enable policy reading on Mac A. Start B and A only after media/signaling approval. The hosted broker establishes the active session scope; the bridge publishes to that scope.

Set the writer secret without echoing it or placing it in shell history, then launch the bridge with one command. This is an **operator command for an approved experiment**, not a command executed during implementation:

```sh
cd /path/to/integrated/smartconnect
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.policy_bridge --server https://smartconnect-imst.onrender.com --prompt-token --execute --duration 120 --output /private/tmp/smartconnect-trial-01.jsonl
```

Use the actual integrated checkout path. A separate plain launch, when the token is already available privately in the process environment, is:

```sh
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.policy_bridge --server https://smartconnect-imst.onrender.com --execute
```

Defaults are `--cycles 6 --count 10 --pause 5 --cellular en6`: at most 120 ICMP echo sends across both interfaces to the fixed public probe target `1.1.1.1`. Mac Wi-Fi is `en0`; confirm the current USB interface and override `--cellular` if necessary. The bridge requires an active Mac role-A session before its first probe. Review `python -m experiments.webrtc_continuity.policy_bridge --help` offline before approval to confirm window count, packet count and interfaces; the probe target is fixed in this version. The execute flag authorizes the program mechanically; the operator must already have approved the exact probe destination, duration, uploads and media experiment. The bridge does not start HTTPS download workloads or change routes. Its authenticated HTTPS policy uploads are additional control traffic and do not verify their own physical egress.

Set `--duration` to the approved remaining experiment interval (maximum/default 300 seconds), not longer than the intended call. The bridge also obeys the server's current session lease. It refuses to start a probe window without enough remaining time for the monitor's `count+6` second timeout. Windows are timestamped **before** probes; old measurements are never freshened by a late upload. A fresh journal path is optional and never overwritten; journal permissions are owner-only. It records decisions, original engine explanations, delivery/discard outcomes and bounded failures, without raw probe output, addresses, secrets or session identifiers.

## One-command local server launch

For approved local rehearsal, this command starts the unchanged loopback-only service without probes or media:

```sh
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.server --approved-local-traffic
```

For the integrated local policy channel, privately set a fresh `SMARTCONNECT_POLICY_TOKEN` in the server process environment and add `--policy-token-from-env`. The server still generates a separate temporary signaling token and prints private A/B control URLs. After an approved call starts, the bridge can connect with:

```sh
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.policy_bridge --server http://127.0.0.1:8766 --allow-loopback --prompt-token --execute --duration 120 --output /private/tmp/smartconnect-local-trial-01.jsonl
```

Use the same private writer token at the hidden prompt. Plain HTTP is permitted only for literal loopback with the explicit flag; hosted communication requires HTTPS. These are future operator commands, **not executed during implementation**. Same-Mac calls can remain on loopback and do not validate cross-network media. Two-machine automatic signaling uses the approved hosted deployment. Legacy `--policy-log` remains available for read-only manual use, but cannot be combined with live writer mode; manually pasted/file recommendations are not independent authenticated bridge evidence.

## Policy channel and failure behavior

The writer retrieves the current active session through authenticated `GET /policy/session` and publishes bounded sanitized measurements with timestamp and increasing sequence through `POST /policy`. Browser reads remain authenticated separately and scoped to the joined peer/session. Session mismatch, unauthorized writes, old/replayed sequence or timestamp, duplicate JSON keys, invalid metric coverage and stale data are rejected. Freshness is bounded to 45 seconds with monotonic expiry as well as wall-clock checks. Keep device clocks synchronized; a future timestamp is rejected rather than silently trusted. The browser labels missing/stale input unavailable and must not manufacture zero-valued quality measurements or physical path success.

Transient session HTTP failures have at most three retries, with 1/2/4-second waits and a 10-second maximum per request, all within the approved/session budget. Each observation POST is attempted once. After a lost response the bridge checks the accepted sequence; it never replays that old observation. Subsequent fresh windows retain the same engine state. Authentication failure, wrong session, another writer advancing the sequence, expired approval or exhausted retries stops the collector. Restarting a collector against a session that already accepted policy is rejected; begin a separately approved new call instead of silently resetting hysteresis.

The server room has a 360-second absolute lifetime from the first peer joining and a 180-second inactivity lease per joined peer. Writer traffic cannot keep the room alive. Ending either peer invalidates the shared room, queues and policy. Signaling queues hold at most 64 descriptions for 120 seconds, coalesce duplicate queued messages, and retain them until the integrated browser acknowledges receipt into its bounded inbox. Offers and answers retain revision/session checks; duplicate offers can obtain a cached answer. There is no automatic creation of a replacement call. Client recovery remains bounded to three restart attempts, a 10-second cooldown and bounded signaling retries. All call participants must use the integrated client/server revision together.

Initial offer generation/gathering has at most three retries after the first attempt, at least three seconds after each failed attempt, on the same peer connection. Unpublished assisted recovery offers can retry only within the existing three-restart/10-second limits while their cause remains applicable. If browser rollback fails, negotiation stops and the UI requires explicit session end; old answers cannot revive the failed negotiation. A retry limit is an observed failure, not a successful transition.

The server is a single controlled room with in-memory ownership, messages and policy. It is not a multi-tenant production calling service. End both peers before another trial; do not reuse evidence across calls. Server restart loses broker state and can interrupt signaling. If the service uses Render's free plan, idle spin-down and startup delays are additional demo constraints; the actual plan was not verified. [Render free-service documentation](https://render.com/docs/free).

## Connectivity and limits

Standard browser WebRTC cannot bind its media sockets to `en0`/`en6`; an ICE restart requests new connectivity checks and negotiation, not named-interface steering. No system-wide application steering, session-migration guarantee or imperceptible recovery claim is supported. [WebRTC specification](https://www.w3.org/TR/webrtc/).

Carrier NAT/firewalls may require approved TURN. Enter the same approved `iceServers` configuration privately on both clients, using expiring provider credentials where available. `iceTransportPolicy: "relay"` can test an approved TURN path but does not select the Mac's physical interface. No default third-party server or embedded credential is supplied, and no TURN account was provisioned. [WebRTC TURN guidance](https://webrtc.org/getting-started/turn-server).

A private configuration template follows; replace every placeholder using an already-approved service. Never commit populated credentials. Prefer provider-issued short-lived, least-privilege TURN credentials and renew them before a trial. Do not use open unauthenticated relays or disable certificate validation. Provisioning/purchase requires separate approval.

```json
{"iceServers":[{"urls":["turns:YOUR-APPROVED-TURN-HOST:5349?transport=tcp"],"username":"YOUR-EXPIRING-USERNAME","credential":"YOUR-EXPIRING-CREDENTIAL"}],"iceTransportPolicy":"all"}
```

If the selected local candidate is a relay, its address belongs to TURN. Interface attribution then needs independent packet/transport evidence on the Mac; the offline address matcher deliberately leaves it unverified.

## Independent address evidence

During an approved active Mac call, the private path button explicitly downloads a minimal selected-pair snapshot. It contains addresses and must remain private. Within 30 seconds, run the read-only local inventory command (no probes or traffic capture):

```sh
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.media_path capture-interfaces --output /private/tmp/PRIVATE-interfaces-before.json
/opt/anaconda3/bin/python -m experiments.webrtc_continuity.media_path compare --path-snapshot /path/to/PRIVATE-selected-media-path.json --interfaces /private/tmp/PRIVATE-interfaces-before.json --output /private/tmp/path-match-before.json
```

Repeat with new filenames after recovery in the **same** call. The offline comparison accepts only an active selected host candidate whose exact IPv4/IPv6 address uniquely matches an active interface; obscured mDNS, NAT/reflexive, relay, ambiguous, stale and disconnected evidence stays unverified. It resolves no names and sends no traffic. A successful result is `candidate_interface_match`, with `physical_egress_verified=false` and `same_session_handover_verified=false`. Compare the private session identifiers before/after, retain observed media progress and add separately approved packet corroboration before claiming physical migration. The public UI remains unverified because it cannot independently establish physical egress.

Current policy observation windows, hysteresis and dwell remain unchanged; they may react too slowly for an imperceptible interruption. Keep recommendation-driven recovery separate from ICE disconnected/failed, video-stall and manual recovery causes. Browser recovery can occur without any SmartConnect intervention. Existing bounded retry/cooldown rules can suppress a requested intervention; report that outcome.

## Delivery classification

- **Implemented and offline-tested:** consult the accompanying test report for exact suites/counts; mocks validate protocol and control flow, not real media migration.
- **Implemented, awaiting hardware verification:** Mac measurements → hosted session-scoped policy → same-peer-connection ICE recovery and live interruption observations.
- **Currently blocked:** production use of the new channel until deployment/secret configuration approval; real probes/media tests until experiment approval; confirmed same-session physical migration until independent evidence.
- **Optional improvements:** approved TURN, repeatable physical path instrumentation, resilient persistent/multi-room signaling, a separately evaluated faster application-failure policy. None changes the frozen policy in this delivery.

## Judge-facing summary and checklist

“Prototype 1 decides from measured network quality. Prototype 2 now connects that recommendation to a real two-party video call and requests recovery while retaining the call's peer connection. We separately show what was recommended, what recovery was requested, what WebRTC observed, and whether the physical path was independently verified. Any interruption and failed attempt remain visible.”

Before showing the integrated experiment: confirm the approved deployed revision; confirm both peers, media permissions and approved ICE destinations; establish the active session; start the approved Mac bridge; confirm fresh measurements; distinguish selected-pair observations from verified interface evidence; retain baseline results; stop at the approved duration. Keep the established competition dashboard and recorded run ready as a separate verified demonstration. Use HARDWARE_VALIDATION.md for the actual experiment.
