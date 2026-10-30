@echo off
REM ============================================================
REM  start.bat - start the LEGACY puppet-xp bot (needs WeChat 3.9.10.27)
REM  If this window closes immediately, open cmd and run:
REM    cd /d <project folder>
REM    start.bat
REM ============================================================
setlocal
cd /d "%~dp0"
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found. Run install.bat first.
  goto :end
)
if not exist "node_modules" (
  echo [ERROR] node_modules missing. Run install.bat first.
  goto :end
)
if not exist ".env" (
  echo [ERROR] .env missing. Copy .env.example to .env and fill in OPENAI_API_KEY.
  goto :end
)
echo Prerequisite: WeChat for Windows 3.9.10.27 is running and logged in.
echo Press Ctrl+C to stop.
echo.
node scripts\check-config.js
if errorlevel 1 goto :end
node src\index.js
:end
echo.
pause
