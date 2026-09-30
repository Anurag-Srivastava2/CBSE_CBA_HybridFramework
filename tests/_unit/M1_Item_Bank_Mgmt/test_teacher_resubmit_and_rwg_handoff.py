"""Unit coverage for the teacher resubmit guard and the RWG handoff wait.

Both exist because the same run failure - "not visible in any configured RWG
queue" - had two causes that the test could not tell apart: a resubmit control
that was never clicked, and a queue sweep that raced the QAR-to-RWG handoff.
The first is now a failure at the point it happens, the second is waited out
before the sweep begins, so that message means what it says.
"""
import pytest
from selenium.webdriver.common.by import By

from tests.M1_Item_Bank_Mgmt.test_e2e_teacher_excel_triple_revision_rejection_to_pit_publication import (  # noqa: E501
    TestE2ETeacherExcelTripleRevisionRejectionToPITPublication as Teacher,
)


class FakeUploadPage:
    def __init__(self, rerun_message="Teacher resubmitted the revised set for review.",
                 assignees=(), statuses=None):
        self.rerun_message = rerun_message
        self.assignees = list(assignees)
        self.statuses = statuses or {}
        self.opens = 0

    def rerun_qar_if_enabled(self):
        return self.rerun_message

    def open_item_set_url_and_wait(self, _url, _item_set_id):
        self.opens += 1

    def get_item_set_assignee(self, _role):
        return self.assignees.pop(0) if self.assignees else ""

    def get_item_set_status_summary(self):
        return self.statuses


class FakeBody:
    def __init__(self, text):
        self.text = text


class FakeDriver:
    def __init__(self, text):
        self.body = FakeBody(text)

    def find_element(self, by, value):
        assert (by, value) == (By.TAG_NAME, "body")
        return self.body


def build_runner(page_text, monkeypatch=None):
    runner = Teacher.__new__(Teacher)
    runner.driver = FakeDriver(page_text)
    if monkeypatch is not None:
        # The wait paces itself with sleep(15); the poll sequence is what is
        # under test, not the pacing, so it runs without the wall clock.
        monkeypatch.setattr(
            "tests.M1_Item_Bank_Mgmt."
            "test_e2e_teacher_excel_triple_revision_rejection_to_pit_publication"
            ".sleep",
            lambda _seconds: None,
        )
    return runner


class TestResubmitGuard:
    @pytest.mark.parametrize(
        "message",
        ["Re-run QAR button found but disabled.", "Re-run QAR button not available."],
    )
    def test_an_unclicked_resubmit_fails_here_not_at_the_rwg_queue(
        self, message, record_property
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Resubmit a revised set when the resubmit control is disabled or "
            "missing.\n"
            "Check it fails right there, naming the control, instead of passing and "
            "failing later as a reviewer-queue problem.",
        )
        page = FakeUploadPage(rerun_message=message)

        with pytest.raises(AssertionError, match="never resubmitted"):
            Teacher.resubmit_revised_item_set(page, "IS1405-G1-Mathematics-Ch29", 1)

    def test_a_real_resubmit_is_passed_through(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Resubmit a revised set when the control works.\n"
            "Check the reported message is passed through unchanged for the report.",
        )
        page = FakeUploadPage()

        assert Teacher.resubmit_revised_item_set(
            page, "IS1405-G1-Mathematics-Ch29", 1
        ) == "Teacher resubmitted the revised set for review."


class TestRWGHandoffWait:
    def test_an_assignee_that_appears_late_is_returned(self, monkeypatch, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Wait for a resubmitted set whose reviewer is not assigned yet, then is.\n"
            "Check the set page is re-fetched until the reviewer appears, and that "
            "reviewer is returned.",
        )
        runner = build_runner("Item Set Status\nPENDING_QAR", monkeypatch)
        # First read: no assignee yet. Second: the handoff has happened.
        page = FakeUploadPage(assignees=["", "rwg2"])

        assert runner.wait_for_rwg_handoff(
            page, "IS1405-G1-Mathematics-Ch29", "http://set", 1, timeout=120
        ) == "rwg2"
        assert page.opens == 2

    def test_waiting_stops_once_the_set_has_left_qar(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Wait on a set that has left QAR but shows no reviewer label.\n"
            "Check the wait ends immediately rather than burning its whole window, "
            "because the queue sweep can find the reviewer from here.",
        )
        runner = build_runner("Item Set Status\nUnder Review")
        page = FakeUploadPage(assignees=[""])

        assert runner.wait_for_rwg_handoff(
            page, "IS1405-G1-Mathematics-Ch29", "http://set", 1, timeout=600
        ) == ""
        assert page.opens == 1

    def test_a_set_stuck_in_qar_is_not_fatal_on_its_own(self, monkeypatch, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Wait on a set that never leaves QAR at all.\n"
            "Check the wait gives up quietly and lets the queue sweep report the "
            "outcome, so an unrendered reviewer label alone cannot fail the run.",
        )
        runner = build_runner("Item Set Status\nPENDING_QAR")
        page = FakeUploadPage(assignees=[])

        assert runner.wait_for_rwg_handoff(
            page, "IS1405-G1-Mathematics-Ch29", "http://set", 2, timeout=0.1
        ) == ""


