import re
from time import monotonic, sleep
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.sme.manual_item_page import ManualItemPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
# Drives the shared teacher login, whose dashboard and staged "Added Items"
# list live server-side per account: a second session on the same account
# changes what this one sees mid-test.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestTeacherManualItemCreation:
    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_role_usernames("teacher")[0],
            ReadConfig.get_all_users_password(),
        )
        page = ManualItemPage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        return page

    def wait_for_dashboard_text(self, patterns, timeout=30):
        """Dashboard text once the given patterns are present.

        The shell renders before the stat tiles have their counts, so reading
        the page straight after login can catch "All Items" with no number in
        front of it yet. Returns whatever is on the page at the deadline so
        the caller's assertions still report the real content.
        """
        deadline = monotonic() + timeout
        while True:
            text = self.driver.execute_script(
                "return document.body.innerText || document.body.textContent || '';"
            )
            if all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
                return text
            if monotonic() >= deadline:
                return text
            sleep(0.5)

    def test_tc_tcib_01_p01_contribution_dashboard_and_create_cta(self):
        self.login_as_teacher()
        text = self.wait_for_dashboard_text(
            [
                r"hello,\s*teacher",
                r"create an item set|create new item",
                r"all items",
                r"under review",
                r"rejected",
                r"published",
            ]
        ).casefold()
        assert "hello, teacher" in text
        assert "create an item set" in text or "create new item" in text
        for status in ("all items", "under review", "rejected", "published"):
            assert status in text

    def test_tc_tcib_01_p02_dashboard_stat_counters_are_numeric(self):
        self.login_as_teacher()
        statuses = ("All Items", "Under Review", "Rejected", "Published")
        text = self.wait_for_dashboard_text(
            [rf"\b\d+\s+{re.escape(status)}\b" for status in statuses]
        )
        for status in statuses:
            assert re.search(rf"\b\d+\s+{re.escape(status)}\b", text, re.IGNORECASE), (
                f"No numeric counter was shown for {status}."
            )

    def test_tc_tcib_02_p01_submit_locked_until_mandatory_item_complete(self):
        page = self.login_as_teacher()
        page.open_true_false_manual_item_form()
        assert page.is_continue_enabled() is False

        # "Added Items" is staged server-side per account, so the list can
        # already hold items from an earlier run or another session on the
        # same login. What this test verifies is that adding one complete
        # item adds exactly one and unlocks Continue - assert the increment,
        # not an absolute count.
        items_before = int(page.get_settled_added_items_count())
        run_id = uuid4().hex[:10]
        page.add_true_false_manual_item(
            question_text=f"Is 91 greater than 19? Teacher contribution {run_id}",
            answer="True",
            explanation="91 is greater than 19.",
        )
        assert int(page.get_settled_added_items_count()) == items_before + 1
        assert page.is_continue_enabled() is True

    def test_tc_tcib_02_n01_teacher_grade_subject_rbac_is_enforced(self):
        page = self.login_as_teacher()
        page.open_true_false_manual_item_form()
        assert page.is_dropdown_option_available("Grade *", "Grade 1") is True
        assert page.is_dropdown_option_available("Grade *", "Grade 10") is False
        assert page.is_dropdown_option_available("Subject *", "Mathematics") is True
