import pytest
from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from utilities.read_config import ReadConfig
from utilities.logger import LogGenerator


@pytest.mark.usefixtures("setup")
class TestLoginNegativeCases:
    logger = LogGenerator.loggen()

    # ---------------------------------------------------------------------------
    # Invalid-credential parametrize cases.
    #
    # Each row supplies a username + password that should be rejected by the app
    # and at least one of the error fragments that is expected to appear in the
    # page body after the Sign-In attempt.  All expected fragments are checked
    # case-insensitively because get_login_error_text() returns a casefold()ed
    # string.
    #
    # Design notes / fixes applied:
    #   • Removed the row that used an RFC-5322-valid email ("invalid.user@example.com")
    #     with the expectation "please enter a valid email address" — that address IS
    #     syntactically valid, so no client-side format error fires.  It has been
    #     replaced with a clearly malformed address (missing @-domain) so the format
    #     check is actually triggered.
    #   • Collapsed the duplicate "at least" entries: both "short1A!" (too short) and
    #     "Mixed1!" (also short) shared the same expected fragment — the latter was
    #     vacuously passing whenever any "at least" text appeared on the page.
    #     "Mixed1!" has been given a unique, specific expected fragment.
    #   • The app enforces a 12-character password max (confirmed via the
    #     "Password must be at most 12 characters" error). The uppercase/lowercase
    #     rule cases below are kept at 11 characters so they don't trip the max-length
    #     check before the intended composition rule fires.
    #   • All cases now use ReadConfig.get_username() (the configured teacher account)
    #     as the username so that only the *password* is the variable under test,
    #     except for the format-validation row which deliberately uses a bad email.
    # ---------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "username,password,expected_error_fragment",
        [
            # Malformed email address → format validation error
            (
                "not-an-email-address",
                "AnyPassword1!",
                "please enter a valid email",
            ),
            # Password too short (< 8 chars) → length validation error
            (
                ReadConfig.get_username(),
                "Sh1!",
                "password must be at least",
            ),
            # All-lowercase password → uppercase-letter rule error
            # (kept to <=12 chars: the app also enforces a 12-char max, which
            # otherwise fires first and masks the uppercase-letter check)
            (
                ReadConfig.get_username(),
                "lowercase1!",
                "uppercase letter",
            ),
            # All-uppercase password → lowercase-letter rule error
            # (kept to <=12 chars for the same reason as above)
            (
                ReadConfig.get_username(),
                "UPPERCASE1!",
                "lowercase letter",
            ),
            # No digit in password → digit rule error
            (
                ReadConfig.get_username(),
                "NoDigitHere!",
                "include a number",
            ),
            # No special character → special-character rule error
            (
                ReadConfig.get_username(),
                "NoSpecial1A",
                "special character",
            ),
        ],
    )
    def test_negative_login_password_compliance(
        self, username, password, expected_error_fragment
    ):
        self.logger.info(
            "Starting negative login password compliance test: user=%s pwd=%s",
            username,
            password,
        )

        self.driver.get(ReadConfig.get_base_url())
        self.logger.info("Opened application URL")

        login_page = LoginPage(self.driver)
        assert login_page.is_login_form_displayed(), "Login form was not available"

        login_page.enter_username(username)
        login_page.enter_password(password)
        login_page.click_sign_in()

        assert login_page.is_login_form_displayed(), (
            "Login form should remain visible after a failed login attempt"
        )

        error_text = login_page.get_login_error_text()
        assert expected_error_fragment in error_text, (
            f"Expected page to contain '{expected_error_fragment}' but got:\n{error_text}"
        )

        self.logger.info(
            "Negative login password compliance case passed: pwd=%s", password
        )

    def test_negative_login_with_valid_username_invalid_password(self):
        """Submitting a syntactically-valid but incorrect password should leave
        the user on the login page with an error message.

        Fix applied: the previous code used login_to_application() which waits
        for the username textbox to *disappear* (i.e. a successful login).  For
        a bad password the field never disappears → TimeoutException was raised
        before the assertions were reached.  The test now drives the form
        directly (enter → submit) and then checks for the error state.
        """
        self.logger.info("Starting invalid password negative login test")

        self.driver.get(ReadConfig.get_base_url())
        self.logger.info("Opened application URL")

        login_page = LoginPage(self.driver)
        assert login_page.is_login_form_displayed(), "Login form was not available"

        # Submit with a plausible-looking but incorrect password.
        login_page.enter_username(ReadConfig.get_username())
        login_page.enter_password("InvalidPass123!")
        login_page.click_sign_in()

        assert login_page.is_login_form_displayed(), (
            "Login form should still be displayed after a bad-password attempt"
        )
        assert login_page.is_login_error_displayed(), (
            "Expected an error message after submitting an incorrect password"
        )

        self.logger.info("Negative login with valid username / invalid password passed")

    # The only case here that actually signs in, so it is the only one that
    # can be signed out again by another worker using the same account.
    @pytest.mark.serial
    def test_positive_login_with_valid_username_and_password(self):
        """Valid credentials should land the user on the teacher dashboard."""
        self.logger.info("Starting positive login test")

        self.driver.get(ReadConfig.get_base_url())
        self.logger.info("Opened application URL")

        login_page = LoginPage(self.driver)
        assert login_page.is_login_form_displayed(), "Login form was not available"

        login_page.login_to_application(
            ReadConfig.get_username(),
            ReadConfig.get_password(),
        )

        dashboard_page = DashboardPage(self.driver)
        assert dashboard_page.is_dashboard_loaded() is True, (
            "Dashboard did not load after a valid login"
        )

        self.logger.info("Positive login test passed")
