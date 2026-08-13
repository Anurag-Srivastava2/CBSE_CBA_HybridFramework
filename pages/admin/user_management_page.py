from time import monotonic, sleep

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class UserManagementPage(BasePage):
    """Admin > User Management (/admin/user).

    The account table is keyed on User Code and display name — it does not
    render the email — so rows are located by name and the generated
    USER-### code is read back after creation.
    """

    PATH = "/admin/user"

    PAGE_HEADING = (By.XPATH, "//*[normalize-space()='User Management']")
    SEARCH_INPUT = (By.XPATH, "//input[contains(@placeholder,'Search by name')]")
    CREATE_USER_BTN = (By.XPATH, "//button[normalize-space()='Create User']")

    # Create-user form (stable cu-* ids)
    FORM_FIRST_NAME = (By.ID, "cu-firstName")
    FORM_LAST_NAME = (By.ID, "cu-lastName")
    FORM_EMAIL = (By.ID, "cu-email")
    FORM_MOBILE = (By.ID, "cu-mobile")
    FORM_PASSWORD = (By.ID, "cu-password")
    FORM_CONFIRM_PASSWORD = (By.ID, "cu-confirmPassword")
    FORM_ROLE_TRIGGER = (By.XPATH, "//*[normalize-space()='Role']/following::button[@role='combobox'][1]")
    FORM_SUBMIT_BTN = (By.XPATH, "//button[normalize-space()='Add user']")
    FORM_CANCEL_BTN = (By.XPATH, "//button[normalize-space()='Cancel']")

    TABLE_ROWS = (By.XPATH, "//table//tbody//tr")
    TOAST = (
        By.XPATH,
        "//*[@data-slot='toast' or @role='status' or @role='alert' or contains(@class,'toast')]",
    )

    def open(self, base_url):
        self.driver.get(base_url.rstrip("/") + self.PATH)
        self.wait_for_ready()

    def wait_for_ready(self, timeout=30):
        self.wait_utils.until_condition(
            lambda driver: "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=timeout,
        )
        self.wait_utils.until_visible(self.PAGE_HEADING, timeout=timeout)

    def body_text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    OPEN_OVERLAY = (
        By.XPATH,
        "//*[@data-radix-popper-content-wrapper] | //*[@role='listbox'] | //*[@data-state='open'][@role='dialog']",
    )

    def dismiss_open_overlays(self, attempts=3):
        """Radix renders selects/popovers into a portal whose overlay swallows
        clicks on the form behind it. Close anything still open before acting."""
        for _ in range(attempts):
            if not self.is_element_visible_quick(self.OPEN_OVERLAY, timeout=2):
                return
            try:
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except WebDriverException:
                return
            sleep(0.5)

    def click_with_js_fallback(self, locator):
        try:
            self.click_element(locator)
        except WebDriverException:
            self.dismiss_open_overlays()
            self.element_utils.js_click(locator)

    # ------------------------------------------------------------------ create

    def open_create_user_form(self):
        self.click_element(self.CREATE_USER_BTN)
        self.wait_utils.until_visible(self.FORM_FIRST_NAME, timeout=20)

    def select_role(self, role):
        """Radix select: the trigger is a button[role=combobox] and the options
        render into a portal. The option list scrolls, so an option can sit
        under a sibling and swallow a plain click — scroll it into view first
        and fall back to a JS click, then to Radix's typeahead."""
        self.click_element(self.FORM_ROLE_TRIGGER)
        option = (By.XPATH, f"//*[@role='option'][normalize-space()='{role}']")
        element = self.wait_utils.until_visible(option, timeout=15)
        self.element_utils.scroll_to_element(element)

        for attempt in (
            lambda: element.click(),
            lambda: self.element_utils.js_click(option),
        ):
            try:
                attempt()
                if self.get_selected_role() == role:
                    return
            except WebDriverException:
                continue

        # Typeahead: Radix highlights the first option matching the typed text.
        trigger = self.wait_utils.until_visible(self.FORM_ROLE_TRIGGER, timeout=10)
        trigger.send_keys(role.split()[0])
        trigger.send_keys(Keys.ENTER)
        if self.get_selected_role() != role:
            raise TimeoutException(
                f"Could not select role {role!r}; trigger still reads {self.get_selected_role()!r}."
            )

    def get_selected_role(self):
        try:
            return self.get_text(self.FORM_ROLE_TRIGGER).strip()
        except WebDriverException:
            return ""

    def _select_multi_option(self, field_label, values):
        """Grades/Subjects are multi-select popovers; they are only present for
        roles that need them, so a missing control is not an error."""
        trigger = (
            By.XPATH,
            f"//*[normalize-space()='{field_label}']/following::button[1]",
        )
        if not self.is_element_visible_quick(trigger, timeout=3):
            return []
        selected = []
        try:
            self.click_element(trigger)
            for value in values:
                option = (
                    By.XPATH,
                    f"//*[@role='option' or @role='menuitemcheckbox' or @role='checkbox']"
                    f"[contains(normalize-space(),'{value}')]",
                )
                if self.is_element_visible_quick(option, timeout=5):
                    self.click_element(option)
                    selected.append(value)
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except WebDriverException:
            pass
        return selected

    def create_user(
        self,
        first_name,
        last_name,
        email,
        mobile,
        password,
        role="SME role",
        grades=("Grade 1",),
        subjects=("Mathematics",),
    ):
        """Fill and submit the create-user form. Returns the submit duration in
        seconds so the caller can assert the 2 s creation SLA."""
        self.open_create_user_form()
        self.enter_text(self.FORM_FIRST_NAME, first_name)
        self.enter_text(self.FORM_LAST_NAME, last_name)
        self.enter_text(self.FORM_EMAIL, email)
        self.enter_text(self.FORM_MOBILE, mobile)
        self.enter_text(self.FORM_PASSWORD, password)
        self.enter_text(self.FORM_CONFIRM_PASSWORD, password)
        self.select_role(role)
        self._select_multi_option("Grades", grades)
        self._select_multi_option("Subjects", subjects)

        self.dismiss_open_overlays()
        started = monotonic()
        self.click_with_js_fallback(self.FORM_SUBMIT_BTN)
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.is_element_visible_quick(self.FORM_FIRST_NAME, timeout=1),
                timeout=30,
            )
        except TimeoutException:
            raise TimeoutException(
                "Create-user form did not close after submitting. Form state: "
                f"{self.body_text()[:600]}"
            )
        return monotonic() - started

    # ------------------------------------------------------------------ lookup

    def search_user(self, value):
        """Type into the grid's search box. The box can briefly be present but
        not interactable while the table re-renders after navigation, so this
        retries and clicks to focus before typing."""
        last_error = None
        for attempt in range(3):
            try:
                search_input = self.wait_utils.until_clickable(self.SEARCH_INPUT, timeout=20)
                self.element_utils.scroll_to_element(search_input)
                search_input.click()
                search_input.send_keys(Keys.CONTROL, "a")
                search_input.send_keys(Keys.DELETE)
                search_input.send_keys(value)
                # The grid filters as you type; let the re-render settle.
                sleep(1.5)
                return
            except WebDriverException as error:
                last_error = error
                sleep(2)
        raise last_error

    def _row_for(self, identifier):
        return (
            By.XPATH,
            f"//table//tbody//tr[.//*[contains(normalize-space(),'{identifier}')]]",
        )

    def is_user_listed(self, identifier):
        return self.is_element_visible_quick(self._row_for(identifier), timeout=10)

    def get_user_code(self, identifier):
        """Read the USER-### code from the first cell of the matching row."""
        cell = (
            By.XPATH,
            f"//table//tbody//tr[.//*[contains(normalize-space(),'{identifier}')]]/td[1]",
        )
        return self.get_text(cell).strip()

    def get_user_status(self, identifier):
        """Return 'Active' / 'Inactive' from the row's status badge."""
        badge = (
            By.XPATH,
            f"//table//tbody//tr[.//*[contains(normalize-space(),'{identifier}')]]"
            "//span[normalize-space()='Active' or normalize-space()='Inactive']",
        )
        return self.get_text(badge).strip()

    def is_user_active(self, identifier):
        return self.get_user_status(identifier).casefold() == "active"

    ROW_COLUMN_USER_CODE = 1
    ROW_COLUMN_NAME = 2
    ROW_COLUMN_ROLE = 3
    ROW_COLUMN_STATUS = 6

    def get_listed_users(self):
        """Rows currently in view as {code, name, role, status} dicts."""
        users = []
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            try:
                cells = [cell.text.strip() for cell in row.find_elements(By.XPATH, "./td")]
                if len(cells) < self.ROW_COLUMN_STATUS or not cells[0]:
                    continue
                users.append(
                    {
                        "code": cells[self.ROW_COLUMN_USER_CODE - 1],
                        "name": cells[self.ROW_COLUMN_NAME - 1],
                        "role": cells[self.ROW_COLUMN_ROLE - 1],
                        "status": cells[self.ROW_COLUMN_STATUS - 1],
                    }
                )
            except WebDriverException:
                continue
        return users

    @staticmethod
    def has_role(user, role_label):
        """Exact role-token match. A substring test would wrongly treat
        'SRWG role' as holding 'RWG role'."""
        roles = {part.strip().casefold() for part in (user.get("role") or "").split(",")}
        return role_label.strip().casefold() in roles

    def _filter_trigger(self, label):
        return (
            By.XPATH,
            f"//button[@aria-haspopup='menu'][.//span[normalize-space()='{label}']]",
        )

    def filter_by_role(self, role_label):
        """Use the grid's Roles filter — searching by name misses role holders
        whose display name does not contain the role (e.g. 'SocSci SME')."""
        self.click_with_js_fallback(self._filter_trigger("Roles"))
        option = (By.XPATH, f"//*[@role='menuitem'][normalize-space()='{role_label}']")
        self.wait_utils.until_visible(option, timeout=15)
        self.click_with_js_fallback(option)
        self.dismiss_open_overlays()
        sleep(2)

    def find_users_by_role(self, role_label, search_term=None):
        """All users holding role_label, enumerated via the Roles filter."""
        if search_term is not None:
            self.search_user(search_term)
        else:
            self.filter_by_role(role_label)
        return [user for user in self.get_listed_users() if self.has_role(user, role_label)]

    # ------------------------------------------------------------- activation

    def _status_toggle(self, identifier):
        return (
            By.XPATH,
            f"//table//tbody//tr[.//*[contains(normalize-space(),'{identifier}')]]"
            "//button[starts-with(@aria-label,'Deactivate') or starts-with(@aria-label,'Activate')]",
        )

    # Deactivation opens a native <dialog>, not a role="dialog" div, and the
    # reason field is mandatory before the confirm button will submit.
    CONFIRM_MODAL = (By.XPATH, "//dialog[@aria-modal='true']")
    CONFIRM_MODAL_REASON = (By.XPATH, "//dialog[@aria-modal='true']//textarea")
    CONFIRM_MODAL_ACTION = (
        By.XPATH,
        "//dialog[@aria-modal='true']//button["
        "normalize-space()='Deactivate' or normalize-space()='Activate'"
        " or normalize-space()='Confirm' or normalize-space()='Yes']",
    )

    def toggle_user_status(self, identifier, reason="Automated lifecycle verification"):
        """Flip the row's Active/Inactive switch, clear the confirmation modal,
        and wait for aria-pressed to actually change rather than sleeping."""
        toggle = self.wait_utils.until_visible(self._status_toggle(identifier), timeout=20)
        before = toggle.get_attribute("aria-pressed")
        toggle.click()
        self.confirm_if_prompted(reason)
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*self._status_toggle(identifier)).get_attribute(
                    "aria-pressed"
                )
                != before,
                timeout=20,
            )
        except (TimeoutException, WebDriverException):
            pass
        return before

    def confirm_if_prompted(self, reason="Automated lifecycle verification"):
        """Complete the confirmation modal if one opened. Returns True when a
        modal was handled."""
        if not self.is_element_visible_quick(self.CONFIRM_MODAL, timeout=5):
            return False
        if self.is_element_visible_quick(self.CONFIRM_MODAL_REASON, timeout=3):
            self.enter_text(self.CONFIRM_MODAL_REASON, reason)
        self.click_with_js_fallback(self.CONFIRM_MODAL_ACTION)
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.is_element_visible_quick(self.CONFIRM_MODAL, timeout=1),
                timeout=20,
            )
        except TimeoutException:
            raise TimeoutException(
                "Confirmation modal stayed open after confirming. Modal text: "
                f"{self.get_text(self.CONFIRM_MODAL)[:400]}"
            )
        return True

    def get_toast_message(self, timeout=10):
        if not self.is_element_visible_quick(self.TOAST, timeout=timeout):
            return ""
        try:
            return self.get_text(self.TOAST).strip()
        except WebDriverException:
            return ""
