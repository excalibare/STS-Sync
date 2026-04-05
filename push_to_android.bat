@echo off
cd /d E:\code\codex\sts_syn

echo ================================
echo  Pushing progress to Android...
echo ================================

python -m sts_syn --config .\config.json push-progress

echo.
echo Done. Press any key to exit.
pause >nul