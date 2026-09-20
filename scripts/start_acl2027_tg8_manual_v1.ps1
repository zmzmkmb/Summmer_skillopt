param(
    [switch]$CheckOnly,
    [switch]$SelfTest
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Initialize-KeepAwake {
    if ("TG8ManualAwake" -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Threading;
public sealed class TG8ManualAwake : IDisposable {
    [DllImport("kernel32.dll")]
    private static extern uint SetThreadExecutionState(uint flags);
    [DllImport("kernel32.dll")]
    private static extern bool GetSystemPowerStatus(out PowerStatus status);
    [StructLayout(LayoutKind.Sequential)]
    private struct PowerStatus {
        public byte ACLineStatus, BatteryFlag, BatteryLifePercent, SystemStatusFlag;
        public uint BatteryLifeTime, BatteryFullLifeTime;
    }
    public static bool OnAC() {
        PowerStatus status;
        return GetSystemPowerStatus(out status) && status.ACLineStatus == 1;
    }
    private readonly ManualResetEvent ready = new ManualResetEvent(false);
    private readonly ManualResetEvent stop = new ManualResetEvent(false);
    private readonly Thread thread;
    private uint acquired;
    public TG8ManualAwake() {
        thread = new Thread(() => {
            acquired = SetThreadExecutionState(0x80000001u);
            ready.Set();
            try { stop.WaitOne(); }
            finally { SetThreadExecutionState(0x80000000u); }
        });
        thread.IsBackground = true;
        thread.Start();
        ready.WaitOne();
        if (acquired == 0) {
            Dispose();
            throw new InvalidOperationException("Cannot acquire system-awake request.");
        }
    }
    public void Dispose() {
        stop.Set();
        thread.Join();
        ready.Dispose();
        stop.Dispose();
    }
}
'@
}

function Stop-TG8Service([string]$Unit) {
    if ($Unit -notmatch '^tg8-v2-[a-f0-9]{20}$') { throw "Unexpected service identity." }
    $stopper = Start-Process -FilePath "wsl.exe" -WindowStyle Hidden -PassThru `
        -ArgumentList @("--user", "root", "--exec", "systemctl", "stop", "$Unit.service")
    if (-not $stopper.WaitForExit(45000)) {
        throw "Stop confirmation timed out. Do not restart. Check the service manually."
    }
    if ($stopper.ExitCode -ne 0) { throw "Service stop failed. Do not restart." }
}

Push-Location $root
$awake = $null
$unit = $null
$finished = $false
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    if ($SelfTest) {
        Initialize-KeepAwake
        $awake = [TG8ManualAwake]::new()
        Write-Output "SELFTEST: acquired system-awake request; no experiment or authorization."
        & powercfg /requests
        Start-Sleep -Seconds 2
        $finished = $true
        return
    }
    & python -B scripts/acl2027_experiment_handoff.py validate
    if ($LASTEXITCODE -ne 0) { throw "Handoff validation failed." }
    $review = & python -B scripts/prepare_acl2027_tg8_manual_v1.py review
    if ($LASTEXITCODE -ne 0) { throw "Manual plan validation failed; nothing launched." }
    $plan = ($review -join "`n") | ConvertFrom-Json
    Write-Host ($review -join "`n")
    Write-Host ""
    Write-Host "ONE NEW INDEPENDENT TG8 RUN: 360 rows, <=75 steps, zero retries."
    Write-Host "First hard invariant stops the run. No network/provider/model/API/paid calls."
    Write-Host "No Phase 0-6, WebShop, other models or datasets. Old results are preserved."
    Write-Host "6-hour limit from launch; 30-second service shutdown grace."
    Write-Host "Temporary system-awake request; display may turn off. No permanent power changes."
    Write-Host "Keep AC connected, lid open, and THIS terminal open (minimizing is fine)."
    Write-Host "Forced sleep/shutdown cannot be prevented; a suspended host cannot enforce a wall deadline."
    Write-Host "This version does not add a per-step worker timeout. A stalled row may consume the 6-hour cap."
    Write-Host "No Codex connection or chat monitor is needed."
    if ($CheckOnly) {
        Write-Host "CHECK ONLY: no receipt, experiment, power setting or launch was created."
        $finished = $true
        return
    }
    Initialize-KeepAwake
    if (-not [TG8ManualAwake]::OnAC()) { throw "Connect AC power before starting." }
    $active = & wsl.exe --user root --exec systemctl list-units --type=service `
        --state=active,activating,deactivating --no-legend --plain "tg8-v2-*"
    if ($LASTEXITCODE -ne 0) { throw "Cannot verify existing services; nothing launched." }
    if (($active -join "`n").Trim()) { throw "An existing TG8 service is present; nothing launched." }
    $expected = "AUTHORIZE " + $plan.plan_sha256
    Write-Host "To authorize exactly the plan above, type: $expected"
    $answer = Read-Host
    if ($answer -cne $expected) { throw "Not authorized; nothing launched." }
    $awake = [TG8ManualAwake]::new()
    $activation = & python -B scripts/prepare_acl2027_tg8_manual_v1.py confirm --authorization $answer
    if ($LASTEXITCODE -ne 0) { throw "Activation failed; preserve artifacts and do not retry." }
    $authorization = ($activation -join "`n") | ConvertFrom-Json
    $config = Get-Content -LiteralPath $authorization.config -Encoding UTF8 -Raw | ConvertFrom-Json
    $unit = "tg8-v2-" + $config.authorization_receipt_sha256.Substring(0, 20)
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($config.max_wall_seconds)
    $launch = & "$PSScriptRoot/start_acl2027_tracegraph_tg8_durable_v2.ps1" -Config $authorization.config
    $launchText = $launch -join "`n"
    Write-Host $launchText
    # The frozen launcher prints validation JSON before its final launch JSON.
    $launchPath = Join-Path $root ("artifacts/acl2027_tracegraph_tg8_durable_v2/.launch_records/" +
        $config.authorization_receipt_sha256 + "/launch.json")
    $record = Get-Content -LiteralPath $launchPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $keeper = Get-Process -Id $record.windows_pid -ErrorAction Stop
    $directory = Join-Path $root $config.run_directory
    Write-Host "Running. Output: $directory"
    Write-Host ("Host deadline (local): " + $deadline.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss zzz"))
    $lastCount = -1
    while (-not $keeper.HasExited) {
        if ([DateTimeOffset]::UtcNow -ge $deadline) {
            Write-Host "Deadline reached. Stopping this service, without retries."
            Stop-TG8Service $unit
            if (-not $keeper.WaitForExit(35000)) { throw "WSL keeper did not exit after service stop." }
            break
        }
        $count = @(Get-ChildItem -LiteralPath (Join-Path $directory "rows") -Filter "*.json" `
            -ErrorAction SilentlyContinue).Count
        if ($count -ne $lastCount) {
            Write-Host ("{0}  Saved rows: {1}/360" -f (Get-Date -Format "HH:mm:ss"), $count)
            $lastCount = $count
        }
        Start-Sleep -Seconds 5
        $keeper.Refresh()
    }
    $finished = $true
    $exitPath = Join-Path $directory "exit.json"
    if (Test-Path -LiteralPath $exitPath) {
        Write-Host (Get-Content -LiteralPath $exitPath -Raw -Encoding UTF8)
        Write-Host "Terminal evidence saved. Full scientific audit is still required."
    } else {
        throw "No exit record. This is NOT successful completion. Preserve evidence; do not retry."
    }
} finally {
    if ($unit -and -not $finished) {
        try { Stop-TG8Service $unit }
        catch { Write-Warning $_ }
    }
    if ($null -ne $awake) { $awake.Dispose() }
    Pop-Location
}
