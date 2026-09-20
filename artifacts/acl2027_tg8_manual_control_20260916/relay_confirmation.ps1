param([switch]$TransportSmoke)
$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$token = (Get-Content -LiteralPath (Join-Path $PSScriptRoot "confirmation.stdin.txt") -Raw).Trim()
$expectedToken = "AUTHORIZE bb68465f38a85105042dc086426415f1b6b2465c67997569d5bc412399c072ba"
if ($token -cne $expectedToken) { throw "Unexpected authorization transport payload." }
$promptLine = "To authorize exactly the plan above, type: $token"
if ($TransportSmoke) {
    $command = '$null = & wsl.exe --user root --exec systemctl list-units --type=service --state=active --no-legend --plain "tg8-v2-*"; if ($LASTEXITCODE -ne 0) { exit 3 }; Write-Host "' + $promptLine + '"; $answer = Read-Host; if ($answer -ceq "' + $token + '") { Write-Output "TRANSPORT SMOKE PASSED; no experiment invoked"; exit 0 } else { exit 2 }'
} else {
    foreach ($relative in @(
        "configs/acl2027/tracegraph_tg8_manual_authorized_20260916.json",
        "configs/acl2027/tracegraph_tg8_manual_receipt_20260916.json",
        "artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1"
    )) {
        if (Test-Path -LiteralPath (Join-Path $root $relative)) {
            throw "Authorization or experiment already exists; no invocation permitted."
        }
    }
    $entrypoint = Join-Path $root "scripts/start_acl2027_tg8_manual_v1.ps1"
    $hash = (Get-FileHash -LiteralPath $entrypoint -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne "353d82f1d88250b3c780474b63a0ca9e466fb75b31396499da0d01890cb7ccf5") {
        throw "Frozen entrypoint hash mismatch."
    }
    $command = "& '" + $entrypoint.Replace("'", "''") + "'"
}
$info = [Diagnostics.ProcessStartInfo]::new()
$info.FileName = "powershell.exe"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
$info.Arguments = "-NoProfile -EncodedCommand $encoded"
$info.WorkingDirectory = $root
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardInput = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$process = [Diagnostics.Process]::new()
$process.StartInfo = $info
if (-not $process.Start()) { throw "Unable to start confirmation host." }
Write-Output ("Confirmation host PID: " + $process.Id)
$errors = $process.StandardError.ReadToEndAsync()
$sent = $false
try {
    while ($null -ne ($line = $process.StandardOutput.ReadLine())) {
        Write-Output $line
        # Native preflight children can consume inherited stdin; send only at the prompt.
        if ($line -ceq $promptLine) {
            if ($sent) { throw "Repeated confirmation prompt; no second authorization sent." }
            $process.StandardInput.WriteLine($token)
            $process.StandardInput.Flush()
            $sent = $true
            Write-Output "Relayed the user's exact chat authorization once."
        }
    }
    $process.WaitForExit()
    $errorText = $errors.GetAwaiter().GetResult()
    if ($errorText) { [Console]::Error.WriteLine($errorText) }
    if (-not $sent) { throw "Confirmation prompt never reached; inspect preserved output." }
    exit $process.ExitCode
} finally {
    $process.StandardInput.Close()
    $process.Dispose()
}
