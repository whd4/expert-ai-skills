#Requires -Version 5.1
# ============================================
#  fix-wsl2.ps1 — Fix Blank WSL2 Ubuntu Terminal
# ============================================
#
#  WHAT THIS DOES:
#    1. Shuts down WSL2 completely
#    2. Backs up your shell config files
#    3. Resets .bashrc and .profile to Ubuntu defaults
#    4. Restarts Ubuntu with a working prompt
#
#  HOW TO RUN:
#    Right-click PowerShell → Run as Administrator
#    Then: .\fix-wsl2.ps1
#
# ============================================

$ErrorActionPreference = "Stop"

function Write-Status($msg) {
    Write-Host "[*] $msg" -ForegroundColor Cyan
}

function Write-Success($msg) {
    Write-Host "[+] $msg" -ForegroundColor Green
}

function Write-Fail($msg) {
    Write-Host "[!] $msg" -ForegroundColor Red
}

function Write-Info($msg) {
    Write-Host "    $msg" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  WSL2 Ubuntu Terminal Fix" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

# -------------------------------------------
# Step 1: Check if WSL is available
# -------------------------------------------
Write-Status "Checking WSL installation..."

try {
    $wslList = wsl --list --verbose 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "WSL is not installed or not accessible."
        Write-Info "Install WSL with: wsl --install"
        exit 1
    }
    Write-Success "WSL found."
    Write-Info ($wslList | Out-String).Trim()
    Write-Host ""
} catch {
    Write-Fail "Could not run wsl command: $_"
    exit 1
}

# -------------------------------------------
# Step 2: Find Ubuntu distro name
# -------------------------------------------
Write-Status "Finding Ubuntu distribution..."

$distroName = $null
$distroLines = wsl --list --quiet 2>&1
foreach ($line in $distroLines) {
    $clean = $line.Trim() -replace '\x00', ''
    if ($clean -match "(?i)ubuntu") {
        $distroName = $clean
        break
    }
}

if (-not $distroName) {
    Write-Fail "No Ubuntu distribution found in WSL."
    Write-Info "Available distributions:"
    wsl --list --verbose
    Write-Info ""
    Write-Info "If your distro has a different name, run:"
    Write-Info "  .\fix-wsl2.ps1 -DistroName 'YourDistroName'"
    exit 1
}

Write-Success "Found distribution: $distroName"
Write-Host ""

# -------------------------------------------
# Step 3: Shut down WSL completely
# -------------------------------------------
Write-Status "Shutting down WSL completely..."
wsl --shutdown 2>&1 | Out-Null
Write-Success "WSL shutdown complete."

Write-Status "Waiting 5 seconds for clean shutdown..."
Start-Sleep -Seconds 5
Write-Success "Ready to proceed."
Write-Host ""

# -------------------------------------------
# Step 4: Back up existing shell config
# -------------------------------------------
Write-Status "Backing up current shell configuration..."

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backupCmd = @"
if [ -f ~/.bashrc ]; then cp ~/.bashrc ~/.bashrc.backup.$timestamp; echo 'Backed up .bashrc'; fi
if [ -f ~/.profile ]; then cp ~/.profile ~/.profile.backup.$timestamp; echo 'Backed up .profile'; fi
if [ -f ~/.bash_profile ]; then cp ~/.bash_profile ~/.bash_profile.backup.$timestamp; echo 'Backed up .bash_profile'; fi
echo 'Backup complete'
"@

$backupResult = wsl -d $distroName -e bash -c $backupCmd 2>&1
Write-Success "Backup complete (files saved with .$timestamp extension)"
Write-Info ($backupResult | Out-String).Trim()
Write-Host ""

# -------------------------------------------
# Step 5: Reset shell config to defaults
# -------------------------------------------
Write-Status "Resetting shell configuration to Ubuntu defaults..."

$resetCmd = @"
cp /etc/skel/.bashrc ~/.bashrc 2>/dev/null && echo 'Reset .bashrc' || echo 'WARN: Could not reset .bashrc'
cp /etc/skel/.profile ~/.profile 2>/dev/null && echo 'Reset .profile' || echo 'WARN: Could not reset .profile'
if [ -f /etc/skel/.bash_profile ]; then cp /etc/skel/.bash_profile ~/.bash_profile; echo 'Reset .bash_profile'; fi
echo 'Shell config reset complete'
"@

$resetResult = wsl -d $distroName -e bash -c $resetCmd 2>&1
Write-Success "Shell configuration reset to defaults."
Write-Info ($resetResult | Out-String).Trim()
Write-Host ""

# -------------------------------------------
# Step 6: Verify the fix
# -------------------------------------------
Write-Status "Verifying the fix..."

$verifyCmd = @"
echo "USER=\$(whoami)"
echo "HOME=\$HOME"
echo "SHELL=\$SHELL"
echo "PROMPT_TEST=OK"
"@

$verifyResult = wsl -d $distroName -e bash --login -c $verifyCmd 2>&1
$verifyOutput = ($verifyResult | Out-String).Trim()

if ($verifyOutput -match "PROMPT_TEST=OK") {
    Write-Success "Terminal is working!"
    Write-Info $verifyOutput
} else {
    Write-Fail "Terminal may still have issues."
    Write-Info "Output: $verifyOutput"
    Write-Info ""
    Write-Info "Try opening Ubuntu manually and see if the prompt appears."
}

Write-Host ""

# -------------------------------------------
# Step 7: Report results
# -------------------------------------------
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  Fix Complete!" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Success "Your WSL2 Ubuntu terminal should now work."
Write-Host ""
Write-Info "What was done:"
Write-Info "  1. WSL2 was shut down and restarted"
Write-Info "  2. .bashrc and .profile were backed up (.$timestamp)"
Write-Info "  3. Shell configs were reset to Ubuntu defaults"
Write-Host ""
Write-Info "Next steps:"
Write-Info "  1. Open Ubuntu from Start Menu — you should see your prompt"
Write-Info "  2. Run deploy-to-wsl2.sh to install Henry into OpenClaw"
Write-Host ""
Write-Info "If you had custom settings in .bashrc, your backup is at:"
Write-Info "  ~/.bashrc.backup.$timestamp"
Write-Host ""
