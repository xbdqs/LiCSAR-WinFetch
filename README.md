# LiCSAR-WinFetch

LiCSAR-WinFetch is an open-source Python tool for reproducible LiCSAR product acquisition, resumable transfer, LiCSBAS-ready file organisation, structural validation, and inventory-only multi-frame temporal planning.

The project was originally developed to remove a practical acquisition barrier for Windows users. The core implementation uses platform-neutral Python path, networking, temporary-file and rename operations. The reviewer-revision candidate (`1.3.0-rc1`) is configured for continuous-integration testing on Windows, Ubuntu Linux and macOS. The current status of those jobs must be read from the repository **Actions** page; do not infer a pass before the jobs have completed.

The software does **not** generate interferograms, perform time-series inversion, mosaic frames, harmonise cross-frame references, model atmospheric effects, perform ascending/descending LOS decomposition, or interpret deformation.

## Main capabilities

- Frame-aware LiCSAR product discovery.
- Resolution of tested direct, redirected, HTML-manifest and text-manifest resources.
- Parallel transfer with `.part` files, HTTP Range resume, retries and byte checks.
- Machine-readable file-level reports and logs.
- LiCSBAS-ready `GEOC`/pair organisation for the tested workflow.
- Standalone structural validation of required `unw`/`cc` pairs.
- Multi-frame inventory planning using common calendar intervals, common epochs, exact common pairs and graph-connectivity diagnostics.
- Zero-download reviewer validation utilities for temporal-network comparison.
- Bounded correctness-comparison utilities for LiCSAR-WinFetch versus maintained LiCSBAS Step 01 outputs.

The maintained LiCSBAS Step 01 already provides frame-aware discovery, parallel transfer, existing-file checks, representative MLI retrieval, optional GACOS retrieval and the established directory hierarchy. LiCSAR-WinFetch is complementary; it is not a replacement for LiCSBAS.

## Platform support and intended users

The original user case was Windows-first acquisition. The Python core itself is not intended to depend on a Windows-only runtime. For the reviewer revision, the same deterministic tests and command-line checks are configured on:

- Windows (`windows-latest`),
- Ubuntu Linux (`ubuntu-latest`),
- macOS (`macos-latest`),
- Python 3.10 and 3.12.

The public GitHub Actions result is the evidence for the actual pass/fail state. Windows `.bat` files in this repository are convenience launchers only.

## Installation

Python 3.10 or later is required.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux / macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Alternatively, on any supported Conda platform:

```text
conda env create -f environment.yml
conda activate licsar_download
```

## Single-frame dry run and download

Review `config_example.json` first. The distributed example has `dry_run` enabled.

```text
python download_licsar_windows.py --config config_example.json --dry-run
```

After checking the frame, dates, products, output directory and expected queue, set `dry_run` to `false` or run without the command-line dry-run override:

```text
python download_licsar_windows.py --config config_example.json
```

Incomplete transfers remain as `.part` files. The final filename is exposed only after the available remote-size check succeeds.

## Multi-frame inventory planning

The Qilian Mountains example is **metadata-only** and must not be interpreted as a 22-frame raster-download script.

Windows example:

```powershell
python multiframe_planner.py `
  --frames examples\qilian_metadata_planning\qilianshan_frames.json `
  --start 20141001 --end 20260728 --mode common-period `
  --output Qilian_Multiframe_Plan
```

Linux/macOS example:

```bash
python multiframe_planner.py \
  --frames examples/qilian_metadata_planning/qilianshan_frames.json \
  --start 20141001 --end 20260728 --mode common-period \
  --output Qilian_Multiframe_Plan
