[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$DryRun,
    [switch]$Apply,
    [switch]$Full,
    [switch]$RunTests,
    [switch]$RunFrontend,
    [switch]$RunBrowser,
    [ValidateSet('OFFLINE_TEST', 'LOCAL_CANONICAL', 'LIVE_EXTERNAL')]
    [string]$Profile = 'OFFLINE_TEST',
    [string]$PythonVersion = '3.11',
    [string]$BaseUrl = 'http://127.0.0.1:18000',
    [string]$FrontendBaseUrl = 'http://127.0.0.1:18000',
    [string]$DbPath,
    [string]$RuntimeMarker = 'runtime/test-runtime.json',
    [string]$ExpectedRoot
)

$ErrorActionPreference = 'Stop'
$modeCount = 0
if ($Plan) { $modeCount++ }
if ($DryRun) { $modeCount++ }
if ($Apply) { $modeCount++ }
if ($modeCount -ne 1) { throw 'Specify exactly one mode: -Plan, -DryRun or -Apply.' }
if ($Full -and -not $DryRun) { throw '-Full is available only with -DryRun; it runs read-only acceptance checks.' }

$guard = Join-Path $PSScriptRoot 'assert_workspace.ps1'
$guardHostName = if ($PSEdition -eq 'Core') { 'pwsh.exe' } else { 'powershell.exe' }
$guardHost = Join-Path $PSHOME $guardHostName
$guardArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $guard)
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) { $guardArgs += @('-ExpectedRoot', $ExpectedRoot) }
& $guardHost @guardArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $root 'scripts\diagnostics\diagnostic_runner.py'

if ($Plan) {
    Write-Output '[PASS] Doctor plan is read-only.'
    Write-Output "[PASS] Profile: $Profile. Profiles distinguish required, optional and forbidden evidence without installing or starting anything."
    Write-Output '[PASS] OFFLINE_TEST: disposable DB, test dependencies, backend regression, frontend gates, safe runtime and Playwright are required; canonical DB, private .env, SMTP/IMAP and real mail are forbidden.'
    Write-Output '[PASS] LOCAL_CANONICAL: canonical DB inspection is optional/read-only; live mail remains outside the safe Doctor path.'
    Write-Output '[SAFETY_BLOCK] LIVE_EXTERNAL is manual-only; Doctor will not connect to providers or send mail.'
    Write-Output '[PASS] No server, provider, migration, database write, email, Git mutation or secret-value read is planned.'
    exit 0
}

if ($Apply) {
    Write-Output '[SAFETY_BLOCK] No recovery actions are implemented in Diagnostic Plane V1.1; Doctor Apply remains blocked.'
    Write-Output '[SAFETY_BLOCK] Use setup_test_env.ps1 -Apply only for isolated dependency preparation; no database, mail, credential or Git action was performed.'
    exit 3
}

if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    Write-Output '[PRODUCT_FAILURE] Diagnostic runner is missing.'
    exit 1
}

$pythonPath = $null
$pythonArgs = @()
$venvPython = Join-Path $root '.venv-test\Scripts\python.exe'
$legacyVenvPython = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $pythonPath = $venvPython
} elseif (Test-Path -LiteralPath $legacyVenvPython -PathType Leaf) {
    $pythonPath = $legacyVenvPython
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
$commandArgs = @($pythonArgs + @($runner, '--root', $root, '--output', $outputPath, '--base-url', $BaseUrl, '--frontend-base-url', $FrontendBaseUrl, '--profile', $Profile))
if ($DbPath) { $commandArgs += @('--db-path', $DbPath) }
if ($RuntimeMarker) { $commandArgs += @('--runtime-marker', $RuntimeMarker) }
if ($Full -or $RunTests) { $commandArgs += '--run-tests' }
if ($Full -or $RunFrontend) { $commandArgs += '--run-frontend' }
if ($Full -or $RunBrowser) { $commandArgs += '--run-browser' }

Write-Output "[PASS] DryRun mode: profile=$Profile; diagnostics are read-only; machine output is outside the repository."
& $pythonPath @commandArgs
$exitCode = $LASTEXITCODE
Write-Output "[INFO] Machine-readable evidence: $outputPath"
exit $exitCode
