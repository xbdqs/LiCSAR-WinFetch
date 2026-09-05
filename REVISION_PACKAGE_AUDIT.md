# Reviewer revision package audit

Version: `1.3.0`
Date: 2026-09-05

## Completed validation

- Cross-platform CI: 6/6 jobs passed (Windows, Ubuntu, macOS × Python 3.10, 3.12).
- Local deterministic tests: 15/15 passed.
- Qilian zero-download planning evidence: 22/22 frame inventories, four-mode 106D comparison, three isolated common epochs explicitly recorded.
- Maintained COMET LiCSBAS Step 01 comparison: 20/20 expected paths present in both outputs, 19/20 byte-identical, all 12 IFG products byte-identical; representative MLI source epoch is the sole content difference.
- SHA-256 coverage: all 20 benchmark files hashed on both sides; 19/19 fixed-size products matched.
- LiCSBAS Step 02: exit 0; all six bounded IFGs processed; GEOCml1 generated with 28 files.

## Scope limits retained

No claim is made for transfer-speed superiority, universal/future LiCSAR archive compatibility, LiCSBAS Step 03+, time-series inversion, cross-frame reference harmonisation, LOS decomposition, or geophysical validity.

## Version history

`v1.2.4` remains the immutable initial-submission release. `v1.3.0` is the reviewer-revision release.
