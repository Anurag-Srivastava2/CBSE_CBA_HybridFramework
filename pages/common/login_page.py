from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from pages.common.base_page import BasePage


class LoginPage(BasePage):
    # Locators extracted from BlazeMeter recording.
    # Prefer ID/Name/CSS over absolute XPath.
    USERNAME_TEXTBOX = (By.ID, "identifier")
    PASSWORD_TEXTBOX = (By.ID, "password")
    SIGN_IN_BUTTON = (By.XPATH, "//button[@type='submit' and normalize-space()='Sign In']")
    AVATAR_MENU_TRIGGER = (By.XPATH, "//*[@aria-haspopup='menu'][contains(@class,'avatar')]")
    LOGOUT_MENU_ITEM = (
        By.XPATH,
        "//*[self::button or self::a or @role='menuitem']"
        "[contains(translate(normalize-space(),'LOGUT SIGNO','logut signo'),'logout')"
        " or contains(translate(normalize-space(),'LOGUT SIGNO','logut signo'),'sign out')]",
    )

    def enter_username(self, username):
        self.enter_text(self.USERNAME_TEXTBOX, username)

    def enter_password(self, password):
        self.enter_text(self.PASSWORD_TEXTBOX, password)

    def click_sign_in(self):
        self.click_element(self.SIGN_IN_BUTTON)

    def is_login_screen_text_visible(self):
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.casefold()
        except Exception:
            return False
        return any(
            marker in page_text
            for marker in (
                "welcome back",
                "sign in",
                "enter your email",
                "enter your password",
            )
        )

    def wait_for_login_form_or_authenticated_page(self):
        def login_form_or_authenticated_page(driver):
            if self.is_element_visible_quick(self.USERNAME_TEXTBOX):
                return True
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
            except Exception:
                return False
            if not page_text.strip() or "loading" in page_text:
                return False
            return not any(
                marker in page_text
                for marker in (
                    "welcome back",
                    "sign in",
                    "enter your email",
                    "enter your password",
                )
            )

        last_error = None
        for attempt in range(3):
            try:
                self.wait_utils.until_condition(
                    login_form_or_authenticated_page,
                    timeout=30,
                )
                return
            except TimeoutException as error:
                last_error = error
                if attempt < 2:
                    self.driver.refresh()
        raise TimeoutException(
            "The application remained on its global Loading screen and did not "
            "show either the login form or an authenticated page after refresh retries."
        ) from last_error

    def login_to_application(self, username, password):
        self.wait_for_login_form_or_authenticated_page()
        if not self.is_element_visible_quick(self.USERNAME_TEXTBOX):
            return
        for attempt in range(3):
            if attempt:
                # Retype into a form the SPA may have re-rendered underneath
                # the previous attempt: reload so the fields are the live ones.
                self.driver.refresh()
                self.wait_for_login_form_or_authenticated_page()
                if not self.is_element_visible_quick(self.USERNAME_TEXTBOX):
                    return
            self.enter_username(username)
            self.enter_password(password)
            self.click_sign_in()
            try:
                self.wait_utils.until_condition(
                    lambda driver: not self.wait_utils.is_visible(self.USERNAME_TEXTBOX, timeout=1),
                    timeout=45,
                )
                # Guard against credential-rejection errors that dismiss the
                # username field but land on an error state (not a real session).
                if self.is_login_error_displayed():
                    raise TimeoutException(
                        f"Login failed for {username!r}: the application rejected the credentials."
                    )
                self.driver._logged_in_user = username
                return
            except TimeoutException:
                if attempt == 2:
                    raise

    def logout(self, base_url=None):
        """End the session so another user can sign in.

        Prefers the avatar menu's Logout item; falls back to clearing cookies
        and web storage, which the SPA treats as a signed-out session.
        """
        try:
            self.click_element(self.AVATAR_MENU_TRIGGER)
            self.click_element(self.LOGOUT_MENU_ITEM)
            self.wait_utils.until_condition(
                lambda driver: self.is_element_visible_quick(self.USERNAME_TEXTBOX, timeout=2),
                timeout=20,
            )
        except Exception:
            self.driver.delete_all_cookies()
            try:
                self.driver.execute_script(
                    "window.localStorage.clear(); window.sessionStorage.clear();"
                )
            except Exception:
                pass
            self.driver.get(base_url or self.driver.current_url)
            self.wait_for_login_form_or_authenticated_page()
        self.driver._logged_in_user = None

    def is_login_form_displayed(self, timeout=20):
        # The default 5s probe is a snapshot of a page that is still booting:
        # with several browsers driving the app at once the login form can
        # take longer than that to paint, which reads as "no login form" even
        # though the app is fine.
        return (
            self.is_element_visible_quick(self.USERNAME_TEXTBOX, timeout)
            and self.is_element_visible_quick(self.PASSWORD_TEXTBOX, timeout)
        )

    def get_login_error_text(self):
        try:
            return self.driver.find_element(By.TAG_NAME, "body").text.casefold()
        except Exception:
            return ""

    def is_login_error_displayed(self):
        page_text = self.get_login_error_text()
        return any(
            marker in page_text
            for marker in (
                "invalid password",
                "incorrect password",
                "login failed",
                "invalid credentials",
                "username or password",
                "please check your password",
                "please check your username",
                "please enter a valid email address",
                "please enter a valid email",
                "password must include an uppercase letter",
                "password must include a lowercase letter",
                "password must include a number",
                "password must include a special character",
                "password must be at least",
                "password must be at most",
                "please enter your password",
            )
        )
