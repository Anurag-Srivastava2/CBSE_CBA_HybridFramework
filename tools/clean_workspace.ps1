<#
.SYNOPSIS
    Clears the generated run output that accumulates in the framework workspace.

.DESCRIPTION
    Every run writes screenshots, an Extent/Allure report tree and temporary upload
    workbooks. None of it is tracked by git, and none of it is read back by a later
    run, so it only ever grows. This script removes it while preserving:

      - the .gitkeep sentinels that keep logs/, reports/ and screenshots/ in git
      - the tracked fixtures under data/ and test_images/
      - any run output newer than -KeepDays

    Extent reports embed their screenshots as base64 data URIs, so clearing
    screenshots/ never breaks a report you are keeping.

.PARAMETER KeepDays
    Keep run output modified within this many days. Default 1. Use 0 to keep none.

.PARAMETER DryRun
    List what would be removed without deleting anything.

.EXAMPLE
    tools\clean_workspace.ps1 -DryRun
    tools\clean_workspace.ps1 -KeepDays 7
#>
[CmdletBinding()]
param(
    [int]$KeepDays = 1,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
# Restore the caller's directory even if an unhandled error aborts the run.
trap { Pop-Location; break }

# Directories whose entire contents are disposable. A trailing .gitkeep is kept so
# the directory survives in git.
$wipeContents = @('screenshots', 'reports', 'test-reports', 'logs')

# Directories removed outright, then recreated empty where test code writes into them.
$wipeWhole   = @('artifacts', 'tmp', 'tmp_uploads', 'output', 'outputs', 'allure-results')
$recreate    = @('artifacts', 'tmp_uploads', 'output')

# Loose regenerable files at the repo root. item_bank_workbook_builder.py rebuilds
# the large workbook from the template named by CBSE_UPLOAD_ITEM_FILE.
$looseGlobs  = @('test_large.xlsx', 'scratch_*.xlsx', 'sme_sheet*.xlsx', 'test-images*.zip', '*_console.log')

$cutoff  = (Get-Date).AddDays(-$KeepDays)
$targets = [System.Collections.ArrayList]::new()

function Add-Target($item, $reason) {
    # An empty directory measures to $null rather than 0, so coalesce before dividing.
    $size = if ($item.PSIsContainer) {
        (Get-ChildItem $item.FullName -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
    } else { $item.Length }
    if ($null -eq $size) { $size = 0 }
    [void]$targets.Add([PSCustomObject]@{
        Path   = $item.FullName.Replace("$root\", '')
        MB     = [math]::Round($size / 1MB, 2)
        Reason = $reason
    })
}

foreach ($dir in $wipeContents) {
    if (-not (Test-Path $dir)) { continue }
    Get-ChildItem $dir -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne '.gitkeep' -and $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { Add-Target $_ "$dir output" }
}

foreach ($dir in $wipeWhole) {
    if (Test-Path $dir) {
        $item = Get-Item $dir -Force
        if ($item.LastWriteTime -lt $cutoff) { Add-Target $item 'run output' }
    }
}

foreach ($glob in $looseGlobs) {
    Get-ChildItem $glob -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { Add-Target $_ 'regenerable fixture' }
}

Get-ChildItem $root -Recurse -Directory -Force -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike '*\.venv\*' -and $_.FullName -notlike '*\.git\*' } |
    ForEach-Object { Add-Target $_ 'python cache' }

if (Test-Path '.pytest_cache') { Add-Target (Get-Item '.pytest_cache' -Force) 'pytest cache' }

if ($targets.Count -eq 0) {
    Write-Host "Workspace is already clean (keeping output newer than $KeepDays day(s))." -ForegroundColor Green
    Pop-Location
    exit 0
}

$totalMb = [math]::Round((($targets | Measure-Object -Property MB -Sum).Sum), 1)
$targets | Sort-Object MB -Descending | Select-Object -First 25 | Format-Table -AutoSize

if ($targets.Count -gt 25) {
    Write-Host "... and $($targets.Count - 25) more paths" -ForegroundColor DarkGray
}

if ($DryRun) {
    Write-Host "`nDRY RUN: $($targets.Count) paths / $totalMb MB would be removed." -ForegroundColor Yellow
    Pop-Location
    exit 0
}

$failed = 0
foreach ($t in $targets) {
    try {
        Remove-Item -LiteralPath (Join-Path $root $t.Path) -Recurse -Force -Confirm:$false -ErrorAction Stop
    } catch {
        Write-Host "FAILED $($t.Path): $($_.Exception.Message)" -ForegroundColor Red
        $failed++
    }
}

foreach ($dir in $recreate) {
    if (-not (Test-Path $dir)) { [void](New-Item -ItemType Directory -Path $dir) }
}

$colour = if ($failed) { 'Yellow' } else { 'Green' }
Write-Host "`nRemoved $($targets.Count - $failed)/$($targets.Count) paths, reclaimed ~$totalMb MB." -ForegroundColor $colour
Pop-Location
