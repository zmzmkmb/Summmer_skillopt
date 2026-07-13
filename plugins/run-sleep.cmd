@echo off
setlocal enabledelayedexpansion

:: Resolve REPO_ROOT
set "SCRIPT_DIR=%~dp0"
:: Strip trailing backslash
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if exist "%SCRIPT_DIR%\..\skillopt_sleep" (
    cd /d "%SCRIPT_DIR%\.."
    set "REPO_ROOT=%CD%"
) else if not "%CLAUDE_PLUGIN_ROOT%"=="" if exist "%CLAUDE_PLUGIN_ROOT%\..\..\skillopt_sleep" (
    cd /d "%CLAUDE_PLUGIN_ROOT%\..\.."
    set "REPO_ROOT=%CD%"
) else if not "%SKILLOPT_SLEEP_REPO%"=="" if exist "%SKILLOPT_SLEEP_REPO%\skillopt_sleep" (
    set "REPO_ROOT=%SKILLOPT_SLEEP_REPO%"
) else (
    :: Search upward from current directory
    set "d=%CD%"
    set "REPO_ROOT="
    :loop
    if exist "!d!\skillopt_sleep" (
        set "REPO_ROOT=!d!"
        goto found
    )
    for %%I in ("!d!") do set "parent=%%~dpI"
    :: Strip trailing backslash from parent if it's not root
    if "!parent!"=="!d!" goto notfound
    set "parent=!parent:~0,-1!"
    if "!parent!"=="" goto notfound
    set "d=!parent!"
    goto loop
    :notfound
    echo [sleep] ERROR: could not locate the skillopt_sleep package. Set SKILLOPT_SLEEP_REPO to the repo root. >&2
    exit /b 1
    :found
)

if not "%REPO_ROOT%"=="" (
    :: Find python >= 3.10
    set "PY="
    if not "%SKILLOPT_SLEEP_PYTHON%"=="" (
        set "PY=%SKILLOPT_SLEEP_PYTHON%"
    ) else (
        for %%p in (python3.exe python.exe py.exe) do (
            where %%p >nul 2>nul
            if !errorlevel! equ 0 (
                %%p -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
                if !errorlevel! equ 0 (
                    set "PY=%%p"
                    goto py_found
                )
            )
        )
    )
    :py_found

    if "%PY%"=="" (
        echo [sleep] ERROR: need Python >= 3.10 (found none). >&2
        exit /b 1
    )

    cd /d "%REPO_ROOT%"
    if "%~1"=="" (
        "%PY%" -m skillopt_sleep status
    ) else (
        "%PY%" -m skillopt_sleep %*
    )
    exit /b !errorlevel!
)

:: No source checkout found — fall back to an installed engine.

:: Fallback 1: skillopt-sleep CLI on PATH (uv tool install / pipx / pip install).
where skillopt-sleep >nul 2>nul
if !errorlevel! equ 0 (
    if "%~1"=="" (
        skillopt-sleep status
    ) else (
        skillopt-sleep %*
    )
    exit /b !errorlevel!
)

:: Fallback 2: importable as a module (pip install into the active Python).
set "PY="
for %%p in (python3.exe python.exe py.exe) do (
    where %%p >nul 2>nul
    if !errorlevel! equ 0 (
        %%p -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if !errorlevel! equ 0 (
            %%p -c "import skillopt_sleep" >nul 2>nul
            if !errorlevel! equ 0 (
                set "PY=%%p"
                goto py_import_found
            )
        )
    )
)
:py_import_found

if not "%PY%"=="" (
    if "%~1"=="" (
        "%PY%" -m skillopt_sleep status
    ) else (
        "%PY%" -m skillopt_sleep %*
    )
    exit /b !errorlevel!
)

echo [sleep] ERROR: could not locate the skillopt_sleep package. >&2
echo [sleep] Install it with 'uv tool install skillopt' or 'pip install skillopt', >&2
echo [sleep] or set SKILLOPT_SLEEP_REPO to a clone of the SkillOpt repo. >&2
exit /b 1
