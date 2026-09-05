@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo LiCSAR-WinFetch reviewer revision local checks
echo ============================================================
python --version || goto :fail
python reviewer_validation\system_report.py || goto :fail
python -m compileall -q . || goto :fail
python download_licsar_windows.py --help > NUL || goto :fail
python multiframe_planner.py --help > NUL || goto :fail
python verify_licsbas_structure.py --help > NUL || goto :fail
python -m unittest discover -s tests -v || goto :fail
python reviewer_validation\reviewer_r1_mode_metrics.py --check --output-dir reviewer_outputs || goto :fail

echo.
echo ALL LOCAL ZERO-DOWNLOAD CHECKS PASSED.
echo Please ZIP the reviewer_outputs folder or send screenshots/results back.
exit /b 0

:fail
echo.
echo CHECK FAILED. Do not change files yet. Send the error output back for review.
exit /b 1
