# Reviewer-revision repository package audit

Candidate: `1.3.0-rc1`

Purpose: replace the **main-branch working tree** for reviewer testing while preserving the immutable initial-submission `v1.2.4` tag/release.

Checks completed during package assembly:

- Source compilation: PASS.
- Existing deterministic unit tests: 15/15 PASS on the assembly Linux environment.
- Zero-download 106D reviewer regression: PASS.
- 106D exact-common-pair reference result recomputed from archived inventories: 1970 common pairs, 4 graph components, 3 isolated common epochs (`20220409`, `20230323`, `20230814`).
- Figure 3 regenerated with the three isolated 106D common epochs marked.
- Cross-platform GitHub Actions matrix configured for Windows, Ubuntu and macOS, Python 3.10 and 3.12. **The package does not claim these jobs passed until the author uploads the candidate and the Actions jobs actually finish.**
- Full 20-file bounded benchmark manifest included.
- Full-20 SHA-256 utility included, but no new 20/20 result is claimed until run on the author's local benchmark.
- LiCSAR-WinFetch versus maintained LiCSBAS Step 01 equivalence utility included, but no equivalence result is claimed until both bounded directories are actually produced/located and compared.
- No Qilian bulk GeoTIFF download is included or required.
- No credentials, tokens, cookies, benchmark rasters or 22-frame raster collection are included.
- Public citation/notice authorship is aligned with the submitted manuscript author: Qingsong Du.

After upload, the first feedback required is the GitHub Actions result plus the Windows `RUN_REVISION_CHECKS.bat` result. Do not create `v1.3.0` before these checks and the remaining reviewer validations are complete.
