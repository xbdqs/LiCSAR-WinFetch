@echo off
cd /d "%~dp0"
python -m compileall -q .
if errorlevel 1 exit /b 1
python -m unittest discover -s tests -v
pause
