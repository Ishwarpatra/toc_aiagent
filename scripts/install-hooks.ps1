# =============================================================================
# Auto-DFA Hook Installer
# =============================================================================
#
# This script installs the Git pre-commit hook for the Auto-DFA project.
# It detects the OS and installs the appropriate version (Shell or PowerShell).
#
# Usage:
#   .\install-hooks.ps1
# =============================================================================

Write-Host "`n🔧 Auto-DFA Git Hook Installer" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor DarkGray

# 1. Locate directories
$RepoRoot = git rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    Write-Host "❌ Error: Not a git repository." -ForegroundColor Red
    exit 1
}

$HooksDir = Join-Path $RepoRoot ".git\hooks"
$ScriptsDir = Join-Path $RepoRoot "backend\scripts"
$PreCommitDest = Join-Path $HooksDir "pre-commit"

if (-not (Test-Path $HooksDir)) {
    New-Item -ItemType Directory -Path $HooksDir -Force | Out-Null
}

# 2. Detect OS and Source
$IsWindows = $env:OS -match "Windows"
$SourceFile = if ($IsWindows) { "pre-commit.ps1" } else { "pre-commit" }
$SourcePath = Join-Path $ScriptsDir $SourceFile

Write-Host "   📂 Repo Root: $RepoRoot" -ForegroundColor Gray
Write-Host "   📂 Hooks Dir: $HooksDir" -ForegroundColor Gray
Write-Host "   🖥️  OS Detected: $(if ($IsWindows) {'Windows'} else {'Unix/Mac'})" -ForegroundColor Gray

if (-not (Test-Path $SourcePath)) {
    Write-Host "`n❌ Error: Source hook not found at $SourcePath" -ForegroundColor Red
    exit 1
}

# 3. Install Hook
Write-Host "`n   Installing $SourceFile..." -ForegroundColor White

if ($IsWindows) {
    # For Windows, we create a wrapper shell script that calls the PowerShell script
    # This is required because Git bash expects a sh-compatible executable
    $WrapperContent = @"
#!/bin/sh

# Wrapper for PowerShell hook
powershell.exe -ExecutionPolicy Bypass -File ./.git/hooks/pre-commit.ps1
"@
    
    # 1. Copy the PS1 file
    Copy-Item -Path $SourcePath -Destination (Join-Path $HooksDir "pre-commit.ps1") -Force
    
    # 2. Create the shell wrapper named 'pre-commit' (no extension)
    Set-Content -Path $PreCommitDest -Value $WrapperContent -NoNewline
    
    Write-Host "   ✓ Copied pre-commit.ps1" -ForegroundColor Green
    Write-Host "   ✓ Created shell wrapper" -ForegroundColor Green
} else {
    # For Unix, direct copy
    Copy-Item -Path $SourcePath -Destination $PreCommitDest -Force
    # Make executable
    chmod +x $PreCommitDest
    Write-Host "   ✓ Copied pre-commit (Unix)" -ForegroundColor Green
}

Write-Host "`n✅ Hook installed successfully!" -ForegroundColor Green
Write-Host "`n🎉 Setup Complete." -ForegroundColor Cyan
Write-Host "   The smoke tests will now run automatically before every commit."
Write-Host "   (Use 'git commit --no-verify' to bypass in emergencies)" -ForegroundColor DarkGray
Write-Host ""
