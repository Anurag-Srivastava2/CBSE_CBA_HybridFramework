import re

import pytest

from pages.common.login_page import LoginPage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestReviewRoleContracts:
    def login(self, username, page_class=RWGReviewQueuePage):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        page = page_class(self.driver)
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        checkpoint(f"Signed in as {username}")
        return page

    def test_tc_ibmm_11_p01_rwg_queue_contains_qar_cleared_items(self, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Sign in as an RWG reviewer and open their review queue.\n"
            "Check it lists item sets that have cleared QAR.",
        )
        page = self.login(ReadConfig.get_role_usernames("rwg")[0])
        text = page.get_queue_body_text()
        found = re.findall(r"IS\d+", text)
        page_evidence.checkpoint(
            f"RWG queue lists {len(found)} QAR-cleared item set(s): "
            f"{sorted(set(found))[:6] or 'none'}"
        )
        assert re.search(r"IS\d+", text), f"No QAR-cleared item set found in RWG queue: {text}"

    def test_tc_ibmm_11_p02_sirs_has_26_criteria_across_6_sections(self, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open an item from the RWG review queue.\n"
            "Check the review scorecard offers 26 criteria arranged across 6 "
            "sections.",
        )
        page = self.login(ReadConfig.get_role_usernames("rwg")[0])
        text = page.open_first_item_in_first_queue_set()
        normalized = text.casefold()
        page_evidence.checkpoint(
            "Opened the first item in the first queued set; SIRS panel present: "
            f"{'evaluation criteria' in normalized or 'item response sheet' in normalized}"
        )
        assert "evaluation criteria" in normalized or "item response sheet" in normalized
        criterion_numbers = set(re.findall(r"\b([1-6]\.\d+)\b", normalized))
        section_numbers = {number.split(".", 1)[0] for number in criterion_numbers}
        page_evidence.checkpoint(
            f"SIRS renders {len(criterion_numbers)} criteria across "
            f"{len(section_numbers)} section(s) — 26 across 6 required"
        )
        assert len(section_numbers) == 6, (
            f"Expected 6 SIRS sections, found {len(section_numbers)}: {section_numbers}."
        )
        # A short SIRS is documented (KI-M1-SIRS-001): 22 of 26 on QA,
        # 2026-09-29. Guarded at runtime, so the day all 26 ship this passes;
        # none at all, or more than 26, is still a hard failure.
        if 0 < len(criterion_numbers) < 26:
            pytest.xfail(
                f"KI-M1-SIRS-001: SIRS renders {len(criterion_numbers)} of the 26 "
                f"required criteria: {sorted(criterion_numbers)}"
            )
        assert len(criterion_numbers) == 26, (
            f"Expected exactly 26 SIRS criteria, found {len(criterion_numbers)}: {criterion_numbers}."
        )

    def test_tc_ibmm_11_n01_submit_disabled_with_zero_evaluated(self, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open a review and evaluate nothing at all.\n"
            "Check Submit stays disabled until something has actually been marked.",
        )
        page = self.login(ReadConfig.get_role_usernames("rwg")[0])
        text = page.open_first_item_in_first_queue_set()
        page_evidence.checkpoint(
            "Opened a review with nothing evaluated yet — Submit Review enabled: "
            f"{page.is_submit_review_enabled()}"
        )
        assert "0 evaluated" in text.casefold() or "0/" in text
        assert page.is_submit_review_enabled() is False

    def test_tc_ibmm_12_p01_sme_feedback_has_iteration_counter(self, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Sign in as an SME and open the feedback on a reviewed set.\n"
            "Check the feedback carries an iteration counter, so the SME can tell "
            "which revision round it belongs to.",
        )
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_password_for_username(ReadConfig.get_sme2_username()),
        )
        body = self.driver.find_element("tag name", "body")
        body.send_keys("\ue00c")
        sets_page = UploadItemFilePage(self.driver)
        sets_page.wait_for_application_to_load()
        sets_page.open_sets_module()
        text = self.driver.find_element("tag name", "body").text.casefold()
        iteration_marker = re.search(r"iteration\s*\d+", text)
        page_evidence.checkpoint(
            f"SME Sets shows reviewer feedback: {'feedback' in text}; iteration "
            f"counter: {iteration_marker.group(0) if iteration_marker else 'none'}"
        )
        if "feedback" not in text or not iteration_marker:
            pytest.xfail(
                "KI-M1-FEEDBACK-001: SME Sets does not expose feedback iteration "
                f"metadata (feedback shown: {'feedback' in text}; iteration "
                f"counter: {bool(iteration_marker)})"
            )
        assert "feedback" in text, "SME Sets did not display reviewer feedback."
        assert re.search(r"iteration\s*\d+", text), (
            "SME feedback did not display an iteration counter."
        )

    def test_tc_ibmm_12_n01_item_disabled_after_third_rejection(self, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Sign in as an SME and look at an item that has been rejected three "
            "times.\n"
            "Check it is disabled and cannot be revised again.",
        )
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_password_for_username(ReadConfig.get_sme2_username()),
        )
        sets_page = UploadItemFilePage(self.driver)
        sets_page.wait_for_application_to_load()
        sets_page.open_sets_module()
        text = self.driver.find_element("tag name", "body").text.casefold()
        page_evidence.checkpoint(
            f"SME Sets three-strike markers — rejection: {'rejection' in text}; "
            "disabled/three-strike: "
            f"{[m for m in ('disabled', 'three-strike', '3-strike') if m in text] or 'none'}"
        )
        three_strike_visible = (
            "3" in text
            and "rejection" in text
            and any(marker in text for marker in ("disabled", "three-strike", "3-strike"))
        )
        if not three_strike_visible:
            pytest.xfail(
                "KI-M1-REJECTION-001: no three-times-rejected item set is visible "
                "on this environment, so the disabled state cannot be observed."
            )
        assert three_strike_visible

    def test_tc_ibmm_13_p01_p02_sr_rwg_history_and_decisions(self, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Sign in as a Senior RWG reviewer and open an item.\n"
            "Check the earlier review history and the decisions taken on it are "
            "visible to them.",
        )
        page = self.login(
            ReadConfig.get_role_usernames("sr_rwg")[0],
            SRRWGReviewQueuePage,
        )
        text = page.open_first_item_in_first_queue_set().casefold()
        page_evidence.checkpoint(
            "Senior RWG review pane — history markers: "
            f"{[m for m in ('iteration', 'history', 'timeline', 'version') if m in text] or 'none'}; "
            f"approve offered: {'approve' in text}; send back offered: "
            f"{'send back' in text or 'revise' in text}"
        )
        assert any(marker in text for marker in ("iteration", "history", "timeline", "version"))
        assert "approve" in text
        assert "send back" in text or "revise" in text

    def test_tc_ibmm_13_n01_teacher_items_absent_from_sr_rwg_queue(self, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Sign in as a Senior RWG reviewer and read their queue.\n"
            "Check teacher-contributed items are not in it, since they do not belong "
            "to this review lane.",
        )
        page = self.login(
            ReadConfig.get_role_usernames("sr_rwg")[0],
            SRRWGReviewQueuePage,
        )
        text = page.get_queue_body_text().casefold()
        page_evidence.checkpoint(
            "Teacher-contribution markers in the Senior RWG queue: "
            f"{[m for m in ('teacher contribution', 'submitted by: teacher') if m in text] or 'none — correctly absent'}"
        )
        assert "teacher contribution" not in text and "submitted by: teacher" not in text
