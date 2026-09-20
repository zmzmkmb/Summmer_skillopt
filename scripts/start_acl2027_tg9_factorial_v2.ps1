param(
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$Receipt,
    [Parameter(Mandatory=$true)][string]$RunDirectory,
    [Parameter(Mandatory=$true)][string]$Unit,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runDir = [IO.Path]::GetFullPath((Join-Path $root $RunDirectory))
if (-not $runDir.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Run directory escaped the repository."
}
if (-not $CheckOnly -and (Test-Path -LiteralPath $runDir)) { throw "Run directory already exists." }

$configPath = [IO.Path]::GetFullPath((Join-Path $root $Config))
$receiptPath = [IO.Path]::GetFullPath((Join-Path $root $Receipt))
if (-not (Test-Path -LiteralPath $configPath) -or -not (Test-Path -LiteralPath $receiptPath)) {
    throw "Authorized config or receipt is missing."
}

Push-Location $root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $errors = & python -c "import json; from pathlib import Path; from scripts.run_acl2027_tracegraph_tg9_runner_v1 import validate_config; c=json.loads(Path(r'$Config').read_text(encoding='utf-8')); print(json.dumps(validate_config(c)))"
    if ($LASTEXITCODE -ne 0 -or $errors.Trim() -ne "[]") {
        throw "Authorized config validation failed: $errors"
    }

    $repoWsl = (& wsl.exe --user root --exec wslpath -a $root).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoWsl)) {
        throw "Unable to derive the WSL repository path."
    }
    & wsl.exe --user root --exec test -x "$repoWsl/.venv-tracegraph-linux/bin/python"
    if ($LASTEXITCODE -ne 0) { throw "WSL project Python is unavailable." }
    if ($CheckOnly) {
        @{
            status = "check_only_passed"
            config_validation = "passed"
            wsl_repository_path = $repoWsl
            wsl_project_python = "available"
            output_created = $false
            keeper_started = $false
            guardian_started = $false
            systemd_service_started = $false
        } | ConvertTo-Json
        return
    }

    New-Item -ItemType Directory -Path $runDir | Out-Null
    Copy-Item -LiteralPath $configPath -Destination (Join-Path $runDir "authorized_config.json")
    Copy-Item -LiteralPath $receiptPath -Destination (Join-Path $runDir "authorization.json")

    $keeper = Start-Process -FilePath "wsl.exe" `
        -ArgumentList @("--user", "root", "--exec", "sleep", "infinity") `
        -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    if ($keeper.HasExited) { throw "WSL keeper exited before launch." }

    $guardianLog = Join-Path $runDir "awake_guardian.log"
    $monitor = [IO.Path]::GetFullPath((Join-Path $root "scripts/monitor_acl2027_tg9_factorial_v1.ps1"))
    $guardianArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$monitor`" -Unit `"$Unit.service`" -LogPath `"$guardianLog`""
    $guardian = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -ArgumentList $guardianArgs -WindowStyle Hidden -PassThru
    for ($i = 0; $i -lt 20 -and -not (Test-Path -LiteralPath $guardianLog); $i++) {
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path -LiteralPath $guardianLog) -or $guardian.HasExited) {
        throw "System-awake guardian did not acquire its request."
    }

    $runWsl = "$repoWsl/$($RunDirectory.Replace('\','/'))"
    $configWsl = $Config.Replace('\','/')
    $outputWsl = "$RunDirectory/result.json".Replace('\','/')
    & wsl.exe --user root --exec systemd-run --unit=$Unit `
        --property="WorkingDirectory=$repoWsl" --property=PrivateNetwork=yes `
        --property=NoNewPrivileges=yes --property=Restart=no `
        --property="Environment=PYTHONDONTWRITEBYTECODE=1" `
        --property="Environment=ALFWORLD_DATA=/mnt/c/Users/CMCC/ALFWORLD_DATA" `
        --property="StandardOutput=append:$runWsl/runner.stdout.log" `
        --property="StandardError=append:$runWsl/runner.stderr.log" `
        "$repoWsl/.venv-tracegraph-linux/bin/python" -B -u `
        scripts/run_acl2027_tracegraph_tg9_runner_v1.py --config $configWsl `
        --data-root /mnt/c/Users/CMCC/ALFWORLD_DATA --output $outputWsl
    if ($LASTEXITCODE -ne 0) { throw "systemd-run submission failed." }
    Start-Sleep -Seconds 5
    $show = @(& wsl.exe --user root --exec systemctl show "$Unit.service" -p ActiveState -p MainPID -p PrivateNetwork)
    if ("ActiveState=active" -notin $show -or "PrivateNetwork=yes" -notin $show) {
        throw "Experiment service did not remain active: $($show -join '; ')"
    }
    $mainPid = (($show | Where-Object { $_ -like 'MainPID=*' }) -split '=', 2)[1]
    @{
        status = "submitted_not_completion_evidence"
        launched_at = Get-Date -Format o
        unit = "$Unit.service"
        linux_main_pid = [int]$mainPid
        windows_wsl_keeper_pid = $keeper.Id
        windows_awake_guardian_pid = $guardian.Id
        config_sha256 = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
        receipt_sha256 = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        run_directory = $RunDirectory
        private_network = $true
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runDir "startup.json") -Encoding utf8
    Get-Content -Raw -LiteralPath (Join-Path $runDir "startup.json")
}
finally {
    Pop-Location
}
