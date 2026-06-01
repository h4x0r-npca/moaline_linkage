@echo off
set "PY38=%LOCALAPPDATA%\Programs\Python\Python38-32\python.exe"

if not exist "%PY38%" (
    echo Python 3.8 32-bit not found: %PY38%
    pause
    exit /b 1
)

echo Python: %PY38%
"%PY38%" build_helper.py

echo Done! dist\
pause
