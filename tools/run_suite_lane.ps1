<#
.SYNOPSIS
    Runs one lane of the full-suite run, headless, with its own accounts and
    its own report directory.

.DESCRIPTION
    The suite cannot be run as a single `pytest -n 8`: conftest turns every
    `serial` marker into xdist_group("serial"), parking all 35 serial tests on
    one worker (~6h24m critical path). Splitting into independent processes,
    each pinned to its own accounts, is what makes the wall clock tractable -
    the same reasoning as tools/run_m1_groups.ps1, extended past M1.

    M1 itself is NOT a lane here; run it with tools/run_m1_groups.ps1 -All,
    unchanged. This script covers everything else.

    Lanes:
      m2            M2 Web Portal Admin (77). Admin-pool bound - see -Workers.
      unit-browser  The tests/_unit files that drive a browser (38). Must run
                    AFTER the M1 groups: it needs the old SME accounts, which
                    those groups hold, and cannot be moved onto the new
                    @test.com ones - see the lane's comment below.
      logic         The pure-logic tests (70). No browser, finishes in ~2m.
      m5            M5 Teacher Contribution (19).
      m34           M3 Item Testing + M4 QP Creation (6).

    The _unit split is computed by inspection (a file is a browser test if it
    uses the `setup` fixture), so adding a file to tests/_unit lands in the
    right lane without editing this script.

.PARAMETER Lane
    Which lane to run.

.PARAMETER Workers
    xdist worker count for this lane. Defaults per lane. Note that account
    pools cap real parallelism: utilities/read_config.py resolves accounts as
    pool[worker_index % len(pool)], so more workers than accounts means two
    workers sign each other out. The admin pool is 2 unless more are created.

.EXAMPLE
    .\tools\run_suite_lane.ps1 -Lane m2 -Workers 2

.EXAMPLE
    .\tools\run_suite_lane.ps1 -Lane unit-browser
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('m2', 'unit-browser', 'logic', 'm5', 'm34')]
    [string]$Lane,

    [int]$Workers = 0,

    # Collect without running - proves the lane's paths and env still resolve.
    [switch]$CollectOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }


# tests/_unit holds both browser and pure-logic tests. Split them by whether
# the file uses the browser `setup` fixture rather than by name.
$unitFiles = Get-ChildItem -Path (Join-Path $repoRoot 'tests\_unit') -Filter 'test_*.py' -Recurse
$unitBrowser = @()
$unitLogic = @()
foreach ($file in $unitFiles) {
    if (Select-String -Path $file.FullName -Pattern 'usefixtures\("setup"\)' -Quiet) {
        $unitBrowser += (Resolve-Path -Relative $file.FullName)
    } else {
        $unitLogic += (Resolve-Path -Relative $file.FullName)
    }
}

$lanes = @{
    'm2' = @{
        Paths = @('tests/M2_Web_Portal_Admin')
        # Capped by the admin pool (2 today). Raise only after more admins exist.
        Workers = 2
        Env = @{}
    }
    'unit-browser' = @{
        Paths = $unitBrowser
        Workers = 2
        # Deliberately no account overrides. These files pair a resolved
        # username with a hardcoded ReadConfig.get_all_users_password(), so
        # pointing them at the new @test.com accounts signs in with the wrong
        # password and every test dies waiting on the login form. They must run
        # on the accounts the shared password actually belongs to - which means
        # AFTER the M1 groups finish, since those hold all four old SMEs.
        Env = @{}
    }
    'logic' = @{
        Paths = $unitLogic + @('tests/test_qar_retry_flow.py', 'tests/test_manual_typology_coverage.py')
        Workers = 2
        Env = @{}
    }
    'm5' = @{
        Paths = @('tests/M5_Teacher_Contribution')
        Workers = 2
        # No teacher-pool extension: these files hardcode
        # get_all_users_password(), so a new @test.com teacher would sign in
        # with the wrong password. Old pool of 5 is ample for -n 2.
        Env = @{}
    }
    'm34' = @{
        Paths = @('tests/M3_Item_Testing', 'tests/M4_QP_Creation')
        Workers = 2
        # No teacher-pool extension: these files hardcode
        # get_all_users_password(), so a new @test.com teacher would sign in
        # with the wrong password. Old pool of 5 is ample for -n 2.
        Env = @{}
    }
}

$spec = $lanes[$Lane]
if ($Workers -gt 0) { $spec.Workers = $Workers }

$reportDir = Join-Path $repoRoot "test-reports\$Lane"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$env:CBSE_HEADLESS = '1'
# Without this each lane overwrites the others' reports - conftest.get_reports_dir
# reads it and falls back to a single shared ./reports otherwise.
$env:PYTEST_REPORTS_DIR = $reportDir
foreach ($name in $spec.Env.Keys) {
    Set-Item -Path "env:$name" -Value $spec.Env[$name]
}

$arguments = @('-m', 'pytest') + $spec.Paths + @(
    '-n', $spec.Workers,
    '--dist', 'loadgroup',
    # Untracked scratch dirs that otherwise contribute 9 collected tests.
    '--ignore=tests/_tmp_verify',
    '--ignore=tests/_tmp_report_check',
    '--html', (Join-Path $reportDir 'report.html'),
    '--self-contained-html',
    '--alluredir', (Join-Path $reportDir 'allure-results'),
    '--durations', '0'
)

if ($CollectOnly) {
    & $python @(@('-m', 'pytest', '--collect-only', '-q', '--no-header', '-p', 'no:cacheprovider') + $spec.Paths)
    exit $LASTEXITCODE
}

Write-Host "Lane $Lane | $($spec.Paths.Count) path(s) | -n $($spec.Workers) | reports -> $reportDir"
& $python @arguments
exit $LASTEXITCODE
