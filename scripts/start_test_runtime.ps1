[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$Apply,
    [ValidateSet('SAFE_TEST', 'AUTOMATED_TEST')]
    [string]$Purpose = 'SAFE_TEST',
    [int]$Port = 18000,
    [string]$DbPath = 'runtime/test-data/supplier.sqlite3',
    [string]$MarkerPath = 'runtime/test-runtime.json',
    [int]$WaitSeconds = 30,
    [string]$ExpectedRoot
)

$ErrorActionPreference = 'Stop'
$guard = Join-Path $PSScriptRoot 'assert_workspace.ps1'
$guardHostName = if ($PSEdition -eq 'Core') { 'pwsh.exe' } else { 'powershell.exe' }
$guardHost = Join-Path $PSHOME $guardHostName
$guardArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $guard)
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) { $guardArgs += @('-ExpectedRoot', $ExpectedRoot) }
& $guardHost @guardArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$entry = Join-Path $root 'scripts\test_runtime_entry.py'
$venvPython = Join-Path $root '.venv-test\Scripts\python.exe'
$db = [IO.Path]::GetFullPath((Join-Path $root $DbPath))
$marker = [IO.Path]::GetFullPath((Join-Path $root $MarkerPath))
$log = [IO.Path]::GetFullPath((Join-Path $root 'runtime/test-runtime.stdout.log'))
$errorLog = [IO.Path]::GetFullPath((Join-Path $root 'runtime/test-runtime.stderr.log'))

if (($Plan -and $Apply) -or (-not $Plan -and -not $Apply)) {
    throw 'Specify exactly one mode: -Plan or -Apply.'
}
if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) { throw 'Safe runtime entrypoint is missing.' }

$runtimeGuard = Join-Path $root 'scripts\runtime_guard.py'
$runtimePython = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $runtimePython) { throw 'Python is required to run the runtime selection guard.' }
$runtimeGuardArgs = @(
    $runtimeGuard, '--surface', 'backend', '--purpose', $Purpose,
    '--mode', 'SAFE_TEST', '--base-url', ("http://127.0.0.1:{0}" -f $Port),
    '--database-class', 'DISPOSABLE_SQLITE', '--auth-mode', 'SYNTHETIC_AUTH',
    '--database-path', $db, '--application-env', 'test',
    '--mail-outgoing-disabled', '1', '--root', $root
)
& $runtimePython @runtimeGuardArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path -LiteralPath $marker -PathType Leaf) {
    try {
        $oldMarker = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        if ($oldMarker.profile -eq 'OFFLINE_TEST' -and $oldMarker.environment -eq 'test' -and $oldMarker.pid) {
            if (Get-Process -Id ([int]$oldMarker.pid) -ErrorAction SilentlyContinue) {
                Write-Output "[ENVIRONMENT_GAP] Marked OFFLINE_TEST process PID $($oldMarker.pid) is already running; no second runtime was started."
                exit 2
            }
            Remove-Item -LiteralPath $marker -Force
        } else {
            throw 'Existing runtime marker is not an owned OFFLINE_TEST marker.'
        }
    } catch {
        if ($_.Exception.Message -like '*already running*') { throw }
        throw 'Existing runtime marker is unreadable or not an owned OFFLINE_TEST marker; no process was started.'
    }
}

function Test-PortFree([int]$candidate) {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $candidate)
    try { $listener.Start(); return $true } catch { return $false } finally { $listener.Stop() }
}

if (-not (Test-PortFree $Port)) {
    Write-Output "FAIL: RUNTIME_SELECTION_GUARD"
    Write-Output "STOP: SAFE_TEST port $Port is occupied; no alternate port is allowed."
    exit 3
}

Write-Output "[INFO] OFFLINE_TEST port: $Port"
Write-Output "[INFO] Disposable DB: $db"
Write-Output "[INFO] Runtime marker: $marker"
Write-Output '[INFO] Safety contract: test environment; outgoing mail disabled; external providers fake/blocked; loopback-only network.'

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    Write-Output '[ENVIRONMENT_GAP] .venv-test is absent; run scripts\setup_test_env.ps1 -Apply first.'
    exit 2
}

if ($Plan) {
    Write-Output '[PASS] Plan is read-only: no process, database, marker or environment file was changed.'
    exit 0
}

$markerParent = Split-Path -Parent $marker
$logParent = Split-Path -Parent $log
New-Item -ItemType Directory -Path $markerParent -Force | Out-Null
New-Item -ItemType Directory -Path $logParent -Force | Out-Null

$saved = @{}
function Set-TestEnvironment([string]$name, [string]$value) {
    $script:saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    Set-Item -Path ("Env:" + $name) -Value $value
}

