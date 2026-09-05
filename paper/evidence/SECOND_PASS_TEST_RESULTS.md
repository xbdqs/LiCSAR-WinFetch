# Initial-submission second-pass test results (historical record)

This file preserves the evidence state used for the initial v1.2.4 submission. Reviewer-revision evidence supersedes the sampling-based hash/header statements below and is documented in `revision/REVISION_VALIDATION_RESULTS.md` and `reviewer_validation/reference_outputs/R1C5_R1C6/`.

- Source compile: passed with Anaconda Python 3.12.3.
- Deterministic unit tests: 15/15 passed.
- Qilian assertions: passed (22 frames; 11 ascending/11 descending; 12 groups; 2014-11-03 to 2023-09-07 maximum common calendar interval; 71.4%-97.1% same-orbit exact-pair retention; 106D four components/three isolated epochs).
- Initial bounded benchmark revalidation: 20/20 files, 393,567,184 bytes, 6/6 pairs, 7/7 sampled TIFF headers, and 14/14 sampled hash matches.
- LiCSBAS step 02: Ubuntu-22.04, Python 3.10.20, exit 0, GEOCml1, 28 files, no manual reorganisation.
- Product downloads in this historical second pass: zero.

## Reviewer-revision superseding checks

The revision subsequently computed SHA-256 for all 20 benchmark files on both LiCSAR-WinFetch and maintained LiCSBAS step-01 outputs. All 20 expected paths were present in both outputs, 19/20 files were byte-identical, and all 12 interferogram products were byte-identical. The sole difference was the representative MLI source epoch. Cross-platform CI also passed 6/6 Windows/Ubuntu/macOS × Python 3.10/3.12 jobs.
