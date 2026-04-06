@echo off
setlocal
cd /d "%~dp0"
cd ..
python -m sts_syn --config "config.json" gui
if errorlevel 1 pause
