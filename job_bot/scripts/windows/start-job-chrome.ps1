param(
    [ValidateRange(1, 65535)]
    [int]$Port = 9222,
    [string]$UserDataDir = (Join-Path $env:LOCALAPPDATA "JobApplyChrome")
)

$Candidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if (-not $Candidates) {
    throw "Google Chrome was not found under Program Files or Program Files (x86)."
}

$Chrome = @($Candidates)[0]
$Arguments = @(
    "--remote-debugging-port=$Port",
    "--remote-debugging-address=127.0.0.1",
    "--user-data-dir=`"$UserDataDir`"",
    "--no-first-run"
)

Write-Host "Chrome executable: $Chrome"
Write-Host "Dedicated profile: $UserDataDir"
Write-Host "Windows-local CDP endpoint: http://127.0.0.1:$Port"
Write-Host "This script does not stop or replace any existing Chrome process."

Start-Process -FilePath $Chrome -ArgumentList $Arguments

# Verify startup before returning to WSL; Start-Process alone is not readiness.
$Deadline = (Get-Date).AddSeconds(10)
do {
    try {
        $Version = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 2
        if ($Version.Browser) {
            Write-Host "Chrome ready: $($Version.Browser)"
            return
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
} while ((Get-Date) -lt $Deadline)
throw "Chrome was launched but its local CDP endpoint did not become ready on port $Port."
