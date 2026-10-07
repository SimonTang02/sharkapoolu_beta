# Native Windows entry point. Does not install Python/Git/system dependencies.
param([switch]$WithBrowser, [switch]$WithResume, [switch]$SkipTests, [string]$Python = "python")
$ErrorActionPreference = "Stop"
$ProjectDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $ProjectDirectory
try {
    if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
        throw "Install Python 3.10+ first, reopen PowerShell, then rerun bootstrap.ps1."
    }
    & $Python -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
    if ($LASTEXITCODE -ne 0) { throw "Python version check failed" }
    $EnvironmentPython = Join-Path $ProjectDirectory ".venv\Scripts\python.exe"
    if (-not (Test-Path $EnvironmentPython)) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
    }
    $InstallTarget = "."
    if ($WithBrowser -and $WithResume) { $InstallTarget = ".[browser,resume]" }
    elseif ($WithBrowser) { $InstallTarget = ".[browser]" }
    elseif ($WithResume) { $InstallTarget = ".[resume]" }
    & $EnvironmentPython -m pip install -e $InstallTarget
    if ($LASTEXITCODE -ne 0) { throw "Package installation failed" }
    if ($WithBrowser) {
        # Keep the standard Playwright cache so subsequent commands can find it.
        & $EnvironmentPython -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Chromium installation failed" }
    }
    & $EnvironmentPython -m job_bot.private_config init
    if ($LASTEXITCODE -ne 0) { throw "Private initialization failed" }
    & $EnvironmentPython -m job_bot.private_config check
    if ($LASTEXITCODE -ne 0) { throw "Private validation failed" }
    & $EnvironmentPython -m job_bot.config_inspect --config job_bot/config.china_hk_ic_foreign.json
    if ($LASTEXITCODE -ne 0) { throw "Runtime configuration validation failed" }
    if (-not $SkipTests) {
        # SSH RPC tests require Unix pipes; run the native-core contract suite here.
        & $EnvironmentPython -m unittest cv.test_resume_import job_bot.test_manual_database job_bot.test_private_config cv.bot.test_bot application_bot.test_manual_kit
        if ($LASTEXITCODE -ne 0) { throw "Tests failed; inspect results before application use" }
    }
    Write-Host "Bootstrap complete. Use .venv\Scripts\python.exe or activate .venv\Scripts\Activate.ps1."
    Write-Host "Core Windows setup is provided; real portal/TeX compatibility still requires verification."
} finally { Pop-Location }
