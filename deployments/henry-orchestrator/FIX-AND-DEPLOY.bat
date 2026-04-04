@echo off
setlocal EnableDelayedExpansion
REM ============================================
REM  FIX-AND-DEPLOY.bat
REM  One-click: Fix WSL2 Terminal + Deploy Henry
REM ============================================
REM
REM  HOW TO USE:
REM    Right-click this file → Run as Administrator
REM
REM ============================================

title Henry Orchestrator - Fix and Deploy

echo.
echo ========================================
echo   Henry Orchestrator - Fix and Deploy
echo ========================================
echo.
echo This script will:
echo   1. Fix your blank WSL2 Ubuntu terminal
echo   2. Deploy Henry to OpenClaw
echo   3. Open the OpenClaw web UI
echo.
echo Press any key to start, or close this window to cancel.
pause >nul

REM -------------------------------------------
REM  Check for Administrator privileges
REM -------------------------------------------
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo [!] This script needs Administrator privileges.
    echo     Right-click this file and select "Run as Administrator"
    echo.
    pause
    exit /b 1
)

REM -------------------------------------------
REM  Step 1: Run the WSL2 fix script
REM -------------------------------------------
echo.
echo [*] STEP 1: Fixing WSL2 Ubuntu Terminal...
echo ----------------------------------------
echo.

REM Get the directory this batch file is in
set "SCRIPT_DIR=%~dp0"

REM Track WSL fix success
set "WSL_FIX_SUCCESS=1"

REM Run the PowerShell fix script
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%fix-wsl2.ps1"

if !errorLevel! neq 0 (
    set "WSL_FIX_SUCCESS=0"
    echo.
    echo [!] WSL2 fix encountered an error.
    echo     You may need to fix WSL2 manually.
    echo     See DEPLOY.md for manual instructions.
    echo.
    echo Press any key to continue anyway, or close to stop.
    pause >nul
)

echo.
if "!WSL_FIX_SUCCESS!"=="1" (
    echo [+] WSL2 fix complete.
) else (
    echo [!] WSL2 fix may not have succeeded.
)
echo.

REM -------------------------------------------
REM  Step 2: Detect Ubuntu distro name + wait
REM -------------------------------------------
echo [*] STEP 2: Detecting WSL2 Ubuntu distribution...
echo.
timeout /t 3 /nobreak >nul

REM Detect the Ubuntu distro name dynamically (could be Ubuntu, Ubuntu-24.04, etc.)
set "WSL_DISTRO="
for /f "tokens=*" %%d in ('wsl --list --quiet 2^>nul') do (
    echo %%d | findstr /i "ubuntu" >nul 2>&1
    if !errorLevel! equ 0 (
        if not defined WSL_DISTRO (
            set "WSL_DISTRO=%%d"
        )
    )
)

REM Fallback to "Ubuntu" if detection failed
if not defined WSL_DISTRO (
    echo [!] Could not auto-detect Ubuntu distro name. Trying "Ubuntu"...
    set "WSL_DISTRO=Ubuntu"
)

echo [+] Using WSL distro: %WSL_DISTRO%

REM Verify WSL2 is running
wsl -d %WSL_DISTRO% -e bash -c "echo 'WSL2 is ready'" 2>nul
if %errorLevel% neq 0 (
    echo [!] WSL2 may not be fully started yet.
    echo     Waiting 5 more seconds...
    timeout /t 5 /nobreak >nul
)

echo [+] WSL2 is ready.
echo.

REM -------------------------------------------
REM  Step 3: Deploy Henry to OpenClaw
REM -------------------------------------------
echo [*] STEP 3: Deploying Henry to OpenClaw...
echo ----------------------------------------
echo.

REM Convert Windows path to WSL/Linux path (C:\foo\bar -> /mnt/c/foo/bar)
set "WIN_SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "DRIVE_LETTER=%WIN_SCRIPT_DIR:~0,1%"
set "PATH_REST=%WIN_SCRIPT_DIR:~2%"
set "PATH_REST=%PATH_REST:\=/%"
for %%a in ("%DRIVE_LETTER%") do set "DRIVE_LOWER=%%~a"
REM Convert drive letter to lowercase manually
if "%DRIVE_LETTER%"=="C" set "DRIVE_LOWER=c"
if "%DRIVE_LETTER%"=="D" set "DRIVE_LOWER=d"
if "%DRIVE_LETTER%"=="E" set "DRIVE_LOWER=e"
if "%DRIVE_LETTER%"=="F" set "DRIVE_LOWER=f"
set "WSL_SCRIPT_DIR=/mnt/%DRIVE_LOWER%%PATH_REST%"

