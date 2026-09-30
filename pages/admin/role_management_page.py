from time import sleep

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
    CREATE_RELATIVE_URL = "/admin/role/create"

    # Create Role form. The three text fields carry stable ids, and every
    # module checkbox is "mod-<n>" - a role must own at least one module before
    # the form will submit.
    ROLE_NAME_INPUT = (By.ID, "roleName")
    ROLE_CODE_INPUT = (By.ID, "roleCode")
    ROLE_DESCRIPTION_INPUT = (By.ID, "roleDescription")
    FIRST_MODULE_CHECKBOX = (By.ID, "mod-1")
    CREATE_ROLE_BUTTON = (By.XPATH, "//button[normalize-space()='Create Role']")

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

    def get_visible_roles(self):
        """[(role_id, role_name)] for every row currently rendered.

        The grid's first cell is the id (`Role-7`) and the second its name
        ("Testing123"), so this is what any assertion about filtering should be
        written against - a bare row *count* cannot tell "the filter matched 10
        roles" apart from "the filter never applied and this is page 1 of 10".
        """
        roles = []
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            cells = [cell.text.strip() for cell in row.find_elements(By.XPATH, "./td")]
            if len(cells) >= 2:
                roles.append((cells[0], cells[1]))
        return roles

    def search_roles_and_settle(self, search_term, timeout=15):
        """Search, wait for the grid to actually reflect the term, return the rows.

        The filter is debounced, so reading straight after typing can still see
        the unfiltered page. That is how a search was measured as "10 rows of
        10" and read as "search is broken", when the grid simply had not
        repainted yet.

        Settled means every visible row matches the term; a term that matches
        nothing settles immediately on an empty grid.
        """
        self.search_role(search_term)
        term = (search_term or "").casefold()

        def settled(driver):
            if not term:
                return True
            return all(
                term in f"{role_id} {role_name}".casefold()
                for role_id, role_name in self.get_visible_roles()
            )

        try:
            self.wait_utils.until_condition(settled, timeout=timeout)
        except (TimeoutException, WebDriverException):
            # Fall through and let the caller assert on what is actually there.
            pass
        return self.get_visible_roles()

    def get_toast_message(self):
        try:
            return self.driver.find_element(*self.TOAST_MESSAGE).text.strip()
        except NoSuchElementException:
            return ""

    ROWS_PER_PAGE_TRIGGER = (
        By.XPATH,
        "//*[contains(normalize-space(),'Rows per page')]/following::button[@role='combobox'][1]",
    )

    def set_rows_per_page(self, size=100):
        """Best-effort: show `size` rows so the whole role list fits on one page.

        Returns True when the control accepted the size. The grid defaults to
        10 rows, newest first, and throwaway roles created by earlier runs now
        push the seeded Role-1..Role-3 off the first page entirely.
        """
        if not self.is_element_visible_quick(self.ROWS_PER_PAGE_TRIGGER, timeout=5):
            return False
        try:
            self.click_element(self.ROWS_PER_PAGE_TRIGGER)
            option = (By.XPATH, f"//*[@role='option'][normalize-space()='{size}']")
            if not self.is_element_visible_quick(option, timeout=5):
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                return False
            self.click_element(option)
            sleep(2)
            return True
        except WebDriverException:
            return False

    # --- Per-role Active toggle ---
    def _role_row_xpath(self, role_id):
        """XPath for one role's row, matched on a whole cell.

        Two things made the old contains() lookup read the wrong row:

        - Role IDs nest. 'Role-1' also matches 'Role-10'..'Role-13', and the
          grid lists the newest role first, so the first hit was a throwaway
          role. That is how 'Role-1' was reported inactive while the API had
          Admin role (id 1) as isActive=True all along.
        - The grid paginates at 10 rows. With 13 roles present, Role-1..Role-3
          are not on the first page at all, so no lookup could find them.

        So the page size is widened first, then the ID is matched against a
        whole cell.
        """
        exact = f"//table//tbody/tr[./td[normalize-space()='{role_id}']]"
        try:
            if self.driver.find_elements(By.XPATH, exact):
                return exact
            # Not in view - it may simply be on a later page.
            if self.set_rows_per_page(100):
                self.driver.find_elements(By.XPATH, exact)
        except WebDriverException:
            pass
        return exact

    def role_row_locator(self, role_id):
        """Locator for one role's grid row, for presence checks that must not
        raise the way _role_toggle does when the row is absent."""
        return (By.XPATH, self._role_row_xpath(role_id))

    def _role_toggle(self, role_id):
        """Return the toggle control living in the row whose first cell is role_id."""
        row_xpath = self._role_row_xpath(role_id)
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

    def is_role_system(self, role_id):
        """True when the role is one the product protects from deactivation.

        The grid renders the Active toggle as
        `disabled: isSystemRole || isPending`, and isPending only holds while a
        status PATCH is in flight, so a toggle that is disabled at rest is a
        system role. The API confirms it (`isSystemRole` on /admin/rbac/roles);
        the DOM is the only signal the page itself exposes.
        """
        return not self.is_role_toggle_editable(role_id)

    def find_role_id_by_name(self, role_name):
        """Return the Role-N id for a role's display name, or None if absent."""
        self.search_role(role_name)
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            cells = [cell.text.strip() for cell in row.find_elements(By.XPATH, "./td")]
            if any(role_name.casefold() == cell.casefold() for cell in cells):
                return cells[0]
        return None

    def create_custom_role(self, role_name, role_code, description):
        """Create a non-system role and return its Role-N id.

        Every seeded role (Role-1..Role-8) is a system role, so a test that
        needs an *editable* Active toggle has to bring its own role: this is
        the only way to reach the toggle contract from the UI.
        """
        self.driver.get(ReadConfig.get_base_url().rstrip("/") + self.CREATE_RELATIVE_URL)
        self.wait_for_application_ready()
        self.enter_text(self.ROLE_NAME_INPUT, role_name)
        self.enter_text(self.ROLE_CODE_INPUT, role_code)
        self.enter_text(self.ROLE_DESCRIPTION_INPUT, description)
        # A role with no module assigned is rejected by the form.
        self.click_element(self.FIRST_MODULE_CHECKBOX)
        self.pause_before_action()
        self.click_element(self.CREATE_ROLE_BUTTON)
        # A successful create routes back to the grid.
        self.wait_utils.until_condition(
            lambda driver: driver.current_url.rstrip("/").endswith(self.RELATIVE_URL),
            timeout=30,
        )
        self.wait_for_application_ready()
        role_id = self.find_role_id_by_name(role_name)
        if role_id is None:
            raise TimeoutException(
                f"Created role {role_name!r} but it never appeared in the Role Management grid."
            )
        return role_id

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
