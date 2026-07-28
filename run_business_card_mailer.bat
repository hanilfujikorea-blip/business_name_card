@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Could not enter script directory.
    pause
    exit /b 1
)

if not exist "business_card_mailer.py" (
    echo [ERROR] business_card_mailer.py not found.
    pause
    popd
    exit /b 1
)

set "PYTHON_CMD="
if exist "%LocalAppData%\Programs\Python\Launcher\py.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Launcher\py.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYTHON_CMD if exist "C:\Windows\py.exe" set "PYTHON_CMD=py"
if not defined PYTHON_CMD if exist "C:\ProgramData\anaconda3\python.exe" set "PYTHON_CMD=C:\ProgramData\anaconda3\python.exe"
if not defined PYTHON_CMD if exist "C:\Python314\python.exe" set "PYTHON_CMD=C:\Python314\python.exe"
if not defined PYTHON_CMD set "PYTHON_CMD=python"

if "%~1"=="" goto run_portal
if /I "%~1"=="portal" goto run_portal_command
goto run_mailer

:run_portal
call "%PYTHON_CMD%" -u "business_card_portal.py"
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:run_portal_command
shift
call "%PYTHON_CMD%" -u "business_card_portal.py" %1 %2 %3 %4 %5 %6 %7 %8 %9
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:run_mailer
call "%PYTHON_CMD%" -u "business_card_mailer.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

:finish
if not "%EXIT_CODE%"=="0" pause
popd
exit /b %EXIT_CODE%
