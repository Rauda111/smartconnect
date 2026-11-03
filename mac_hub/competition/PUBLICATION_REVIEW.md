# GitHub publication review

Remote read-only check: no codex/edge-competition-demo branch exists on origin.
Remote Phase4 tip: 7bd12b0. Original locally unpushed chain:
7fbc00e -> 71b0ad7 -> c71e746 -> 8f8adfa.
The later sanitized-report commit adds only derived public evidence and tooling.

PUSH BLOCKER: unpublished parent 7fbc00e contains original private socket tuples
in three tracked files:
mac_hub/phase4/evidence/location_pilot_20261030T175502Z/raw/A_before-https/requests.csv
mac_hub/phase4/evidence/location_pilot_20261030T175502Z/raw/B-https/requests.csv
mac_hub/phase4/evidence/location_pilot_20261030T175502Z/raw/A_return-https/requests.csv

Deleting/redacting them only at the branch tip cannot prevent publishing the old
blobs: a normal push uploads reachable history. No push, forced update or history
rewrite has been performed. The original chain and all branches are preserved in
an owner-only permanent LOCAL Git bundle outside /tmp. Private raw copies have
SHA-256 copy verification. No raw evidence was deleted or changed.

Known-token/private-key pattern scan of unpublished changed files found no matching
credentials. Private IP test fixtures in tests are deliberate fictitious examples,
not experimental socket data. This is a heuristic scan, not proof of no secrets.
Existing already-published ancestor data was not rewritten by this backup task.

The public reports use an explicit allowlist: window metrics, scores, statuses,
requested en0/en6 names, binding booleans, timing, byte counts and goodput. Local
IPs, MACs, ports, request IDs, raw errors and ping text are excluded. Report text
was scanned for nonpublic IP/MAC patterns, private field names and home paths.

Required user decision: permit a reviewed sanitized replacement publication
history (which changes affected commit IDs), retaining original commits privately;
or choose an appropriately private remote for original history. Pushing the
current branch unchanged would violate the instruction to keep raw private logs
out of the public repository. We will not bypass that requirement.
