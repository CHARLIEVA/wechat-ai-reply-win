@echo off
REM ============================================================
REM  run_bot.bat - unattended start used by watchdog.ps1 (no pause, output to logs\bot.stdout.log)
REM  无人值守启动（看门狗使用）：不暂停，输出写入 logs\bot.stdout.log
REM ============================================================
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
set http_proxy=
set https_proxy=
set all_proxy=
if not exist "logs" mkdir "logs"
py -3.13 -u bot.py > "logs\bot.stdout.log" 2>&1
