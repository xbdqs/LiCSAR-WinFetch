# Reviewer-revision validation results

This directory contains compact public evidence added during the reviewer revision. It complements, rather than rewrites, the initial-submission evidence retained one directory above.

## Cross-platform deterministic validation

The revision CI matrix passed all six OS/Python combinations: Windows, Ubuntu and macOS under Python 3.10 and 3.12. The deterministic suite passed 15/15 tests in the local revision environment.

## 106D zero-download temporal-mode comparison

For the two-frame 106D relative-orbit group over 2014-10-24 to 2023-09-07, exact common-pair intersection retained 1,970 pairs. This equals 94.0% of the smaller common-period network (2,096 pairs), not 94% of both original networks. The resulting graph contained four components, a largest component of 213 nodes and three isolated common epochs: 2022-04-09, 2023-03-23 and 2023-08-14.

## Maintained LiCSBAS step-01 bounded comparison

The maintained COMET LiCSBAS repository was tested at commit `a145e6c4217b29eb7348ea95630454a099809098` using frame `124D_04854_171313`, dates 2016-09-09 to 2016-10-03, six interferogram pairs and GACOS disabled. The LiCSBAS step-01 run and LiCSAR-WinFetch each produced all 20 benchmark paths. Nineteen of the 20 paths had identical size and SHA-256 values; all 12 interferogram products were byte-identical. The sole content difference was the representative MLI because the two downloaders selected different available source epochs.

SHA-256 was computed for all 20 benchmark files on both sides. All 19 products with fixed expected sizes matched those sizes; representative MLI size was intentionally left unconstrained because its source epoch depends on the representative-selection rule. No transfer-speed superiority claim is made.

The detailed per-path comparison is retained in `Reviewer1_C5_WinFetch_vs_LiCSBAS01_Equivalence.csv` and its compact summary JSON.
