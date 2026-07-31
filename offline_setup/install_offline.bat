@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

call :main %*
exit /b %ERRORLEVEL%

:main
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "INSTALLER=%SCRIPT_DIR%python-3.13.14-amd64.exe"
set "MANIFEST=%SCRIPT_DIR%SHA256SUMS.txt"
set "WHEEL_DIR=%SCRIPT_DIR%wheels"
set "EXPECTED_INSTALLER_SHA=c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0"
set "VERIFY_ONLY=0"

if /I "%~1"=="verify" set "VERIFY_ONLY=1"

call :verify_bundle
if errorlevel 1 (
    if "%VERIFY_ONLY%"=="1" exit /b 1
    goto failure
)

if "%VERIFY_ONLY%"=="1" (
    echo [OK] OFFLINE_BUNDLE_VERIFIED
    exit /b 0
)

call :find_python
if not defined PYTHON_EXE (
    echo [INFO] Installing Python 3.13.14 for the current Windows user...
    start "" /wait "%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1 InstallLauncherAllUsers=0
    set "INSTALL_EXIT=!ERRORLEVEL!"
    if not "!INSTALL_EXIT!"=="0" if not "!INSTALL_EXIT!"=="3010" (
        echo [ERROR] PYTHON_INSTALL_FAILED: exit !INSTALL_EXIT!
        goto failure
    )
    call :find_python
)

if not defined PYTHON_EXE (
    echo [ERROR] PYTHON_NOT_FOUND_AFTER_INSTALL
    goto failure
)

echo [INFO] Python: "%PYTHON_EXE%"
echo [INFO] Installing packages from the local wheelhouse only...
"%PYTHON_EXE%" -m pip install --no-index --find-links="%WHEEL_DIR%" -r "%PROJECT_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] OFFLINE_PACKAGE_INSTALL_FAILED
    goto failure
)

echo [INFO] Running project tests...
pushd "%PROJECT_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PROJECT_DIRECTORY_NOT_ACCESSIBLE
    goto failure
)
"%PYTHON_EXE%" -B -m unittest discover -s tests -v
set "TEST_EXIT=!ERRORLEVEL!"
popd
if not "!TEST_EXIT!"=="0" (
    echo [ERROR] PROJECT_TESTS_FAILED
    goto failure
)

echo.
echo [OK] OFFLINE_INSTALL_COMPLETE
echo You may now run run_business_card_mailer.bat from the project folder.
pause
exit /b 0

:verify_bundle
if not exist "%PROJECT_DIR%\requirements.txt" (
    echo [ERROR] REQUIREMENTS_NOT_FOUND: "%PROJECT_DIR%\requirements.txt"
    exit /b 1
)
if not exist "%INSTALLER%" (
    echo [ERROR] MISSING_ASSET: python-3.13.14-amd64.exe
    exit /b 1
)
if not exist "%MANIFEST%" (
    echo [ERROR] MISSING_ASSET: SHA256SUMS.txt
    exit /b 1
)
if not exist "%WHEEL_DIR%" (
    echo [ERROR] MISSING_ASSET: wheels
    exit /b 1
)

call :hash_file "%INSTALLER%"
if errorlevel 1 (
    echo [ERROR] HASH_CALCULATION_FAILED: python-3.13.14-amd64.exe
    exit /b 1
)
if /I not "!ACTUAL_HASH!"=="%EXPECTED_INSTALLER_SHA%" (
    echo [ERROR] HASH_MISMATCH: python-3.13.14-amd64.exe
    exit /b 1
)

for /f "usebackq tokens=1,*" %%H in ("%MANIFEST%") do (
    set "EXPECTED_HASH=%%H"
    set "RELATIVE_PATH=%%I"
    if "!RELATIVE_PATH:~0,1!"=="*" set "RELATIVE_PATH=!RELATIVE_PATH:~1!"
    set "RELATIVE_PATH=!RELATIVE_PATH:/=\!"
    set "ASSET_PATH=%SCRIPT_DIR%!RELATIVE_PATH!"
    if not exist "!ASSET_PATH!" (
        echo [ERROR] MISSING_ASSET: !RELATIVE_PATH!
        exit /b 1
    )
    call :hash_file "!ASSET_PATH!"
    if errorlevel 1 (
        echo [ERROR] HASH_CALCULATION_FAILED: !RELATIVE_PATH!
        exit /b 1
    )
    if /I not "!ACTUAL_HASH!"=="!EXPECTED_HASH!" (
        echo [ERROR] HASH_MISMATCH: !RELATIVE_PATH!
        exit /b 1
    )
)
exit /b 0

:hash_file
set "HASH_TARGET=%~1"
set "ACTUAL_HASH="
for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -NonInteractive -Command "(Get-FileHash -LiteralPath $env:HASH_TARGET -Algorithm SHA256).Hash.ToLowerInvariant()"`) do set "ACTUAL_HASH=%%H"
if not defined ACTUAL_HASH exit /b 1
exit /b 0

:find_python
set "PYTHON_EXE="
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
if defined PYTHON_EXE exit /b 0
for /f "usebackq delims=" %%P in (`py -3.13 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
exit /b 0

:failure
echo.
echo Offline setup stopped. Fix the error above and run this file again.
pause
exit /b 1
