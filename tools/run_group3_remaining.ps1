<#
.SYNOPSIS
    Re-runs the M1 group 3 tests that failed in the 2026-08-14 headless run.

.DESCRIPTION
    Same account pinning as run_m1_groups.ps1 -Group 3 (every SME slot on
    sme3@dev.com, headless), so the reviewer-resolution fix is exercised under
    the same conditions that produced the failures. Longest test first.
#>
[CmdletBinding()]
param([switch]$CollectOnly)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

$M1 = 'tests/M1_Item_Bank_Mgmt'

$tests = @(
    "$M1/test_smoke_m1_reviewer_queues.py::TestSmokeM1ReviewerQueues::test_smoke_m1_05_reviewer_opens_queue_and_assigned_item_set[RWG]"
    "$M1/test_e2e_qar_need_improvement_retry_flow.py::TestE2EQARNeedImprovementRetryFlow::test_e2e_qar_happy_path_routes_to_rwg_without_retry"
    "$M1/test_smoke_m1_item_bank.py::TestSmokeM1ItemBank::test_smoke_m1_03_bulk_upload_screen_accepts_a_file"
    "$M1/test_sme_bulk_upload_rbac.py::TestSMEBulkUploadRBAC::test_tc_ibmm_01a_p03_sme_sees_only_assigned_grade_subject_items"
)

if ($CollectOnly) {
    & $python @(@('-m', 'pytest', '--collect-only', '-q', '--no-header', '-p', 'no:cacheprovider') + $tests)
    exit $LASTEXITCODE
}

$reportDir = Join-Path $repoRoot 'test-reports\m1_group3_remaining'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$env:CBSE_HEADLESS = '1'
$env:CBSE_SME_USERNAME = 'sme3@dev.com'
$env:CBSE_SME2_USERNAME = 'sme3@dev.com'

Write-Host "M1 group 3 remaining | sme3@dev.com | $($tests.Count) tests"

$arguments = @('-m', 'pytest') + $tests + @(
    '--html', (Join-Path $reportDir 'report.html'),
    '--self-contained-html',
    '--alluredir', (Join-Path $reportDir 'allure-results'),
    '--durations', '0'
)

& $python @arguments
exit $LASTEXITCODE