try {
    Set-TestEnvironment 'SUPPLYDESK_ENV' 'test'
    Set-TestEnvironment 'RUNTIME_PURPOSE' $Purpose
    Set-TestEnvironment 'RUNTIME_MODE' 'SAFE_TEST'
    Set-TestEnvironment 'RUNTIME_DATABASE_CLASS' 'DISPOSABLE_SQLITE'
    Set-TestEnvironment 'RUNTIME_AUTH_MODE' 'SYNTHETIC_AUTH'
    Set-TestEnvironment 'RUNTIME_BASE_URL' ("http://127.0.0.1:$Port")
    Set-TestEnvironment 'APP_HOST' '127.0.0.1'
    Set-TestEnvironment 'PORT' ([string]$Port)
    Set-TestEnvironment 'APP_BASE_URL' ("http://127.0.0.1:$Port")
    Set-TestEnvironment 'MAIL_DB_PATH' $db
    Set-TestEnvironment 'DATABASE_URL' ''
    Set-TestEnvironment 'SUPPLYDESK_CANONICAL_DB_PATH' ''
    Set-TestEnvironment 'MAIL_OUTGOING_DISABLED' '1'
    Set-TestEnvironment 'APP_USER_EMAIL' 'test.user@example.invalid'
    Set-TestEnvironment 'APP_USER_PASSWORD' 'TestOnly-Synthetic-20260901'
    Set-TestEnvironment 'MAIL_SYNC_INTERVAL_SECONDS' '0'
    Set-TestEnvironment 'MAIL_SYNC_ON_VIEW_SECONDS' '0'
    Set-TestEnvironment 'MAIL_SYNC_WAIT_SECONDS' '0'
    Set-TestEnvironment 'ENRICHMENT_RETRY_INTERVAL_SECONDS' '0'
    Set-TestEnvironment 'ENRICH_SYNC_LLM_FALLBACK' '0'
    Set-TestEnvironment 'ENRICH_SYNC_WEB_FALLBACK' '0'
    Set-TestEnvironment 'ENRICH_CHECK_MX' '0'
    Set-TestEnvironment 'YANDEX_CLIENT_ID' ''
    Set-TestEnvironment 'YANDEX_CLIENT_SECRET' ''
    Set-TestEnvironment 'MAILRU_EMAIL' ''
    Set-TestEnvironment 'MAILRU_PASSWORD' ''
    Set-TestEnvironment 'SMTP_HOST' ''
    Set-TestEnvironment 'SMTP_PORT' ''
    Set-TestEnvironment 'SMTP_USER' ''
    Set-TestEnvironment 'SMTP_PASSWORD' ''
    Set-TestEnvironment 'IMAP_HOST' ''
    Set-TestEnvironment 'IMAP_PORT' ''
    Set-TestEnvironment 'IMAP_USER' ''
    Set-TestEnvironment 'IMAP_PASSWORD' ''
    Set-TestEnvironment 'CHECKO_KEY' ''
    Set-TestEnvironment 'XMLRIVER_USER' ''
    Set-TestEnvironment 'XMLRIVER_KEY' ''
    Set-TestEnvironment 'OPENAI_API_KEY' ''
    Set-TestEnvironment 'SUPPLYDESK_RUNTIME_MARKER' $marker

    $process = Start-Process -FilePath $venvPython -ArgumentList @($entry) -WorkingDirectory $root -RedirectStandardOutput $log -RedirectStandardError $errorLog -PassThru -WindowStyle Hidden
} finally {
    foreach ($name in $saved.Keys) {
        $old = $saved[$name]
        if ($null -eq $old) { Remove-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue }
        else { Set-Item -Path ("Env:" + $name) -Value $old }
    }
}

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$ready = $false
$runtimePid = $process.Id
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) { break }
    if (Test-Path -LiteralPath $marker) {
        try {
            $observed = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
            if ($observed.pid) { $runtimePid = [int]$observed.pid }
        } catch { }
    }
    try {
        $response = Invoke-WebRequest -Uri ("http://127.0.0.1:$Port/") -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 250
}

if (-not $ready) {
    if (Get-Process -Id $runtimePid -ErrorAction SilentlyContinue) { Stop-Process -Id $runtimePid -Force -ErrorAction SilentlyContinue }
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    Write-Output "[ENVIRONMENT_GAP] Safe runtime did not become HTTP-ready; logs: $log and $errorLog"
    exit 2
}

if (Test-Path -LiteralPath $marker) {
    try {
        $payload = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        $payload | Add-Member -NotePropertyName status -NotePropertyValue 'ready' -Force
        $payload | Add-Member -NotePropertyName ready_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('o')) -Force
        $markerJson = $payload | ConvertTo-Json -Depth 8
        [IO.File]::WriteAllText($marker, $markerJson + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
        if ($payload.pid) { $runtimePid = [int]$payload.pid }
    } catch { Write-Output '[WARNING] Runtime is HTTP-ready but marker could not be enriched.' }
}
Write-Output "[PASS] Safe test runtime is ready at http://127.0.0.1:$Port/ (PID $runtimePid)."
Write-Output "[INFO] Stop only this runtime with: .\scripts\stop_test_runtime.ps1 -Apply"
Write-Output "[INFO] Marker: $marker"
