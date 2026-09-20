$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$statePath = Join-Path $root "paper/acl2027/experiment_state.json"
$protocolPath = Join-Path $root "paper/acl2027/CROSS_CONVERSATION_PROTOCOL.md"
$pendingState = Join-Path $root "tracegraph_tg6_attempt_checkpoint_state.pending.json"

if (!(Test-Path -LiteralPath $statePath) -or !(Test-Path -LiteralPath $protocolPath)) {
    throw "Run this script from the SummerSkillOpt repository root."
}
if (!(Test-Path -LiteralPath $pendingState)) {
    throw "Pending state file is missing: $pendingState"
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
$marker = "## Current TraceGraph TG6 repaired local-execution attempt (2026-09-02)"
$sectionLines = @(
    "",
    $marker,
    "",
    "The exact authorized repaired runner configuration was present at configs/acl2027/tracegraph_tg6_repaired_local_execution_runner_v1.json (SHA-256 D5EEDD7A934C1A1F005388002769D170C76441759F76A59D120FEA19209618C8), bound to the repaired preflight fingerprint a4855cc665e2404b905df979949980da01305255761f9a7612bcd8b23c1b5feb and the frozen 40-task derived manifest.",
    "The runner was invoked once with zero retries; it stopped before episode 0 because Windows Python could not load the Linux NumPy binary, and the path-appended fallback exposed Linux-only Jericho/Fast Downward binaries. The existing WSL path was also unavailable with Wsl/Service/E_ACCESSDENIED.",
    "",
    "No result.json was written, no episode started, and no network/provider/model/API call occurred. This is an environment dependency blocker, not a TraceGraph capability result. Do not retry this authorization or resume the old terminal TG6 run. After a functioning local runtime is restored, any later execution must use a new versioned runner attempt and fresh exact authorization."
)
$section = ($sectionLines -join [Environment]::NewLine) + [Environment]::NewLine

$protocol = [IO.File]::ReadAllText($protocolPath, [Text.Encoding]::UTF8)
if (!$protocol.Contains($marker)) {
    $protocol = $protocol.TrimEnd() + $section
}

$runId = (Get-Date).ToString("yyyyMMdd_HHmmss") + "_" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$backupDir = Join-Path $env:TEMP ("SummerSkillOpt_checkpoint_backup_" + $runId)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$stateTmp = Join-Path $root ("tracegraph_state_install." + $runId + ".tmp")
$protocolTmp = Join-Path $root ("tracegraph_protocol_install." + $runId + ".tmp")

Copy-Item -LiteralPath $pendingState -Destination $stateTmp -Force
[IO.File]::WriteAllText($protocolTmp, $protocol, $utf8)
$null = [IO.File]::ReadAllText($stateTmp, [Text.Encoding]::UTF8) | ConvertFrom-Json
if (![IO.File]::ReadAllText($protocolTmp, [Text.Encoding]::UTF8).Contains($marker)) {
    throw "Temporary protocol verification failed."
}

Copy-Item -LiteralPath $statePath -Destination (Join-Path $backupDir "experiment_state.json") -Force
Copy-Item -LiteralPath $protocolPath -Destination (Join-Path $backupDir "CROSS_CONVERSATION_PROTOCOL.md") -Force

$stateInstalled = $false
$protocolInstalled = $false
try {
    Move-Item -LiteralPath $stateTmp -Destination $statePath -Force
    $stateInstalled = $true
    Move-Item -LiteralPath $protocolTmp -Destination $protocolPath -Force
    $protocolInstalled = $true
    $null = [IO.File]::ReadAllText($statePath, [Text.Encoding]::UTF8) | ConvertFrom-Json
    if (![IO.File]::ReadAllText($protocolPath, [Text.Encoding]::UTF8).Contains($marker)) {
        throw "Final protocol verification failed."
    }
}
catch {
    if ($stateInstalled) {
        Copy-Item -LiteralPath (Join-Path $backupDir "experiment_state.json") -Destination $statePath -Force
    }
    if ($protocolInstalled) {
        Copy-Item -LiteralPath (Join-Path $backupDir "CROSS_CONVERSATION_PROTOCOL.md") -Destination $protocolPath -Force
    }
    throw
}
finally {
    if (Test-Path -LiteralPath $stateTmp) { Remove-Item -LiteralPath $stateTmp -Force }
    if (Test-Path -LiteralPath $protocolTmp) { Remove-Item -LiteralPath $protocolTmp -Force }
}

$env:PYTHONDONTWRITEBYTECODE = "1"
python scripts/acl2027_experiment_handoff.py validate
if ($LASTEXITCODE -ne 0) { throw "Final handoff validation failed." }

Write-Output "CHECKPOINT_INSTALLED"
Write-Output ("BACKUP_DIR=" + $backupDir)
