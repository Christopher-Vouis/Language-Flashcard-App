@echo off
REM One-time setup: finds a compatible Python, creates .venv, installs packages.
REM faster-whisper needs 64-bit (x86-64) Python 3.9 - 3.14.
cd /d "%~dp0"

REM --- Reuse an existing .venv only if it was built with a compatible Python
if not exist .venv\Scripts\python.exe goto :find_python
echo Checking existing environment...
.venv\Scripts\python.exe check_python.py && goto :install
echo Removing incompatible environment...
rmdir /s /q .venv

:find_python
echo Looking for a compatible Python...
set "PY="
py -3.13 check_python.py 2>nul && set "PY=py -3.13" && goto :make_venv
py -3.12 check_python.py 2>nul && set "PY=py -3.12" && goto :make_venv
py -3.14 check_python.py 2>nul && set "PY=py -3.14" && goto :make_venv
py -3.11 check_python.py 2>nul && set "PY=py -3.11" && goto :make_venv
py -3.10 check_python.py 2>nul && set "PY=py -3.10" && goto :make_venv
python check_python.py 2>nul && set "PY=python" && goto :make_venv
goto :no_python

:make_venv
echo Creating virtual environment with: %PY%
%PY% -m venv .venv
if errorlevel 1 goto :fail

:install
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo.
echo Setup complete. Double-click run.bat to start the app.
pause
exit /b 0

:no_python
echo.
echo ===================================================================
echo  No compatible Python found.
echo  The speech engine needs 64-bit Python 3.10 - 3.14 (3.15, 32-bit
echo  and ARM64 builds are not supported yet).
echo.
echo  Fix: install Python 3.13 "Windows installer (64-bit)" from
echo    https://www.python.org/downloads/windows/
echo  (or, if you have the Python install manager:  py install 3.13 )
echo  You can keep your other Python. Then run setup.bat again.
echo ===================================================================
pause
exit /b 1

:fail
echo.
echo Install failed - copy the messages above and send them over.
pause
exit /b 1
