"""Shared plumbing for the cross-module smoke suite.

Smoke checks are deliberately thin: sign in, land on a module's entry screen,
assert that it rendered, and change nothing. The sign-in and page-probing
helpers they all need live here so each module file reads as a short list of
critical-path checks rather than repeated navigation boilerplate.
"""

from selenium.webdriver.common.by import By

from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


def open_application(driver, attempts=2):
    """Navigate to the configured base URL, surviving a load that never settles.

    A driver.get() can otherwise sit until the remote command times out when
    the environment is slow to respond. Stopping the stalled load and retrying
    recovers the session instead of failing the check on infrastructure noise.
    """
    last_error = None
    for _ in range(attempts):
        try:
            driver.set_page_load_timeout(60)
            driver.get(ReadConfig.get_base_url())
            return
        except Exception as error:
            last_error = error
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass
        finally:
            try:
                driver.set_page_load_timeout(300)
            except Exception:
                pass
    raise last_error


def sign_in(driver, username):
    """Open the application and sign in, resolving the password from config."""
    open_application(driver)
    LoginPage(driver).login_to_application(
        username,
        ReadConfig.get_password_for_username(username),
    )


def reset_session(driver):
    """Drop the current login so another account can sign in.

    The portal keeps one active session per account and treats a cleared
    cookie/storage state as signed out. Used when a check walks several
    accounts in one browser — without it the next sign_in() lands on the
    previous user's authenticated page instead of the login form.
    """
    try:
        driver.delete_all_cookies()
    except Exception:
        pass
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    except Exception:
        # A blank or non-http document has no accessible storage; the cookie
        # clear above is enough for the app to treat the session as gone.
        pass


def body_text(driver):
    return driver.find_element(By.TAG_NAME, "body").text


def has_any_text(driver, *markers):
    """True when any marker appears in the rendered page text."""
    text = body_text(driver).casefold()
    return any(marker.casefold() in text for marker in markers)
