@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Crowdsourcing Research
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launch.py
) else (
  python launch.py
)
if errorlevel 1 (
  echo.
  echo 起動に失敗しました。Python 3.10 以上がインストールされているか確認してください: https://www.python.org/downloads/
  pause
)
