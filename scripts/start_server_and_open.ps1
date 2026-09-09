[CmdletBinding()]
param(
    [string]$ExpectedRoot,
    [int]$FrontendWaitSeconds = 30,
    [switch]$AllowOutgoingMail
)

<# Двойной клик по ярлыку запускает рабочий LOCAL_CANONICAL backend (API на
:8000) и dev-сервер frontend-v2 (UI на :5183, проксирует /api и /oauth на
backend), затем открывает frontend-v2 в браузере — это теперь основной UI,
а не собранный frontend/dist, который backend раньше отдавал на :8000.
SAFE_TEST не является заменой рабочей сессии. #>

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$startScript = Join-Path $PSScriptRoot 'start_local_canonical.ps1'

$startArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $startScript, '-Apply')
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) { $startArgs += @('-ExpectedRoot', $ExpectedRoot) }
if ($AllowOutgoingMail) { $startArgs += '-AllowOutgoingMail' }

& powershell.exe @startArgs
$exitCode = $LASTEXITCODE

# exit 0 = только что запущен; exit 2 = уже был запущен раньше (это тоже
# успех для "поднять сервер" — просто открываем уже работающий).
if ($exitCode -ne 0 -and $exitCode -ne 2) {
    Write-Output "[FAIL] Не удалось запустить backend (код $exitCode). Смотрите вывод выше и логи в runtime\."
    exit $exitCode
}

$frontendUrl = 'http://127.0.0.1:5183/'
$frontendDir = Join-Path $root 'frontend-v2'
$listener = Get-NetTCPConnection -LocalPort 5183 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1

if ($listener) {
    Write-Output "[INFO] frontend-v2 уже запущен (PID $($listener.OwningProcess)) — использую его."
} else {
    $runtimeDir = Join-Path $root 'runtime'
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    $stdout = Join-Path $runtimeDir 'frontend-v2.stdout.log'
    $stderr = Join-Path $runtimeDir 'frontend-v2.stderr.log'

    Write-Output '[INFO] Запускаю dev-сервер frontend-v2 (npm run dev)...'
    $feProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev') -WorkingDirectory $frontendDir `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds($FrontendWaitSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if ($feProcess.HasExited) { break }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $frontendUrl -TimeoutSec 2
            if ([int]$response.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }

    if (-not $ready) {
        Write-Output "[FAIL] frontend-v2 не поднялся за $FrontendWaitSeconds сек. Логи: $stdout и $stderr"
        exit 2
    }
    Write-Output "[PASS] frontend-v2 готов на $frontendUrl (PID $($feProcess.Id))."
}

Write-Output "[INFO] Открываю $frontendUrl в браузере по умолчанию..."
Start-Process $frontendUrl

if ($AllowOutgoingMail) {
    Write-Output 'Открыта рабочая сессия LOCAL_CANONICAL: canonical DB, backend API :8000, UI frontend-v2 :5183, исходящий mail ВКЛЮЧЁН (-AllowOutgoingMail).'
} else {
    Write-Output 'Открыта рабочая сессия LOCAL_CANONICAL: canonical DB, backend API :8000, UI frontend-v2 :5183, исходящий mail отключён launcher-ом.'
}
