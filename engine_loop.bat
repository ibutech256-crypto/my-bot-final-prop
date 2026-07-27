@echo off
cd /d C:\prop-frim-bot
:loop
.venv\Scripts\python.exe -u backend\manage.py run_mt5_engine
timeout /t 5 /nobreak >nul
goto loop
