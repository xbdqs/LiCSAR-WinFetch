@echo off
cd /d "%~dp0"
python download_licsar_windows.py --config config_example.json --dry-run
pause
