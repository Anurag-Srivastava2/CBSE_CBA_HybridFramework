import pytest

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig

# Every absent affordance costs its full timeout, and by design all of them are
# expected to be absent today — so keep it short.
CHECK_TIMEOUT = 2


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2MFASessionContracts:
    """MFA, onboarding-link and idle-session contracts.

    Every check here is `xfail`: each needs something this environment cannot
    give a browser test — a real mailbox or SMS channel, a time-controlled
    onboarding link, an MFA-enrolled throwaway account, or a ten-minute idle
    wait. Those guards are unchanged and still decide the outcome.

    What each check *does* record before xfailing is whether the affordance it
    is waiting on has appeared in the product yet. That is the one piece of
    information a browser can supply here: today every row reports FAILED,
    which is the correct reading of "MFA has not shipped". The run these rows
    start reporting PASSED is the run these xfail guards can be retired — which
    is strictly more than a bare xfail tells anyone.
    """

    def survey_mfa_affordances(self, record_property, known_issue, session_scope=False):
        """Record which MFA / session affordances the app currently exposes.

        Reads the sign-in screen without submitting credentials, so it costs no
        session and cannot contend for an account. `session_scope` additionally
        records the idle-session controls, which belong to the KI-M2-SESSION-*
        contracts rather than the MFA ones.
        """
        login_page = LoginPage(self.driver)
        self.driver.get(ReadConfig.get_base_url())
        checks = ElementChecks(
            login_page, record_property, page_name=f"MFA & Session — {known_issue}"
        )

        # The sign-in form itself is the baseline: if it is missing, the absence
        # of everything below says nothing about MFA.
        checks.check_condition(
            "Sign-in form rendered", lambda: login_page.is_login_form_displayed()
        )

        affordances = list(login_page.MFA_AFFORDANCES)
        if session_scope:
            affordances += list(login_page.SESSION_AFFORDANCES)
        present = []
        for label, attribute in affordances:
            if checks.check(
                f"Affordance — {label}",
                getattr(login_page, attribute),
                timeout=CHECK_TIMEOUT,
            ):
                present.append(label)

        # The run this stops reading "none" is the run the xfail guard below can
        # be retired, which is strictly more than a bare xfail records.
        checkpoint(
            f"{known_issue} — affordances shipped so far: "
            f"{', '.join(present) if present else 'none of ' + str(len(affordances))}"
        )
        record_property("result_description", checks.publish())
        return checks

    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_role_usernames("teacher")[0],
            ReadConfig.get_password_for_username(ReadConfig.get_role_usernames("teacher")[0]),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        return page

    def test_tc_wpad_03_p01_welcome_email_is_sent_within_60_seconds(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "A newly created user should receive a welcome email within 60 seconds.\n"
            "Checking it needs mailbox and SMS integration access this environment "
            "cannot give a browser test, so it is filed as known issue KI-M2-MFA-001 "
            "instead of asserted.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-001")
        pytest.xfail(
            "KI-M2-MFA-001 [M2 Onboarding] Welcome-email delivery requires mailbox/SMS integration access."
        )

    def test_tc_wpad_03_p02_onboarding_link_is_single_use(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "An onboarding link should work once and be dead on the second use.\n"
            "Checking it needs a real onboarding email captured first, so it is filed "
            "as known issue KI-M2-MFA-002 instead of asserted.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-002")
        pytest.xfail(
            "KI-M2-MFA-002 [M2 Onboarding] Single-use onboarding-link verification requires a captured onboarding email link."
        )

    def test_tc_wpad_03_n01_onboarding_link_expires_after_24_hours(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "An onboarding link should stop working 24 hours after it is issued.\n"
            "Checking it needs time-controlled email fixture data, so it is filed as "
            "known issue KI-M2-MFA-003 instead of asserted.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-003")
        pytest.xfail(
            "KI-M2-MFA-003 [M2 Onboarding] 24-hour onboarding-link expiry requires time-controlled email fixture data."
        )

    def test_tc_wpad_04_p01_otp_is_delivered_by_email_and_sms_within_60_seconds(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "A sign-in OTP should arrive by both email and SMS within 60 seconds.\n"
            "Checking it needs access to an external notification inbox, so it is "
            "filed as known issue KI-M2-MFA-004 instead of asserted.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-004")
        pytest.xfail(
            "KI-M2-MFA-004 [M2 MFA] OTP email/SMS delivery requires external notification inbox access."
        )

    def test_tc_wpad_04_p02_otp_expires_after_5_minutes(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "An OTP should stop being accepted 5 minutes after it is issued.\n"
            "Checking it means waiting 300 seconds and reading a real OTP channel, so "
            "it is filed as known issue KI-M2-MFA-005 instead of asserted.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-005")
        pytest.xfail(
            "KI-M2-MFA-005 [M2 MFA] OTP 5-minute expiry requires waiting 300 seconds and reading a real OTP channel."
        )

    def test_tc_wpad_04_n01_account_locks_after_three_invalid_otp_attempts(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Three wrong OTP entries in a row should lock the account.\n"
            "Checking it needs a safe MFA-enrolled throwaway account, so it is filed "
            "as known issue KI-M2-MFA-006 instead of asserted.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-006")
        pytest.xfail(
            "KI-M2-MFA-006 [M2 MFA] Invalid OTP lockout requires a safe MFA-enrolled throwaway account."
        )

    def test_tc_wpad_05_p01_idle_session_expires_after_10_minutes(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "A session left idle for 10 minutes should expire and require signing in "
            "again.\n"
            "Measured on UAT 2026-09-07: an admin session left idle for 11 minutes "
            "never expired, so there is no expiry here to assert. Filed as known "
            "issue KI-M2-SESSION-001.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-SESSION-001", session_scope=True)
        pytest.xfail(
            "KI-M2-SESSION-001 [M2 Session] No idle expiry occurs. Measured on UAT "
            "2026-09-07: signed in, idled 11 minutes sampling every 30s with timer "
            "throttling disabled - the session never expired and the login form never "
            "returned. This is a product gap at the specified 10-minute timing, not a "
            "test that merely takes too long to run."
        )

    def test_tc_wpad_05_p02_idle_warning_appears_at_8_minutes(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "A warning should appear after 8 minutes of inactivity, before the "
            "session expires.\n"
            "Measured on UAT 2026-09-07: no warning appeared at any point during 11 "
            "minutes of idling, so there is no warning here to assert. Filed as known "
            "issue KI-M2-SESSION-002.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-SESSION-002", session_scope=True)
        pytest.xfail(
            "KI-M2-SESSION-002 [M2 Session] No idle warning appears. Measured on UAT "
            "2026-09-07: idled 11 minutes sampling every 30s with timer throttling "
            "disabled - the session-expiry warning never rendered. This is a product "
            "gap at the specified 8-minute timing, not a slow test."
        )

    def test_tc_wpad_05_p03_stay_active_resets_idle_timer(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Clicking Stay Active on the idle warning should reset the timer and keep "
            "the session alive.\n"
            "Measured on UAT 2026-09-07: the idle warning that carries the Stay Active "
            "control never appears, so the control cannot be reached. Filed as known "
            "issue KI-M2-SESSION-003.",
        )
        self.survey_mfa_affordances(record_property, "KI-M2-SESSION-003", session_scope=True)
        pytest.xfail(
            "KI-M2-SESSION-003 [M2 Session] Stay Active is unreachable: it lives on the "
            "idle warning, and that warning never appears (see KI-M2-SESSION-002). "
            "Blocked by the missing warning, not by idle-time control."
        )
