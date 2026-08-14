<#
.SYNOPSIS
    Runs the M1 Item Bank suite as four headless groups, one SME account each.

.DESCRIPTION
    All 47 collectible M1 tests are split into four groups of roughly equal
    wall-clock time (~1 h 52 m each, against ~7 h 29 m serial). Group N drives
    sme<N>@dev.com and nothing else, so the four groups can run at the same time
    without sharing an SME session or a server-side "Added Items" draft.

    Why four processes instead of `pytest -n 4`:
    conftest.pytest_collection_modifyitems turns every `serial` marker into
    xdist_group("serial"), which parks all five serial M1 modules - the 12
    typology E2Es included - on a single xdist worker. That worker alone is a
    ~6 h 24 m critical path, so xdist cannot balance this suite. Splitting by
    nodeid and pinning the account per process can.

    Account resolution this relies on:
      * The typology E2E picks its SME as CBSE_SME_USERNAMES[typology_index % 4],
        so each group takes typologies whose index is congruent to N-1 mod 4 and
        lands on its own account with no override.
      * test_smoke_m1_item_bank picks CBSE_SME_USERNAMES[slot] per check, so its
        four checks are split one per group to match (slot 0 -> group 1, ...).
      * Everything else reads CBSE_SME_USERNAME / CBSE_SME2_USERNAME, which this
        script pins per group.
    CBSE_SME_USERNAMES is deliberately left at its full four-account value.

.PARAMETER Group
    Group to run: 1-4.

.PARAMETER All
    Launch all four groups in parallel, each in its own window.

.EXAMPLE
    .\tools\run_m1_groups.ps1 -All

.EXAMPLE
    .\tools\run_m1_groups.ps1 -Group 3
