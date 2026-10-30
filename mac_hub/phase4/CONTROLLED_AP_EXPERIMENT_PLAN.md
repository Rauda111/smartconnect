# E-1 proposal: dedicated test AP plus an isolated Linux impairment bridge

**Planning only. No equipment was configured, no experiment executed, and no
privileged capture started. Fresh approval is required for setup and testing.**
P-1's unsuitable downstairs result is preserved, not replaced. This proposal
uses controlled path emulation over real Wi-Fi and real cellular connections.
It must not be described as measured RF fading, real congestion or a 5G radio test.

## Recommended topology and required equipment

```text
Existing home LAN spare Ethernet port (unchanged)
       |
Linux test-only UP port -- software bridge -- test-only DOWN port
                                            |
                                  Dedicated wired access point
                                  SSID: SmartConnect-Lab
                                            |
                                      Mac en0 (Wi-Fi)
Mac en6 ------------------- existing iPhone USB cellular tether
```

The bridge is inserted only into the new AP's cable, NEVER between the household
router and its existing uplink/switch/devices. All household equipment keeps its
existing connections. The Mac and iPhone remain stationary. The emulated delay
and rate limit affect only the AP branch; en6 bypasses the bridge entirely.
A dedicated AP alone cannot guarantee controlled deterioration without movement;
the bridge provides a reproducible intervention and clear recovery.

Equipment, to borrow/reuse before purchasing:

- One dedicated Ethernet AP with **native bridge/access-point mode**, independently
  configurable SSID/security and no active DHCP server in that mode. A supported
  spare AP is sufficient; the TP-Link TL-WR3002X manual is one documented example
  of an AP-mode device, not a tested SmartConnect hardware endorsement. Verify the
  exact model/revision/mode and designated Ethernet uplink before buying/connecting.
- A spare Linux laptop/mini-PC with two Ethernet ports, or Raspberry Pi 4/5 plus
  a Linux-supported USB Ethernet adapter, storage and appropriate power supply.
  Linux must provide `ip`, `bridge`, `tc`, `sch_netem`, systemd timers and sudo.
  The Pi alternative requires model/adapter-driver checks; no throughput rating
  is assumed. Two clearly labelled data ports are mandatory.
- Two Ethernet patch cables, a spare existing home-LAN port, and a local keyboard/
  screen or independent management interface on Linux. Administration must not
  depend on the link being impaired. No new switch is needed if a free port exists.
- Existing Mac/iPhone/USB cable, cellular data allowance and a second operator for
  timed condition changes. Do not use the household router as the Linux host.

If no spare LAN port or equipment exists, pause for inventory rather than
unplugging household devices. For a venue, obtain permission for its wired uplink;
otherwise rehearse at home and present a clearly labelled recorded demonstration.
A second independent cellular uplink for the AP can provide portability, but it
adds equipment/variability and must not reuse en6 as both comparison paths.

## Why this is a defensible experiment

Linux bridging forwards Ethernet at Layer 2. `netem` can delay/rate-limit packets
on an egress interface. Put the qdisc on the physical DOWN port toward the AP:
responses to Mac ICMP probes and HTTPS downloads pass it. Do not apply it to UP,
the household uplink, en0/en6, or a bridge master whose datapath is unverified.
Downlink-only impairment is intentional; no IFB/ingress redirection is required.
The commanded setting is an emulation input, NOT a measured RTT/goodput result.
The observed request and ping metrics must verify its actual effect.

Primary references checked for this proposal:

