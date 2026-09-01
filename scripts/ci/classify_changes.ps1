[CmdletBinding()]
param(
    [string[]]$ChangedPath,
    [string]$BaseRef,
    [string]$MappingPath = 'scripts/ci/change_groups.json',
    [string]$EventName = '',
    [string]$Profile = ''
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$mappingFile = [IO.Path]::GetFullPath((Join-Path $root $MappingPath))
if (-not (Test-Path -LiteralPath $mappingFile -PathType Leaf)) {
    throw "Change-group mapping is missing: $MappingPath"
}

$mapping = Get-Content -LiteralPath $mappingFile -Raw | ConvertFrom-Json
$paths = @($ChangedPath | Where-Object { $_ } | ForEach-Object { $_.Trim() -replace '\\', '/' })

if ([string]::IsNullOrWhiteSpace($EventName)) { $EventName = $env:GITHUB_EVENT_NAME }
if ([string]::IsNullOrWhiteSpace($EventName)) { $EventName = 'push' }
if ([string]::IsNullOrWhiteSpace($Profile)) { $Profile = $env:CI_PROFILE }
if ([string]::IsNullOrWhiteSpace($Profile)) { $Profile = 'FAST' }
$EventName = $EventName.ToLowerInvariant()
$Profile = $Profile.ToUpperInvariant()

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

$groups = @(
    'documentation_control', 'backend', 'frontend', 'browser', 'mail', 'auth',
    'database', 'api_shared_runtime', 'security', 'ci', 'dependency', 'control',
    'high_risk'
)
$backend = $false
$frontend = $false
$browser = $false
$browserSurface = $false
$control = $false
$highRisk = $false
$unknownPaths = @()
foreach ($path in $paths) {
    $known = $false
    foreach ($group in $groups) {
        if (Test-Group $group $path) { $known = $true }
    }
    if (-not $known) { $unknownPaths += $path }
    if (Test-Group 'backend' $path) { $backend = $true }
    if (Test-Group 'frontend' $path) { $frontend = $true }
    if (Test-Group 'browser' $path) { $browser = $true }
    if ((Test-Group 'browser' $path) -and $path -notmatch '^frontend/tests/fast-browser-smoke\.spec\.ts$') {
        $browserSurface = $true
    }
    if (Test-Group 'control' $path) { $control = $true }
    if (Test-Group 'high_risk' $path) { $highRisk = $true }
}

$unknown = $unknownPaths.Count -gt 0
$docsOnly = $paths.Count -gt 0 -and -not $backend -and -not $frontend -and -not $browser -and -not $highRisk -and -not $unknown
$fullAll = $EventName -eq 'schedule' -or ($EventName -eq 'workflow_dispatch' -and $Profile -eq 'FULL')
$pullRequest = $EventName -eq 'pull_request'
$backendFull = $fullAll -or ($backend -and ($pullRequest -or $highRisk))
$backendFast = $backend -and -not $backendFull
$frontendRequired = $fullAll -or $frontend
$browserFull = $fullAll -or (($pullRequest -or $highRisk) -and $browserSurface)
$browserSmoke = $EventName -eq 'push' -and ($frontend -or $browser) -and -not $browserFull
$doctorRequired = $fullAll -or $highRisk
$risk = if ($highRisk -or $fullAll) { 'HIGH' } elseif ($backend -or $frontend -or $browser -or $unknown) { 'NORMAL' } else { 'LOW' }
$fullRequired = $highRisk -or $unknown -or $fullAll

$requiredJobs = [System.Collections.Generic.List[string]]::new()
$skippedJobs = [System.Collections.Generic.List[string]]::new()
$requiredJobs.Add('Fast Control')
$requiredJobs.Add('Change Classification')
if ($backendFast) { $requiredJobs.Add('Backend Fast') } else { $skippedJobs.Add('Backend Fast') }
if ($backendFull) { $requiredJobs.Add('Backend Full') } else { $skippedJobs.Add('Backend Full') }
if ($frontendRequired) { $requiredJobs.Add('Frontend') } else { $skippedJobs.Add('Frontend') }
if ($browserSmoke) { $requiredJobs.Add('Browser Smoke') } else { $skippedJobs.Add('Browser Smoke') }
if ($browserFull) { $requiredJobs.Add('Browser Full') } else { $skippedJobs.Add('Browser Full') }
if ($doctorRequired) { $requiredJobs.Add('Full Control') } else { $skippedJobs.Add('Full Control') }

$result = [ordered]@{
    event_name = $EventName
    profile = $Profile
    risk = $risk
    docs_only = $docsOnly.ToString().ToLowerInvariant()
    backend = $backend.ToString().ToLowerInvariant()
    backend_fast = $backendFast.ToString().ToLowerInvariant()
    backend_full = $backendFull.ToString().ToLowerInvariant()
    frontend = $frontend.ToString().ToLowerInvariant()
    frontend_required = $frontendRequired.ToString().ToLowerInvariant()
    browser = $browser.ToString().ToLowerInvariant()
    browser_smoke = $browserSmoke.ToString().ToLowerInvariant()
    browser_full = $browserFull.ToString().ToLowerInvariant()
    high_risk = $highRisk.ToString().ToLowerInvariant()
    control = $control.ToString().ToLowerInvariant()
    doctor_required = $doctorRequired.ToString().ToLowerInvariant()
    unknown = $unknown.ToString().ToLowerInvariant()
    full_required = $fullRequired.ToString().ToLowerInvariant()
    full_all = $fullAll.ToString().ToLowerInvariant()
    changed_count = $paths.Count
    fallback_to_full_tree = $fallback.ToString().ToLowerInvariant()
    jobs_required = ($requiredJobs -join ',')
    jobs_skipped = ($skippedJobs -join ',')
}

foreach ($item in $result.GetEnumerator()) {
    $line = "$($item.Key)=$($item.Value)"
    Write-Output $line
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_OUTPUT)) {
        Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value $line -Encoding utf8
    }
}
if ($unknownPaths.Count -gt 0) {
    $unknownLine = 'unknown_paths=' + ($unknownPaths -join ';')
    Write-Output $unknownLine
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_OUTPUT)) {
        Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value $unknownLine -Encoding utf8
    }
}
