"""Admin > Workflow & SLA Configuration (/admin/workflow-config).

The screen that defines how review work moves and how long each stage may take:
one grid per workflow (Teacher, SME, L1, L2), a row per node, and per-node SLA
timers. Nothing in M2 had ever opened it - the framework knew the route existed
only as a sidebar label ("Workflow" truncates to "Workfl") and never visited it.

Two things shape this page object:

- **The tabs do not share a column layout.** Teacher and SME rows carry the full
  set - Node Code, Reviewer Role, retries, reviewer and approval counts, then
  four SLA timers. The L1 and L2 tabs carry the timers alone, with no node code
  or role. So rows are read against *that tab's own* headers rather than fixed
  indices, and a caller asking for a column a tab does not have gets "" back.
- **Editing is inline, not a dialog.** The row's kebab offers Edit, which swaps
  four numeric inputs into the row, keyed `sla-<nodeId>-<field>`, alongside
  Cancel and Save.

These values drive the live review workflow - `Max Approvals Required` on a PIT
node is the 3/3 quorum M1 depends on - so everything here reads by default and
`edit_sla_field` exists to be used with a restore.
"""

from time import sleep

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class WorkflowConfigPage(BasePage):
    """The Workflow & SLA Configuration grid."""

    PATH = "/admin/workflow-config"

    TABS = ("Teacher Workflow", "SME Workflow", "L1 Workflow", "L2 Workflow")
    # The tabs that carry a full node row; L1/L2 render timers only.
    NODE_TABS = ("Teacher Workflow", "SME Workflow")

    EXPECTED_COLUMNS = (
        "Node Code",
        "Reviewer Role",
        "Max Retries",
        "Max Reviewers",
        "Max Approvals Required",
        "SLA hrs",
        "Escalation Trigger for Admin(hrs)",
        "Reminder Frequency for Role(hrs)",
        "Max Extension (hrs)",
    )

    # The four editable timers, by the suffix of their input id.
    SLA_FIELDS = (
        "slaHours",
        "escalationTriggerHrs",
        "reminderFrequencyHrs",
        "maxExtensionHrs",
    )

    PAGE_HEADER = (
        By.XPATH,
        "//*[self::h1 or self::h2][contains(normalize-space(),'Workflow')]",
    )
    SEARCH_INPUT = (By.XPATH, "//input[contains(@placeholder,'Search by Node Code')]")
    ROLE_FILTER = (By.XPATH, "//button[contains(normalize-space(),'All Roles')]")
    TABLE = (By.XPATH, "//table")
    TABLE_HEADERS = (By.XPATH, "//table//th")
    TABLE_ROWS = (By.XPATH, "//table//tbody/tr[count(td)>1]")

    ROW_KEBAB = ".//button[@data-slot='dropdown-menu-trigger'] | .//td[last()]//button"
    ACTION_EDIT = (By.XPATH, "//*[@role='menuitem'][normalize-space()='Edit']")
    SAVE_BTN = (By.XPATH, "//button[normalize-space()='Save']")
    CANCEL_BTN = (By.XPATH, "//button[normalize-space()='Cancel']")

    # ------------------------------------------------------------------ open

    def open(self, base_url):
        self.driver.get(base_url.rstrip("/") + self.PATH)
        self.wait_for_ready()

    def wait_for_ready(self, timeout=45, attempts=2):
        """Wait for the grid, refreshing a stalled load rather than failing."""
        last_error = None
        for attempt in range(attempts):
            try:
                self.wait_utils.until_condition(
                    lambda driver: "loading"
                    not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
                    timeout=timeout,
                )
                self.wait_utils.until_visible(self.PAGE_HEADER, timeout=timeout)
                self.wait_utils.until_visible(self.TABLE, timeout=timeout)
                return
            except TimeoutException as error:
                last_error = error
                if attempt < attempts - 1:
                    self.driver.refresh()
                    sleep(3)
        raise TimeoutException(
            f"Workflow & SLA Configuration did not load after {attempts} attempts."
        ) from last_error

    def is_on_page(self):
        return self.is_element_visible_quick(self.PAGE_HEADER, timeout=10)

    def get_header_text(self):
        try:
            return self.get_text(self.PAGE_HEADER).strip()
        except (TimeoutException, WebDriverException):
            return ""

    # ------------------------------------------------------------------ tabs

    @staticmethod
    def _tab_locator(label):
        return (
            By.XPATH,
            f"//*[@role='tab'][starts-with(normalize-space(),'{label.split()[0]}')]",
        )

    def switch_tab(self, label):
        locator = self._tab_locator(label)
        element = self.wait_utils.until_visible(locator, timeout=20)
        self.driver.execute_script("arguments[0].click();", element)
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*locator).get_attribute("aria-selected")
                == "true",
                timeout=15,
            )
        except TimeoutException:
            raise TimeoutException(f"Workflow tab {label!r} did not become selected.")
        sleep(1.5)

    def is_tab_present(self, label):
        return self.is_element_visible_quick(self._tab_locator(label), timeout=5)

    # ----------------------------------------------------------------- rows

    def get_table_headers(self):
        return [h.text.strip() for h in self.driver.find_elements(*self.TABLE_HEADERS) if h.text.strip()]

    def missing_columns(self):
        headers = self.get_table_headers()
        return [column for column in self.EXPECTED_COLUMNS if column not in headers]

    def get_rows(self):
        """Every node row on the current tab, keyed by that tab's own headers.

        The L1/L2 tabs render fewer columns than Teacher/SME, so a fixed index
        would read the wrong value on at least one tab. Columns a tab does not
        carry come back as "".
        """
        headers = self.get_table_headers()
        rows = []
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            try:
                cells = [c.text.strip() for c in row.find_elements(By.XPATH, "./td")]
            except WebDriverException:
                continue
            values = {}
            for index, header in enumerate(headers):
                values[header] = cells[index] if index < len(cells) else ""
            values["_cells"] = cells
            rows.append(values)
        return rows

    def get_row_count(self):
        return len(self.driver.find_elements(*self.TABLE_ROWS))

    def get_node_codes(self):
        return [r.get("Node Code", "") for r in self.get_rows() if r.get("Node Code")]

    @staticmethod
    def as_number(value):
        """A cell's integer value, or None when it holds no number."""
        digits = "".join(ch if (ch.isdigit() or ch == "-") else " " for ch in str(value)).split()
        try:
            return int(digits[0]) if digits else None
        except ValueError:
            return None

    # --------------------------------------------------------------- search

    def search_node(self, term):
        """Type into the node search box and commit it.

        Cleared with Ctrl+A / Delete and committed with Enter, the same way
        AdminPortalPage.search drives every other admin grid. Setting `value`
        through JavaScript does not work here: React never sees the change, so
        the grid keeps rendering its unfiltered rows and the search looks
        broken when nothing was ever typed as far as the app is concerned.
        """
        box = self.wait_utils.until_clickable(self.SEARCH_INPUT, timeout=20)
        self.element_utils.scroll_to_element(box)
        box.click()
        box.send_keys(Keys.CONTROL, "a")
        box.send_keys(Keys.DELETE)
        if term:
            box.send_keys(term)
        box.send_keys(Keys.ENTER)
        sleep(2)

    def search_and_settle(self, term, timeout=15):
        """Search, then wait for the grid to reflect the term, and return rows.

        The grid debounces, so reading straight after typing can still show the
        unfiltered page - the same trap that made the Role Management search
        look broken when it was merely slow.
        """
        self.search_node(term)
        needle = (term or "").casefold()

        def settled(driver):
            if not needle:
                return True
            return all(
                needle in " ".join(r.get("_cells", [])).casefold() for r in self.get_rows()
            )

        try:
            self.wait_utils.until_condition(settled, timeout=timeout)
        except (TimeoutException, WebDriverException):
            pass
        return self.get_rows()

    # ----------------------------------------------------------- inline edit

    def _row_element(self, node_code=None, index=0):
        rows = self.driver.find_elements(*self.TABLE_ROWS)
        if not rows:
            raise TimeoutException("The workflow grid holds no rows to edit.")
        if node_code is None:
            return rows[index]
        for row in rows:
            if any(
                c.text.strip() == node_code for c in row.find_elements(By.XPATH, "./td")
            ):
                return row
        raise TimeoutException(f"No workflow row carries node code {node_code!r}.")

    def open_row_editor(self, node_code=None, index=0):
        """Put one row into inline edit mode."""
        row = self._row_element(node_code, index)
        triggers = row.find_elements(By.XPATH, self.ROW_KEBAB)
        if not triggers:
            raise TimeoutException("That workflow row offers no Actions control.")
        self.element_utils.scroll_to_element(triggers[-1])
        self.pause_before_action()
        triggers[-1].click()
        self.wait_utils.until_visible(self.ACTION_EDIT, timeout=15)
        self.click_element(self.ACTION_EDIT)
        self.wait_utils.until_condition(
            lambda driver: bool(self._sla_inputs()), timeout=20
        )

    def _sla_inputs(self):
        return self.driver.find_elements(
            By.XPATH, "//input[contains(@id,'sla-') and @type='number']"
        )

    def _field_locator(self, field):
        return (By.XPATH, f"//input[contains(@id,'{field}') and @type='number']")

    def is_editor_open(self):
        return bool(self._sla_inputs())

    def get_editable_fields(self):
        """Which SLA timers this row's editor exposes, and their current values."""
        values = {}
        for field in self.SLA_FIELDS:
            elements = self.driver.find_elements(*self._field_locator(field))
            if elements:
                values[field] = elements[0].get_attribute("value")
        return values

    def set_field(self, field, value):
        element = self.wait_utils.until_visible(self._field_locator(field), timeout=15)
        self.element_utils.scroll_to_element(element)
        element.clear()
        element.send_keys(str(value))
        return element.get_attribute("value")

    def save_editor(self):
        self.pause_before_action()
        self.click_element(self.SAVE_BTN)
        try:
            self.wait_utils.until_condition(
                lambda driver: not self._sla_inputs(), timeout=25
            )
        except TimeoutException:
            pass
        sleep(2)

    def cancel_editor(self):
        try:
            if self.is_element_visible_quick(self.CANCEL_BTN, timeout=5):
                self.click_element(self.CANCEL_BTN)
                self.wait_utils.until_condition(
                    lambda driver: not self._sla_inputs(), timeout=15
                )
        except (TimeoutException, WebDriverException):
            pass
        sleep(1)

    def has_role_filter(self):
        return self.is_element_visible_quick(self.ROLE_FILTER, timeout=5)
