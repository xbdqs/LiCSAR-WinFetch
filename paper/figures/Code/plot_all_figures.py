from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = [
    "figure_1_software_architecture.py",
    "figure_2_download_reliability_and_directory.py",
    "figure_3_qilian_temporal_coverage.py",
    "figure_4_validation_evidence_boundary.py",
]

for script in SCRIPTS:
    print(f"Running {script} ...")
    subprocess.run([sys.executable, str(HERE / script)], check=True)
print("All figures generated in ../Final")
