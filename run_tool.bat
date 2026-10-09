@echo off
chcp 65001 > nul
title LeEco Le S2 (MSM8976) VoLTE Enabler Tool

:: 1. Launch directly using integrated Embedded Python runtime (zero install required)
if exist "%~dp0python\python.exe" (
    "%~dp0python\python.exe" "%~dp0main.py"
    goto :done
)

:: 2. Fallback to system Python if embedded folder is absent
echo ==============================================================
echo    Verifying host Python runtime environment...
echo ==============================================================

where python >nul 2>nul
if errorlevel 1 goto :no_python

python -c "import serial" >nul 2>nul
if errorlevel 1 goto :install_serial

goto :launch_system

:install_serial
echo [*] Installing required dependency: pyserial...
pip install pyserial
if errorlevel 1 goto :pip_err
goto :launch_system

:no_python
echo [ERROR] Python was not found on your system and embedded bundle is missing!
echo Please install Python 3 and ensure "Add Python to PATH" is checked.
echo ==============================================================
pause
exit /b 1

:pip_err
echo [WARNING] Automatic installation of pyserial failed.
echo If the tool fails to start, open CMD and run: pip install pyserial
echo ==============================================================
goto :launch_system

:launch_system
echo [+] Environment validated. Launching tool...
echo ==============================================================
python "%~dp0main.py"

:done
pause