#>
[CmdletBinding(DefaultParameterSetName = 'Single')]
param(
    [Parameter(ParameterSetName = 'Single', Mandatory = $true)]
    [ValidateRange(1, 4)]
    [int]$Group,

    [Parameter(ParameterSetName = 'All', Mandatory = $true)]
    [switch]$All,

    # Collect the group's tests without running them - use after editing the
    # lists below to prove every nodeid still resolves.
    [Parameter(ParameterSetName = 'Single')]
    [switch]$CollectOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

$M1 = 'tests/M1_Item_Bank_Mgmt'
$Typology = "$M1/test_e2e_sme_excel_typology_image_rwg_srrwg_revision_to_pit_publication.py::TestE2ESMEExcelTypologyImageRWGSRRWGRevisionToPITPublication::test_e2e_sme_typology_image_revision_rwg_srrwg_pit_publish"
$Creation = "$M1/test_sme_manual_item_creation.py::TestSMEManualItemCreation"
$Validation = "$M1/test_sme_manual_item_validation.py::TestSMEManualItemValidation"
$Smoke = "$M1/test_smoke_m1_item_bank.py::TestSmokeM1ItemBank"
$Queues = "$M1/test_smoke_m1_reviewer_queues.py::TestSmokeM1ReviewerQueues::test_smoke_m1_05_reviewer_opens_queue_and_assigned_item_set"
$Qar = "$M1/test_e2e_qar_need_improvement_retry_flow.py::TestE2EQARNeedImprovementRetryFlow"

# Longest test first inside each group: a group that overruns its estimate then
# overruns on a cheap tail rather than on a 27-minute typology E2E.
$groups = @{
    1 = @{
        Account = 'sme1@dev.com'
        Estimate = '1h53m'
        Tests = @(
            "$Typology[01_MCQ.xlsx-Multiple Choice Question]"
            "$Typology[05_AR.xlsx-Assertion and Reasoning]"
            "$Typology[09_FAA.xlsx-FA Activity]"
            "$Creation::test_sme_create_each_typology_manual_item_and_submit_for_qar_individually"
            "$Queues[Senior RWG]"
            "$Queues[PIT]"
            "$Smoke::test_smoke_m1_01_sme_reaches_item_creation_workspace"
            # Also slot 0, and shares check 01's xdist group so the two never
            # contend for the one session that account is allowed.
            "$Smoke::test_smoke_m1_06_my_item_set_lists_uploaded_source_files"
            "$M1/test_negative_non_xlsx_upload_rejected.py::TestNegativeNonXlsxUploadRejected::test_bug_m1_001_non_xlsx_and_bad_header_uploads_rejected_then_valid_xlsx_accepted"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[multiple-choice-question]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[fill-in-the-blank]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[match-the-following]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[true-or-false]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[very-short-answer-question]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[short-answer-question]"
            # Last on purpose: the only M1 test needing two distinct SME logins.
            # It reads CBSE_SME_USERNAMES[0] and [1], so it borrows group 2's
            # account for a few API calls. Run it here after the rest, or on its
            # own if it starts tripping over group 2's session.
            "$M1/test_sme_cross_rbac_api.py::TestSMECrossRBACAPI::test_tc_neg_m1_08_cross_sme_rbac_returns_403_forbidden"
        )
    }
    2 = @{
        Account = 'sme2@dev.com'
        Estimate = '1h52m'
        Tests = @(
            "$Typology[10_FR.xlsx-Free Response]"
            "$Typology[02_TOF.xlsx-True or False]"
            "$Typology[06_VSAQ.xlsx-Very Short Answer Question]"
            "$M1/test_manual_item_rich_content_to_pit_publication.py::TestManualItemRichContentToPITPublication::test_manual_item_rich_content_survives_to_pit_publication"
            "$Qar::test_e2e_qar_retry_path_passes_after_one_edit_and_rerun"
            "$Qar::test_e2e_qar_failure_path_stops_after_three_retries_and_stays_blocked"
            "$M1/test_qar_duplicate_detection.py::TestQARDuplicateDetection::test_qar_duplicate_detection_near_duplicate_content_flagged"
            "$Smoke::test_smoke_m1_02_manual_item_creation_stages_one_item"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[long-answer-question]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[case-based-question]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[source-based-question]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[assertion-and-reasoning]"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[fa-activity]"
        )
    }
    3 = @{
        Account = 'sme3@dev.com'
        Estimate = '1h52m'
        Tests = @(
            "$Typology[11_CABA.xlsx-Case Based Question]"
            "$Typology[03_MTF.xlsx-Match the Following]"
            "$Typology[07_SAQ.xlsx-Short Answer Question]"
            "$M1/test_e2e_sme_excel_upload_with_image_edit_to_pit_publication.py::TestE2ESMEExcelUploadWithImageEditToPITPublication::test_e2e_sme_excel_upload_with_image_edit_qar_rwg_srrwg_pit_publish"
            "$Queues[RWG]"
            "$Qar::test_e2e_qar_happy_path_routes_to_rwg_without_retry"
            "$Smoke::test_smoke_m1_03_bulk_upload_screen_accepts_a_file"
            "$M1/test_sme_bulk_upload_rbac.py::TestSMEBulkUploadRBAC::test_tc_ibmm_01a_p03_sme_sees_only_assigned_grade_subject_items"
            "$Validation::test_tc_ibmm_01b_p02_continue_locked_until_mandatory_item_complete"
            "$Validation::test_tc_ibmm_01b_p03_new_item_is_visible_in_draft_review"
            "$Validation::test_tc_ibmm_01b_n01_out_of_scope_subject_is_not_available"
            "$Validation::test_tc_ibmm_01b_n02_empty_item_content_shows_inline_error_on_blur"
        )
    }
    4 = @{
        Account = 'sme4@dev.com'
        Estimate = '1h52m'
        Tests = @(
            "$Typology[04_FITB.xlsx-Fill in the Blank]"
            "$Typology[08_LAQ.xlsx-Long Answer Question]"
            "$M1/test_e2e_pit_revision_sme_revision_correction_to_pit_publication.py::TestPITSMERevisionApproval::test_e2e_pit_revision_sme_resubmit_then_pit_approval_and_publication"
            "$Typology[12_SBQ.xlsx-Source Based Question]"
            "$Smoke::test_smoke_m1_04_excel_upload_creates_item_set"
            "$M1/test_upload_file_size_limit.py::TestUploadFileSizeLimit::test_tc_neg_m1_10_upload_file_size_limit_exceeded"
            "$Creation::test_sme_required_fields_block_empty_item_for_every_typology[free-response]"
        )
    }
}

if ($All) {
    foreach ($number in 1..4) {
        $spec = $groups[$number]
        Write-Host "Launching group $number ($($spec.Account), est. $($spec.Estimate), $($spec.Tests.Count) tests)"
        Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoExit', '-ExecutionPolicy', 'Bypass',
            '-File', $PSCommandPath, '-Group', $number
        ) -WorkingDirectory $repoRoot
    }
    Write-Host ''
    Write-Host 'Reports land in test-reports/m1_group<N>/report.html'
    return
}

$spec = $groups[$Group]

if ($CollectOnly) {
    & $python @(@('-m', 'pytest', '--collect-only', '-q', '--no-header', '-p', 'no:cacheprovider') + $spec.Tests)
    exit $LASTEXITCODE
}

$reportDir = Join-Path $repoRoot "test-reports\m1_group$Group"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

# Headless, and every SME slot pinned to this group's account.
$env:CBSE_HEADLESS = '1'
$env:CBSE_SME_USERNAME = $spec.Account
$env:CBSE_SME2_USERNAME = $spec.Account

Write-Host "M1 group $Group | $($spec.Account) | $($spec.Tests.Count) tests | est. $($spec.Estimate)"

$arguments = @('-m', 'pytest') + $spec.Tests + @(
    '--html', (Join-Path $reportDir 'report.html'),
    '--self-contained-html',
    '--alluredir', (Join-Path $reportDir 'allure-results'),
    '--durations', '0'
)

& $python @arguments
exit $LASTEXITCODE
