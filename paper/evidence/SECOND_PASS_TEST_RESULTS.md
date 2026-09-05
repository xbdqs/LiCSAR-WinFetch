# Second-pass test results

- Source compile: passed with Anaconda Python 3.12.3.
- Deterministic unit tests: 15/15 passed.
- Qilian assertions: passed (22; 11/11; 12 groups; required inclusion/exclusion; 2014-11-03 to 2023-09-07; 71.4%-97.1%; 106D 4 components/3 isolated epochs).
- Benchmark local revalidation: 20/20 files, 393,567,184 bytes, 6/6 pairs, 7/7 TIFF headers, 14/14 hash matches.
- LiCSBAS step 02: Ubuntu-22.04, Python 3.10.20, exit 0, GEOCml1, 28 files, no manual reorganisation.
- Initial bundled Python compile passed but tests could not import `requests`; this environment-selection failure was resolved by using the configured Anaconda Python.
- Product downloads in this pass: zero.
