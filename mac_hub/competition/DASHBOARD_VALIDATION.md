# Dashboard finalization — 4 November 2026

Base: d611188b0487a2e9e36e817790dfc52f442c7e18, independently confirmed
as remote codex/edge-competition-demo tip. Named working folders were absent;
recovered from the preserved post-sanitization bundle without modifying backups
or importing private historical refs. Initial disk space: approximately 4.1 GiB.

Changes: dashboard, offline presentation adapter, localhost/dark configuration,
Mac launcher, jury script, new regression tests and updated UI assertions.
Engine, policy, collector, thresholds, evidence, original app and logs are unchanged.

## Results

Focused offline suite: **27 passed**, no failures/errors:

```sh
/opt/anaconda3/bin/python -m unittest test_dashboard_finalization test_download_decision_display test_competition_demo
```

Checks include exact eight-window selections, W6 timeout, W7/W8 missing RTT,
exact cellular times, request roles/totals/body sizes, hash mismatch, privacy,
AppTest windows 1/6/7/8, both historical profiles, W4/W18 replay changes,
missing/empty/malformed/fresh/stale live files, completed/error manifests and
mocked runner compatibility. Recorded/historical UI tests deny DNS, probes and HTTPS.

Full discovery: **94 considered; 85 passed, 6 skipped, 3 failed**.
Failures affect unchanged original dashboards: test_app chart count,
test_mac_hub dashboard and test_mac_hub_experiments dashboard. They depend on
newer chart behavior, including width='stretch', than this Mac's installed
Streamlit 1.45.1 / Altair 5.5.0 / pandas 2.3.1. All three were reproduced against
unmodified d611188 source with Git metadata. Six private-original checks remain
intentionally skipped in public history. This is not a clean full-suite pass.

`git diff --check` passes. Engine, policy, runner and reports compare unchanged
against d611188. Actual localhost rendering inspected in headless Chrome;
recorded W1 and W7 screenshots are saved locally in dashboard_screenshots/.

## Limits

No actual probes, measurement DNS, HTTPS transfers, captures or network changes.
Live mode is verified using offline fixtures and runner contracts, not a new field
run. Browser QA covers desktop; smaller screens use Streamlit responsive columns.
The poster was not supplied; the requested navy/cyan palette was used.
The launcher needs an existing Python environment containing Streamlit/pandas/Altair
and installs nothing. Public hashes validate the retained package manifest, not
independent collection authenticity. Evidence provenance and limitations remain.
