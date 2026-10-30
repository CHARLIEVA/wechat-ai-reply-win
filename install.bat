@echo off
REM ============================================================
REM  install.bat - install Python dependencies (main engine)
REM  If the window closes at once, open cmd in this folder and run install.bat
REM ============================================================
setlocal
cd /d "%~dp0"
echo.
echo [1/3] Checking Python 3.13 ...
where py >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python launcher "py" not found.
  echo         Install Python 3.13 x64 from https://www.python.org/downloads/ and reopen cmd.
  goto :fail
)
py -3.13 --version
if errorlevel 1 (
  echo [ERROR] Python 3.13 not found. wxauto4 needs Python 3.9-3.13 x64; 3.13 is recommended.
  goto :fail
)
echo.
echo [2/3] pip install -r requirements.txt ...
py -3.13 -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. See the FAQ in README.md.
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
echo.
echo Done. Next: edit .env, open and log in to WeChat 4.x, then run start.bat
pause
exit /b 0
:fail
pause
exit /b 1
