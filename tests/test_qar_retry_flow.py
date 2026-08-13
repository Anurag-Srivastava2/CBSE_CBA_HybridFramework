from collections import deque

import pytest

from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.qar.qar_report_page import QARReportPage
from utilities.qar_retry_flow import run_qar_need_improvement_retry_loop


class FakeQARWorkflow:
    def __init__(self, statuses_by_run):
        self.statuses_by_run = deque(tuple(statuses) for statuses in statuses_by_run)
        self.current_statuses = self.statuses_by_run.popleft()
        self.corrected = []
        self.reruns = []
        self.blocked_checks = []
        self.routed_checks = []

    def get_failed(self):
        return self.current_statuses

    def correct(self, item_ids, retry_number):
        self.corrected.append((retry_number, tuple(item_ids)))
        return item_ids

    def rerun(self, retry_number):
        self.reruns.append(retry_number)
        self.current_statuses = self.statuses_by_run.popleft()
        return f"QAR rerun {retry_number} completed"

    def assert_blocked(self, item_set_id, item_ids):
        self.blocked_checks.append((item_set_id, tuple(item_ids)))

    def assert_routed(self, item_set_id):
        self.routed_checks.append(item_set_id)

    def run(self, max_retries=3):
        return run_qar_need_improvement_retry_loop(
            item_set_id="IS-QAR-RETRY",
            get_need_improvement_item_ids=self.get_failed,
            correct_items=self.correct,
            rerun_qar=self.rerun,
            assert_blocked_from_rwg=self.assert_blocked,
            assert_routed_to_rwg=self.assert_routed,
            max_retries=max_retries,
        )


def test_happy_path_routes_to_rwg_without_edit_or_rerun():
    workflow = FakeQARWorkflow([[]])

    result = workflow.run()

    assert result.retry_count == 0
    assert workflow.corrected == []
    assert workflow.reruns == []
    assert workflow.blocked_checks == []
    assert workflow.routed_checks == ["IS-QAR-RETRY"]


def test_retry_path_asserts_blocked_then_passes_after_one_edit_and_rerun():
    workflow = FakeQARWorkflow([["item-1"], []])

    result = workflow.run()

    assert result.retry_count == 1
    assert workflow.corrected == [(1, ("item-1",))]
    assert workflow.reruns == [1]
    assert workflow.blocked_checks == [("IS-QAR-RETRY", ("item-1",))]
    assert workflow.routed_checks == ["IS-QAR-RETRY"]


def test_failure_path_stops_after_three_retries_and_reports_remaining_items():
    workflow = FakeQARWorkflow(
        [["item-1"], ["item-1"], ["item-1"], ["item-1"]]
    )

    with pytest.raises(
        AssertionError,
        match=r"Item item-1 still 'Need Improvement' after 3 retries",
    ):
        workflow.run(max_retries=3)

    assert workflow.reruns == [1, 2, 3]
    assert len(workflow.blocked_checks) == 4
    assert workflow.routed_checks == []


def test_retry_loop_fails_before_rerun_when_a_failed_item_was_not_edited():
    workflow = FakeQARWorkflow([["item-1", "item-2"], []])
    workflow.correct = lambda item_ids, retry_number: ("item-1",)

    with pytest.raises(
        AssertionError,
        match="could not edit every Need Improvement item.*item-2",
    ):
        workflow.run()

    assert workflow.reruns == []


def test_retry_loop_rejects_an_unbounded_zero_retry_configuration():
    workflow = FakeQARWorkflow([[]])

    with pytest.raises(ValueError, match="max_retries must be at least 1"):
        workflow.run(max_retries=0)


def test_retry_loop_deduplicates_item_ids_case_insensitively():
    workflow = FakeQARWorkflow([["ITEM-1", "item-1", None], []])

    result = workflow.run()

    assert result.revised_item_ids_by_retry == (("ITEM-1",),)


def test_page_status_map_recognizes_need_improvement_aliases():
    class StatusDriver:
        @staticmethod
        def execute_script(script):
            return [
                ["item-1", "Need Improvement"],
                ["item-2", "Needs Improvement"],
                ["item-3", "Needs Revision"],
                ["item-4", "Pending"],
            ]

    page = UploadItemFilePage(StatusDriver())

    assert page.get_qar_item_statuses() == {
        "item-1": "Need Improvement",
        "item-2": "Needs Improvement",
        "item-3": "Needs Revision",
        "item-4": "Pending",
    }
    assert page.get_qar_need_improvement_item_ids() == [
        "item-1",
        "item-2",
        "item-3",
    ]


