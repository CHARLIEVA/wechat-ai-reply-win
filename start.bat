@echo off
REM ============================================================
REM  start.bat - start the bot (main engine: wxauto4 + WeChat 4.x)
REM  If this window closes immediately, open cmd in this folder and run start.bat
REM ============================================================
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
where py >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Run install.bat first.
  goto :end
)
if not exist ".env" (
  echo [ERROR] .env missing. Run install.bat, then fill in OPENAI_API_KEY in .env.
  goto :end
)
if not exist "logs" mkdir "logs"
py -3.13 check_config.py
if errorlevel 1 goto :end
echo.
echo Prerequisite: WeChat 4.x is running, logged in, main window open.
echo Do not use WeChat on this PC while the bot runs. Press Ctrl+C to stop.
echo Log file: logs\bot.log
echo.
py -3.13 -u bot.py
:end
echo.
pause
