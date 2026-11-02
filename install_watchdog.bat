@echo off
REM ============================================================
REM  install_watchdog.bat - register watchdog.ps1 as a scheduled task (runs at logon)
REM  把 watchdog.ps1 注册为计划任务（登录时启动）。请右键“以管理员身份运行”。
REM  Task name: WechatAiReplyWinWatchdog   (override: set WD_TASK_NAME=...)
REM ============================================================
setlocal
cd /d "%~dp0"
if "%WD_TASK_NAME%"=="" set WD_TASK_NAME=WechatAiReplyWinWatchdog
schtasks /Create /F /TN "%WD_TASK_NAME%" /SC ONLOGON /RL HIGHEST /IT ^
  /TR "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"%~dp0watchdog.ps1\""
if errorlevel 1 (
  echo [ERROR] Could not create the task. Run this file as Administrator.
  goto :end
)
schtasks /Run /TN "%WD_TASK_NAME%"
echo.
echo Watchdog installed and started. Log: logs\watchdog.log
echo Pause:   create an empty file "watchdog.disable" in this folder
echo Remove:  uninstall_watchdog.bat
:end
pause
