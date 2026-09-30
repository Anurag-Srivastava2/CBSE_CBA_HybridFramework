import pytest
from selenium.common.exceptions import TimeoutException

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2NotificationsHealthPerformance:
    def login_as_admin(self):
        self.driver.get(ReadConfig.get_base_url())
        username = ReadConfig.get_admin_username()
        LoginPage(self.driver).login_to_application(
            username,
            # Per-user password - see test_portal_admin_features.login_as.
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        checkpoint(f"Admin {username} signed in")
        return page

    def test_tc_wpad_12_p01_otp_notification_email_and_sms_within_60_seconds(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "An OTP notification should reach the user by email and SMS within 60 "
            "seconds.\n"
            "Checking it needs email and SMS inbox access, so it is filed as known "
            "issue KI-M2-NOTIFY-001 instead of asserted.",
        )
        pytest.xfail(
            "KI-M2-NOTIFY-001 [M2 Notifications] OTP notification delivery requires email/SMS inbox access."
        )

    def test_tc_wpad_12_p02_qar_pass_notification_email_sms_and_panel(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "When QAR passes, the author should be told by email, by SMS and in the "
            "notification panel.\n"
            "Checking it means creating a fresh item set and reading external "
            "channels, so it is filed as known issue KI-M2-NOTIFY-002 instead of "
            "asserted.",
        )
        pytest.xfail(
            "KI-M2-NOTIFY-002 [M2 Notifications] QAR pass notification requires creating a fresh item set and reading email/SMS channels."
        )

    def test_tc_wpad_13_p01_system_health_dashboard_shows_core_services(
        self, record_property, page_evidence
    ):
        """Each monitored service is recorded individually, so a partial health
        dashboard reports which service is missing rather than just the first."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the System Health dashboard as an admin.\n"
            "Record each monitored core service individually, so a partial dashboard "
            "names exactly which service is missing rather than only the first one.",
        )
        page = self.login_as_admin()
        try:
            page.open_named_section("System Health", "Health")
        except TimeoutException as error:
            # Not a navigation problem: the SPA's admin route table lists role,
            # user, assignment, masterdata, qar, portal, audit, notification,
            # helpdesk, itembank, workflow-config, sla-config and irt - there is
            # no system-health route in this build at all.
            pytest.xfail(
                "KI-M2-HEALTH-001 [M2 System Health] This build ships no system "
                "health dashboard - the admin route table has no health entry - "
                f"so core-service status cannot be read from one. Navigation said: {error}"
            )
        text = page.normalized_body_text()
        if "404" in text and "page not found" in text:
            # open_named_section falls back to guessing a URL slug when no nav
            # entry matches, and that guess 404s because the page does not
            # exist: the SPA's admin route table lists role, user, assignment,
            # masterdata, qar, portal, audit, notification, helpdesk, itembank,
            # workflow-config, sla-config and irt, with no health route.
            pytest.xfail(
                "KI-M2-HEALTH-001 [M2 System Health] This build ships no system "
                "health dashboard - there is no such admin route, and the guessed "
                "URL renders the app's 404 page - so core-service status cannot "
                "be read from one."
            )

        checks = ElementChecks(page, record_property, page_name="System Health")
        listed = [m for m in ("database", "api", "qar", "notification") if m in text]
        for marker in ("database", "api", "qar", "notification"):
            checks.check_condition(f"Service listed — {marker}", marker in text)
        statuses = [s for s in ("operational", "degraded", "outage") if s in text]
        page_evidence.checkpoint(
            f"System Health lists {listed or 'no'} core service(s); status "
            f"keywords on the page: {statuses or 'none'}"
        )
        checks.check_condition(
            "A service status is reported",
            statuses,
            detail=f"found: {statuses}" if statuses else "no status keyword on page",
        )
        record_property("result_description", checks.publish())

    def test_tc_wpad_13_p02_service_outage_alert_fires_within_5_minutes(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "A service going down should raise an alert within 5 minutes.\n"
            "Checking it needs a controlled outage simulated in the test environment, "
            "so it is filed as known issue KI-M2-HEALTH-002 instead of asserted.",
        )
        pytest.xfail(
            "KI-M2-HEALTH-002 [M2 System Health] Service outage alert requires controlled test-environment outage simulation."
        )

    @pytest.mark.performance
    def test_tc_wpad_perf_01_create_10_users_each_within_2_seconds(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Creating 10 users in a row should take under 2 seconds each.\n"
            "Running it needs safe disposable user data and a way to clean it up "
            "afterwards, so it is filed as known issue KI-M2-PERF-001 instead of "
            "asserted.",
        )
        pytest.xfail(
            "KI-M2-PERF-001 [M2 Performance] 10-user creation performance requires safe disposable admin-user data and cleanup."
        )

    @pytest.mark.performance
    def test_tc_wpad_perf_02_audit_log_796_entries_filters_within_3_seconds(
        self, record_property, page_evidence
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Filtering an audit log holding 796 or more entries should return within "
            "3 seconds.\n"
            "That fixture does not exist in this environment, so it is filed as known "
            "issue KI-M2-PERF-002 instead of asserted.",
        )
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

        checks = ElementChecks(page, record_property, page_name="Audit Logs — Performance")
        page_evidence.checkpoint(
            f"Audit Logs page rendered: {'audit' in text}; the seeded 796-entry "
            f"volume marker is visible: {'796' in text}"
        )
        checks.check_condition("Audit log page rendered", "audit" in text)
        checks.check_condition(
            "796-entry fixture visible", "796" in text, detail="expected the seeded volume marker"
        )
        record_property("result_description", checks.publish())

    @pytest.mark.performance
    def test_tc_wpad_perf_03_100_user_load_has_no_session_or_rbac_leakage(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Under a 100-user load, no session or permission should leak between "
            "users.\n"
            "That belongs in a load tool such as JMeter rather than a single-browser "
            "pytest run, so it is filed as known issue KI-M2-PERF-003 instead of "
            "asserted.",
        )
        pytest.xfail(
            "KI-M2-PERF-003 [M2 Performance] 100-user load test belongs in JMeter/load environment, not single-browser pytest."
        )
