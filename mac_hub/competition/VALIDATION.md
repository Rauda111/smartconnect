# Offline validation

Final command: existing repository Python environment, `python -B -m unittest -v`.
Result: **76 tests passed, 0 failures, 0 errors**, 33.128 seconds.
Full record: `verification/offline_suite.log`.

15 additive competition tests cover deterministic historical replay and forbidden
network operations, both recommendation transitions, hold/dwell and recovery,
flapping, unavailable/missing paths, new-flow evidence semantics, binding failure
without retry, blocked/certificate-failed/cancelled requests, real TLS-phase failure
with mocked sockets, bounds, failed preparation, cancellation persistence,
no-eligible-path suppression, download calibration integration, privacy allowlist,
partial/corrupt append handling, historical dashboard and live-log failure display.
The preserved 61-test suite also passes. No new actual network observations were
collected. AppTest and mocks are software validation, not a live steering test.

Changes are additive: no Phase1–4 client, policy, runner, collector, historical
result or original log was modified. The competition evidence copy is verified
against the original capture and manifest by SHA-256. Replay remains deterministic
and contains no fabricated HTTPS outcomes or assumed movement boundaries.

Live smoke test and packet capture remain unexecuted and require separate approval.

## Movement-pause update

Full offline suite: **79 tests passed, 0 failures, 0 errors**, 36.940 seconds.
Record: `verification/movement_pause_suite.log`. Targeted competition/movement
suite: 18 passed. Three virtual-clock tests add checks for the exact 90-second
pause after completed Window 2, eight real-window slots only, preserved hold/trend/
selection state, elapsed-time dwell advancement, no extra monitoring/request calls,
cancellation during movement and invalid arguments rejected before output creation.
No actual waits, probes, DNS or HTTPS are used by the new tests. Existing policy,
thresholds, historical capture and live smoke evidence are unchanged.

## Decision inspector and File Download audit update

Final full offline suite: **86 tests passed, 0 failures, 0 errors**, 32.364 seconds.
Record: `verification/download_display_suite.log`. Seven additional tests verify
same-size pre-decision transfers on both interfaces, alternating order, binding
records, independent Mbps/utility/score calculations, differing Video/Download
choices on identical ICMP fixtures, failed/invalid calibration fallback without
retry, public-field privacy, requested vs successful-bound change semantics,
normal switch hold-reset display, and historical/live Streamlit decision inspection.
Targeted final download/display suite: 7 passed. No live probes, DNS, HTTPS or
capture were initiated. Fixture traffic is mocked, never field performance evidence.
Runner, client, collector, policy and all thresholds remain unchanged from c71e746.

## Sanitized public-history checkout

89 tests considered: **83 passed, 6 explicitly skipped, 0 failures/errors**,
35.186 seconds. The six skipped checks require private historical socket originals
excluded from public history (pilot preservation/anti-tampering: 3; saved Stage A
proof/display: 2; stable measured-request audit: 1). All competition functionality,
synthetic networking contracts, replay and sanitized-report tests still run.
The original private checkout's complete 89-test pass is retained separately.
Record: verification/publication_suite.log. No thresholds or traffic code changed.
