param(
    [string]$Unit = "tg9-v1-49c34a95f3e34f239af2.service",
    [string]$LogPath = "E:\桌面\暑期实训\SummerSkillOpt\artifacts\acl2027_tracegraph_tg9_factorial_v1\independent_20260918_v1\awake_guardian.log",
    [int]$StartupTimeoutSeconds = 120,
    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class TG9Awake {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern uint SetThreadExecutionState(uint flags);
}
"@

$continuous = [Convert]::ToUInt32("80000000", 16)
$systemRequired = [Convert]::ToUInt32("00000001", 16)
$previous = [TG9Awake]::SetThreadExecutionState($continuous -bor $systemRequired)
if ($previous -eq 0) { throw "Unable to acquire the Windows system-awake request." }

try {
    Add-Content -LiteralPath $LogPath -Value (@{
        at = Get-Date -Format o
        event = "awake_acquired"
        pid = $PID
        unit = $Unit
        display_requested = $false
    } | ConvertTo-Json -Compress)
    if ($SelfTest) {
        Start-Sleep -Seconds 2
        return
    }
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $serviceObserved = $false
    while ($true) {
        $state = (& wsl.exe --user root --exec systemctl show $Unit -p ActiveState --value 2>$null).Trim()
        if ($state -in @("active", "activating", "deactivating")) {
            $serviceObserved = $true
        }
        if ($serviceObserved -and $state -in @("inactive", "failed")) {
            Add-Content -LiteralPath $LogPath -Value (@{
                at = Get-Date -Format o
                event = "service_terminal"
                state = $state
            } | ConvertTo-Json -Compress)
            break
        }
        if (-not $serviceObserved -and (Get-Date) -ge $deadline) {
            Add-Content -LiteralPath $LogPath -Value (@{
                at = Get-Date -Format o
                event = "service_start_timeout"
                state = $state
            } | ConvertTo-Json -Compress)
            break
        }
        Start-Sleep -Seconds 15
    }
}
finally {
    [void][TG9Awake]::SetThreadExecutionState($continuous)
    Add-Content -LiteralPath $LogPath -Value (@{
        at = Get-Date -Format o
        event = "awake_released"
    } | ConvertTo-Json -Compress)
}
