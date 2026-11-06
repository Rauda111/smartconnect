# UX finalization — 6 November 2026

Branch: codex/dashboard-finalization. Base: cca6afb61bb36b8b051ba8184f1c7831d5911675.
This is local-only work; no push, merge, upload or history rewrite is authorized.

## Scope

The overview shows selection, the reason, both network observations, request
result and full-run totals. Native timeline buttons inspect all eight recorded
windows. Previous/Next, Play/Pause, Restart and three speeds are functional.
Replay advances on elapsed time, not widget rerenders; stops at the final window;
and pauses on manual selection, speed/mode changes, glossary/tour navigation and
technical inspection. Play is disabled while details are open and in Live mode.
Technical tables, charts, scoring, glossary, ledger and provenance have a dedicated
area with collapsed sections. Back to Overview leaves replay paused.

The read-only log picker checks only the conventional approved location, or reads
a user-entered masked path. It does not recursively search private folders or
start collection. Empty, missing, incomplete, corrupt, stale and finished states
use fixed public messages. Neither raw paths nor exception strings are printed.
New live windows do not silently replace the user's inspected window.

## Offline validation

Installed environment: Streamlit 1.45.1, Altair 5.5.0, pandas 2.3.1, Python 3.13.

```sh
/opt/anaconda3/bin/python -m unittest test_dashboard_ux test_dashboard_finalization test_download_decision_display test_competition_demo
```

**39 tests passed**, no failures/errors. Tests cover all timeline windows and
navigation boundaries; replay clocks, pause/resume, speeds and finish/restart;
mode/profile transitions; technical locks, glossary and guided tour; all live
status categories, refresh and inspection preservation; exact recorded data,
missing RTT, historical W4/W18 changes; readback/ledger privacy; and missing or
corrupt evidence. New UI tests deny DNS, probes and HTTPS. Runner integration
uses mocks, never new network observations. `git diff --check` passes.

## Actual browser walkthrough

Verified the existing localhost viewer in the Codex browser, including keyboard
activation of W7, the exact 224.695 ms result, replay finishing at W8 with disabled
Next/Play, Back to Overview, glossary, historical ICMP mode and its arrow-key
window selection, and the live empty state with its return-to-recorded action.
Opening Technical Details during playback exposed a fragment scheduling race;
it was fixed by keeping one local UI clock and gating advancement on explicit
play state. The browser recheck confirmed paused/locked technical inspection
without a changing window. AppTest and pure clock tests also cover this contract.
At 1366 × 768, DOM measurements put both network cards and all three inspected
HTTPS result metrics within the viewport. Supporting footnotes may need scrolling
on smaller displays. Final screenshots are saved under dashboard_screenshots/ux-*.

## Preservation and limits

Engine, scoring policy, thresholds, runner, presentation data adapter, evidence,
UTC timestamps and experimental results remain unchanged from the base commit.
No probes, real HTTPS requests, packet captures, network-setting changes or
unapproved uploads were performed. Browser checks use the existing localhost
viewer only. The earlier full-suite compatibility limits documented in
DASHBOARD_VALIDATION.md are unchanged; no new full-suite pass is claimed.

Healthy/degraded/unknown/unavailable badges describe observed ICMP status/loss,
not certified application QoE. The W7 result remains an availability exception,
not a proactive goodput switch. Wi-Fi-first makes identical selections in this
run; socket readback does not establish physical egress or session continuity.

Live UX is tested with offline fixtures and runner contracts, not an approved
new field collection. Very small screens may need scrolling. The conventional
picker lists only the approved default location; other approved logs must be
entered in the masked field. Historical replay has no HTTPS outcomes or recorded
movement-stage boundaries. Screenshots under dashboard_screenshots/ux-* show the
updated UI; older screenshot files are retained as earlier layout records.

## Exact changed files in this UX commit

- mac_hub/competition/dashboard.py
- mac_hub/competition/dashboard_ui.py
- mac_hub/competition/dashboard.css
- mac_hub/competition/JURY_DEMO.md
- mac_hub/competition/UX_VALIDATION.md
- test_dashboard_ux.py
- test_dashboard_finalization.py
- test_competition_demo.py
- test_download_decision_display.py
- dashboard_screenshots/ux-overview.jpg
- dashboard_screenshots/ux-window7.jpg
- dashboard_screenshots/ux-technical.jpg
- dashboard_screenshots/ux-live-empty.jpg

The launch script and environment are unchanged. Use the existing one-command
launcher documented in JURY_DEMO.md; it now serves the updated local dashboard.
