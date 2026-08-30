param(
    [switch]$Plan,
    [switch]$DryRun,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if ($Apply) {
    throw "This test runner has no apply mode; the standalone pilot does not mutate the current system."
}
if ($Plan) {
    & python -m supplier_discovery_v2.run --plan --key "кабель ВВГнг 3х2.5"
    exit $LASTEXITCODE
}
if ($DryRun) {
    & python -m supplier_discovery_v2.run --dry-run --key "кабель ВВГнг 3х2.5"
    exit $LASTEXITCODE
}
& python -m unittest discover -s (Join-Path $root "supplier_discovery_v2\tests") -p "test*.py" -v
exit $LASTEXITCODE
