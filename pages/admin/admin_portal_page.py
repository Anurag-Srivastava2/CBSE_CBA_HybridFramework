import re
from time import monotonic
from urllib.parse import urljoin

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class AdminPortalPage(BasePage):
    """Generic admin portal helper for M2 Web Portal Admin contracts."""

    SEARCH_INPUT = (
        By.XPATH,
        "//input[contains(@placeholder,'Search') or contains(@aria-label,'Search')]",
    )
    SAVE_BUTTONS = [
        (By.XPATH, "//button[normalize-space()='Save' or normalize-space()='Create User' or normalize-space()='Add User']"),
        (By.XPATH, "//button[contains(normalize-space(),'Save') or contains(normalize-space(),'Create') or contains(normalize-space(),'Add')]"),
    ]
    CONFIRM_BUTTONS = [
        (By.XPATH, "//*[@role='dialog' or contains(@class,'modal')]//button[normalize-space()='Confirm' or normalize-space()='Yes']"),
        (By.XPATH, "//button[normalize-space()='Confirm' or normalize-space()='Yes']"),
    ]

    def body_text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def normalized_body_text(self):
        return self.body_text().casefold()

    def open_relative_url(self, path):
        self.driver.get(urljoin(self.driver.current_url, path))
        self.wait_for_application_ready()

    def wait_for_application_ready(self, timeout=30):
        self.wait_utils.until_condition(
            lambda driver: "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=timeout,
        )

    def open_named_section(self, *names):
        """Open a sidebar/top-nav section by visible label, falling back to a likely URL."""
        for name in names:
            locators = [
                (By.XPATH, f"//*[self::a or self::button][normalize-space()='{name}']"),
                (By.XPATH, f"//*[self::a or self::button][contains(normalize-space(),'{name}')]"),
                # The sidebar truncates its labels - 'Masters Management' renders
                # as 'Master', 'Portal Settings' as 'Portal', 'Notifications' as
                # 'Notifi'. Neither match above can ever hit those, so every
                # multi-word section fell through to the URL-slug guess below and
                # xfailed when the guess was wrong. This matches the other way
                # round: a button whose visible label is a prefix of the wanted
                # name. The length guard matters because starts-with(x, '') is
                # true for every icon-only button on the page.
                (
                    By.XPATH,
                    f"//*[self::a or self::button]"
                    f"[string-length(normalize-space())>2 and starts-with('{name}', normalize-space())]",
                ),
                (By.XPATH, f"//*[contains(normalize-space(),'{name}')]/ancestor::*[self::a or self::button][1]"),
            ]
            for locator in locators:
                try:
                    self.click_element(locator)
                    self.wait_for_application_ready()
                    return
                except Exception:
                    continue

        slug = names[0].strip().lower().replace("&", "and")
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        self.open_relative_url(f"/admin/{slug}")

    def require_text_anywhere(self, *markers):
        text = self.normalized_body_text()
        missing = [marker for marker in markers if marker.casefold() not in text]
        if missing:
            raise TimeoutException(f"Missing expected text {missing}. Page text: {self.body_text()[:1000]}")

    def has_forbidden_text(self, *markers):
        text = self.normalized_body_text()
        return any(marker.casefold() in text for marker in markers)

    def search(self, value):
        search_input = self.wait_utils.until_visible(self.SEARCH_INPUT, timeout=20)
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        search_input.send_keys(value)
        search_input.send_keys(Keys.ENTER)
        self.wait_for_application_ready()

    def click_button_containing(self, *labels, timeout=10):
        locators = [
            (By.XPATH, f"//button[contains(normalize-space(),'{label}') and not(@disabled)]")
            for label in labels
        ]
        self.click_any_element(locators)

    def fill_by_label_or_placeholder(self, label, value):
        locators = [
            (
                By.XPATH,
                f"//label[contains(normalize-space(),'{label}')]/following::input[1]",
            ),
            (
                By.XPATH,
                f"//input[contains(@placeholder,'{label}') or contains(@aria-label,'{label}') or @name='{label}']",
            ),
            (
                By.XPATH,
                f"//textarea[contains(@placeholder,'{label}') or contains(@aria-label,'{label}') or @name='{label}']",
            ),
        ]
        self.enter_text_any_locator(locators, value)

    def select_option_by_visible_text(self, field_label, option_text):
        option_locators = [
            (By.XPATH, f"//label[contains(normalize-space(),'{field_label}')]/following::*[self::button or @role='combobox'][1]"),
            (By.XPATH, f"//*[contains(normalize-space(),'{field_label}')]/following::*[self::button or @role='combobox'][1]"),
        ]
        self.click_any_element(option_locators)
        self.click_any_element(
            [
                (By.XPATH, f"//*[@role='option' and contains(normalize-space(),'{option_text}')]"),
                (By.XPATH, f"//*[self::button or self::div or self::span][normalize-space()='{option_text}']"),
            ]
        )

    def save_form(self):
        self.click_any_element(self.SAVE_BUTTONS)
        self.confirm_if_prompted()
        self.wait_for_application_ready()

    def confirm_if_prompted(self):
        for locator in self.CONFIRM_BUTTONS:
            try:
                self.click_element(locator)
                return True
            except Exception:
                continue
        return False

    def create_user(self, name, email, mobile, role, grade="", subject=""):
        self.open_named_section("User Management", "Users")
        self.click_button_containing("Create User", "Add User", "New User")
        self.fill_by_label_or_placeholder("Name", name)
        self.fill_by_label_or_placeholder("Email", email)
        self.fill_by_label_or_placeholder("Mobile", mobile)
        self.select_option_by_visible_text("Role", role)
        if grade:
            self.select_option_by_visible_text("Grade", grade)
        if subject:
            self.select_option_by_visible_text("Subject", subject)
        started = monotonic()
        self.save_form()
        return monotonic() - started

    def deactivate_user(self, email):
        self.open_named_section("User Management", "Users")
        self.search(email)
        self.click_button_containing("Deactivate", "Disable")
        self.confirm_if_prompted()
        self.wait_for_application_ready()

    def generate_report(self, role="", date_range=""):
        self.open_named_section("Reports")
        if date_range:
            self.select_option_by_visible_text("Date", date_range)
        if role:
            self.select_option_by_visible_text("Role", role)
        started = monotonic()
        self.click_button_containing("Generate")
        self.wait_for_application_ready(timeout=10)
        return monotonic() - started
