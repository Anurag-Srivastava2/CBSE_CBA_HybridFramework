import pytest
from selenium.common.exceptions import TimeoutException

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2MFASessionContracts:
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

    def test_tc_wpad_03_p01_welcome_email_is_sent_within_60_seconds(self):
        pytest.xfail(
            "KI-M2-MFA-001 [M2 Onboarding] Welcome-email delivery requires mailbox/SMS integration access."
        )

    def test_tc_wpad_03_p02_onboarding_link_is_single_use(self):
        pytest.xfail(
            "KI-M2-MFA-002 [M2 Onboarding] Single-use onboarding-link verification requires a captured onboarding email link."
        )

    def test_tc_wpad_03_n01_onboarding_link_expires_after_24_hours(self):
        pytest.xfail(
            "KI-M2-MFA-003 [M2 Onboarding] 24-hour onboarding-link expiry requires time-controlled email fixture data."
        )

    def test_tc_wpad_04_p01_otp_is_delivered_by_email_and_sms_within_60_seconds(self):
        pytest.xfail(
            "KI-M2-MFA-004 [M2 MFA] OTP email/SMS delivery requires external notification inbox access."
        )

    def test_tc_wpad_04_p02_otp_expires_after_5_minutes(self):
        pytest.xfail(
            "KI-M2-MFA-005 [M2 MFA] OTP 5-minute expiry requires waiting 300 seconds and reading a real OTP channel."
        )

    def test_tc_wpad_04_n01_account_locks_after_three_invalid_otp_attempts(self):
        pytest.xfail(
            "KI-M2-MFA-006 [M2 MFA] Invalid OTP lockout requires a safe MFA-enrolled throwaway account."
        )

    def test_tc_wpad_05_p01_idle_session_expires_after_10_minutes(self):
        pytest.xfail(
            "KI-M2-SESSION-001 [M2 Session] 10-minute idle expiry is a long-running timing test and should run in a dedicated session suite."
        )

    def test_tc_wpad_05_p02_idle_warning_appears_at_8_minutes(self):
        pytest.xfail(
            "KI-M2-SESSION-002 [M2 Session] 8-minute idle warning is a long-running timing test and should run in a dedicated session suite."
        )

    def test_tc_wpad_05_p03_stay_active_resets_idle_timer(self):
        pytest.xfail(
            "KI-M2-SESSION-003 [M2 Session] Stay Active timer reset requires long-running browser idle control."
        )
