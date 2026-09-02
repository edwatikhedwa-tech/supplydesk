[CmdletBinding()]
param(
    [switch]$Quick,
    [switch]$Full,
    [switch]$Diagnostics,
    [string]$PythonPath,
    [string]$ExpectedRoot
)

$ErrorActionPreference = 'Stop'
$guard = Join-Path $PSScriptRoot '..\scripts\assert_workspace.ps1'
$guardHostName = if ($PSEdition -eq 'Core') { 'pwsh.exe' } else { 'powershell.exe' }
$guardHost = Join-Path $PSHOME $guardHostName
$guardArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $guard)
if (-not [string]::IsNullOrWhiteSpace($ExpectedRoot)) { $guardArgs += @('-ExpectedRoot', $ExpectedRoot) }
& $guardHost @guardArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

$modeCount = 0
if ($Quick) { $modeCount++ }
if ($Full) { $modeCount++ }
if ($Diagnostics) { $modeCount++ }
if ($modeCount -gt 1) {
    throw 'Specify at most one suite mode: -Quick, -Full or -Diagnostics.'
}

$suite = 'full'
if ($Diagnostics) { $suite = 'diagnostics' }
elseif ($Quick) { $suite = 'quick' }

$requirements = Join-Path $root 'requirements-test.txt'
$runner = Join-Path $root 'scripts\run_test_suite.py'
if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    Write-Output '[ENVIRONMENT_GAP] requirements-test.txt is missing; no packages were installed.'
    exit 2
}
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    Write-Output '[PRODUCT_FAILURE] Official Python test runner is missing.'
    exit 1
}

if (-not $PythonPath) {
    $preferred = Join-Path $root '.venv-test\Scripts\python.exe'
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        $PythonPath = $preferred
    } else {
        Write-Output '[ENVIRONMENT_GAP] .venv-test is absent; run scripts\setup_test_env.ps1 -Apply first.'
        exit 2
    }
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    Write-Output '[ENVIRONMENT_GAP] Selected Python executable is absent; no installation was attempted.'
    exit 2
}

Write-Output "[PASS] Official backend runner selected: $suite; installation is not performed by this command."
& $PythonPath $runner '--root' $root '--suite' $suite
$exitCode = $LASTEXITCODE
exit $exitCode
