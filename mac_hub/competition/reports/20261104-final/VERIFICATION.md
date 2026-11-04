# Offline verification of sanitized backup package

89 tests passed, zero failures/errors, in 35.562 seconds using the existing
Python environment and `python -B -m unittest -v`. Three additional public-backup
tests check original-derived output hashes, 46 window/44 request counts, natural
run completeness, private-address/identifier exclusion, download timeout
missingness and unverified-egress labels. Existing 86 tests also passed.

Every archived original copy was independently rehashed: 542 copied files matched.
Owner-only permissions were verified throughout the private permanent archive.
The private full-history Git bundle passed `git bundle verify`.

Public report text passed nonpublic IPv4/MAC/private-field/home-path checks.
Known-token/private-key patterns were scanned in unpublished changed files;
no matching credential was found. Fictitious addresses in unit tests are not raw
experimental identifiers. These checks do not guarantee absence of all secrets.
Two example charts were visually inspected for units, missing values and captions.

Public GitHub push is pending a history decision: an unpublished ancestor contains
raw private socket logs. No force-push, rewrite or upload was performed.

## Subsequent approved publication

The user approved sanitized history. Identified private raw artifacts were excluded
from every reachable competition commit; original history remains privately bundled.
Current public-only test outcome: 83 passed, 6 private-original checks skipped,
zero failures/errors (89 total). See ../../PUBLICATION_REVIEW.md and the commit map.
The initial 89/89 result above describes the original private-evidence checkout.
