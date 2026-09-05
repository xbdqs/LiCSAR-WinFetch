# Reviewer 1 C5-C6 bounded equivalence and SHA-256 validation

## Validation scope

This evidence set addresses Reviewer 1 comments 5 and 6 for LiCSAR-WinFetch.

- Frame: `124D_04854_171313`
- Date range: `20160909` to `20161003`
- GACOS: disabled
- Available epochs in range: 4
- Interferogram pairs: 6
- Expected benchmark files: 20
- Comparison scope: bounded correctness/equivalence only; no transfer-speed claim

## LiCSBAS reference

Maintained COMET LiCSBAS repository:

- Repository: `https://github.com/comet-licsar/LiCSBAS`
- Branch: `main`
- Commit: `a145e6c4217b29eb7348ea95630454a099809098`
- Step 01 script: `LiCSBAS01_get_geotiff.py`
- Script version reported at runtime: `1.7.0 20250907`

Command used:

```bash
LiCSBAS01_get_geotiff.py -f 124D_04854_171313 -s 20160909 -e 20161003 --n_para 4
```

The run completed successfully and produced 6 interferogram directories and 20 benchmark files in `GEOC/`.

## LiCSAR-WinFetch reference

Version tested for the bounded acquisition run: `1.3.0-rc1`. The final `1.3.0` release retains the same acquisition/planning logic; subsequent changes were version metadata, reviewer-evidence packaging, figure/table updates, and the hash-manifest utility fix.

Command used:

```text
python download_licsar_windows.py -f 124D_04854_171313 -s 20160909 -e 20161003 -o <OUTPUT_PARENT> --no-gacos --n_para 4
```

The run completed successfully with:

- 20 files downloaded
- 12/12 required interferogram files complete
- 6 interferogram pairs
- LiCSBAS-compatible GEOC structure verification passed

## File-set and SHA-256 comparison

For the same bounded selection:

- Expected file paths: 20
- Present in both outputs: 20
- Identical file sizes: 19
- Identical SHA-256 values: 19

The sole difference was the representative MLI:

- LiCSBAS Step 01 selected `20160909.geo.mli.tif`
- LiCSAR-WinFetch selected `20161003.geo.mli.tif`

All 12 interferogram products (`6 × unw` and `6 × cc`) and all fixed geometry/metadata products compared in the manifest were byte-identical by SHA-256.

No transfer-speed comparison is claimed.

## Full-file SHA-256 coverage

SHA-256 was computed for all 20 benchmark files on both sides.

For each side:

- Manifest files: 20
- Files present: 20
- Missing files: 0
- Fixed-size products checked: 19
- Fixed-size products matched: 19
- Fixed-size mismatches: 0
- Size-unconstrained representative MLI: 1
- SHA-256 values computed: 20

The representative MLI is intentionally not constrained to a fixed expected byte size because the selected source epoch may differ according to the downloader's representative-MLI selection rule.

## Evidence files

- `Reviewer1_C5_WinFetch_vs_LiCSBAS01_Equivalence.csv`
- `Reviewer1_C5_WinFetch_vs_LiCSBAS01_Summary.json`
- `WinFetch_SHA256_All20.csv`
- `WinFetch_SHA256_Summary.json`
- `LiCSBAS_SHA256_All20.csv`
- `LiCSBAS_SHA256_Summary.json`
