@echo off
rem Creates a "Capture to PDF" shortcut on the Desktop (Windows)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Capture to PDF.lnk'));" ^
  "$s.TargetPath='%~dp0start_windows.bat';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%SystemRoot%\System32\shell32.dll,22';" ^
  "$s.Save()"
if errorlevel 1 (
  echo Failed to create the shortcut.
) else (
  echo Created "Capture to PDF" on your Desktop.
)
pause
