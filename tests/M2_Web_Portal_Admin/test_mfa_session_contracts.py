import pytest

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
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
        for label, attribute in affordances:
            checks.check(
                f"Affordance — {label}",
                getattr(login_page, attribute),
                timeout=CHECK_TIMEOUT,
            )

        record_property("result_description", checks.publish())
        return checks

    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_role_usernames("teacher")[0],
            ReadConfig.get_all_users_password(),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        return page

    def test_tc_wpad_03_p01_welcome_email_is_sent_within_60_seconds(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-001")
        pytest.xfail(
            "KI-M2-MFA-001 [M2 Onboarding] Welcome-email delivery requires mailbox/SMS integration access."
        )

    def test_tc_wpad_03_p02_onboarding_link_is_single_use(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-002")
        pytest.xfail(
            "KI-M2-MFA-002 [M2 Onboarding] Single-use onboarding-link verification requires a captured onboarding email link."
        )

    def test_tc_wpad_03_n01_onboarding_link_expires_after_24_hours(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-003")
        pytest.xfail(
            "KI-M2-MFA-003 [M2 Onboarding] 24-hour onboarding-link expiry requires time-controlled email fixture data."
        )

    def test_tc_wpad_04_p01_otp_is_delivered_by_email_and_sms_within_60_seconds(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-004")
        pytest.xfail(
            "KI-M2-MFA-004 [M2 MFA] OTP email/SMS delivery requires external notification inbox access."
        )

    def test_tc_wpad_04_p02_otp_expires_after_5_minutes(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-005")
        pytest.xfail(
            "KI-M2-MFA-005 [M2 MFA] OTP 5-minute expiry requires waiting 300 seconds and reading a real OTP channel."
        )

    def test_tc_wpad_04_n01_account_locks_after_three_invalid_otp_attempts(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-MFA-006")
        pytest.xfail(
            "KI-M2-MFA-006 [M2 MFA] Invalid OTP lockout requires a safe MFA-enrolled throwaway account."
        )

    def test_tc_wpad_05_p01_idle_session_expires_after_10_minutes(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-SESSION-001", session_scope=True)
        pytest.xfail(
            "KI-M2-SESSION-001 [M2 Session] 10-minute idle expiry is a long-running timing test and should run in a dedicated session suite."
        )

    def test_tc_wpad_05_p02_idle_warning_appears_at_8_minutes(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-SESSION-002", session_scope=True)
        pytest.xfail(
            "KI-M2-SESSION-002 [M2 Session] 8-minute idle warning is a long-running timing test and should run in a dedicated session suite."
        )

    def test_tc_wpad_05_p03_stay_active_resets_idle_timer(self, record_property):
        self.survey_mfa_affordances(record_property, "KI-M2-SESSION-003", session_scope=True)
        pytest.xfail(
            "KI-M2-SESSION-003 [M2 Session] Stay Active timer reset requires long-running browser idle control."
        )
