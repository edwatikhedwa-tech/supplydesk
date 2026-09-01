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
$runner = Join-Path $root 'scripts\diagnostics\diagnostic_runner.py'

if ($Plan) {
    Write-Output '[PASS] Doctor plan is read-only.'
    Write-Output '[PASS] DOC-001..DOC-018: Git, manifest, documentation, backend, safe HTTP, frontend, SQLite, tests, browser, secret-path and specialized static contract checks.'
    Write-Output '[PASS] No server, provider, migration, database write, email, Git mutation or secret-value read is planned.'
    exit 0
}

if ($Apply) {
    Write-Output '[SAFETY_BLOCK] No recovery actions are implemented in Diagnostic Plane V1.1.'
    Write-Output '[SAFETY_BLOCK] Use -Plan or -DryRun for observation; no database, mail, migration, credential or Git action was performed.'
    exit 3
}

if (-not (Test-Path -LiteralPath $runner)) {
    Write-Output '[PRODUCT_FAILURE] Diagnostic runner is missing.'
    exit 1
}

$pythonPath = $null
$pythonArgs = @()
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    $pythonPath = $venvPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $pythonPath = $pythonCommand.Source
    } else {
        $pyCommand = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCommand) {
            $pythonPath = $pyCommand.Source
            $pythonArgs = @("-$PythonVersion")
        }
    }
}

if (-not $pythonPath) {
    Write-Output '[ENVIRONMENT_GAP] Python or py.exe was not found; no diagnostic checks were run.'
    exit 2
}

$outputRoot = Join-Path ([IO.Path]::GetTempPath()) 'supplydesk-diagnostics'
$outputPath = Join-Path $outputRoot 'latest-doctor.json'
$commandArgs = @($pythonArgs + @($runner, '--root', $root, '--output', $outputPath, '--base-url', 'http://127.0.0.1:8000'))

Write-Output '[PASS] DryRun mode: diagnostics are read-only; machine output is outside the repository.'

& $pythonPath @commandArgs
$exitCode = $LASTEXITCODE
Write-Output "[INFO] Machine-readable evidence: $outputPath"
exit $exitCode