```

The planner creates frame, epoch, pair, relative-orbit, direction and project summaries plus a machine-readable plan. Exact common epochs and pairs are evaluated only for comparable same-relative-orbit groups. Across different relative orbits, a common calendar interval is the conservative default. Tolerance-based cross-orbit date matching is discussed as a possible extension; it is not claimed as implemented LOS-decomposition functionality in this revision candidate.

## Validate an existing frame

```text
python verify_licsbas_structure.py <FRAME_DIRECTORY>
```

The default check requires complete, non-empty `unw`/`cc` pairs and reports frame-level auxiliary products separately. Use `--strict` only when every listed auxiliary is required by the intended workflow.

## Deterministic tests

Run locally:

```text
python -m compileall -q .
python download_licsar_windows.py --help
python multiframe_planner.py --help
python verify_licsbas_structure.py --help
python -m unittest discover -s tests -v
```

Windows users can also run:

```text
RUN_REVISION_CHECKS.bat
```

Linux/macOS users can run:

```text
./run_revision_checks.sh
```

The deterministic tests use synthetic HTTP responses and temporary files. They do not establish compatibility with every future archive representation or every LiCSAR frame.

## Reviewer-revision validation

The `reviewer_validation/` directory contains utilities specifically added to make the revision evidence reproducible.

### Reviewer 1 comment 3: zero-download four-mode comparison

```text
python reviewer_validation/reviewer_r1_mode_metrics.py --check --output-dir reviewer_outputs
```

This uses the already archived `epoch_inventory.csv` and `pair_inventory.csv`. It does not access the network or download raster data. It compares `independent`, `common-period`, `common-epochs` and `common-pairs` for the 106D two-frame group and reports node/edge counts, components, largest component, isolated epochs, mean degree, edge/node ratio, cycle rank, maximum temporal gap, median temporal baseline and baseline IQR.

The archived inventory currently yields three isolated common epochs under exact-common-pair mode: `20220409`, `20230323` and `20230814`. The script recomputes these values rather than reading a hard-coded result table.

### Reviewer 1 comment 6: SHA-256 for all 20 bounded benchmark files

After locating the existing bounded benchmark frame directory:

```text
python reviewer_validation/hash_manifest.py <WINFETCH_FRAME_DIR> --output-dir reviewer_outputs
```

The exact 20 expected relative paths and byte counts are defined in `reviewer_validation/manifests/bounded_benchmark_20_files.csv`.

### Reviewer 1 comment 5: correctness comparison with LiCSBAS Step 01

After independently producing the same bounded selection with LiCSAR-WinFetch and maintained LiCSBAS Step 01:

```text
python reviewer_validation/compare_bounded_downloads.py <WINFETCH_FRAME_DIR> <LICSBAS_FRAME_DIR> --output-dir reviewer_outputs
```

The script compares the same 20 expected LiCSAR objects by presence, size and SHA-256. It intentionally does **not** compare transfer speed.

See `REVIEWER_REVISION_TESTING_GUIDE_CN.md` for the step-by-step revision workflow.

## Paper evidence and figures

The `paper/` directory preserves the evidence package associated with the initial submission, including sanitised LiCSBAS Step-02 logs, Qilian inventories, figure source data and plotting scripts. Reviewer-revision outputs are kept separately under `reviewer_outputs/` so that new evidence is not silently mixed with the original submission evidence.

Recreate the initial-submission figures with:

```text
python paper/figures/Code/plot_all_figures.py
```

The 22-frame Qilian case is an inventory-planning case; no Qilian GeoTIFF collection was downloaded. The bounded benchmark demonstrates one tested transfer and one LiCSBAS Step-02 execution boundary. It does not establish global compatibility, transfer-speed superiority, geophysical pixel validity or later LiCSBAS processing.

## Repository structure

```text
LiCSAR-WinFetch/
├─ .github/workflows/
├─ download_licsar_windows.py
├─ multiframe_planner.py
├─ verify_licsbas_structure.py
├─ config_example.json
├─ requirements.txt
├─ environment.yml
├─ tests/
├─ validation/
├─ reviewer_validation/
├─ examples/qilian_metadata_planning/
├─ paper/
├─ RUN_REVISION_CHECKS.bat
├─ run_revision_checks.sh
└─ REVIEWER_REVISION_TESTING_GUIDE_CN.md
```

## Version status

- `v1.2.4`: immutable initial-submission release.
- `1.3.0-rc1`: reviewer-revision testing candidate on the `main` branch.
- Do **not** create `v1.3.0` until the reviewer-requested validations have been completed and checked.

## License and citation

LiCSAR-WinFetch is distributed under GPL-3.0-or-later. See `LICENSE`, `NOTICE` and `CITATION.cff`.

## Support

Please use the repository issue tracker for reproducible bug reports. Include the software version, frame ID, command/configuration with credentials removed and the relevant log excerpt. Do not upload authentication files or large LiCSAR rasters.
