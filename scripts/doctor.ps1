[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$DryRun,
    [switch]$Apply,
    [string]$PythonVersion = '3.11'
)

$modeCount = 0
if ($Plan) { $modeCount++ }
if ($DryRun) { $modeCount++ }
if ($Apply) { $modeCount++ }
if ($modeCount -ne 1) {
    throw 'Specify exactly one mode: -Plan, -DryRun or -Apply.'
}

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$requirements = Join-Path $root 'requirements.txt'
$envFile = Join-Path $root '.env'
$dbPath = Join-Path $root 'mail-data\supplier.sqlite3'
$errors = 0

function Report([string]$status, [string]$message) {
    Write-Output "[$status] $message"
}

if ($Plan) {
    Report 'OK' "Plan mode: read-only, project root $root"
} elseif ($DryRun) {
    Report 'OK' 'DryRun mode: checks only, no changes will be made'
} else {
    Report 'WARN' 'Doctor Apply only runs checks; use recover_supplydesk.ps1 to start the server'
}

if (Test-Path -LiteralPath $requirements) {
    Report 'OK' 'requirements.txt found'
} else {
    Report 'ERROR' 'requirements.txt was not found'
    $errors++
}

if (Test-Path -LiteralPath $envFile) {
    Report 'OK' '.env found; secrets are not printed'
} else {
    Report 'ERROR' '.env was not found'
    $errors++
}

$pythonPath = $null
$pythonArgs = @()
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    $pythonPath = $venvPython
    Report 'OK' "Project Python found: $venvPython"
} else {
    $directCandidates = @()
    $pythonInstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $pythonInstallRoot) {
        $directCandidates = @(Get-ChildItem -LiteralPath $pythonInstallRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName 'python.exe' } |
            Where-Object { Test-Path -LiteralPath $_ })
    }
    foreach ($candidate in $directCandidates) {
        $probe = & $candidate --version 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            $pythonPath = $candidate
            Report 'WARN' "Project .venv not found; direct Python found: $pythonPath"
            break
        }
    }
    if (-not $pythonPath) {
        $pyCommand = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCommand) {
            $pythonPath = $pyCommand.Source
            $pythonArgs = @("-$PythonVersion")
            Report 'WARN' "Project .venv not found; Python $PythonVersion will be checked through py.exe"
        } else {
            Report 'ERROR' 'Python or py.exe was not found'
            $errors++
        }
    }
}

function Invoke-SelectedPython([string]$code) {
    if ($pythonArgs.Count -gt 0) {
        & $pythonPath @pythonArgs -c $code 2>&1
    } else {
        & $pythonPath -c $code 2>&1
    }
}

if ($pythonPath) {
    $versionOutput = (Invoke-SelectedPython 'import sys; print(sys.version.split()[0]); print(sys.executable)' | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        Report 'ERROR' "Python does not start: $versionOutput"
        $errors++
    } else {
        $versionLines = $versionOutput -split "`r?`n"
        Report 'OK' "Python $($versionLines[0]) available: $($versionLines[-1])"
    }
}

if ($pythonPath -and $LASTEXITCODE -eq 0) {
    $packageCode = "import importlib.util,sys; names=['requests','bs4','lxml','cryptography','nh3','quotequail','openai','dns','psycopg','pypdf']; missing=[n for n in names if importlib.util.find_spec(n) is None]; print(','.join(missing)); sys.exit(1 if missing else 0)"
    $missingPackages = (Invoke-SelectedPython $packageCode | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        Report 'ERROR' "Missing Python packages: $missingPackages"
        $errors++
    } else {
        Report 'OK' 'All required Python package imports are available'
    }
}

if (Test-Path -LiteralPath $dbPath) {
    Report 'OK' "Canonical SQLite found: $dbPath"
} else {
    Report 'ERROR' "Canonical SQLite was not found: $dbPath"
    $errors++
}

if (Test-Path -LiteralPath $envFile) {
    $envKeys = @{}
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=') {
            $envKeys[$Matches[1]] = $true
        }
    }
    foreach ($key in @('SUPPLYDESK_ENV', 'MAIL_DB_PATH', 'MAIL_TOKEN_ENCRYPTION_KEY')) {
        if ($envKeys.ContainsKey($key)) {
            Report 'OK' ".env contains key $key"
        } else {
            Report 'ERROR' ".env does not contain key $key"
            $errors++
        }
    }
}

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Report 'WARN' "Port 8000 is already used by process $($listener[0].OwningProcess)"
} else {
    Report 'OK' 'Port 8000 is free'
}

if ($errors -gt 0) {
    Report 'ERROR' "Doctor finished with $errors error(s)"
    exit 2
}

Report 'OK' 'Doctor finished without errors; start the server only with outgoing OFF'
exit 0
