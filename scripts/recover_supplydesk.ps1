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
$doctor = Join-Path $PSScriptRoot 'doctor.ps1'

if ($Plan) {
    Write-Output '[OK] Plan: recovery checks the environment and starts nothing'
    if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) {
        & $doctor -Plan -PythonVersion $PythonVersion -ExpectedRoot $ExpectedRoot
    } else {
        & $doctor -Plan -PythonVersion $PythonVersion
    }
    exit $LASTEXITCODE
}

if ($DryRun) {
    Write-Output '[OK] DryRun: recovery checks the environment and starts nothing'
    if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) {
        & $doctor -DryRun -PythonVersion $PythonVersion -ExpectedRoot $ExpectedRoot
    } else {
        & $doctor -DryRun -PythonVersion $PythonVersion
    }
    exit $LASTEXITCODE
}

Write-Output '[WARN] Apply: the server starts only with MAIL_OUTGOING_DISABLED=1'
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) {
    & $doctor -DryRun -PythonVersion $PythonVersion -ExpectedRoot $ExpectedRoot
} else {
    & $doctor -DryRun -PythonVersion $PythonVersion
}
if ($LASTEXITCODE -ne 0) {
    Write-Output '[ERROR] Preflight failed; the server will not start'
    exit 2
}

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    Write-Output '[ERROR] Apply requires .venv\Scripts\python.exe; install dependencies in a normal Windows runtime'
    exit 2
}

$runtimeGuard = Join-Path $root 'scripts\runtime_guard.py'
$guardArgs = @(
    $runtimeGuard, '--surface', 'backend', '--purpose', 'OWNER_SESSION',
    '--mode', 'LOCAL_CANONICAL', '--base-url', 'http://127.0.0.1:8000',
    '--database-class', 'CANONICAL_SQLITE', '--auth-mode', 'OWNER_SESSION',
    '--database-path', (Join-Path $root 'mail-data\supplier.sqlite3'),
    '--application-env', 'development', '--mail-outgoing-disabled', '1', '--root', $root
)
& $python @guardArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$runtime = Join-Path $root 'runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stdout = Join-Path $runtime "supplier_app.recovery.$stamp.out.log"
$stderr = Join-Path $runtime "supplier_app.recovery.$stamp.err.log"
$previousOutgoing = [Environment]::GetEnvironmentVariable('MAIL_OUTGOING_DISABLED', 'Process')
$env:MAIL_OUTGOING_DISABLED = '1'
$env:RUNTIME_PURPOSE = 'OWNER_SESSION'
$env:RUNTIME_MODE = 'LOCAL_CANONICAL'
$env:RUNTIME_DATABASE_CLASS = 'CANONICAL_SQLITE'
$env:RUNTIME_AUTH_MODE = 'OWNER_SESSION'
$env:RUNTIME_BASE_URL = 'http://127.0.0.1:8000'
$process = $null

try {
    $process = Start-Process -FilePath $python -ArgumentList @('supplier_app.py') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/' -TimeoutSec 3
                if ([int]$response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            } catch {
                # The server may still be starting; retry the smoke-test.
            }
        }
        if ($process.HasExited) {
            break
        }
    }

    if (-not $ready) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
        Write-Output "[ERROR] HTTP smoke-test failed. Logs: $stdout and $stderr"
        exit 2
    }

    Write-Output '[OK] SupplyDesk started: http://127.0.0.1:8000/'
    Write-Output "[OK] PID: $($process.Id); outgoing forced OFF"
    Write-Output "[OK] Logs: $stdout and $stderr"
} finally {
    if ($null -eq $previousOutgoing) {
        Remove-Item Env:MAIL_OUTGOING_DISABLED -ErrorAction SilentlyContinue
    } else {
        $env:MAIL_OUTGOING_DISABLED = $previousOutgoing
    }
}