- [Linux kernel Ethernet bridging](https://docs.kernel.org/networking/bridge.html)
- [ip-link syntax](https://man7.org/linux/man-pages/man8/ip-link.8.html)
- [iproute2 netem manual and timer/rate limitations](https://man7.org/linux/man-pages/man8/tc-netem.8.html)
- [systemd transient timer commands](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)
- [TP-Link AP-mode setup](https://www.tp-link.com/au/support/faq/1384/)
- [Example AP-mode hardware manual](https://static.tp-link.com/upload/manual/2025/202503/20250324/1910013931_TL-WR3002X%201.0_UG_REV1.0.0.pdf)
- [Raspberry Pi networking hardware](https://www.raspberrypi.com/documentation/computers/getting-started.html)

## Exact setup sequence — proposed, not authorized to execute yet

1. **Approve and identify hardware.** Record model/firmware, Linux distribution,
   kernel and iproute2 versions, labelled UP/DOWN interface names/MACs and cabling.
   Use a dedicated Linux machine, local console and unconnected test data ports.
   A hardware-specific review is needed before substituting interface names.
2. **Prepare the AP offline.** With no home cable attached, use its own management
   UI and model manual to choose native Access Point/bridge mode. Create only
   `SmartConnect-Lab` with a new WPA2-AES/WPA3 password shared with the test Mac
   only. Set its actual country correctly; use a fixed supported channel/band for
   the test and record it. Disable this AP's DHCP server, automatic/Smart DHCP,
   repeater/mesh mode and any built-in traffic shaper. Its management address should
   be a DHCP client on the existing LAN, not a conflicting static address. No home
   AP SSID/password/channel/settings are changed. Never expose an unconfigured
   factory DHCP server to the home LAN. If these controls cannot be verified, stop.
3. **Prepare Linux offline.** Install iproute2 and the matching kernel netem module
   using the distribution's supported package mechanism. Make only the two labelled
   test NICs unmanaged by its network manager (on NetworkManager systems, the
   proposed commands below do that). They must have no IP addresses/default routes
   and must not be the management connection. If they do, stop for a scoped setup
   review instead of blindly flushing production configuration.
4. **Create a nonpersistent transparent bridge at the Linux console.** The commands
   below require administrator privileges **on the dedicated Linux test box only**.
   They are templates with intentionally unresolved names, not commands for macOS.

```sh
# Linux ONLY, after approval and physical port identification:
SC_UP='REPLACE_WITH_TEST_UPLINK_NIC'
SC_DOWN='REPLACE_WITH_TEST_AP_DOWNLINK_NIC'
ip -brief link
ip -brief address
ip route show
# Only if this dedicated Linux installation uses NetworkManager:
sudo nmcli device set "$SC_UP" managed no
sudo nmcli device set "$SC_DOWN" managed no
# Recheck: both data NICs must be unaddressed and not carry management/default routes.
ip -brief address
ip route show
sudo modprobe sch_netem
sudo ip link add name scbr0 type bridge stp_state 0
sudo ip link set dev "$SC_UP" master scbr0
sudo ip link set dev "$SC_DOWN" master scbr0
sudo ip link set dev "$SC_UP" up
sudo ip link set dev "$SC_DOWN" up
sudo ip link set dev scbr0 up
bridge link show
tc -s qdisc show dev "$SC_DOWN"
```

There is one upstream connection and no loop. Do not add DHCP/DNS services, NAT,
IP forwarding rules, firewall rules or addresses to the bridge. Do not disable a
firewall to make it work. Existing Linux bridge filtering/manager behavior may
need hardware-specific review; if forwarding fails, stop. No provisioning shell
script is shipped/executed by this plan. Preserve pre-setup NIC/manager settings
for later restoration. If root qdiscs are custom, stop instead of replacing them.

5. **Connect the isolated branch.** Existing spare home LAN port → Linux UP;
   Linux DOWN → AP's designated AP-mode Ethernet uplink. No other AP clients or
   cables. Verify only the home DHCP service is assigning addresses before adding
   the Mac; no bridge loops or unexpected LAN services. Keep normal household use.
6. **Approve the Mac association change separately.** Manually join
   `SmartConnect-Lab` in the macOS Wi-Fi UI, keeping iPhone USB connected. This
   changes en0's association and may renew DHCP/default-route/DNS information
   normally; do not claim Mac networking is unchanged by joining an SSID. No
   manual `route`, `networksetup`, DNS, firewall or priority commands are used.
   Confirm interface names remain en0/en6 and both paths work with the existing
   bounded pilot tooling. Stop if names or paths differ; do not silently remap.
7. **Verify clean baseline before any shaping.** Reuse the P-1 measurement sizes,
   target and stationary procedure but use a NEW directory/labels. Check actual
   latency, goodput, loss, binding failures and cellular variability. Confirm the
   bridge DOWN qdisc counters see test traffic and no other clients use the AP.
   Record baseline qdisc output/configuration. Baseline with this equipment is a
   NEW baseline; old downstairs/stable results are not matched controls.

## Proposed impairment and safe removal — dedicated Linux box only

Start with deterministic **100 ms extra DOWN egress delay, 512 kbit/s configured
rate, no configured random loss**, queue limit 1,000 packets. This should leave
Wi-Fi reachable while making it a worse request/download path; it is a hypothesis
requiring measurement, not an asserted result. Delay is applied to downstream
frames, not 100 ms in each direction. Kernel timing, queueing, TCP and framing
mean observed RTT/goodput will not equal simple configured numbers. Queue limits
can still cause drops; save `tc -s` counters. No household congestion generation.

Before each induction, at the Linux console, schedule an independent 90-second
rollback, verify its timer is active, then add only the test qdisc. Timer expiry
is a backstop, not the planned recovery marker. Failure to arm it means no test.
Example commands after approval and review of installed tool paths/versions:

```sh
SC_TC="$(command -v tc)"
SC_ROLLBACK="sc-netem-rollback-$(date +%s)"
sudo systemd-run --unit="$SC_ROLLBACK" --on-active=90s --timer-property=AccuracySec=1s "$SC_TC" qdisc del dev "$SC_DOWN" root handle 40:
sudo systemctl is-active "$SC_ROLLBACK.timer"
# Proceed only if the timer is active and the baseline qdisc was checked:
sudo tc qdisc add dev "$SC_DOWN" root handle 40: netem delay 100ms rate 512kbit limit 1000
date -u +%Y-%m-%dT%H:%M:%SZ
sudo tc -s qdisc show dev "$SC_DOWN"
```

Save timestamped command results/counters in a new Linux experiment log. If `add`
fails, stop and cancel the timer; never change to `replace` to overwrite an
unknown qdisc. The handle limits deletion to the experiment's qdisc. If the timer
fires, verify qdisc removal and mark its actual time. Never extend it to force a
switch. Its scheduling precision is not a hard real-time guarantee; the local
operator remains responsible for manual recovery. Prove the timer/cleanup works
in the approved short preflight before a full run.

For planned recovery OR emergency abort, at the Linux console:

```sh
date -u +%Y-%m-%dT%H:%M:%SZ
sudo tc -s qdisc show dev "$SC_DOWN"
sudo tc qdisc del dev "$SC_DOWN" root handle 40:
sudo systemctl stop "$SC_ROLLBACK.timer"
sudo systemctl stop "$SC_ROLLBACK.service"
sudo tc -s qdisc show dev "$SC_DOWN"
```

A missing handle after automatic removal can return an error: verify no handle
40 remains, do not delete other qdiscs. Confirm both timer/service are inactive
before ANY subsequent induction; stale timers must not delete a later test's
qdisc. Check the restored default qdisc matches the baseline's relevant behavior.
Stopping a timer does not itself remove the qdisc. Retain all errors/output.

Emergency procedure: Ctrl-C the Mac workload, remove the experiment qdisc at the
Linux console, cancel its timer/service, and verify recovery. If the lab branch
fails, disconnect only its UP cable and manually return the Mac to the original
home SSID; this association change also requires prior approval. Keep USB intact.
Do not change household equipment or reset its router. Removing a dedicated box
cannot recover a live TCP session; existing Mac applications can stall throughout.
After the whole test, remove only the lab bridge/unenslave the labelled ports at
its console and restore their recorded manager state, or power off the dedicated
box with its UP cable removed. No persistent configuration is required.

## Short preflight gate before the full experiment

Only after hardware/setup/impairment approval: run clean → impaired → clean pilot
with both devices stationary, the same 4×10-packet windows and four 64-KiB HTTPS
requests per path/stage as P-1. Every output directory is new. Arm the rollback
immediately before the impaired stage; if it expires before collection completes,
keep that stage as mixed and stop for review rather than pretending full impairment.
Applying/removing the qdisc is the ONLY intended condition intervention.

Predeclare the same manipulation/recovery and cellular-control tolerances as P-1.
Additionally inspect queue counters and achieved RTT/goodput, not just successful
`tc` commands. Counter evidence is intervention evidence, not packet-confirmed
Mac egress. If this configuration does not produce the intended contrast, retain
it and revise a new labelled protocol before repeating; do not tune mid-run.

**Video Call feasibility matters:** the downstairs pilot's cellular baseline
median RTT was 67.28 ms, above the existing 60 ms Video Call guardrail. Do not
relax that guardrail for a demo. If contemporaneous cellular inputs breach it,
SmartConnect can correctly decline cellular even when Wi-Fi degrades. File
Download's observed loss guardrail has no RTT cap and is the primary live-demo
candidate. Preflight must check actual profile eligibility and enough advantage
for the existing margin; there is no guaranteed return-to-Wi-Fi recommendation
if recovered Wi-Fi still lacks sufficient advantage. Report holds and adverse
results, not only successful selections.

## Paired evaluation after preflight review and explicit full-run approval

Keep all engine/profile parameters, target, devices and station positions fixed.
Use the existing Phase 4 4-trial/12-cycle/64-KiB/10-second protocol (96 rounds,
up to 384 requests, 24 MiB requested-payload ceiling). Per profile/trial block:
cycles 0–3 clean, 4–7 impaired, 8–11 recovered, one uninterrupted controller.
The second operator adds the qdisc after cycle 3's TWO outcome requests finish,
and removes it after cycle 7's TWO outcomes finish, during the 10-second pauses.
Use the progress observer from the location protocol for cycle identification;
its MOVE/RETURN words now mean ADD/REMOVE test qdisc, never physical movement.
No built-in barrier exists. Late/overlapping interventions are mixed-condition
pairs retained in overall reports and separated from stationary-stage analysis.
Log actual Linux intervention times and Mac window/request times; record clock
offset/uncertainty between machines. Do not assign an exact Mac event-response
latency from unsynchronized clocks or from cycle number alone.

Proposed Mac command ONLY AFTER those approvals:

```sh
cd ~/smartconnect
source venv/bin/activate
sc_lab_dir="$PWD/mac_hub/logs/phase4-lab-netem-$(date -u +%Y%m%dT%H%M%SZ)"
python -m mac_hub.phase4.run --execute --output "$sc_lab_dir" --trials 4 --cycles 12 --bytes 65536 --interval 10 --condition dedicated_AP_downlink_netem_100ms_512kbit
```

Both policies receive the same real ICMP/calibration inputs before their actual
outcomes; policy and probe order alternate, as does profile order. Wi-Fi-first
prefers reachable Wi-Fi even if slow. If Wi-Fi becomes unavailable, it may also
fall back to cellular; this is not automatically a unique SmartConnect benefit.
Never feed a later outcome backwards into a decision. Missing remains missing.

After collection, preserve originals, source snapshots, qdisc stats/times,
hardware/versions and clock-offset notes. Existing offline commands:

```sh
python -m mac_hub.phase4.report "$sc_lab_dir"
python -m mac_hub.phase4.report "$sc_lab_dir" --audit-only
streamlit run mac_hub/phase4/dashboard.py
```

The existing report is whole-run/per-profile, not automatic clean/impaired/recovery
analysis. Derive stage-specific paired tables separately with documented event
alignment, exclusion counts and uncertainty, keeping raw evidence unchanged.
Report both successful-response/goodput contrasts and failed/no-path slots.
Require different selected paths before attributing contrasts to selection.
Use the prior fixed trial-cluster uncertainty convention, recognizing four
adjacent trials are exploratory. Publish negative intervals/harms and unchanged
recommendations too. New-request failure gaps include cadence/other probes;
existing-session disruption and video QoE are unmeasured.

## Physical proof and achievable EDGE demonstration

Without new dual-interface packet evidence, display **requested/bound interface,
physical egress unverified**. All Phase 4 rows stay unverified. For a confirmed
change, separately approved capture must correlate SmartConnect OUTCOME flows
before and after the decision to their tuple/time/handshake/payload on en0 vs en6,
not merely observe periodic cellular probes. Require readiness, clean termination,
drop counts, hashes and per-flow reasons. Timing of a new connection on a new
path is not seamless migration. The frozen Phase 3 proof applies only to its four
historical requests, not this setup. Capture scope/endpoint/duration and an
appropriate verifier require separate review; no capture command is run here.

Achievable presentation plan:

1. Rehearse/audit the full run in advance (~20–30 minutes in typical conditions;
   longer with failures). Check setup and rollback first, not on stage.
2. For a short poster/demo slot, show the actual clean → impaired → recovered
   traces and paired request outcomes from that rehearsal, plus a clearly dated
   2–3-minute recording of one profile block. Label it recorded real-traffic
   evidence under emulated path impairment, not a live RF fade.
3. With sufficient stage time and separate approval, run an abbreviated two-trial
   paired protocol (`--trials 2 --cycles 12 --bytes 65536 --interval 10`) live,
   around 10–15 minutes normally, with 12 MiB requested-payload ceiling and at most
   192 requests. Two trials do NOT support the report's four-trial uncertainty
   interval. Do not silently cancel other blocks to present a complete trial.
4. The current dashboard audits completed manifests, not streaming in-progress
   Phase 4 manifests. Use Terminal/CSV progress during a run; open the completed
   audited directory afterwards. A live-stream dashboard/barrier would be future
   implementation, not a claimed feature of this plan.

The truthful EDGE claim, if supported: **application-aware selection of subsequent
real HTTPS requests across a real Wi-Fi path with controlled emulated impairment
and a real USB-cellular path, evaluated against Wi-Fi-first.** Do not claim poor
RF, actual congestion, seamless sessions, automatic system-wide switching, real
5G radio access or measured application QoE gains from these proxy tests.

## Approval boundary

Still required: approve hardware/cabling inventory, dedicated AP/Linux setup,
manual Mac test-SSID association (and recovery association), short impairment
preflight and automatic lab-only rollback; review those results before approving
the full paired workload. Privileged packet capture is separately unapproved.
No proposed configuration command or experiment in this document was executed.
