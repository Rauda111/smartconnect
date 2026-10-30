# Dashboard evidence-selection verification

The old dashboard defaults selected the earlier `phase3-approved-requests` run
and a nonexistent/different optional verification path. This did not correspond
to the subsequent clean capture. The new selector defaults to the committed clean
Stage A source requests and their exact verified CSV/report, with separate presets
for the controlled, live and earlier unverified runs.

All 46 automated tests passed (the original 44 plus two regression groups).
AppTest confirms 4 packet-confirmed Stage A requests, 0 packet-confirmed requests
for each later workload, and 32/8 successful actual requests respectively.
Switching back restores the historical Stage A confirmation. Loader tests reject
request hash mismatches, changed rows, missing provenance and embedded confirmation
labels without matching evidence. All source paths and provenance are visible.
Historical confirmation is not presented as fresh live path validation.

Both existing audits passed: Phase 3 re-correlated the four saved flows and
reproduced the two later workload reports; Phase 2 verified all 248 policy-run
summaries and independent numerical/report checks. No capture, test HTTP request,
network configuration change or experiment rerun was performed for this update.
The original raw/derived experimental results and earlier verification logs are
preserved. Only dashboard selection/provenance code, tests and documentation
changed, with these additional verification logs retained separately.
