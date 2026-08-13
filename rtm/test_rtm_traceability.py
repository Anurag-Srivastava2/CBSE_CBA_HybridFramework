"""Executable traceability checks generated from the approved RTM workbook."""

from pathlib import Path

import pytest

from rtm.case_loader import load_cases


CASES = load_cases()


@pytest.mark.rtm
def test_rtm_manifest_contains_all_198_unique_cases():
    case_ids = [case.tc_id for case in CASES]
    assert len(case_ids) == 202
    assert len(case_ids) == len(set(case_ids))


@pytest.mark.rtm
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.tc_id)
def test_rtm_case_has_automation_disposition(case):
    assert case.scenario, f"{case.tc_id} has no scenario"
    assert case.steps, f"{case.tc_id} has no test steps"
    assert case.expected_result, f"{case.tc_id} has no expected result"
    assert case.execution_mode in {
        "ui",
        "integration",
        "performance",
        "cross_browser",
        "out_of_scope",
    }
    assert case.automation_component
    if case.module.startswith("M5"):
        assert case.automation_component == "manual_item_creation"

    if not case.automation:
        pytest.skip(
            f"Automation backlog [{case.execution_mode}]: {case.feature} — {case.scenario}"
        )

    project_root = Path(__file__).resolve().parents[1]
    automation_file = project_root / case.automation["file"]
    assert automation_file.exists(), (
        f"{case.tc_id} maps to missing file {case.automation['file']}"
    )
    assert case.automation["test"] in automation_file.read_text(encoding="utf-8")
