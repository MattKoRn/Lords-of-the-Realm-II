@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt >nul 2>&1
py neural_30s.py
if errorlevel 1 pause
