@echo off
REM ============================================================
REM  install.bat - install dependencies / install dependencies
REM  Run from cmd to see errors:  cd /d <project folder> ^& install.bat
REM ============================================================
setlocal
cd /d "%~dp0"
echo.
echo [1/3] Checking Node.js ...
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found. Install Node.js 18 LTS from https://nodejs.org/ and reopen cmd.
  goto :fail
)
node -v
call npm -v
echo.
echo [2/3] npm install (wechaty + wechaty-puppet-xp 2.1.1) ...
call npm install --no-fund --no-audit
if errorlevel 1 (
  echo [ERROR] npm install failed. See the FAQ section in README.md in this folder.
  goto :fail
)
echo.
echo [3/3] Preparing config ...
if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example. Open .env and fill in OPENAI_API_KEY.
) else (
  echo .env already exists, left unchanged.
)
if not exist "logs" mkdir "logs"
echo.
echo Done. Next: edit .env, log in to WeChat 3.9.10.27, then run start.bat
pause
exit /b 0
:fail
pause
exit /b 1
