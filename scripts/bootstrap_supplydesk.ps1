[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$DryRun,
    [switch]$Apply,
    [string]$PythonVersion = '3.11',
    [string]$ExpectedRoot
)

$modeCount = 0
if ($Plan) { $modeCount++ }
if ($DryRun) { $modeCount++ }
if ($Apply) { $modeCount++ }
if ($modeCount -ne 1) {
    throw 'Specify exactly one mode: -Plan, -DryRun or -Apply.'
}

$ErrorActionPreference = 'Stop'
$guard = Join-Path $PSScriptRoot 'assert_workspace.ps1'
$guardHostName = if ($PSEdition -eq 'Core') { 'pwsh.exe' } else { 'powershell.exe' }
$guardHost = Join-Path $PSHOME $guardHostName
$guardArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $guard)
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) { $guardArgs += @('-ExpectedRoot', $ExpectedRoot) }
& $guardHost @guardArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$requirements = Join-Path $root 'requirements.txt'
$venv = Join-Path $root '.venv'
$python = Join-Path $venv 'Scripts\python.exe'

Write-Output "[OK] Project root: $root"
Write-Output "[OK] Required Python version: $PythonVersion"
Write-Output "[OK] Requirements: $requirements"

if (-not (Test-Path -LiteralPath $requirements)) {
    Write-Output '[ERROR] requirements.txt was not found'
    exit 2
}

if (Test-Path -LiteralPath $python) {
    Write-Output "[OK] Project venv already exists: $python"
} else {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    $basePython = $null
    $baseArgs = @()
    if ($launcher) {
        & $launcher.Source "-$PythonVersion" --version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $basePython = $launcher.Source
            $baseArgs = @("-$PythonVersion")
        }
    }
    if (-not $basePython) {
        $pythonInstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
        if (Test-Path -LiteralPath $pythonInstallRoot) {
            $directCandidates = @(Get-ChildItem -LiteralPath $pythonInstallRoot -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName 'python.exe' } |
                Where-Object { Test-Path -LiteralPath $_ })
            foreach ($candidate in $directCandidates) {
                & $candidate --version 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $basePython = $candidate
                    break
                }
            }
        }
    }
    if (-not $basePython) {
        Write-Output '[ERROR] No usable Python was found; install Python in the normal Windows runtime'
        exit 2
    }

    if ($Plan -or $DryRun) {
        Write-Output "[WARN] Project venv is missing; Apply would create $venv"
        exit 0
    }

    Write-Output "[WARN] Apply: creating project venv at $venv"
    & $basePython @baseArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        Write-Output '[ERROR] Python venv creation failed; no application process was started'
        exit 2
    }
}

if ($Plan -or $DryRun) {
    Write-Output '[OK] No changes made'
    exit 0
}

Write-Output '[WARN] Apply: installing only requirements.txt into the project venv'
& $python -m pip install --disable-pip-version-check --requirement $requirements
if ($LASTEXITCODE -ne 0) {
    Write-Output '[ERROR] Dependency installation failed; outgoing remains untouched'
    exit 2
}

& $python -m pip check
if ($LASTEXITCODE -ne 0) {
    Write-Output '[ERROR] pip check failed; server will not be started'
    exit 2
}

Write-Output '[OK] Project venv is ready; next step is recover_supplydesk.ps1 -Apply'
exit 0
