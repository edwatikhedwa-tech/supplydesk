[CmdletBinding()]
param(
    [string[]]$ChangedPath,
    [string]$BaseRef,
    [string]$MappingPath = 'scripts/ci/change_groups.json'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$mappingFile = [IO.Path]::GetFullPath((Join-Path $root $MappingPath))
if (-not (Test-Path -LiteralPath $mappingFile -PathType Leaf)) {
    throw "Change-group mapping is missing: $MappingPath"
}

$mapping = Get-Content -LiteralPath $mappingFile -Raw | ConvertFrom-Json
$paths = @($ChangedPath | Where-Object { $_ } | ForEach-Object { $_.Trim() -replace '\\', '/' })

if ($paths.Count -eq 0) {
    $ref = $BaseRef
    if ([string]::IsNullOrWhiteSpace($ref)) { $ref = $env:GITHUB_EVENT_BEFORE }
    if (-not [string]::IsNullOrWhiteSpace($ref) -and $ref -notmatch '^0+$') {
        $paths = @(git -C $root diff --name-only "$ref...HEAD")
    } else {
        $parent = git -C $root rev-parse 'HEAD^' 2>$null
        if ($LASTEXITCODE -eq 0) { $paths = @(git -C $root diff --name-only "$parent...HEAD") }
    }
}

$paths = @($paths | Where-Object { $_ } | ForEach-Object { $_.Trim() -replace '\\', '/' } | Sort-Object -Unique)
if ($paths.Count -eq 0) {
    $paths = @(git -C $root ls-files | ForEach-Object { $_.Trim() -replace '\\', '/' })
    $fallback = $true
} else {
    $fallback = $false
}

function Test-Group([string]$group, [string]$path) {
    foreach ($pattern in @($mapping.$group)) {
        if ($path -match [string]$pattern) { return $true }
    }
    return $false
}

$backend = $false
$frontend = $false
$browser = $false
$control = $false
$highRisk = $false
$unknownPaths = @()
foreach ($path in $paths) {
    $known = $false
    foreach ($group in @('documentation_control', 'backend', 'frontend', 'browser', 'mail', 'auth', 'database', 'api_shared_runtime', 'security', 'ci', 'dependency', 'control', 'high_risk')) {
        if (Test-Group $group $path) { $known = $true }
    }
    if (-not $known) { $unknownPaths += $path }
    if (Test-Group 'backend' $path) { $backend = $true }
    if (Test-Group 'frontend' $path) { $frontend = $true }
    if (Test-Group 'browser' $path) { $browser = $true }
    if (Test-Group 'control' $path) { $control = $true }
    if (Test-Group 'high_risk' $path) { $highRisk = $true }
}

$unknown = $unknownPaths.Count -gt 0
$docsOnly = $paths.Count -gt 0 -and -not $backend -and -not $frontend -and -not $browser -and -not $highRisk -and -not $unknown
$fullRequired = $highRisk -or $unknown
$result = [ordered]@{
    docs_only = $docsOnly.ToString().ToLowerInvariant()
    backend = $backend.ToString().ToLowerInvariant()
    frontend = $frontend.ToString().ToLowerInvariant()
    browser = $browser.ToString().ToLowerInvariant()
    high_risk = $highRisk.ToString().ToLowerInvariant()
    control = $control.ToString().ToLowerInvariant()
    unknown = $unknown.ToString().ToLowerInvariant()
    full_required = $fullRequired.ToString().ToLowerInvariant()
    changed_count = $paths.Count
    fallback_to_full_tree = $fallback.ToString().ToLowerInvariant()
}

foreach ($item in $result.GetEnumerator()) {
    $line = "$($item.Key)=$($item.Value)"
    Write-Output $line
    if ($env:GITHUB_OUTPUT) { Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value $line -Encoding utf8 }
}
if ($unknownPaths.Count -gt 0) {
    $unknownLine = 'unknown_paths=' + ($unknownPaths -join ';')
    Write-Output $unknownLine
    if ($env:GITHUB_OUTPUT) { Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value $unknownLine -Encoding utf8 }
}
