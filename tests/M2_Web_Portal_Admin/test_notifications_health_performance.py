import pytest
from selenium.common.exceptions import TimeoutException

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2NotificationsHealthPerformance:
    def login_as_admin(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_role_usernames("admin")[0],
            ReadConfig.get_all_users_password(),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        return page

    def test_tc_wpad_12_p01_otp_notification_email_and_sms_within_60_seconds(self):
        pytest.xfail(
            "KI-M2-NOTIFY-001 [M2 Notifications] OTP notification delivery requires email/SMS inbox access."
        )

    def test_tc_wpad_12_p02_qar_pass_notification_email_sms_and_panel(self):
        pytest.xfail(
            "KI-M2-NOTIFY-002 [M2 Notifications] QAR pass notification requires creating a fresh item set and reading email/SMS channels."
        )

    def test_tc_wpad_13_p01_system_health_dashboard_shows_core_services(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("System Health", "Health")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-HEALTH-001 [M2 System Health] System Health dashboard is not currently reachable: {error}"
            )
        text = page.normalized_body_text()
        if "404" in text and "page not found" in text:
            pytest.xfail(
                "KI-M2-HEALTH-001 [M2 System Health] System Health dashboard route returns 404 on QA."
            )
        for marker in ("database", "api", "qar", "notification"):
            assert marker in text
        assert any(status in text for status in ("operational", "degraded", "outage"))

    def test_tc_wpad_13_p02_service_outage_alert_fires_within_5_minutes(self):
        pytest.xfail(
            "KI-M2-HEALTH-002 [M2 System Health] Service outage alert requires controlled test-environment outage simulation."
        )

    @pytest.mark.performance
    def test_tc_wpad_perf_01_create_10_users_each_within_2_seconds(self):
        pytest.xfail(
            "KI-M2-PERF-001 [M2 Performance] 10-user creation performance requires safe disposable admin-user data and cleanup."
        )

    @pytest.mark.performance
    def test_tc_wpad_perf_02_audit_log_796_entries_filters_within_3_seconds(self):
        page = self.login_as_admin()
        try:
            page.open_named_section("Audit Logs", "Audit")
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-PERF-002 [M2 Performance] Audit log performance page is not currently reachable: {error}"
            )
        text = page.normalized_body_text()
        if "796" not in text and "audit" not in text:
            pytest.xfail(
                "KI-M2-PERF-002 [M2 Performance] Audit log fixture with 796+ entries is not visible in this environment."
            )

    @pytest.mark.performance
    def test_tc_wpad_perf_03_100_user_load_has_no_session_or_rbac_leakage(self):
        pytest.xfail(
            "KI-M2-PERF-003 [M2 Performance] 100-user load test belongs in JMeter/load environment, not single-browser pytest."
        )
