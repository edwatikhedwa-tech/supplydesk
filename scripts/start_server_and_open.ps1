[CmdletBinding()]
param(
    [string]$ExpectedRoot
)

<#
Двойной клик по ярлыку на рабочем столе запускает этот файл через
start_server.bat. Поднимает безопасный тестовый сервер SupplyDesk
(scripts/start_test_runtime.ps1 -Apply — одноразовая база, реальная почта и
внешние провайдеры отключены; это единственный режим, который работает без
файла .env с боевыми ключами, а его в этом окружении нет) и открывает его в
браузере по умолчанию.
#>

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$startScript = Join-Path $PSScriptRoot 'start_test_runtime.ps1'
$marker = Join-Path $root 'runtime\test-runtime.json'

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

if (-not (Test-Path -LiteralPath $marker)) {
    Write-Output '[FAIL] Сервер должен был запуститься, но файл-метка runtime\test-runtime.json не найден.'
    exit 1
}

$info = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
$url = $info.base_url
if ([string]::IsNullOrWhiteSpace($url)) { $url = 'http://127.0.0.1:18000/' }

Write-Output "[INFO] Открываю $url в браузере по умолчанию..."
Start-Process $url

Write-Output ''
Write-Output 'Это безопасный тестовый режим: одноразовая база данных, реальная почта и внешние сервисы отключены — не боевые данные.'
Write-Output 'На странице входа рабочих кнопок Яндекс/Google/Mail.ru в этом окружении нет (нужны боевые OAuth-ключи).'
Write-Output 'Тестовый вход по email+паролю (не секрет, тестовые данные из scripts/start_test_runtime.ps1):'
Write-Output '  email:  test.user@example.invalid'
Write-Output '  пароль: TestOnly-Synthetic-20260901'
Write-Output 'Выполните на этой странице в консоли браузера (F12 → Console):'
Write-Output "  fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({email:'test.user@example.invalid',password:'TestOnly-Synthetic-20260901'})}).then(r=>r.json()).then(console.log)"
Write-Output ''
Write-Output 'Остановить сервер: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_test_runtime.ps1 -Apply'
