import re

import pytest

from pages.common.login_page import LoginPage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestReviewRoleContracts:
    def login(self, username, page_class=RWGReviewQueuePage):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_all_users_password(),
        )
        page = page_class(self.driver)
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        return page

    def test_tc_ibmm_11_p01_rwg_queue_contains_qar_cleared_items(self):
        page = self.login(ReadConfig.get_role_usernames("rwg")[0])
        text = page.get_queue_body_text()
        assert re.search(r"IS\d+", text), f"No QAR-cleared item set found in RWG queue: {text}"

    def test_tc_ibmm_11_p02_sirs_has_26_criteria_across_6_sections(self):
        page = self.login(ReadConfig.get_role_usernames("rwg")[0])
        text = page.open_first_item_in_first_queue_set()
        normalized = text.casefold()
        assert "evaluation criteria" in normalized or "item response sheet" in normalized
        criterion_numbers = set(re.findall(r"\b([1-6]\.\d+)\b", normalized))
        section_numbers = {number.split(".", 1)[0] for number in criterion_numbers}
        assert len(section_numbers) == 6, (
            f"Expected 6 SIRS sections, found {len(section_numbers)}: {section_numbers}."
        )
        assert len(criterion_numbers) == 26, (
            f"Expected exactly 26 SIRS criteria, found {len(criterion_numbers)}: {criterion_numbers}."
        )

    def test_tc_ibmm_11_n01_submit_disabled_with_zero_evaluated(self):
        page = self.login(ReadConfig.get_role_usernames("rwg")[0])
        text = page.open_first_item_in_first_queue_set()
        assert "0 evaluated" in text.casefold() or "0/" in text
        assert page.is_submit_review_enabled() is False

    def test_tc_ibmm_12_p01_sme_feedback_has_iteration_counter(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_all_users_password(),
        )
        body = self.driver.find_element("tag name", "body")
        body.send_keys("\ue00c")
        sets_page = UploadItemFilePage(self.driver)
        sets_page.wait_for_application_to_load()
        sets_page.open_sets_module()
        text = self.driver.find_element("tag name", "body").text.casefold()
        assert "feedback" in text, "SME Sets did not display reviewer feedback."
        assert re.search(r"iteration\s*\d+", text), (
            "SME feedback did not display an iteration counter."
        )

    def test_tc_ibmm_12_n01_item_disabled_after_third_rejection(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_all_users_password(),
        )
        sets_page = UploadItemFilePage(self.driver)
        sets_page.wait_for_application_to_load()
        sets_page.open_sets_module()
        text = self.driver.find_element("tag name", "body").text.casefold()
        assert (
            "3" in text
            and "rejection" in text
            and any(marker in text for marker in ("disabled", "three-strike", "3-strike"))
        ), "No third-rejection disabled/three-strike state was visible in SME Sets."

    def test_tc_ibmm_13_p01_p02_sr_rwg_history_and_decisions(self):
        page = self.login(
            ReadConfig.get_role_usernames("sr_rwg")[0],
            SRRWGReviewQueuePage,
        )
        text = page.open_first_item_in_first_queue_set().casefold()
        assert any(marker in text for marker in ("iteration", "history", "timeline", "version"))
        assert "approve" in text
        assert "send back" in text or "revise" in text

    def test_tc_ibmm_13_n01_teacher_items_absent_from_sr_rwg_queue(self):
        page = self.login(
            ReadConfig.get_role_usernames("sr_rwg")[0],
            SRRWGReviewQueuePage,
        )
        text = page.get_queue_body_text().casefold()
        assert "teacher contribution" not in text and "submitted by: teacher" not in text
