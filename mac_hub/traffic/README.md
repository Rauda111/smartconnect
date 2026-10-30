# Phase 3 — Stage A: controlled new HTTPS requests

Branch `codex/mac-hub-phase3`, based on `44d202e`. The original Cisco, simulation,
Phase 1/2 code and evidence are preserved. No routes, DNS, network priorities,
firewall rules, Internet Sharing or router settings are changed by this code.

## Status and stage gate

**Stage A passed** on the user-approved corrected 60-second capture. Both
interfaces exited cleanly with zero kernel drops. Four HTTP 200 requests (two per
interface) were independently matched to the requested physical interface using
connection tuples, capture times, handshake sequence/ACK numbers, TCP timestamp
options where present and payload packets; the other interface had no matching
outbound flow. See [per-request verification](evidence/stage_a_verification/VERIFICATION.md)
and the detailed `stage_a.json` beside it.

The initial app-side sudo attempts could not authenticate. The first Terminal
capture exposed a shutdown-forwarding bug and took about ten extra seconds to
clean up. That run was conservatively marked failed despite clean tcpdump exits.
It is preserved under ignored local diagnostic logs. Shutdown now terminates both
sudo wrappers concurrently using SIGTERM, and the separately approved corrected
capture completed cleanly. No further packet capture was run after the user's
instruction to stop captures.

**Stage B is implemented and was exercised only after Stage A passed.** It uses
the unchanged bound client and the existing Phase 1 scoring/stability engine.
Execution is opt-in and requires a recent independently passed Stage A gate,
the same client hash, interface indices and endpoint. Dry-run has no probes or
requests and uses a virtual cadence for controlled inputs. Unavailable paths
produce `no_request` workload slots rather than invented HTTP attempts.

The controlled functional workload completed 32/32 successful HTTPS requests;
the short live ICMP-driven workload completed 8/8. Later requests remain
**unverified per-request egress** because no additional capture was authorized.
The controlled workload requested two SmartConnect path changes, but confirmed
traffic-transition delay and network interruption remain unknown. It does not
demonstrate actual application QoE improvements. See [final results](FINAL_RESULTS.md).

## Method and research

The installed SDK `<netinet/in.h>` and Apple's XNU define `IP_BOUND_IF = 25`.
Apple documents in the kernel implementation that this option restricts an
IPv4 socket's outgoing traffic to the selected interface:

