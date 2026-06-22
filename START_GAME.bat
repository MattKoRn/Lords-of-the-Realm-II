@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt >nul 2>&1
py run_game.py
if errorlevel 1 pause
