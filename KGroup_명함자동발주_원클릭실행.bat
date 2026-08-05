@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot open project folder.
    pause
    exit /b 1
)
if not exist "run_business_card_mailer.bat" (
    echo [ERROR] run_business_card_mailer.bat not found.
    pause
    popd
    exit /b 1
)
if not exist "output" mkdir "output" >nul 2>&1

echo [INFO] Starting portal...
start "KGroup Business Card Portal" /min "%ComSpec%" /k call run_business_card_mailer.bat

set "PORT_READY=0"
for /L %%N in (1,1,30) do (
    powershell.exe -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "PORT_READY=1"
        goto :OPEN_BROWSER
    )
    timeout /t 1 /nobreak >nul
)

if "%PORT_READY%"=="0" (
    echo [ERROR] Portal did not start within 30 seconds.
    echo Restore the minimized KGroup Business Card Portal window to see the error.
    pause
    popd
    exit /b 1
)

:OPEN_BROWSER
start "" "http://127.0.0.1:8765/"
echo [OK] Browser opened.
popd
exit /b 0
