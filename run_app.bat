@echo off
title DhVaani - ZipVoice Speech Studio
echo ========================================================
echo        Starting DhVaani ZipVoice Speech Studio...
echo ========================================================
echo.

cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment Python...
    "venv\Scripts\python.exe" web_app.py 7860
) else (
    echo [WARNING] venv not found, using global python
    python web_app.py 7860
)
pause
