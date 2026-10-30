# Verification evidence

Live smoke capture: 30 October 2026, 19:25:35 Asia/Dubai (15:25:35 UTC), five echo requests per interface to 1.1.1.1 with Apple ping socket binding. Both en0 and en6 returned five replies, zero observed loss. Mean RTT: 22.4976 ms and 24.6308 ms respectively. Adjacent RTT variation: 29.2655 ms and 5.69075 ms. These five-packet observations are a functional check, not a field improvement experiment or statistical loss guarantee. Binding was not independently packet-capture verified. No network settings were changed.

The manifest hashes identify the smoke-tested source; the collector subsequently gained raw-output logging, so those hashes intentionally differ from final source. The capture predates that addition and contains no raw packet text. A preceding sandbox-limited run received no replies; the successful run used execution outside that sandbox. Do not pool these conditions.

Synthetic recovery comparison: deterministic fixture, 60 windows. Wi-Fi-first selected-probe RTT mean 61.6667 ms versus partial SmartConnect 29.5833 ms; observed-breach-or-no-path counts 25 versus 2; recommendation transitions zero versus two. These values verify comparison plumbing and policy response only. They are not live application improvements.

The full suite passed all 17 tests (full_suite.log). The five Mac Hub test groups also passed independently (adapter_tests.log). Existing simulation/dashboard/Cisco source files were retained; the old dashboard test expectation was corrected to include its already-existing hardware tab. Physical Cisco behavior was not rerun.
