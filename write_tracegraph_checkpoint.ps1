$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$statePath = Join-Path $root "paper/acl2027/experiment_state.json"
$protocolPath = Join-Path $root "paper/acl2027/CROSS_CONVERSATION_PROTOCOL.md"

if (!(Test-Path -LiteralPath $statePath) -or !(Test-Path -LiteralPath $protocolPath)) {
    throw "Run this script from the SummerSkillOpt repository root."
}

$env:PYTHONDONTWRITEBYTECODE = "1"
python scripts/acl2027_experiment_handoff.py validate
if ($LASTEXITCODE -ne 0) {
    throw "Initial handoff validation failed."
}

$stamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")
$date = (Get-Date).ToString("yyyy-MM-dd")
$runId = (Get-Date).ToString("yyyyMMdd_HHmmss") + "_" + [guid]::NewGuid().ToString("N").Substring(0, 8)

$lf = [string][char]10
$crlf = [string][char]13 + [string][char]10
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Replace-Once(
    [string]$Text,
    [string]$Old,
    [string]$New,
    [string]$Label
) {
    $count = ([regex]::Matches($Text, [regex]::Escape($Old))).Count
    if ($count -ne 1) {
        throw "$Label match count was $count, expected exactly 1."
    }
    return $Text.Replace($Old, $New)
}

$state = [IO.File]::ReadAllText($statePath, [Text.Encoding]::UTF8).Replace($crlf, $lf)
$protocol = [IO.File]::ReadAllText($protocolPath, [Text.Encoding]::UTF8).Replace($crlf, $lf)

$state = Replace-Once `
    $state `
    '  "updated_at": "2026-08-31T14:45:00+08:00",' `
    ('  "updated_at": "' + $stamp + '",') `
    "updated_at"

$oldVerification = @(
    '    "timestamp": "2026-08-31T14:45:00+08:00",',
    '    "scope": "TraceGraph TG6 derived PDDL repair plus Fast Downward zero-network preflight",',
    '    "pytest": "cache-free repair, integrity-audit, and handoff regressions passed",'
) -join $lf

$newVerification = @(
    ('    "timestamp": "' + $stamp + '",'),
    '    "scope": "TraceGraph TG6 derived PDDL repair plus repaired local-execution zero-network preflight",',
    '    "pytest": "cache-free repaired preflight, repaired runner, and handoff regressions passed (15 tests)",'
) -join $lf

$state = Replace-Once $state $oldVerification $newVerification "verification"

$oldBinding = @(
    '    "preflight_sha256": "fce9414862e2718b2ef15615cd2486bce309da62dd9ba41bd0c83f95549582d8",',
    '    "planner_status_counts": {'
) -join $lf

$newBinding = @(
    '    "preflight_sha256": "fce9414862e2718b2ef15615cd2486bce309da62dd9ba41bd0c83f95549582d8",',
    '    "repaired_execution_preflight": "configs/acl2027/tracegraph_tg6_repaired_local_execution_preflight_v1.json",',
    '    "repaired_execution_preflight_sha256": "a4855cc665e2404b905df979949980da01305255761f9a7612bcd8b23c1b5feb",',
    '    "planner_status_counts": {'
) -join $lf

$state = Replace-Once $state $oldBinding $newBinding "preflight binding"

$oldAcceptance = '    "acceptance": "Derived repair passed Fast Downward pddl2sas for all 40 tasks and repaired exactly 8 source-integrity blockers. No official file, frozen schedule, terminal TG6 artifact, episode, provider/model/API call, or Phase 0-6 artifact was modified or reused."'

$newAcceptance = '    "acceptance": "Derived repair passed Fast Downward pddl2sas for all 40 tasks and repaired exactly 8 source-integrity blockers. The separately versioned repaired local-execution preflight and runner guard passed 15 cache-free tests; execution_authorized remains false, no authorized runner config exists, and no episode, provider/model/API call, or Phase 0-6 artifact was modified or reused."'

$state = Replace-Once $state $oldAcceptance $newAcceptance "acceptance"

$marker = "## Current TraceGraph TG6 repaired local-execution preflight handoff ($date)"
if ($protocol.Contains("## Current TraceGraph TG6 repaired local-execution preflight handoff")) {
    throw "A repaired local-execution checkpoint section already exists."
}

$section = @(
    "",
    $marker,
    "",
    "The separately versioned closed preflight is",
    '`configs/acl2027/tracegraph_tg6_repaired_local_execution_preflight_v1.json`',
    "with SHA-256",
    '`a4855cc665e2404b905df979949980da01305255761f9a7612bcd8b23c1b5feb`.',
    "Its validator and the repaired runner guard passed 15 cache-free regression",
    "tests, including handoff validation. The scope remains exactly 40 derived",
    "held-out tasks, zero retries, stop on the first hard invariant violation, and",
    'runtime inputs limited to `observation`, `historical_actions`, and',
    '`admissible_actions`.',
    "",
    "This is still a closed preflight: `execution_authorized=false`, the",
    "authorized runner configuration does not exist, and zero episodes,",
    "provider/model/API calls, receipts, Phase 6 actions, WebShop assets, or",
    "Phase 0-6 reuse are permitted. Do not create the authorized config or run the",
    "repaired runner without a fresh exact user authorization bound to this",
    "preflight fingerprint and scope."
) -join $lf

$protocol = $protocol.TrimEnd([char]10) + $section + $lf
$null = $state | ConvertFrom-Json

$backupDir = Join-Path $env:TEMP ("SummerSkillOpt_checkpoint_backup_" + $runId)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$stateTmp = Join-Path $root ("paper/acl2027/.experiment_state." + $runId + ".tmp")
$protocolTmp = Join-Path $root ("paper/acl2027/.protocol." + $runId + ".tmp")

[IO.File]::WriteAllText($stateTmp, $state.Replace($lf, $crlf), $utf8)
[IO.File]::WriteAllText($protocolTmp, $protocol.Replace($lf, $crlf), $utf8)

$null = [IO.File]::ReadAllText($stateTmp, [Text.Encoding]::UTF8) | ConvertFrom-Json
if (!([IO.File]::ReadAllText($protocolTmp, [Text.Encoding]::UTF8).Contains($marker))) {
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
    if (!([IO.File]::ReadAllText($protocolPath, [Text.Encoding]::UTF8).Contains($marker))) {
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
    if (Test-Path -LiteralPath $stateTmp) {
        Remove-Item -LiteralPath $stateTmp -Force
    }
    if (Test-Path -LiteralPath $protocolTmp) {
        Remove-Item -LiteralPath $protocolTmp -Force
    }
}

python scripts/run_acl2027_tracegraph_tg6_repaired_local_execution_preflight_v1.py
if ($LASTEXITCODE -ne 0) {
    throw "Repaired preflight failed."
}

python -m pytest -p no:cacheprovider `
    tests/test_acl2027_tracegraph_tg6_repaired_local_execution_preflight_v1.py `
    tests/test_acl2027_tracegraph_tg6_repaired_local_execution_runner_v1.py `
    tests/test_acl2027_experiment_handoff.py

if ($LASTEXITCODE -ne 0) {
    throw "Checkpoint regression tests failed."
}

python scripts/acl2027_experiment_handoff.py validate
if ($LASTEXITCODE -ne 0) {
    throw "Final handoff validation failed."
}

Write-Output "CHECKPOINT_APPLIED"
Write-Output ("BACKUP_DIR=" + $backupDir)