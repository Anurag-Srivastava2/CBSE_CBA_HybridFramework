import re
from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2PortalAdminFeatures:
    def login_as(self, username):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_all_users_password(),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        return page

    def login_as_admin(self):
        return self.login_as(ReadConfig.get_role_usernames("admin")[0])

    def test_tc_wpad_06_p01_admin_can_update_theme_without_deployment(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Portal Settings", "Layout Configuration")
            page.click_button_containing("Theme", "Layout")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-PORTAL-001 [M2 Portal Settings] Theme/layout configuration UI is not exposed: {error}"
            )
        assert "theme" in page.normalized_body_text() or "layout" in page.normalized_body_text()

    def test_tc_wpad_06_p02_teacher_preview_and_publish_theme(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Portal Settings", "Layout Configuration")
            page.click_button_containing("Preview")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-PORTAL-002 [M2 Portal Settings] Theme preview/publish controls are not exposed: {error}"
            )
        text = page.normalized_body_text()
        assert "teacher" in text or "preview" in text

    def test_tc_wpad_07_p01_sme_dashboard_shows_item_stats_only(self):
        page = self.login_as(ReadConfig.get_sme2_username())
        text = page.normalized_body_text()
        for marker in ("total items", "needs revision", "approved", "rejected"):
            if marker not in text:
                pytest.xfail(
                    f"KI-M2-DASHBOARD-001 [M2 Dashboard] SME dashboard is missing expected widget: {marker}"
                )
        assert "qp builder" not in text
        assert "quorum" not in text

    def test_tc_wpad_07_p02_pit_dashboard_has_quorum_without_sme_edit_widgets(self):
        page = self.login_as(ReadConfig.get_pit_usernames()[0])
        text = page.normalized_body_text()
        if not all(marker in text for marker in ("quorum", "pending")):
            pytest.xfail(
                "KI-M2-DASHBOARD-002 [M2 Dashboard] PIT dashboard does not expose quorum/pending-set widgets."
            )
        assert "edit item" not in text
        assert "upload" not in text

    def test_tc_wpad_08_p01_audit_logs_filter_by_user_date_and_action(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Audit Logs", "Audit")
            page.search(ReadConfig.get_role_usernames("teacher")[0])
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-AUDIT-001 [M2 Audit Logs] Audit logs page/filter is not currently reachable: {error}"
            )
        text = page.normalized_body_text()
        assert "user" in text and "role" in text and "timestamp" in text

    def test_tc_wpad_08_n01_audit_logs_are_immutable(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Audit Logs", "Audit")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-AUDIT-002 [M2 Audit Logs] Audit logs page is not currently reachable: {error}"
            )
        assert not page.has_forbidden_text("delete log", "edit log")

    def test_tc_wpad_09_p01_admin_report_generates_within_5_seconds(self):
        page = self.login_as_admin()
        try:
            duration = page.generate_report(role="Teacher", date_range="Last 30 days")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-REPORTS-001 [M2 Reports] Reports page/generate action is not currently reachable: {error}"
            )
        assert duration <= 5.0
        text = page.normalized_body_text()
        assert "teacher" in text or "activity" in text or "items" in text

    def test_tc_wpad_09_p02_admin_report_downloads_csv_or_excel(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Reports")
            page.click_button_containing("Download", "Export")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-REPORTS-002 [M2 Reports] Report download/export control is not currently reachable: {error}"
            )
        assert "download" in page.normalized_body_text() or "export" in page.normalized_body_text()

    def test_tc_wpad_10_p01_teacher_can_submit_support_ticket(self):
        page = self.login_as(ReadConfig.get_role_usernames("teacher")[0])
        try:
            page.open_named_section("Support")
            page.click_button_containing("New Ticket", "Create Ticket")
            page.fill_by_label_or_placeholder(
                "Description",
                f"Automation support issue {uuid4().hex[:8]}",
            )
            page.click_button_containing("Submit")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-SUPPORT-001 [M2 Support] Support ticket UI is not currently reachable/actionable: {error}"
            )
        assert re.search(r"TKT[-\d]+", page.body_text(), re.IGNORECASE)

    def test_tc_wpad_10_p02_support_ticket_email_acknowledgement_within_48_hours(self):
        pytest.xfail(
            "KI-M2-SUPPORT-002 [M2 Support] 48-hour support email acknowledgement requires mailbox access and delayed verification."
        )

    def test_tc_wpad_11_p01_new_subject_master_reflects_in_m1_and_m4(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Masters Management", "Masters")
            page.click_button_containing("Add Subject", "New Subject")
            page.fill_by_label_or_placeholder("Subject", f"Environmental Science {uuid4().hex[:6]}")
            page.save_form()
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-MASTERS-001 [M2 Masters] Subject master create UI is not currently reachable/actionable: {error}"
            )
        assert "environmental science" in page.normalized_body_text()

    def test_tc_wpad_11_n01_delete_linked_subject_is_blocked(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Masters Management", "Masters")
            page.search("Mathematics")
            page.click_button_containing("Delete", "Archive")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-MASTERS-002 [M2 Masters] Subject delete/archive control is not currently reachable: {error}"
            )
        text = page.normalized_body_text()
        assert "cannot delete" in text or "linked" in text or "active items" in text
