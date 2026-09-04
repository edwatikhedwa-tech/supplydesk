[CmdletBinding()]
param(
    [string]$ExpectedRoot
)

<# Двойной клик по ярлыку запускает рабочий LOCAL_CANONICAL runtime и
открывает его в браузере. SAFE_TEST не является заменой рабочей сессии. #>

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$startScript = Join-Path $PSScriptRoot 'start_local_canonical.ps1'

$startArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $startScript, '-Apply')
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) { $startArgs += @('-ExpectedRoot', $ExpectedRoot) }

& powershell.exe @startArgs
$exitCode = $LASTEXITCODE

# exit 0 = только что запущен; exit 2 = уже был запущен раньше (это тоже
# успех для "поднять сервер" — просто открываем уже работающий).
if ($exitCode -ne 0 -and $exitCode -ne 2) {
    Write-Output "[FAIL] Не удалось запустить сервер (код $exitCode). Смотрите вывод выше и логи в runtime\."
    exit $exitCode
}

$url = 'http://127.0.0.1:8000/'

Write-Output "[INFO] Открываю $url в браузере по умолчанию..."
Start-Process $url

Write-Output 'Открыта рабочая сессия LOCAL_CANONICAL: canonical DB, runtime :8000, исходящий mail отключён launcher-ом.'
