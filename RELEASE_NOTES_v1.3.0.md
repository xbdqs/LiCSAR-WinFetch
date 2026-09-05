# LiCSAR-WinFetch v1.3.0

This release incorporates the reviewer-requested validation and documentation updates for the SoftwareX revision while preserving `v1.2.4` unchanged as the initial-submission release.

## Main revision evidence

- Cross-platform CI: 6/6 jobs passed on Windows, Ubuntu and macOS with Python 3.10 and 3.12.
- Deterministic unit tests: 15/15 passed.
- Qilian inventory planning: 22/22 frame scans; 12 relative-orbit groups, including two single-frame groups for which exact intersection metrics are not applicable.
- 106D four-mode zero-download comparison: exact common-pair mode retained 1,970 pairs, equal to 94.0% of the smaller common-period network (2,096 pairs), with four components and three isolated common epochs.
- Maintained LiCSBAS Step-01 bounded comparison: 20/20 expected paths present in both outputs; 19/20 files byte-identical by SHA-256; all 12 IFG products byte-identical. The representative MLI differed because the two downloaders selected different source epochs.
- Full SHA-256 coverage: 20/20 benchmark files hashed on both sides; 19/19 fixed-size products matched expected sizes.
- LiCSBAS Step 02: all six bounded interferograms processed successfully, exit code 0, without manual reorganisation.

No transfer-speed superiority, global archive compatibility, later LiCSBAS processing, inversion accuracy or geophysical validity is claimed.
