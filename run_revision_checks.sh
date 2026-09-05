#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python --version
python reviewer_validation/system_report.py
python -m compileall -q .
python download_licsar_windows.py --help >/dev/null
python multiframe_planner.py --help >/dev/null
python verify_licsbas_structure.py --help >/dev/null
python -m unittest discover -s tests -v
python reviewer_validation/reviewer_r1_mode_metrics.py --check --output-dir reviewer_outputs
echo "ALL LOCAL ZERO-DOWNLOAD CHECKS PASSED."