echo [*] Windows path: %WIN_SCRIPT_DIR%
echo [*] WSL path: %WSL_SCRIPT_DIR%

REM Track deployment success
set "DEPLOY_SUCCESS=0"

REM Try to run the deploy script directly from mounted Windows path
wsl -d %WSL_DISTRO% -e bash -c "if [ -f '%WSL_SCRIPT_DIR%/deploy-to-wsl2.sh' ]; then echo 'FOUND_LOCAL'; fi" 2>nul | findstr "FOUND_LOCAL" >nul 2>&1

if !errorLevel! equ 0 (
    echo [*] Running deploy from local path...
    wsl -d %WSL_DISTRO% -e bash -c "cd '%WSL_SCRIPT_DIR%' && chmod +x deploy-to-wsl2.sh && ./deploy-to-wsl2.sh"
    if !errorLevel! equ 0 set "DEPLOY_SUCCESS=1"
) else (
    echo [*] Local deploy script not found in WSL path.
    echo [*] Copying files directly to WSL2...

    REM Create temp directory in WSL and copy files
    wsl -d %WSL_DISTRO% -e bash -c "mkdir -p /tmp/henry-deploy/memory /tmp/henry-deploy/protocols"

    REM Copy each file using wsl
    wsl -d %WSL_DISTRO% -e bash -c "cat > /tmp/henry-deploy/HENRY.solmd" < "%SCRIPT_DIR%HENRY.solmd"
    wsl -d %WSL_DISTRO% -e bash -c "cat > /tmp/henry-deploy/config.yaml" < "%SCRIPT_DIR%config.yaml"
    wsl -d %WSL_DISTRO% -e bash -c "cat > /tmp/henry-deploy/memory/henry_memory.json" < "%SCRIPT_DIR%memory\henry_memory.json"

    REM Copy protocols
    for %%f in ("%SCRIPT_DIR%protocols\*.md") do (
        wsl -d %WSL_DISTRO% -e bash -c "cat > /tmp/henry-deploy/protocols/%%~nxf" < "%%f"
    )

    REM Copy and run the deploy script
    wsl -d %WSL_DISTRO% -e bash -c "cat > /tmp/henry-deploy/deploy-to-wsl2.sh" < "%SCRIPT_DIR%deploy-to-wsl2.sh"
    wsl -d %WSL_DISTRO% -e bash -c "chmod +x /tmp/henry-deploy/deploy-to-wsl2.sh && cd /tmp/henry-deploy && ./deploy-to-wsl2.sh"
    if !errorLevel! equ 0 set "DEPLOY_SUCCESS=1"
)

echo.

REM -------------------------------------------
REM  Step 4: Open the web UI
REM -------------------------------------------
echo [*] STEP 4: Opening OpenClaw Web UI...
echo.

start http://localhost:18789/agents

echo.
echo ========================================
echo   Summary
echo ========================================
echo.
if "!WSL_FIX_SUCCESS!"=="1" (
    echo [+] WSL2 terminal: FIXED
) else (
    echo [!] WSL2 terminal: FIX MAY HAVE FAILED - check output above
)
if "!DEPLOY_SUCCESS!"=="1" (
    echo [+] Henry: DEPLOYED
) else (
    echo [!] Henry: DEPLOYMENT MAY HAVE FAILED - check output above
)
echo [+] Web UI: OPENING in browser
echo.
if "!WSL_FIX_SUCCESS!"=="1" if "!DEPLOY_SUCCESS!"=="1" (
    echo You can now:
    echo   - Use Ubuntu terminal ^(should have your prompt back^)
    echo   - Use Henry at http://localhost:18789/agents
    echo   - Say: "Henry, what needs my attention today?"
) else (
    echo Some steps may have failed. Please check the error messages above.
    echo You can try running the scripts manually - see DEPLOY.md for instructions.
)
echo.
echo Press any key to close this window.
pause >nul
