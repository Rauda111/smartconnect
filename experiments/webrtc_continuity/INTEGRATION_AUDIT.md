# Integration audit · 7 November 2026

## Repository and preservation

- Starting local branch: `codex/webrtc-render-signaling`, HEAD `22c401b`, matching the user-reported deployed revision. GitHub's connected repository confirms that branch exists and its `cloud_server.py` matches the inspected local entrypoint. The tool did not independently expose Render's active commit or private configuration.
- Implementation branch: `codex/prototype-integration-demo`, isolated at `/private/tmp/smartconnect-prototype-integration`, based on `22c401b`.
- Original worktree preserved: uncommitted `mac_hub/experiments/dashboard.py`, its backup, the Core JS backup and `demo_evidence/` were not modified or discarded.
- An existing separate worktree, `/private/tmp/smartconnect-integrated-video` on `codex/integrated-video-policy`, already contained an uncommitted integration draft. That draft was copied into this isolated worktree, then reviewed, corrected and extended. Its source files were not edited. This delivery does not claim those draft changes as newly invented work.
- No merge, push, production deployment, Render setting change, package installation, probe, media call, route change, Wi-Fi disruption or packet capture was performed. Reading public deployment pages failed through the browsing tool; this is an audit access limitation, not evidence that the service is down.

## Reused implementation

| Layer | Existing behavior retained | Integration addition |
| --- | --- | --- |
| `smartconnect.py` | Video weights, bounds, trend classification and guardrail definitions | No algorithm changes |
| `mac_hub/engine.py` | Partial-metric normalization, trends, availability reset, margin .05, hold 3, dwell 30 s | Same persistent instance across bridge windows |
| `mac_hub/phase4/policy.py` | Video Call RTT/loss adapter | No artificial jitter/throughput/RSSI |
| `mac_hub/competition/run.py` | `Session.decide` and recorded stability state | Bridge calls it directly; does not invoke its HTTPS workload runner |
| `mac_hub/monitor.py` | Bounded Apple `ping -b enN`, no fallback to default-route probing | Approved concurrent `en0`/USB measurements |
| WebRTC core | Real media APIs, same-PC offer/answer, ICE/stall recovery, observations | Session scope, robust answer retry, cached duplicate responses, lifecycle and stale-policy handling |
| Python broker | Token authentication, same-origin controls, bounded private SDP queues | Separate policy writer, strict envelope, leases, replay rejection and delivery acknowledgements |

Video score coverage is 0.60: the existing latency and loss weights are renormalized over measured dimensions. Scores/trends are derived values. Jitter, throughput and RSSI remain unavailable; an ICMP loss observation is not media-packet loss. A timeout means no probe replies, not proof that an interface is physically absent. The available-network display represents current probe reachability, not a cellular radio-generation determination.

## Smallest architecture

```text
Mac en0 + en6
  → approved bounded ICMP monitor
  → existing persistent Video Call Session / Controller / Engine
  → separate writer token + timestamp + increasing window + active session
  → HTTPS POST /policy on the existing shared broker
  → authenticated browser polling on both peers
  → Mac A only: fresh recommendation transition requests ICE restart
  → same peer connection / camera / microphone / receiver observations
  → getStats media progress + separate private candidate/interface evidence
```

The policy collector runs on the Mac. Render never attempts to inspect Mac interfaces. The server uses in-memory state for one controlled two-peer room; it must run as one process/instance. Load-balanced instances without shared state, service restart or idle spin-down require a new explicitly approved session. No persistent public store of SDP, credentials or private candidate addresses is introduced.

## Gaps addressed during review

The base `/policy` endpoint only read a local historical/live log path, while Render instantiated it without such a path. There was no Mac-to-hosted writer. The copied draft introduced that channel but aborted on a single transient transport error and could timestamp measurements only after completion. Delivery could be lost when a polling response vanished, and failed answer transmission needed stronger retry handling. The final integration uses conservative measurement age, bounded control-plane recovery, sequence reconciliation, acknowledged signaling, cached answers, and rejection of changed session scope.

Regression testing exposed an unrelated existing Streamlit `width='stretch'` incompatibility with this Mac's installed version. The exact two-line `use_container_width=True` fix already present in the original working tree was carried into the branch. One existing test also assumed only the `vega_lite_chart` element name; it now recognizes the installed version's `arrow_vega_lite_chart` name while still requiring all five charts. Existing tests cover the behavior; no simulation result or recorded evidence was regenerated in the source tree.

## Remaining practical blockers

1. **Approval/configuration:** production use needs an explicitly approved deployment of this tested branch and a separate writer credential in Render and on the Mac. Existing production remains unchanged. No missing credential prevents local software validation.
2. **Physical test:** the Mac/Windows trial, camera/microphone, ICMP target and cellular usage require explicit approval. Perturbation and packet capture require approval at their own stages. They have not been performed.
3. **Connectivity:** host-only ICE may not traverse carrier NAT/firewalls. An approved authenticated TURN service may be required. A secure private configuration path exists; no account or paid resource was provisioned.
4. **Interface selection:** browser ICE cannot promise `en6` selection. A restart requests renegotiation; its success must be judged by continued media and independently matched/corroborated paths. Controlled Wi-Fi loss may make the surviving path usable but is not automatic named-interface steering.
5. **Timing:** unchanged ICMP windows, three-observation hold and 30-second dwell may be slower than the call's failure detector. Event causes are recorded separately; do not attribute failure-driven recovery to the recommendation engine.

See [INTEGRATION_TESTS.md](INTEGRATION_TESTS.md) for tested scope and [HARDWARE_VALIDATION.md](HARDWARE_VALIDATION.md) for the shortest reproducible path to a defensible physical result.