@pytest.mark.parametrize("status", ["Need Improvement", "Needs Improvement"])
def test_qar_report_fallback_extracts_need_improvement_status(status):
    class Body:
        text = f"IS-RETRY-i1 {status}"

    class ReportDriver:
        @staticmethod
        def execute_script(script, item_id):
            return ""

        @staticmethod
        def find_element(by, value):
            return Body()

    report = QARReportPage(ReportDriver())

    assert report.get_item_status("IS-RETRY-i1") == status


def test_page_revision_adapter_opens_and_corrects_every_flagged_item():
    class ImmediateWait:
        @staticmethod
        def until_condition(condition, timeout=None):
            assert condition(None)
            return True

    class RevisionPage(UploadItemFilePage):
        def __init__(self):
            self.wait_utils = ImmediateWait()
            self.remaining_labels = ["IS-RETRY-i1", "IS-RETRY-i2"]
            self.edits = []

        @staticmethod
        def is_item_set_detail_loading(driver):
            return False

        def get_revision_item_targets(self):
            return [(object(), label) for label in self.remaining_labels]

        def click_first_revision_item(self):
            return self.remaining_labels.pop(0)

        def edit_open_revision_item(
            self,
            item_id,
            revised_question=None,
            revision_note=None,
        ):
            self.edits.append((item_id, revised_question, revision_note))
            return revised_question

    page = RevisionPage()

    revised = page.revise_qar_need_improvement_items(
        "IS-RETRY",
        ("IS-RETRY-i1", "IS-RETRY-i2"),
        lambda item_id, retry: {
            "question": f"Valid correction for {item_id} on retry {retry}",
            "revision_note": f"Corrected on retry {retry}",
        },
        retry_number=1,
    )

    assert revised == ["IS-RETRY-i1", "IS-RETRY-i2"]
    assert page.edits == [
        (
            "IS-RETRY-i1",
            "Valid correction for IS-RETRY-i1 on retry 1",
            "Corrected on retry 1",
        ),
        (
            "IS-RETRY-i2",
            "Valid correction for IS-RETRY-i2 on retry 1",
            "Corrected on retry 1",
        ),
    ]


def test_page_revision_adapter_passes_qar_report_feedback_to_correction(
    monkeypatch,
):
    class ImmediateWait:
        @staticmethod
        def until_condition(condition, timeout=None):
            assert condition(None)
            return True

    class FeedbackReport:
        def __init__(self, _driver):
            pass

        @staticmethod
        def inspect_item_feedback(item_id):
            return {
                "status": "Need Improvement",
                "score": 42.0,
                "failure_reasons": {
                    "Clarity": f"{item_id} wording was ambiguous",
                },
            }

    class RevisionPage(UploadItemFilePage):
        def __init__(self):
            self.driver = object()
            self.wait_utils = ImmediateWait()
            self.remaining_labels = ["IS-REPORT-i1"]
            self.edits = []

        @staticmethod
        def is_item_set_detail_loading(driver):
            return False

        def get_revision_item_targets(self):
            return [(object(), label) for label in self.remaining_labels]

        def click_first_revision_item(self):
            return self.remaining_labels.pop(0)

        def edit_open_revision_item(
            self,
            item_id,
            revised_question=None,
            revision_note=None,
        ):
            self.edits.append((item_id, revised_question, revision_note))

    monkeypatch.setattr(
        "pages.sme.upload_item_file_page.QARReportPage",
        FeedbackReport,
    )
    captured_feedback = []
    page = RevisionPage()

    page.revise_qar_need_improvement_items(
        "IS-REPORT",
        ("IS-REPORT-i1",),
        lambda item_id, retry, feedback: (
            captured_feedback.append(feedback)
            or {
                "question": f"Clear correction for {item_id}",
                "revision_note": f"Corrected on retry {retry}.",
            }
        ),
        retry_number=1,
    )

    assert captured_feedback[0]["failure_reasons"] == {
        "Clarity": "IS-REPORT-i1 wording was ambiguous",
    }
    assert "status=Need Improvement" in page.edits[0][2]
    assert "score=42.0%" in page.edits[0][2]
    assert "Clarity" in page.edits[0][2]
