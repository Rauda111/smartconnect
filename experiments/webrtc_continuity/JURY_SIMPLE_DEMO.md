# Simple jury workflow

Prepared on the isolated `codex/jury-simple-workflow` branch. This change is not
deployed. Production, the existing staging release, credentials and historical
evidence are unchanged. Fresh staging deployment approval is required.

## Operator flow

The private kit provides three Mac application icons: Prototype 1 — Engine and
Results, Prototype 2 — Mac A, and Offline Recorded Demo. The Windows folder has
Prototype 2 — Windows B.cmd, Offline Recorded Demo.cmd, and Prototype 1 — Verified
Results.cmd. Install that folder on Windows once, before presentation. No file
transfer is needed between calls. The full interactive Prototype 1 dashboard runs
on the Mac; the Windows results shortcut opens its offline presentation.

The two Prototype 2 launchers check for staging support, open Chrome/Edge, and
preselect A/B, SmartConnect-assisted recovery, automatic signaling, and 300
seconds. They never start camera, microphone or recording. Mac policy recovery
is enabled; Windows displays REMOTE MAC recommendations. A fresh separately
approved measurement grant is required for the local real-engine collector.
No grant ships in the kit. No measurements run just by opening Prototype 1.

Refresh keeps access and configuration in that tab but ends any media session.
End Call closes the peer connection, stops tracks and releases broker ownership.
New Call repeats cleanup if necessary and reloads an inert document with retained
configuration. Both laptops choose New Call before the next explicit Start Call.
The engine and WebRTC recovery implementation are reused unchanged.

The main dashboard keeps recommendations, selected media-candidate information,
and physical verification separate. Missing information stays unknown. Inventory,
ICE controls, diagnostic events, evidence exports and the older recorder remain
available under Technical Details. None is a call prerequisite. Manual recording
is separate: select only the SmartConnect window/region, hide private controls
and browser chrome, and obtain the required recording approval first.

## 60-second rehearsal after deployment and fresh live-session approval

Warm free staging before the jury slot; a cold start may exceed this schedule.

1. **0–10 seconds:** connect the iPhone USB hotspot, keep both Wi-Fi links
   available, and use headphones. No route change or Wi-Fi interruption.
2. **10–20 seconds:** double-click Mac A and Windows B. Confirm peer labels,
   private access loaded, NOT STARTED and End disabled. No inventory linking.
3. **20–30 seconds:** click Start Call on B, then A; allow camera/microphone.
4. **30–45 seconds:** wave and speak both ways. Show the measured recommendation,
   observed media candidate and physical verification as distinct claims.
5. **45–60 seconds:** End Call; choose New Call on both. Start B then A again
   only when two calls are explicitly approved. No launcher reopening.

For an offline request, open Offline Recorded Demo. It is the preserved narrated
evidence edition, not newly recorded hardware footage. If venue networking blocks
direct WebRTC, use it immediately. No STUN/TURN server is configured by default;
HTTPS availability does not establish media reachability across client isolation,
NAT or firewall restrictions. Venue compatibility remains a physical acceptance
check and may require a separately approved alternative network.

## Security and lifecycle corrections

- Inert public document navigation previously rejected file-launch navigation
  marked cross-site. Only `/` and `/index.html` top-level document navigation now
  have the narrow public exception, with destination Host validation.
- A dedicated `/launch` accepts top-level URL-encoded POSTs from a file's null
  Origin or the exact application Origin. It requires the existing reader token,
  rejects the writer, validates field count/body size, and never joins a room.
  Existing signaling/policy origin and authorization checks remain strict.
- New private launch files send credentials in the POST body, never in URL
  fragments, query strings or process arguments. The no-store bootstrap removes
  its inert data node, stores access/configuration in sessionStorage, and replaces
  the document. Legacy fragment links remain supported for the preserved kits.
- Approval checkboxes are not persisted. Start is explicit. Saved ownership is
  scoped to role, client and session. Late join completion is released after End;
  late media permission completion stops its tracks. Failed cleanup blocks reset.
- The local watcher requires a fresh owner-only grant, consumes each approved
  session once, locks out duplicate watchers, and supports at most two calls per
  grant. Each collector is bounded to 360 echoes, 270 seconds, en0/en6 and the
  approved target. The absolute room lease is distinct from its rolling idle
  heartbeat deadline; the existing engine decisions and thresholds are unchanged.

## Validation completed

- 118 JavaScript/core/real-engine contract tests passed.
- 100 Python continuity, authentication, policy, budget and tooling tests passed.
- 31 Prototype 1 recorded-data/dashboard regression tests passed.
- Actual in-app browser, loopback HTTP and synthetic credentials: A/B POST
  bootstrap accepted; clean document URL; refresh retained tab access/settings;
  New Call remained inert; 300-second settings and Windows REMOTE MAC labels
  correct; End disabled; no Start clicked and zero broker join requests.
- Actual preserved Prototype 1 viewer loaded its recorded real experiment,
  eight windows and real saved values through the local launcher backend.
- 101 archived evidence entries still match their preservation hashes. The
  offline MP4 and Prototype 1 source/data are copied unchanged into the kit.

The browser security review rejected file:// navigation because its URL policy
blocks that protocol. No alternate route was used to bypass the restriction.
The successful HTTP test is not evidence of native file-origin or double-click
success. Native Windows execution is unavailable here; Mac native app launch and
two actual consecutive media calls remain unverified. No new physical handover,
venue-media compatibility or live measurement result is claimed.

## Short physical acceptance test

After approved staging deployment, install the prepared Windows folder once and
double-click each laptop's launcher. Confirm the dashboard opens without URL
copying; refresh once and verify access/role/settings remain and media stays off.
After separate approval for two bounded calls, Start B then A, verify live audio
and video in both directions, End, New Call on both, then Start B/A again. Check
fresh counters and two local sanitized downloads. This is the remaining shortest
end-to-end acceptance test; no interruption or handover claim is involved.

Developer checks (not operator presentation steps):

```
SMARTCONNECT_TEST_PYTHON=/opt/anaconda3/bin/python node --test experiments/webrtc_continuity/test_*.cjs
/opt/anaconda3/bin/python -m unittest discover -s experiments/webrtc_continuity -p 'test_*.py'
/opt/anaconda3/bin/python -m unittest test_competition_demo test_dashboard_ux test_public_competition_backup
```
