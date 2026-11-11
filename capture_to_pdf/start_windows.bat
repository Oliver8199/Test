@echo off
rem Launcher for capture.py (Windows)
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install it from https://www.python.org/downloads/
  echo  ^(check "Add python.exe to PATH" during install^)
  pause
  exit /b 1
)
if not exist ".setup_done" (
  echo First run: installing required packages. This takes a few minutes...
  %PY% -m pip install -r requirements.txt || goto :fail
  %PY% -m playwright install chromium || goto :fail
  echo done> .setup_done
)
%PY% capture.py %*
pause
exit /b 0
:fail
echo Setup failed. Please check the messages above.
pause
exit /b 1
