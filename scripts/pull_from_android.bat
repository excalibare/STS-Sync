@echo off
cd /d E:\this\repository\where\you\clone

echo ================================
echo  Pulling progress from Android...
echo ================================

python -m sts_syn --config .\config.json pull-progress

echo.
echo Done. Press any key to exit.
pause >nul