def test_pending_qar_counts_as_a_qar_stage_but_under_review_does_not(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Look at the wording that means a set is still inside QAR.\n"
        "Check it covers PENDING_QAR and excludes the post-QAR review states, so "
        "the wait ends when the set actually moves on.",
    )
    markers = Teacher.QAR_STAGE_MARKERS

    assert any("pending_qar" == marker for marker in markers)
    assert not any("under review" in marker or "rwg" in marker for marker in markers)


class TestUnrevisedItemsAreNamed:
    """"Revise" and "Revised" differ by two characters and mean opposites."""

    def test_the_pending_badge_is_not_read_as_the_done_badge(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Read a set where some items are revised and one still says Revise.\n"
            "Check only the unrevised one is reported, so a half-edited set is "
            "not mistaken for a finished one.",
        )
        page = FakeUploadPage()
        page.get_qar_item_statuses = lambda _set_id: {
            "IS1476-G1-Mathematics-Ch29-i1": "Revised",
            "IS1476-G1-Mathematics-Ch29-i2": "Revised",
            "IS1476-G1-Mathematics-Ch29-i3": "Revise",
            "IS1476-G1-Mathematics-Ch29-i4": "Revised",
            "IS1476-G1-Mathematics-Ch29-i5": "Approved",
        }

        assert Teacher.unrevised_items(page, "IS1476-G1-Mathematics-Ch29") == {
            "IS1476-G1-Mathematics-Ch29-i3": "Revise"
        }

    def test_a_fully_revised_set_reports_nothing_outstanding(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Read a set where every flagged item is revised.\n"
            "Check nothing is reported outstanding, so the blame lands on the "
            "resubmit control rather than on the revisions.",
        )
        page = FakeUploadPage()
        page.get_qar_item_statuses = lambda _set_id: {
            "IS1476-G1-Mathematics-Ch29-i1": "Revised",
            "IS1476-G1-Mathematics-Ch29-i2": "Approved",
        }

        assert Teacher.unrevised_items(page, "IS1476-G1-Mathematics-Ch29") == {}

    def test_an_unreadable_set_does_not_invent_outstanding_items(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Read a set whose statuses cannot be read at all.\n"
            "Check nothing is claimed either way, so an unreadable page is not "
            "reported as a half-edited one.",
        )
        page = FakeUploadPage()

        def boom(_set_id):
            raise RuntimeError("detail page not loaded")

        page.get_qar_item_statuses = boom

        assert Teacher.unrevised_items(page, "IS1476-G1-Mathematics-Ch29") == {}


class TestResubmitGuardNamesTheRealCause:
    def test_an_incomplete_revision_is_blamed_on_the_save(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Try to resubmit a set that still has an unrevised item.\n"
            "Check the failure blames the revision save and names the item, not "
            "the resubmit control and not reviewer routing.",
        )
        page = FakeUploadPage(
            rerun_message=(
                "Resubmit set for review is on screen but disabled - the set "
                "still has items awaiting revision."
            )
        )
        page.get_qar_item_statuses = lambda _set_id: {
            "IS1476-G1-Mathematics-Ch29-i3": "Revise",
        }

        with pytest.raises(AssertionError, match="still awaiting revision") as failure:
            Teacher.resubmit_revised_item_set(page, "IS1476-G1-Mathematics-Ch29", 1)
        assert "IS1476-G1-Mathematics-Ch29-i3" in str(failure.value)
        assert "not RWG routing" in str(failure.value)

    def test_a_fully_revised_set_blames_the_control(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Try to resubmit a set where everything is revised but the control "
            "is missing.\n"
            "Check the failure blames the control, since the revisions are not "
            "at fault.",
        )
        page = FakeUploadPage(rerun_message="Re-run QAR button not available.")
        page.get_qar_item_statuses = lambda _set_id: {
            "IS1476-G1-Mathematics-Ch29-i1": "Revised",
        }

        with pytest.raises(AssertionError, match="control itself is the problem"):
            Teacher.resubmit_revised_item_set(page, "IS1476-G1-Mathematics-Ch29", 1)
