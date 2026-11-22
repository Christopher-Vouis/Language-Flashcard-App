@echo off
REM Starts the app. The first time, the app sets itself up (bootstrap.py):
REM it creates .venv and installs the packages, then opens.
cd /d "%~dp0"
if exist .venv\Scripts\pythonw.exe (
  start "" .venv\Scripts\pythonw.exe app.py %*
  exit /b 0
)
where pyw >nul 2>nul && (
  start "" pyw -3 app.py %*
  exit /b 0
)
where pythonw >nul 2>nul && (
  start "" pythonw app.py %*
  exit /b 0
)
echo.
echo  Python isn't installed. Install Python 3.13 "Windows installer (64-bit)" from
echo    https://www.python.org/downloads/windows/
echo  then double-click run.bat again.
pause
exit /b 1
