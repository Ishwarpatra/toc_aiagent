# =============================================================================
# Pre-Commit Hook for Auto-DFA (Windows PowerShell Version)
# =============================================================================
#
# This script runs a "Smoke Test" before allowing commits.
#
# INSTALLATION:
#   Run install-hooks.ps1 from the project root
#
# MANUAL SETUP:
#   1. Copy to .git/hooks/pre-commit (no extension)
#   2. Or configure git to use PowerShell hooks
#
# TO SKIP (Emergency only):
#   git commit --no-verify -m "message"
#
# =============================================================================

Write-Host "`n🧪 Running DFA Smoke Tests..." -ForegroundColor Cyan
Write-Host "   (To skip: git commit --no-verify)" -ForegroundColor DarkGray
Write-Host ""

# Find script directory
$RepoRoot = git rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$ScriptDir = Join-Path $RepoRoot "backend\scripts"

if (-not (Test-Path $ScriptDir)) {
    Write-Host "⚠️  Warning: backend/scripts not found. Skipping smoke tests." -ForegroundColor Yellow
    exit 0
}

Set-Location $ScriptDir

# Check Python
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Write-Host "⚠️  Warning: Python not found. Skipping smoke tests." -ForegroundColor Yellow
    exit 0
}

# Generate test suite
Write-Host "   [1/3] Generating 30 test cases..." -ForegroundColor White
$GenResult = python generate_tests.py --count 30 --output smoke_test.csv 2>&1

if ($LASTEXITCODE -ne 0 -or -not (Test-Path "smoke_test.csv")) {
    Write-Host "⚠️  Warning: Could not generate tests. Skipping smoke tests." -ForegroundColor Yellow
    exit 0
}

# Run verification
Write-Host "   [2/3] Running verification..." -ForegroundColor White
$Output = python batch_verify.py --input smoke_test.csv --no-color 2>&1
$ExitCode = $LASTEXITCODE

# Parse results (handle PowerShell output)
$OutputText = $Output | Out-String
$PassMatch = [regex]::Match($OutputText, "PASSED:\s*(\d+)")
$FailMatch = [regex]::Match($OutputText, "FAILED:\s*(\d+)")
$OracleMatch = [regex]::Match($OutputText, "ORACLE_FAILED:\s*(\d+)")

$PassCount = if ($PassMatch.Success) { $PassMatch.Groups[1].Value } else { "0" }
$FailCount = if ($FailMatch.Success) { $FailMatch.Groups[1].Value } else { "0" }
$OracleFailCount = if ($OracleMatch.Success) { $OracleMatch.Groups[1].Value } else { "0" }

# Clean up
Remove-Item -Path "smoke_test.csv" -ErrorAction SilentlyContinue

# Report results
Write-Host "   [3/3] Results:" -ForegroundColor White
Write-Host "         Passed: $PassCount" -ForegroundColor Green
Write-Host "         Failed: $FailCount" -ForegroundColor $(if ([int]$FailCount -gt 0) { "Red" } else { "Green" })
Write-Host "         Oracle Failures: $OracleFailCount" -ForegroundColor $(if ([int]$OracleFailCount -gt 0) { "Yellow" } else { "Green" })
Write-Host ""

# Check results
if ($ExitCode -ne 0) {
    Write-Host "❌ SMOKE TESTS FAILED!" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Some tests did not pass. Please fix issues before committing." -ForegroundColor Red
    Write-Host ""
    Write-Host "   To debug, run:" -ForegroundColor Yellow
    Write-Host "     cd backend\scripts" -ForegroundColor White
    Write-Host "     python generate_tests.py --count 30 --output test.csv" -ForegroundColor White
    Write-Host "     python batch_verify.py --input test.csv --verbose" -ForegroundColor White
    Write-Host ""
    Write-Host "   To skip this check (not recommended):" -ForegroundColor Yellow
    Write-Host "     git commit --no-verify -m `"your message`"" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Warn about Oracle failures
if ([int]$OracleFailCount -gt 0) {
    Write-Host "⚠️  WARNING: $OracleFailCount Oracle failure(s) detected." -ForegroundColor Yellow
    Write-Host "   The Analyst may be misinterpreting some prompts." -ForegroundColor Yellow
    Write-Host "   Consider running: python retrain_analyst.py" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "✅ Smoke tests passed! Proceeding with commit..." -ForegroundColor Green
Write-Host ""
exit 0
