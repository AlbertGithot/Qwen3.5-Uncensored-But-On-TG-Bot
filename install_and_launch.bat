@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title HeyMate Installer and Launcher

set "PYTHON_CMD="
py -3 --version >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python --version >nul 2>nul && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    cls
    echo Hello!
    echo I am the installer. Simple and convenient.
    echo.
    echo Python 3.11+ was not found.
    echo Install Python and run this file again.
    echo.
    pause
    exit /b 1
)

%PYTHON_CMD% "%~dp0launcher_cli.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Something went wrong. Exit code: %EXIT_CODE%
    pause
)

endlocal & exit /b %EXIT_CODE%
