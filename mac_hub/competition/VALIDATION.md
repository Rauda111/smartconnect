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
