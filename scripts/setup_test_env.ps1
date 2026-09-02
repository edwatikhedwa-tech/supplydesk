[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$Apply,
    [string]$PythonVersion = '3.11',
    [string]$VenvPath = '.venv-test',
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
$venv = [IO.Path]::GetFullPath((Join-Path $root $VenvPath))
$requirements = Join-Path $root 'requirements-test.txt'
$runtimeRequirements = Join-Path $root 'requirements.txt'

if (($Plan -and $Apply) -or (-not $Plan -and -not $Apply)) {
    throw 'Specify exactly one mode: -Plan or -Apply.'
}

function Get-PythonSelection {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $selector = "-$PythonVersion"
        $versionText = (& $py.Source $selector '--version' 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Path = $py.Source; Args = @($selector); Version = $versionText }
        }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $versionText = (& $python.Source '--version' 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Path = $python.Source; Args = @(); Version = $versionText }
        }
    }
    return $null
}

function Get-ManifestLines([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return @() }
    return @(Get-Content -LiteralPath $path | Where-Object { $_.Trim() -and -not $_.Trim().StartsWith('#') })
}

$selection = Get-PythonSelection
Write-Output "[INFO] Python requested: $PythonVersion"
if ($selection) {
    Write-Output "[PASS] Python selected: $($selection.Version) via $($selection.Path)"
} else {
    Write-Output '[ENVIRONMENT_GAP] Python launcher or requested version was not found.'
    exit 2
}
Write-Output "[INFO] Test venv: $venv"
Write-Output "[INFO] Runtime manifest: $runtimeRequirements"
Write-Output "[INFO] Test manifest: $requirements"
Write-Output '[INFO] Test-only package classification: unittest is standard library; pytest and pytest-cov are NOT_REQUIRED.'
Write-Output '[INFO] Declared requirements:'
foreach ($line in (Get-ManifestLines $requirements)) { Write-Output "  $line" }

if (-not (Test-Path -LiteralPath $runtimeRequirements -PathType Leaf) -or -not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    Write-Output '[PRODUCT_FAILURE] A declared dependency manifest is missing.'
    exit 1
}

if ($Plan) {
    if (Test-Path -LiteralPath $venv -PathType Container) {
        $candidate = Join-Path $venv 'Scripts\python.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            Write-Output '[PASS] Existing .venv-test can be reused; Plan made no changes.'
        } else {
            Write-Output '[ENVIRONMENT_GAP] Existing test venv has no Scripts\python.exe.'
            exit 2
        }
    } else {
        Write-Output '[PASS] Apply would create the missing test venv and install only requirements-test.txt.'
    }
    Write-Output '[PASS] Plan is read-only: no venv, package, database, env-file or Git change was made.'
    exit 0
}

if (-not (Test-Path -LiteralPath $venv -PathType Container)) {
    Write-Output '[INFO] Creating isolated test venv.'
    & $selection.Path @($selection.Args + @('-m', 'venv', $venv))
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed with exit code $LASTEXITCODE" }
}

$venvPython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw 'Created test venv does not contain Scripts\python.exe.'
}

Write-Output '[INFO] Installing only declared runtime and test requirements into .venv-test.'
& $venvPython '-m' 'pip' 'install' '--disable-pip-version-check' '--no-input' '-r' $requirements
if ($LASTEXITCODE -ne 0) { throw "dependency installation failed with exit code $LASTEXITCODE" }

& $venvPython '-c' "import importlib.util, sys; names=['requests','bs4','lxml','cryptography','nh3','quotequail','openai','dns','psycopg','pypdf']; missing=[name for name in names if importlib.util.find_spec(name) is None]; print('IMPORT_CHECK missing=' + (','.join(missing) if missing else 'none')); raise SystemExit(1 if missing else 0)"
if ($LASTEXITCODE -ne 0) { throw 'Declared runtime imports are incomplete.' }
Write-Output '[PASS] Test environment is ready; no global Python package was changed.'
