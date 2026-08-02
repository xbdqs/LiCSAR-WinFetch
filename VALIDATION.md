# Validation instructions

## Deterministic checks

```powershell
python -m compileall -q .
python download_licsar_windows.py --help
python multiframe_planner.py --help
python verify_licsbas_structure.py --help
python -m unittest discover -s tests -v
```

These checks do not require a network connection or raster download.

## Bounded network validation

Use a dedicated JSON configuration with a short date range and a small selected
network. Inventory before transfer, record the selected epochs and pairs, and stop
if the queue is larger than intended. Never use the Qilian 22-frame example as a
bulk-raster benchmark.

## Downstream LiCSBAS check

Directory validation is not the same as executing LiCSBAS. Report step 02 as passed
only when an actual command log, zero exit code, and generated output directory are
available. Do not continue to full time-series processing as part of this check.

