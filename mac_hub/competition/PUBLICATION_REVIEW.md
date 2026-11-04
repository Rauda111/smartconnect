# Sanitized publication history

The user approved a sanitized competition publication history on 4 November 2026.
Only codex/edge-competition-demo was rewritten. Main and Phase branches are unchanged.
Original commits and raw evidence remain byte-preserved in the owner-only permanent
local archive, including two verified pre-sanitization full-history Git bundles.

Private raw request CSVs, packet/socket correlation records and raw route outputs
were excluded throughout this branch's reachable history, not merely deleted at
the tip. Aggregate reports and numeric experimental results were retained. The
public Phase3 result report omits opaque original request identifiers. The
competition runner, policy, client and measured values were not changed.

A plain push before sanitization would have exposed private socket information
from unpublished pilot commit 7fbc00e. The review also found older private request
artifacts already present on other published branches; those artifacts are now
excluded from the competition history too. This does NOT erase copies on existing
main/Phase branches or elsewhere on GitHub. Those branches were not force-pushed.

Public evidence uses an allowlist: metrics, scores, statuses, en0/en6, binding
booleans, durations, byte counts and goodput. No local IP/MAC/port, raw errors,
request identifiers or raw packet records are included in the new report package.
Fictitious private addresses in tests and example Linux lab subnets in hardware
source are intentional examples, not collected personal network identifiers.

Tests requiring withheld private originals explicitly skip in a public checkout;
synthetic unit tests, competition integration tests, historical ICMP replay and
sanitized-report checks still run. Historical full-audit logs describe the original
private-evidence checkout, not a promise that omitted raw audits run in public.
For original raw re-auditing use the preserved private original checkout/bundle.

Sanitized reports: reports/20261104-final/. Original hash references establish
export consistency, not authenticated measurements. Charts do not establish
physical handover or application QoE. No experimental traffic occurred during
backup, sanitization or publication; GitHub operations were the only network use.
