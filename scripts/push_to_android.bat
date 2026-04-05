@echo off
cd /d E:\this\repository\where\you\clone

echo ================================
echo  Pushing progress to Android...
echo ================================

python -m sts_syn --config .\config.json push-progress

echo.
echo Done. Press any key to exit.
pause >nul