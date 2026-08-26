import pytest
from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig
from utilities.logger import LogGenerator

# The sign-in survey runs a dozen checks against controls that paint together.
CHECK_TIMEOUT = 2


@pytest.mark.usefixtures("setup")
class TestLoginNegativeCases:
    logger = LogGenerator.loggen()

    def survey(self, login_page, record_property, scope):
        """Soft-check the sign-in form furniture.

        Deliberately narrow: the full branding and theme survey of this screen
        lives in TestTeacherLoginPageBranding, so this records only the controls
        a credential test actually depends on rather than duplicating that
        inventory in eight more report cards.
        """
        checks = ElementChecks(
            login_page, record_property, page_name=f"Sign-in Form — {scope}"
        )
        checks.check("Heading — Welcome Back!", login_page.WELCOME_HEADING, timeout=CHECK_TIMEOUT)
        checks.check("Label — email", login_page.EMAIL_LABEL, timeout=CHECK_TIMEOUT)
        checks.check("Label — password", login_page.PASSWORD_LABEL, timeout=CHECK_TIMEOUT)
        checks.check("Field — email", login_page.USERNAME_TEXTBOX, timeout=CHECK_TIMEOUT)
        checks.check("Field — password", login_page.PASSWORD_TEXTBOX, timeout=CHECK_TIMEOUT)
        checks.check("Button — Sign In", login_page.SIGN_IN_BUTTON, timeout=CHECK_TIMEOUT)
        checks.check(
            "Button — password visibility toggle",
            login_page.PASSWORD_VISIBILITY_TOGGLE,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Link — Forgot Password?", login_page.FORGOT_PASSWORD_LINK, timeout=CHECK_TIMEOUT
        )
        checks.check(
            "Link — Contact Support", login_page.CONTACT_SUPPORT_LINK, timeout=CHECK_TIMEOUT
        )
        checks.check("Theme picker", login_page.THEME_PICKER, timeout=CHECK_TIMEOUT)
        checks.check("Language — EN", login_page.LANG_EN, timeout=CHECK_TIMEOUT)
        checks.check("Language — हिंदी", login_page.LANG_HI, timeout=CHECK_TIMEOUT)
        return checks

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
    #
    # get_username() rather than the worker-aware get_teacher_username() on
    # purpose: this list is evaluated at collection time and its values end up in
    # the test IDs. pytest-xdist requires every worker to collect identical IDs,
    # so a per-worker username here would break the run outright. None of these
    # rows establishes a session, so they never contend for the account anyway.
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
        self, username, password, expected_error_fragment, record_property,
        page_evidence,
    ):
        """Password-policy rejection. The rejection itself is a security
        contract, so the error-text assertions stay hard; only the form
        furniture around them is recorded softly."""
        self.logger.info(
            "Starting negative login password compliance test: user=%s pwd=%s",
            username,
            password,
        )

        self.driver.get(ReadConfig.get_base_url())
        self.logger.info("Opened application URL")

        login_page = LoginPage(self.driver)
        checks = self.survey(login_page, record_property, expected_error_fragment)
        record_property("result_description", checks.publish())

        assert login_page.is_login_form_displayed(), "Login form was not available"

        login_page.enter_username(username)
        login_page.enter_password(password)
        # The password is safe to name: every one of these is a deliberately
        # non-compliant literal from the parametrize table, never a real
        # credential.
        page_evidence.checkpoint(
            f"Submitting {username!r} with the non-compliant password "
            f"{password!r}, expecting {expected_error_fragment!r}"
        )
        login_page.click_sign_in()

        form_still_shown = login_page.is_login_form_displayed()
        error_text = login_page.get_login_error_text()
        page_evidence.checkpoint(
            f"Rejected — login form still shown: {form_still_shown}; error text: "
            f"{error_text[:160] or 'none'}"
        )
        assert form_still_shown, (
            "Login form should remain visible after a failed login attempt"
        )

        assert expected_error_fragment in error_text, (
            f"Expected page to contain '{expected_error_fragment}' but got:\n{error_text}"
        )

        self.logger.info(
            "Negative login password compliance case passed: pwd=%s", password
        )

    def test_negative_login_with_valid_username_invalid_password(
        self, record_property, page_evidence
    ):
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
        checks = self.survey(login_page, record_property, "Invalid Password")

        # A rendered-but-dead visibility toggle would pass every presence check
        # above. Driving it here is safe: it changes nothing but the input type.
        checks.check_interaction(
            "Password visibility toggle reveals the password",
            lambda: login_page.click_element(login_page.PASSWORD_VISIBILITY_TOGGLE),
            lambda: login_page.attribute_of(login_page.PASSWORD_TEXTBOX, "type") == "text",
        )
        checks.check_interaction(
            "Password visibility toggle hides it again",
            lambda: login_page.click_element(login_page.PASSWORD_VISIBILITY_TOGGLE),
            lambda: login_page.attribute_of(login_page.PASSWORD_TEXTBOX, "type")
            == "password",
        )
        record_property("result_description", checks.publish())
        page_evidence.checkpoint(
            "Password visibility toggle round-tripped the field between text and "
            "password, so the control is live rather than merely rendered"
        )

        assert login_page.is_login_form_displayed(), "Login form was not available"

        # Submit with a plausible-looking but incorrect password.
        login_page.enter_username(ReadConfig.get_teacher_username())
        login_page.enter_password("InvalidPass123!")
        page_evidence.checkpoint(
            f"Submitting a real account ({ReadConfig.get_teacher_username()}) with "
            "a policy-compliant but wrong password — only the password is wrong here"
        )
        login_page.click_sign_in()

        form_still_shown = login_page.is_login_form_displayed()
        error_shown = login_page.is_login_error_displayed()
        page_evidence.checkpoint(
            f"Rejected — login form still shown: {form_still_shown}; error "
            f"displayed: {error_shown}"
        )
        assert form_still_shown, (
            "Login form should still be displayed after a bad-password attempt"
        )
        assert error_shown, (
            "Expected an error message after submitting an incorrect password"
        )

        self.logger.info("Negative login with valid username / invalid password passed")

    # The only case here that actually signs in, so it is the only one that
    # can be signed out again by another worker using the same account.
    @pytest.mark.serial
    def test_positive_login_with_valid_username_and_password(
        self, record_property, page_evidence
    ):
        """Valid credentials should land the user on the teacher dashboard."""
        self.logger.info("Starting positive login test")

        self.driver.get(ReadConfig.get_base_url())
        self.logger.info("Opened application URL")

        login_page = LoginPage(self.driver)
        checks = self.survey(login_page, record_property, "Valid Credentials")
        record_property("result_description", checks.publish())

        assert login_page.is_login_form_displayed(), "Login form was not available"

        username = ReadConfig.get_teacher_username()
        page_evidence.checkpoint(
            f"Signing in as {username} with its configured password — the control "
            "for every rejection case above"
        )
        login_page.login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )

        dashboard_page = DashboardPage(self.driver)
        dashboard_loaded = dashboard_page.is_dashboard_loaded()
        page_evidence.checkpoint(
            f"Teacher dashboard loaded after a valid login: {dashboard_loaded}"
        )
        assert dashboard_loaded is True, (
            "Dashboard did not load after a valid login"
        )

        self.logger.info("Positive login test passed")
