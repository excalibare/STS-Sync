@echo off
cd /d E:\code\codex\sts_syn

echo ================================
echo  Pulling progress from Android...
echo ================================

python -m sts_syn --config .\config.json pull-progress

echo.
echo Done. Press any key to exit.
pause >nul