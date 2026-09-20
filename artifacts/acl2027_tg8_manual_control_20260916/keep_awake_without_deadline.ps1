param([switch]$PowerSelfTest, [switch]$CheckOnly)
$ErrorActionPreference = "Stop"
$nativeHome = Join-Path $env:SystemRoot "System32/WindowsPowerShell/v1.0"
Import-Module (Join-Path $nativeHome "Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1") -Force
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$entrypoint = Join-Path $root "scripts/start_acl2027_tg8_manual_v1.ps1"
if ((Get-FileHash -LiteralPath $entrypoint -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    "353d82f1d88250b3c780474b63a0ca9e466fb75b31396499da0d01890cb7ccf5") {
    throw "Frozen wakefulness helper changed."
}
# Reuse only the existing hashed power helper, never the script's launch body.
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($entrypoint, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw "Unable to parse frozen power helper." }
$functions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq "Initialize-KeepAwake"
}, $false))
if ($functions.Count -ne 1) { throw "Expected exactly one frozen power helper." }
$initialize = $functions[0].Body.GetScriptBlock()
& $initialize
$awake = $null
try {
    if ($PowerSelfTest) {
        $awake = [TG8ManualAwake]::new()
        Write-Output "POWER SELFTEST: acquired SYSTEM request only; no launch or stop."
        & powercfg /requests
        Start-Sleep -Seconds 2
        return
    }
    $configPath = Join-Path $root "configs/acl2027/tracegraph_tg8_manual_authorized_20260916.json"
    if ((Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne
        "aba5b4567e8d635587e6f58c2bf0493bae8a821f0b3cbacbd58d0e8ecdcbd205") {
        throw "Existing run config changed."
    }
    $keeper = Get-Process -Id 29516 -ErrorAction Stop
    $expectedStart = [DateTimeOffset]::Parse("2026-09-16T23:21:27.7498335+08:00")
    if ($keeper.ProcessName -ne "wsl" -or
        [Math]::Abs(($keeper.StartTime.ToUniversalTime() - $expectedStart.UtcDateTime).TotalSeconds) -gt 1) {
        throw "WSL keeper identity changed; do not attach to a different process."
    }
    $unit = "tg8-v2-f0cdf278bffd858564cf.service"
    $state = @(& wsl.exe --user root --exec systemctl show $unit -p ActiveState -p MainPID)
    if ($LASTEXITCODE -ne 0 -or "ActiveState=active" -notin $state -or "MainPID=380" -notin $state) {
        throw "Existing experiment is not the expected active process."
    }
    if ($CheckOnly) {
        Write-Output "CHECK ONLY: original service, keeper and hashes verified; no launch, stop or power change."
        return
    }
    $awake = [TG8ManualAwake]::new()
    Write-Output (@{at=(Get-Date -Format o);event="awake_acquired";pid=$PID;
        service=$unit;keeper_pid=29516;deadline=$null;display_requested=$false} | ConvertTo-Json -Compress)
    while ($true) {
        if (-not $keeper.WaitForExit(5000)) { continue }
        $terminal = @(& wsl.exe --user root --exec systemctl show $unit -p ActiveState)
        if ($LASTEXITCODE -eq 0 -and
            ("ActiveState=inactive" -in $terminal -or "ActiveState=failed" -in $terminal)) {
            Write-Output (@{at=(Get-Date -Format o);event="service_terminal";
                state=$terminal;scientific_result_audited=$false} | ConvertTo-Json -Compress)
            break
        }
        Write-Output "Keeper exited but service terminal state is unconfirmed; retaining awake request."
        Start-Sleep -Seconds 30
    }
} finally {
    if ($null -ne $awake) {
        $awake.Dispose()
        Write-Output "SYSTEM awake request released."
    }
}
