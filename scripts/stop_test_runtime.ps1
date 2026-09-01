[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$Apply,
    [string]$MarkerPath = 'runtime/test-runtime.json'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$marker = [IO.Path]::GetFullPath((Join-Path $root $MarkerPath))
if (($Plan -and $Apply) -or (-not $Plan -and -not $Apply)) { throw 'Specify exactly one mode: -Plan or -Apply.' }
if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { Write-Output '[PASS] Runtime marker is absent; no process was targeted.'; exit 0 }
$payload = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
if ($payload.profile -ne 'OFFLINE_TEST' -or $payload.environment -ne 'test' -or $payload.outgoing_mail -ne 'disabled') { throw 'Marker is not an OFFLINE_TEST runtime marker; no process was targeted.' }
$pidValue = [int]$payload.pid
$process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
if ($Plan) {
    if ($process) { Write-Output "[INFO] Plan would stop only PID $pidValue from the OFFLINE_TEST marker." }
    else { Write-Output '[PASS] Marked runtime process is not running.' }
    exit 0
}
if ($process) {
    Stop-Process -Id $pidValue -Force
    Write-Output "[PASS] Stopped only marked OFFLINE_TEST process PID $pidValue."
} else {
    Write-Output '[PASS] Marked runtime process was already stopped.'
}
