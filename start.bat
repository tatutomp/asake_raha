@echo off
REM Kaynnistaa volatiliteetti-skannerin ja avaa selaimen.
cd /d "%~dp0"
set PYTHONUTF8=1
start "" http://127.0.0.1:5000
py -3.12 app.py
pause
