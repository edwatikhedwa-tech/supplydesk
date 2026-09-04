[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$Apply,
    [int]$WaitSeconds = 30,
    [string]$ExpectedRoot
)

$ErrorActionPreference = 'Stop'
if (($Plan -and $Apply) -or (-not $Plan -and -not $Apply)) {
    throw 'Specify exactly one mode: -Plan or -Apply.'
}

$workspaceGuard = Join-Path $PSScriptRoot 'assert_workspace.ps1'
$guardHostName = if ($PSEdition -eq 'Core') { 'pwsh.exe' } else { 'powershell.exe' }
$guardHost = Join-Path $PSHOME $guardHostName
$workspaceArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $workspaceGuard)
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) { $workspaceArgs += @('-ExpectedRoot', $ExpectedRoot) }
& $guardHost @workspaceArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { Write-Output '[ENVIRONMENT_GAP] Python was not found; canonical runtime was not started.'; exit 2 }
$guard = Join-Path $root 'scripts\runtime_guard.py'
$canonicalDb = Join-Path $root 'mail-data\supplier.sqlite3'
$guardArgs = @(
    $guard, '--surface', 'backend', '--purpose', 'OWNER_SESSION',
    '--mode', 'LOCAL_CANONICAL', '--base-url', 'http://127.0.0.1:8000',
    '--database-class', 'CANONICAL_SQLITE', '--auth-mode', 'OWNER_SESSION',
    '--database-path', $canonicalDb, '--application-env', 'development',
    '--mail-outgoing-disabled', '1', '--root', $root
)
& $python @guardArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Plan) {
    Write-Output '[PASS] LOCAL_CANONICAL plan is read-only; no process or database was started.'
    exit 0
}

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    Write-Output 'FAIL: RUNTIME_SELECTION_GUARD'
    Write-Output "STOP: LOCAL_CANONICAL port 8000 is already occupied by PID $($listener.OwningProcess); no second process was started."
    exit 2
}

$runtimeDir = Join-Path $root 'runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$stdout = Join-Path $runtimeDir 'local-canonical.stdout.log'
$stderr = Join-Path $runtimeDir 'local-canonical.stderr.log'
$saved = @{}
function Set-RuntimeEnvironment([string]$name, [string]$value) {
    $script:saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    Set-Item -Path ("Env:" + $name) -Value $value
}

$process = $null
try {
    Set-RuntimeEnvironment 'RUNTIME_PURPOSE' 'OWNER_SESSION'
    Set-RuntimeEnvironment 'RUNTIME_MODE' 'LOCAL_CANONICAL'
    Set-RuntimeEnvironment 'RUNTIME_DATABASE_CLASS' 'CANONICAL_SQLITE'
    Set-RuntimeEnvironment 'RUNTIME_AUTH_MODE' 'OWNER_SESSION'
    Set-RuntimeEnvironment 'RUNTIME_BASE_URL' 'http://127.0.0.1:8000'
    Set-RuntimeEnvironment 'MAIL_OUTGOING_DISABLED' '1'
    $process = Start-Process -FilePath $python -ArgumentList @('supplier_app.py') -WorkingDirectory $root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
} finally {
    foreach ($name in $saved.Keys) {
        $old = $saved[$name]
        if ($null -eq $old) { Remove-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue }
        else { Set-Item -Path ("Env:" + $name) -Value $old }
    }
}

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) { break }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/' -TimeoutSec 2
        if ([int]$response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 250
}

if (-not $ready) {
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    Write-Output "[ENVIRONMENT_GAP] LOCAL_CANONICAL did not become HTTP-ready; logs: $stdout and $stderr"
    exit 2
}

Write-Output "[PASS] LOCAL_CANONICAL is ready at http://127.0.0.1:8000/ (PID $($process.Id))."
Write-Output '[INFO] Outgoing mail was forced disabled for this launcher; .env was not changed.'
Write-Output "[INFO] Logs: $stdout and $stderr"
