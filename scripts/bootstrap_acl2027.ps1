<##
.SYNOPSIS
    Prepare a fresh Windows checkout for the ACL 2027 experiments.

.DESCRIPTION
    This script is intentionally a preparation and validation tool. It never
    launches an experiment, creates an authorization receipt, or downloads
    private data. Use the WSL companion script for ALFWorld execution.
##>
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$ValidateOnly,
    [string]$DataRoot = $env:ALFWORLD_DATA
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venv = Join-Path $repo ".venv-acl2027"
$python = Join-Path $venv "Scripts\python.exe"

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

function Invoke-Python([string[]]$Arguments) {
    if (-not (Test-Path -LiteralPath $python)) {
        Fail "Python environment is missing. Run: .\scripts\bootstrap_acl2027.ps1 -Install"
    }
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

Write-Host "Repository: $repo"
Write-Host "Branch: $(& git -C $repo branch --show-current)"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "Git is required. Install Git for Windows, then rerun this script."
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Fail "The Python launcher (py.exe) is required. Install Python 3.11 or 3.12."
}

if ($Install) {
    if (-not (Test-Path -LiteralPath $venv)) {
        & py -3.11 -m venv $venv
        if ($LASTEXITCODE -ne 0) {
            & py -3.12 -m venv $venv
        }
        if ($LASTEXITCODE -ne 0) {
            Fail "Could not create a Python 3.11/3.12 virtual environment."
        }
    }
    & $python -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { Fail "pip bootstrap failed." }
    & $python -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { Fail "Core/development dependency installation failed." }
    $envFile = Join-Path $repo ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        Copy-Item (Join-Path $repo ".env.example") $envFile
        Write-Host "Created .env from .env.example. Fill local credentials; .env is ignored by Git."
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    Fail "No prepared environment found. Run with -Install first."
}

Write-Host "Python: $(& $python --version)"
Write-Host "--- handoff validation ---"
Invoke-Python @("scripts/acl2027_experiment_handoff.py", "validate")

if ($DataRoot) {
    $resolved = Resolve-Path -LiteralPath $DataRoot -ErrorAction SilentlyContinue
    if ($resolved) {
        $alfworldJson = Join-Path $resolved.Path "json_2.1.1"
        if (Test-Path -LiteralPath $alfworldJson) {
            Write-Host "ALFWorld data: found at $($resolved.Path)"
        } else {
            Write-Warning "ALFWorld_DATA exists but json_2.1.1 is missing: $($resolved.Path)"
        }
    } else {
        Write-Warning "ALFWORLD_DATA does not exist yet: $DataRoot"
    }
} else {
    Write-Warning "ALFWORLD_DATA is not set. Set it only after copying the dataset to the new machine."
}

if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    Write-Host "WSL: available"
} else {
    Write-Warning "WSL is not available. ALFWorld TG6-TG9 runners require WSL2 Ubuntu."
}

Write-Host "Preparation complete. No experiment was launched."
Write-Host "Next: read docs/ACL2027_NEW_MACHINE.md and run the WSL companion script."
