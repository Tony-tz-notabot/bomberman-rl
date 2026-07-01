@echo off
setlocal enabledelayedexpansion
title Bomberman PVP Launcher

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not added to PATH.
    echo Please install Python 3.7+ from https://www.python.org/downloads/
    echo and make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check if pygame is installed
python -c "import pygame" >nul 2>&1
if %errorlevel% neq 0 (
    echo Pygame is not installed. Installing now...
    python -m pip install pygame
    if %errorlevel% neq 0 (
        echo Failed to install pygame. Check your internet connection and pip configuration.
        pause
        exit /b 1
    )
    echo Pygame installed successfully.
)

:: Change to the directory where the batch file is located
cd /d "%~dp0"

:: Verify main.py exists
if not exist "src\main.py" (
    echo main.py not found.
    echo Please place this launcher in the same folder as src\main.py.
    pause
    exit /b 1
)

echo Starting Bomberman PVP...
python src\main.py

:: Keep the window open if the game closes unexpectedly
pause