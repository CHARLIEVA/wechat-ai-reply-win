@echo off
REM uninstall_watchdog.bat - stop and remove the watchdog scheduled task / 停止并删除看门狗计划任务
setlocal
if "%WD_TASK_NAME%"=="" set WD_TASK_NAME=WechatAiReplyWinWatchdog
schtasks /End /TN "%WD_TASK_NAME%" >nul 2>&1
schtasks /Delete /F /TN "%WD_TASK_NAME%"
pause
