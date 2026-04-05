@echo off
setlocal
cd /d "%~dp0"
python -m sts_syn --config "%~dp0config.json" gui
if errorlevel 1 pause
