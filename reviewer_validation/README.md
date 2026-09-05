# Reviewer-revision validation utilities

These scripts support the revision of SoftwareX manuscript `SOFTX-D-26-00981`.
They are intentionally separated from the initial-submission evidence.

## Zero-download network comparison

```text
python reviewer_validation/reviewer_r1_mode_metrics.py --check --output-dir reviewer_outputs
```

Inputs: archived Qilian `epoch_inventory.csv` and `pair_inventory.csv`.
Network use: none.
Raster downloads: none.

## All-20 benchmark SHA-256

```text
python reviewer_validation/hash_manifest.py <WINFETCH_FRAME_DIR> --output-dir reviewer_outputs
```

Input manifest: `manifests/bounded_benchmark_20_files.csv`.

## LiCSBAS Step 01 equivalence

```text
python reviewer_validation/compare_bounded_downloads.py <WINFETCH_FRAME_DIR> <LICSBAS_FRAME_DIR> --output-dir reviewer_outputs
```

The comparison checks the exact bounded 20-file manifest by presence, size and
SHA-256. It makes no speed claim.
