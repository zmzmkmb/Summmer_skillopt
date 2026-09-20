param(
    [string]$Config = "configs/acl2027/tracegraph_tg8_durable_v2_candidate.json"
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if ($Config -notmatch '^configs/acl2027/[a-zA-Z0-9_-]+\.json$') {
    throw "Config must be a repository-relative ACL2027 JSON path."
}
$configPath = Join-Path $root $Config
$configHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
Push-Location $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & python -B scripts/run_acl2027_tracegraph_tg8_durable_v2.py validate --config $Config
    if ($LASTEXITCODE -ne 0) { throw "Authorization/preflight validation failed; nothing launched." }
    $payload = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $logBase = Join-Path $root "artifacts/acl2027_tracegraph_tg8_durable_v2/.launch_records"
    [System.IO.Directory]::CreateDirectory($logBase) | Out-Null
    $launchDir = Join-Path $logBase $payload.authorization_receipt_sha256
    # A directory claim prevents even an ambiguous launch from being retried.
    if (Test-Path -LiteralPath $launchDir) { throw "This authorization already has a launch record." }
    New-Item -ItemType Directory -Path $launchDir -ErrorAction Stop | Out-Null
    $arguments = @(
        "--user", "root", "--cd", "`"$root`"", "--exec",
        ".venv-tracegraph-linux/bin/python", "-B", "-u",
        "scripts/run_acl2027_tracegraph_tg8_durable_v2.py", "launch",
        "--config", $Config, "--expected-config-sha256", $configHash
    )
    $process = Start-Process -FilePath "wsl.exe" -ArgumentList $arguments `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $launchDir "launcher.stdout.log") `
        -RedirectStandardError (Join-Path $launchDir "launcher.stderr.log")
    $record = @{
        launched_at = (Get-Date -Format o)
        windows_pid = $process.Id
        config_sha256 = $configHash
        receipt_sha256 = $payload.authorization_receipt_sha256
        systemd_unit = "tg8-v2-" + $payload.authorization_receipt_sha256.Substring(0, 20)
        launch_record = $launchDir
        result_directory = $payload.run_directory
        status = "submitted_not_completion_evidence"
    }
    $record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $launchDir "launch.json") -Encoding utf8
    $record | ConvertTo-Json
} finally {
    Pop-Location
}
