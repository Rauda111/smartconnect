# Phase 3 verification

All 44 automated tests passed (`full_suite.log`): the 29 existing tests plus 15
Phase 3 tests. `audit.log` records the successful offline Phase 3 check. The
preserved Phase 2 audit also passed (`phase2_preservation_audit.log`). No packet
capture or network setting changes occur in either audit.

The actual approved clean capture's four flows are individually documented in
`../evidence/stage_a_verification/VERIFICATION.md` and `stage_a.json`. Raw PCAPs
remain under ignored local `mac_hub/logs/phase3-stage-a-clean-capture`; source
requests remain under `mac_hub/logs/phase3-stage-a-clean-requests`. Their original
manifests, request data, hashes and derived evidence are committed. No raw PCAPs
are committed. Fresh clones require these retained local capture files to repeat
the packet-level audit. Never substitute requested source IP or HTTP success for
that evidence.

Stage A passed before any engine-driven traffic was executed. Two early
app-side sudo authentications failed before capture readiness; the first
Terminal capture had a shutdown timeout and was not accepted as the complete
Stage A pass. Its packet files and diagnostics remain local. After the user
separately approved the corrected check, the new 60-second capture exited
cleanly with zero drops and the full gate passed. No capture was repeated after
the user's subsequent instruction prohibiting more capture.

The controlled final workload (32 requests) and short live workload (8 requests)
were unprivileged. All succeeded, but each later request's physical egress is
explicitly unverified, confirmed path-change counts/transition delays are blank,
and no bracketed interruption gap was observed. This is not evidence of zero
network outage or seamless session continuity. Source snapshots and hashes
preserve the executed controller versions; the bound HTTPS client is unchanged
from independently verified Stage A.

Unavailable paths, failed binding, timeout, cancellation, reconnection and
recovery were covered by mock/unit scenarios without disrupting household
networks. Actual outage/failure behavior under field conditions was not induced.
No source/evidence under hardware/, cisco/, the original simulation or Phase 1/2
was changed. The existing untracked docs/slides directory was not touched.

Phase 3 CSV artifacts retain the standard CSV writer CRLF bytes. A narrowly
scoped .gitattributes entry prevents newline normalization and accepts CR at
CSV line endings, preserving original evidence hashes.