- [Apple XNU IPv4 socket option](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/ip_output.c)
- [Apple XNU constants](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/in.h)
- [curl interface option](https://curl.se/libcurl/c/CURLOPT_INTERFACE.html)

We choose a small standard-library HTTPS client with a directly configured
Darwin socket rather than assuming curl's source-address selection proves
physical egress. It sets the bound interface before connect and checks readback.
Failure stops that request; there is no unbound or alternate-path fallback.
Independent capture remains required to validate behavior on the actual host.

Each request uses a fresh IPv4 TCP socket and verified TLS session, then a small
HTTP GET. The default destination is literal `1.1.1.1:443`, with TLS SNI and Host
`one.one.one.one` and path `/cdn-cgi/trace`. There is no DNS lookup, proxy,
redirect-following, automatic retry or reused connection. No server response
body is saved; its byte count and SHA-256 digest are logged. TLS verification is
never disabled. Target unavailability is a test failure, not proof of bad access.

A total deadline (default ten seconds), cancellation signal handler and watchdog
bound request attempts. SIGINT/SIGTERM stops further work and interrupts active
sockets. A cancelled request is logged separately. Each subsequent request is
new, permitting recovery without moving existing sessions. Run normally as your
user; ordinary client operation needs no administrator privileges.

## Exact commands on your Mac

```sh
cd ~/smartconnect
source venv/bin/activate
python -m unittest test_mac_hub_traffic -v
python -m mac_hub.traffic.run_stage_a --output-dir mac_hub/logs/phase3-dry-new
```

Dry-run performs no socket creation or DNS lookup. A fresh output directory is
required for every run. To send the manual four-request sequence without capture:

```sh
python -m mac_hub.traffic.run_stage_a --execute --output-dir mac_hub/logs/phase3-http-new
```

Those successes remain `unverified`. This command does not require sudo and is
not sufficient to pass Stage A.

### Packet capture: reference only; do not repeat during this run

The following procedure is retained for future separately approved validation.
The user explicitly requested no further capture in this run; do not execute it
again now. Only after a new explicit approval, in your authenticated Terminal:

```sh
sudo -v
python -m mac_hub.traffic.capture --execute --approved-capture --duration 60 --output-dir mac_hub/logs/phase3-approved-capture --stage-a-requests-dir mac_hub/logs/phase3-approved-requests
```

Do **not** run Python with sudo. The helper starts only two elevated commands:
`sudo -n /usr/sbin/tcpdump -i en0` and the equivalent for `en6`, with `-p -n -s 96
-U -w FILE 'tcp and host 1.1.1.1 and port 443'`. The helper waits for readiness,
sends exactly four manual HTTPS requests as the ordinary user, and stops capture
after 60 seconds. It records commands, readiness, return codes, stderr/drop counts
and file hashes. It never requests a password. `sudo -v` authenticates in your
Terminal; that credential may not be shared with this app's execution session.
The dry-run form of `capture` prints commands without invoking sudo.

The filter is restricted, but capture may include other processes' packets to
the same endpoint, local IP/MAC addresses and a small part of encrypted TLS data.
The verifier uses the exact request connection tuple and time interval rather
than assuming every captured packet belongs to this experiment. No unrelated
household traffic is captured promiscuously. Do not change BPF device permissions
or grant permanent capture privileges. PCAPs contain local-network identifiers;
keep raw evidence local unless you choose to share it.

After the capture finishes (no administrator privileges for verification):

```sh
python -m mac_hub.traffic.verify --request-dir mac_hub/logs/phase3-approved-requests --capture-dir mac_hub/logs/phase3-approved-capture --output-dir mac_hub/logs/phase3-verified
python -m mac_hub.traffic.report --requests-csv mac_hub/logs/phase3-verified/verified_requests.csv --output-dir mac_hub/logs/phase3-stage-a-report
python -m streamlit run mac_hub/traffic/dashboard.py
```

The independent parser accepts classic PCAP Ethernet/IPv4, raw IPv4 and BSD
loopback headers (not pcapng). It checks checksums of evidence files, complete
capture readiness coverage, clean exit and zero reported kernel drops. For each
flow it requires outbound SYN, inbound SYN-ACK and outbound TCP payload on the
requested interface and **no matching outbound packets on the other interface**.
An incomplete, dropped, unsupported, ambiguous or mismatched capture fails
closed. Stage A requires at least two successful independently confirmed requests
per physical interface and all recorded requests confirmed. The binding index
and local socket IP are diagnostic fields, never path proof by themselves.

## Evidence definitions and limits

`dry_run` means no HTTP traffic; `actual_https` means real test-client traffic;
`pcap_confirmed` is a separately correlated physical-interface observation.
Unit-test PCAP fixtures are synthetic tests and never live experiment evidence.
Request duration is cumulative client setup + TCP + TLS + HTTP headers/body.
TCP/TLS/first-byte milestones are cumulative from request start, not isolated
network RTTs. Failed/timeout/cancelled requests are counted separately; missing
latencies and unknown egress are never zero-filled. There is no application
throughput, RSSI, RTP jitter, video-call QoE, seamless-session or 5G-radio claim.

The default endpoint has a tiny variable response, so byte counts and raw timing
are not a controlled download-goodput benchmark. Source paths such as iPhone USB
may have changing interface numbers or active radio technology. Per-interface
HTTPS success alone does not establish reliable steering. Independent packet
verification, including failure cases, precedes all automated decision use.

## Stage B and live dashboard commands (no administrator privileges)

The existing evidence is in `mac_hub/traffic/evidence/`. Review it without sending
any traffic or starting capture:

```sh
python -m unittest -v
python -m mac_hub.traffic.audit
python -m streamlit run mac_hub/traffic/dashboard.py
```

The audit reads the already collected PCAPs under
`mac_hub/logs/phase3-stage-a-clean-capture` and requests under
`mac_hub/logs/phase3-stage-a-clean-requests`; it does not invoke tcpdump or sudo.
Raw PCAPs stay in that ignored local directory and are not committed. A fresh
clone needs those locally retained artifacts to repeat packet-level auditing.
Derived reports, exact packet metadata, original request/capture manifests and
hashes are committed. In the dashboard set Request CSV to
`mac_hub/traffic/evidence/controlled_final/requests.csv` or
`mac_hub/traffic/evidence/live_workload/requests.csv`. Leave the optional verified
CSV path absent for later workloads, so their egress remains explicitly unknown.
For Stage A, select `evidence/stage_a_verification/source_requests.csv` and the
corresponding `verified_requests.csv` using full repository-relative paths.

Dry-run both profiles and the controlled deterioration/recovery schedule:

```sh
python -m mac_hub.traffic.experiment --mode controlled --application video_call --output-dir mac_hub/logs/phase3-plan-video
python -m mac_hub.traffic.experiment --mode controlled --application file_download --output-dir mac_hub/logs/phase3-plan-download
```

Optional new **non-privileged** traffic (no capture, no configuration changes):

```sh
python -m mac_hub.traffic.experiment --execute --mode controlled --stage-a mac_hub/traffic/evidence/stage_a_verification/stage_a.json --output-dir mac_hub/logs/phase3-controlled-new
python -m mac_hub.traffic.experiment --execute --mode live --cycles 4 --stage-a mac_hub/traffic/evidence/stage_a_verification/stage_a.json --output-dir mac_hub/logs/phase3-live-new
python -m mac_hub.traffic.compare --input-dir mac_hub/logs/phase3-controlled-new --output-dir mac_hub/logs/phase3-comparison-new
```

Controlled mode deliberately feeds synthetic QoS values to the real engine to
exercise fresh-request selection without harming household networks. It is not
real deterioration or a test of QoS prediction accuracy. Live mode concurrently
measures both interfaces with three ICMP echoes per round (coarse loss resolution),
then gives the same snapshot to both policies. Each sends a separate small GET;
order alternates by round. Their outcomes are actual, sequential and different
observations, rather than identical measurements or a randomized performance
trial. Whole-request timing includes TLS and client overhead. No throughput or
application jitter is inferred. The original guardrail rescue hold limitation
from Phase 2 is retained, not silently retuned.

Monitoring-window duration, engine computation, request dispatch after decision
and decision-to-response latency are separate fields. Physical transition timing
is left blank unless separately verified. The failure-gap proxy counts failures
between two successes and includes intentional request spacing; no failures does
not establish zero network interruption. All workload slots are retained, with
complete paired-round counts to expose cancellation imbalance.

The execution gate expires 24 hours after the capture ended (re-rendering an old
verification does not refresh it), and rejects changed interfaces or client code.
If it expires, use dry-run/offline review until a new independent validation is
separately authorized. Do not work around the gate with routes or privileges.
SIGINT/SIGTERM cancels subsequent requests; deadlines interrupt active sockets.
No fallback reroutes traffic automatically.

## Approval boundaries

- Dry-run, tests, existing-PCAP audit, reports and the read-only dashboard: no
  administrator access and no packet-capture approval required.
- Explicit `--execute` HTTP/ICMP runs: ordinary user privileges only; opt-in
  test traffic, never system-wide handover.
- Any new tcpdump capture: separate explicit approval and Terminal sudo
  authentication required. No such additional capture is authorized in this run.
- Route/DNS/firewall/priorities/Internet Sharing/router changes: not implemented
  or authorized. Existing sessions, VPNs and multi-device gateways are out of scope.
