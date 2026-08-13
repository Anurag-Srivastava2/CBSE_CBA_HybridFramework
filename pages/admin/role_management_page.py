from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

from pages.admin.admin_portal_page import AdminPortalPage
from utilities.read_config import ReadConfig


class RoleManagementPage(AdminPortalPage):
    """Role Management grid: search, per-role Active toggles, and pagination.

    Inherits the admin portal's navigation/search helpers so the section is
    reached the same way as every other M2 admin screen.
    """

    DEFAULT_ROLE_COUNT = 8

    PAGE_HEADERS = [
        (By.XPATH, "//*[self::h1 or self::h2 or self::h3][normalize-space()='Role Management']"),
        (By.XPATH, "//*[contains(normalize-space(),'Role Management')]"),
    ]
    # The empty state renders as a single full-width cell ("No Data to display"),
    # so require more than one cell to count a row as actual data.
    TABLE_ROWS = (By.XPATH, "//table//tbody/tr[count(td) > 1]")
    EMPTY_STATE = (By.XPATH, "//table//tbody/tr/td[@colspan]")
    TOAST_MESSAGE = (
        By.XPATH,
        "//*[contains(@class,'toast') or @role='status' or @role='alert']",
    )
    ROWS_PER_PAGE = [
        (By.XPATH, "//*[contains(normalize-space(),'Rows per page')]"),
    ]
    NEXT_PAGE_BUTTONS = [
        (By.XPATH, "//button[@aria-label='Go to next page']"),
        (By.XPATH, "//button[.//*[local-name()='svg' and contains(@data-testid,'chevron_right')]]"),
        (By.XPATH, "(//table/following::button)[last()]"),
    ]

    RELATIVE_URL = "/admin/role"

    def open(self):
        """Go straight to the Role Management URL.

        The sidebar labels are CSS-truncated ("Workfl", "Notifi"), so matching
        the section by visible text is unreliable here - only "Roles" renders in
        full, and never the "Role Management" heading the page itself uses.
        """
        self.driver.get(ReadConfig.get_base_url().rstrip("/") + self.RELATIVE_URL)
        self.wait_for_application_ready()
        self.wait_utils.until_condition(lambda driver: self.is_on_page(), timeout=30)
        return self

    def is_on_page(self):
        return any(self.is_element_visible_quick(locator, timeout=2) for locator in self.PAGE_HEADERS)

    def search_role(self, search_term):
        self.search(search_term)

    def clear_search(self):
        self.search("")

    def get_table_row_count(self):
        return len(self.driver.find_elements(*self.TABLE_ROWS))

    def get_toast_message(self):
        try:
            return self.driver.find_element(*self.TOAST_MESSAGE).text.strip()
        except NoSuchElementException:
            return ""

    # --- Per-role Active toggle ---
    def _role_toggle(self, role_id):
        """Return the toggle control living in the row whose first cell is role_id."""
        row_xpath = (
            f"//table//tbody/tr[.//td[contains(normalize-space(),'{role_id}')]]"
        )
        for suffix in (
            "//input[@type='checkbox']",
            "//*[@role='switch']",
            "//button[contains(@class,'switch') or contains(@class,'toggle')]",
        ):
            elements = self.driver.find_elements(By.XPATH, row_xpath + suffix)
            if elements:
                return elements[0]
        raise NoSuchElementException(f"No Active toggle found in the row for {role_id}.")

    def is_role_active(self, role_id):
        """True when the row's Active toggle is on.

        Checkboxes report state as a DOM property (is_selected), not an
        attribute, while headless-UI style buttons use aria-checked - reading
        get_attribute('checked') alone misses both cases.
        """
        toggle = self._role_toggle(role_id)
        aria_checked = (toggle.get_attribute("aria-checked") or "").casefold()
        if aria_checked in ("true", "false"):
            return aria_checked == "true"
        return toggle.is_selected()

    def is_role_toggle_editable(self, role_id):
        """False when the Active control is rendered read-only for this user."""
        toggle = self._role_toggle(role_id)
        return toggle.get_attribute("disabled") is None and toggle.is_enabled()

    def toggle_role_status(self, role_id):
        """Flip one role's Active toggle and wait for the state to actually change."""
        if not self.is_role_toggle_editable(role_id):
            raise TimeoutException(
                f"The Active toggle for {role_id} is disabled - this build renders "
                "the column read-only, so it cannot be switched from the UI."
            )
        before = self.is_role_active(role_id)
        toggle = self._role_toggle(role_id)
        # The real input is often visually hidden behind a styled label, so a
        # scripted click is more reliable than a native one here.
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", toggle)
        self.wait_utils.until_condition(
            lambda driver: self.is_role_active(role_id) != before,
            timeout=20,
        )
        return not before

    def ensure_all_roles_active(self, role_count=DEFAULT_ROLE_COUNT):
        """Activate any of Role-1..Role-N that are currently off.

        Returns the roles it had to switch on, so a test can report what state
        the environment was left in rather than silently normalising it.
        """
        activated = []
        for index in range(1, role_count + 1):
            role_id = f"Role-{index}"
            if not self.is_role_active(role_id):
                self.toggle_role_status(role_id)
                activated.append(role_id)
        return activated

    def has_next_page_control(self):
        return any(
            self.is_element_visible_quick(locator, timeout=2)
            for locator in self.NEXT_PAGE_BUTTONS
        )

    def has_rows_per_page_control(self):
        return any(
            self.is_element_visible_quick(locator, timeout=2)
            for locator in self.ROWS_PER_PAGE
        )
