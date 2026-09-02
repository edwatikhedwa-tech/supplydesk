[CmdletBinding()]
param(
    [string]$ExpectedRoot
)

$ErrorActionPreference = 'Stop'
$defaultRoot = 'C:\Users\edwat\SupplyDesk'
$runningOnWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
$hasExplicitExpectedRoot = $PSBoundParameters.ContainsKey('ExpectedRoot')

function Normalize-WorkspacePath([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        throw 'Workspace path is empty.'
    }
    if (-not [IO.Path]::IsPathRooted($PathValue)) {
        throw "Workspace path must be absolute: $PathValue"
    }
    $fullPath = [IO.Path]::GetFullPath($PathValue)
    $pathRoot = [IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.Length -gt $pathRoot.Length) {
        $fullPath = $fullPath.TrimEnd([char]'\', [char]'/')
    }
    return $fullPath
}

$gitOutput = & git rev-parse --show-toplevel 2>$null
$gitExitCode = $LASTEXITCODE
$rawGitRoot = ($gitOutput | Select-Object -First 1)
if ($gitExitCode -ne 0 -or [string]::IsNullOrWhiteSpace([string]$rawGitRoot)) {
    Write-Output 'WORKSPACE_GUARD: FAIL'
    Write-Output 'ERROR: current directory is not inside a readable Git checkout.'
    exit 2
}

$actualRoot = Normalize-WorkspacePath ([string]$rawGitRoot).Trim()
$expectedInput = if ($hasExplicitExpectedRoot) { $ExpectedRoot } else { $defaultRoot }

if (-not $hasExplicitExpectedRoot -and -not $runningOnWindows) {
    Write-Output 'BLOCKED_WRONG_WORKSPACE'
    Write-Output "EXPECTED_ROOT: $defaultRoot"
    Write-Output "ACTUAL_ROOT: $actualRoot"
    exit 1
}

try {
    $expectedRoot = Normalize-WorkspacePath $expectedInput
} catch {
    Write-Output 'WORKSPACE_GUARD: FAIL'
    Write-Output "ERROR: $($_.Exception.Message)"
    exit 2
}

$comparison = if ($runningOnWindows) {
    [StringComparer]::OrdinalIgnoreCase
} else {
    [StringComparer]::Ordinal
}

if ($comparison.Equals($actualRoot, $expectedRoot)) {
    Write-Output 'WORKSPACE_GUARD: PASS'
    exit 0
}

Write-Output 'BLOCKED_WRONG_WORKSPACE'
Write-Output "EXPECTED_ROOT: $expectedRoot"
Write-Output "ACTUAL_ROOT: $actualRoot"
exit 1
