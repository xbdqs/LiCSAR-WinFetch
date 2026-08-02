# LiCSAR-WinFetch

LiCSAR-WinFetch is an open-source Python tool for Windows-native LiCSAR product
acquisition, resumable transfer, LiCSBAS-ready file organisation, structural
validation, and inventory-only multi-frame temporal planning.

The software does **not** generate interferograms, perform time-series inversion,
mosaic frames, harmonise cross-frame references, model atmospheric effects, or
interpret deformation.

## Main capabilities

- Frame-aware LiCSAR product discovery.
- Resolution of tested direct, redirected, HTML-manifest, and text-manifest resources.
- Parallel transfer with `.part` files, HTTP Range resume, retries, and byte checks.
- Machine-readable file-level reports and logs.
- LiCSBAS-ready `GEOC`/pair organisation for the tested workflow.
- Standalone structural validation of required `unw`/`cc` pairs.
- Multi-frame inventory planning using common calendar intervals, common epochs,
  exact common pairs, and graph-connectivity diagnostics.

The maintained LiCSBAS step 01 already provides frame-aware discovery, parallel
transfer, existing-file checks, representative MLI retrieval, optional GACOS
retrieval, and the established directory hierarchy. LiCSAR-WinFetch is a
complementary Windows-oriented client; it is not a replacement for LiCSBAS.

## Installation

Python 3.10 or later is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Alternatively:

```powershell
conda env create -f environment.yml
conda activate licsar_download
```

## Single-frame dry run and download

Review `config_example.json` first. The distributed example has `dry_run` enabled.

```powershell
python download_licsar_windows.py --config config_example.json --dry-run
```

After checking the frame, dates, products, output directory, and expected queue,
set `dry_run` to `false` or run without the command-line dry-run override:

```powershell
python download_licsar_windows.py --config config_example.json
```

Incomplete transfers remain as `.part` files. The final filename is exposed only
after the available remote-size check succeeds.

## Multi-frame inventory planning

The Qilian Mountains example is **metadata-only** and must not be interpreted as a
22-frame raster-download script.

```powershell
python multiframe_planner.py `
  --frames examples\qilian_metadata_planning\qilianshan_frames.json `
  --start 20141001 --end 20260728 --mode common-period `
  --output Qilian_Multiframe_Plan
```

The planner creates frame, epoch, pair, relative-orbit, direction, and project
summaries plus a machine-readable plan. Exact common epochs and pairs are evaluated
only for comparable same-relative-orbit groups. Across different relative orbits,
a common calendar interval is the conservative default.

## Validate an existing frame

```powershell
python verify_licsbas_structure.py data\021D_04972_131213
```

The default check requires complete, non-empty `unw`/`cc` pairs and reports
frame-level auxiliary products separately. Use `--strict` only when every listed
auxiliary is required by the intended workflow.

## Tests

```powershell
python -m compileall -q .
python download_licsar_windows.py --help
python multiframe_planner.py --help
python verify_licsbas_structure.py --help
python -m unittest discover -s tests -v
```

The deterministic tests use synthetic HTTP responses and temporary files. They do
not establish compatibility with every future archive representation or every
LiCSAR frame.

## Paper evidence and figures

The `paper/` directory contains:

- evidence summaries and sanitised LiCSBAS step-02 logs;
- figure source data;
- independent scripts for all four manuscript figures;
- final PNG/PDF figures;
- the two manuscript table data files.

Recreate all figures with:

```powershell
python paper\figures\Code\plot_all_figures.py
```

The 22-frame Qilian case is an inventory-planning case; no Qilian GeoTIFF collection
was downloaded. The bounded benchmark demonstrates one tested transfer and one
LiCSBAS step-02 execution boundary. It does not establish global compatibility,
transfer-speed superiority, geophysical pixel validity, or later LiCSBAS processing.

## Repository structure

```text
LiCSAR-WinFetch/
├─ download_licsar_windows.py
├─ multiframe_planner.py
├─ verify_licsbas_structure.py
├─ config_example.json
├─ requirements.txt
├─ environment.yml
├─ tests/
├─ validation/
├─ examples/qilian_metadata_planning/
└─ paper/
```

## License and citation

LiCSAR-WinFetch is distributed under GPL-3.0-or-later. See `LICENSE`, `NOTICE`,
and `CITATION.cff`. When a permanent software archive is created, add its DOI to
`CITATION.cff` and cite both the archived software release and associated paper.

## Support

Please use the repository issue tracker for reproducible bug reports. Include the
software version, frame ID, command/configuration with credentials removed, and the
relevant log excerpt. Do not upload authentication files or large LiCSAR rasters.
