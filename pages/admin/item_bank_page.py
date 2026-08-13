import re
from pathlib import Path
from time import sleep, time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class ItemBankPage(BasePage):
    """Admin > Item Bank Overview (/admin/itembank).

    Columns: (select) | Item ID | Item | Grade | Subject & Chapter | Typology |
    Marks | Bloom's Level | Difficulty | Competency | Learning Outcome | Type |
    Submitted By | View.

    Two kinds of <tr> live in the tbody: data rows carry data-slot='tbody-row',
    and the accordion detail that the View button opens is a separate row
    carrying data-expanded-content='true'. Every row helper filters on the
    former so an expanded item never inflates the row count.
    """

    PATH = "/admin/itembank"

    COLUMN_SELECT = 1
    COLUMN_ITEM_ID = 2
    COLUMN_ITEM = 3
    COLUMN_GRADE = 4
    COLUMN_SUBJECT_CHAPTER = 5
    COLUMN_TYPOLOGY = 6
    COLUMN_MARKS = 7
    COLUMN_BLOOMS = 8
    COLUMN_DIFFICULTY = 9
    COLUMN_COMPETENCY = 10
    COLUMN_LEARNING_OUTCOME = 11
    COLUMN_TYPE = 12
    COLUMN_SUBMITTED_BY = 13
    COLUMN_VIEW = 14

    EXPECTED_COLUMNS = (
        "Item ID",
        "Item",
        "Grade",
        "Subject & Chapter",
        "Typology",
        "Marks",
        "Bloom's Level",
        "Difficulty",
        "Competency",
        "Learning Outcome",
        "Type",
        "View",
    )

    # The five metric cards above the grid, in render order.
    KPI_LABELS = (
        "Total Items in IB1",
        "Total Items in IB2",
        "Items in Active Pipeline",
        "Items Disabled",
        "Items Flagged for Retirement",
    )

    TAB_LABELS = ("All", "IB1", "IB2", "Retired")

    # Header of the CSV the Export button produces. Its "Item ID" column holds
    # the internal numeric row id (3355), not the displayed item code.
    EXPORT_COLUMNS = (
        "Item ID",
        "Bank",
        "Question",
        "Grade",
        "Subject",
        "Chapter",
        "Typology",
        "Marks",
        "Bloom Level",
        "Difficulty",
        "Submitted By",
        "Last Updated",
    )

    # Filters is a toggle that reveals inline dropdowns rather than a modal.
    FILTER_LABELS = ("Grade", "Subject", "Chapter", "Typology", "Bloom's Level", "Difficulty")

    # The sidebar carries a second, hidden 'Item Bank Overview' label, so the
    # header must be pinned to the <h1> the page renders.
    PAGE_HEADER = (By.XPATH, "//h1[normalize-space()='Item Bank Overview']")
    SUBTEXT = (
        By.XPATH,
        "//*[contains(@class,'subtitle')][contains(normalize-space(),'Comprehensive repository overview')]",
    )

    FILTERS_BTN = (By.XPATH, "//button[normalize-space()='Filters']")
    EXPORT_BTN = (By.XPATH, "//button[normalize-space()='Export']")

    TABLE = (By.XPATH, "//table")
    TABLE_HEADERS = (By.XPATH, "//table//th")
    TABLE_ROWS = (By.XPATH, "//table//tbody//tr[@data-slot='tbody-row']")
    EXPANDED_ROW = (By.XPATH, "//table//tbody//tr[@data-expanded-content='true']")

    MASTER_CHECKBOX = (By.XPATH, "//table//thead//input[@type='checkbox']")
    ROW_CHECKBOXES = (By.XPATH, "//table//tbody//input[@type='checkbox']")
    SELECTION_SUMMARY = (By.XPATH, "//*[contains(normalize-space(),'row(s) selected')]")

    RETIRE_ITEM_BTN = (
        By.XPATH,
        "//table//tbody//tr[@data-expanded-content='true']//button[normalize-space()='Retire Item']",
    )
    # Retire Item raises an inline Cancel/Retire confirmation that is not a
    # role='dialog', so it can only be found by its button label. The exact
    # match on 'Retire' is what separates the confirmation from the trigger.
    RETIRE_CONFIRM_BTN = (
        By.XPATH,
        "//button[normalize-space()='Retire' or normalize-space()='Confirm Retire'"
        " or normalize-space()='Confirm' or normalize-space()='Yes']",
    )
    RETIRE_CANCEL_BTN = (By.XPATH, "//button[normalize-space()='Cancel']")
    # Retirement demands a written reason; Retire is inert until it is supplied.
    RETIRE_REASON_INPUT = (By.XPATH, "//textarea[contains(@placeholder,'reason for retiring')]")
    RETIRE_CONFIRM_PROMPT = (
        By.XPATH,
        "//*[contains(normalize-space(),'This action cannot be undone')]"
        "[not(.//*[contains(normalize-space(),'This action cannot be undone')])]",
    )

    # Both summaries must be pinned to the innermost node; their containers also
    # hold the pagination text, which would corrupt any number parsed from them.
    SHOWING_SUMMARY = (
        By.XPATH,
        "//*[starts-with(normalize-space(),'Showing ')]"
        "[not(.//*[starts-with(normalize-space(),'Showing ')])]",
    )
    ROWS_PER_PAGE = (
        By.XPATH,
        "//*[contains(normalize-space(),'Rows per page')]/following::button[@role='combobox'][1]",
    )
    NEXT_PAGE_BTN = (By.XPATH, "//button[@aria-label='Next page']")
    PREV_PAGE_BTN = (By.XPATH, "//button[@aria-label='Previous page']")
    PAGE_INDICATOR = (
        By.XPATH,
        "//*[starts-with(normalize-space(),'Page ')][not(.//*[starts-with(normalize-space(),'Page ')])]",
    )

    TOAST = (
        By.XPATH,
        "//*[@data-slot='toast' or @role='status' or @role='alert' or contains(@class,'toast')]",
    )

    # ------------------------------------------------------------------- setup

    def open(self, base_url):
        self.driver.get(base_url.rstrip("/") + self.PATH)
        self.wait_for_ready()

    def wait_for_ready(self, timeout=30):
        self.wait_utils.until_condition(
            lambda driver: "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=timeout,
        )
        self.wait_utils.until_visible(self.PAGE_HEADER, timeout=timeout)
        self.wait_utils.until_visible(self.TABLE, timeout=timeout)

    def body_text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def is_on_page(self):
        return self.is_element_visible_quick(self.PAGE_HEADER, timeout=15) and self.is_element_visible_quick(
            self.SUBTEXT, timeout=10
        )

    def dismiss_overlays(self):
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            sleep(0.5)
        except WebDriverException:
            pass

    def click_resilient(self, locator):
        """Radix leaves click-swallowing overlays behind; clear one and retry."""
        try:
            self.click_element(locator)
        except WebDriverException:
            self.dismiss_overlays()
            self.element_utils.js_click(locator)

    # --------------------------------------------------------------- kpi cards

    @staticmethod
    def _kpi_value_locator(label):
        return (
            By.XPATH,
            f"//*[contains(@class,'statsLabel')][normalize-space()='{label}']"
            f"/following-sibling::*[contains(@class,'statsValue')]",
        )

    def is_kpi_visible(self, label):
        return self.is_element_visible_quick(self._kpi_value_locator(label), timeout=10)

    def missing_kpis(self):
        return [label for label in self.KPI_LABELS if not self.is_kpi_visible(label)]

    def get_kpi_value(self, label):
        """Numeric value of a metric card, or -1 when it is not a number."""
        try:
            raw = self.get_text(self._kpi_value_locator(label)).strip()
        except (TimeoutException, WebDriverException):
            return -1
        digits = "".join(character for character in raw if character.isdigit())
        return int(digits) if digits else -1

    def get_all_kpi_values(self):
        return {label: self.get_kpi_value(label) for label in self.KPI_LABELS}

    # ------------------------------------------------------------------- tabs

    @staticmethod
    def _tab_locator(label):
        return (
            By.XPATH,
            f"//button[contains(@class,'tabBtn')][starts-with(normalize-space(),'{label}')]",
        )

    def is_tab_visible(self, label):
        return self.is_element_visible_quick(self._tab_locator(label), timeout=10)

    def missing_tabs(self):
        return [label for label in self.TAB_LABELS if not self.is_tab_visible(label)]

    def get_tab_badge_count(self, label):
        """'IB1 48' -> 48. Returns -1 when the tab carries no badge."""
        try:
            raw = self.get_text(self._tab_locator(label)).strip()
        except (TimeoutException, WebDriverException):
            return -1
        digits = "".join(character if character.isdigit() else " " for character in raw).split()
        return int(digits[-1]) if digits else -1

    def is_tab_active(self, label):
        try:
            classes = self.driver.find_element(*self._tab_locator(label)).get_attribute("class") or ""
        except WebDriverException:
            return False
        return "tabBtnActive" in classes

    def switch_tab(self, label):
        """Activate a quick-filter tab and wait for the grid to settle."""
        locator = self._tab_locator(label)
        self.dismiss_overlays()
        self.click_resilient(locator)
        try:
            self.wait_utils.until_condition(lambda driver: self.is_tab_active(label), timeout=20)
        except TimeoutException:
            raise TimeoutException(f"Tab {label!r} did not become the active tab after clicking it.")
        sleep(2)

    # ------------------------------------------------------------------ table

    def get_table_headers(self):
        return [header.text.strip() for header in self.driver.find_elements(*self.TABLE_HEADERS) if header.text.strip()]

    def missing_columns(self):
        headers = self.get_table_headers()
        return [column for column in self.EXPECTED_COLUMNS if column not in headers]

    def get_rows(self):
        """Data rows only — the expanded-detail row is a sibling <tr> and the
        empty state renders a placeholder with no Item ID."""
        rows = []
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            try:
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < self.COLUMN_ITEM_ID:
                    continue
                if not cells[self.COLUMN_ITEM_ID - 1].text.strip():
                    continue
                rows.append(row)
            except WebDriverException:
                continue
        return rows

    def get_table_row_count(self):
        return len(self.get_rows())

    def _column_values(self, column_index):
        values = []
        for row in self.get_rows():
            try:
                values.append(row.find_elements(By.XPATH, "./td")[column_index - 1].text.strip())
            except (IndexError, WebDriverException):
                continue
        return values

    def get_item_ids_in_view(self):
        return self._column_values(self.COLUMN_ITEM_ID)

    def get_row_ids_in_view(self):
        """Internal numeric row ids, read off the expand control's aria-label
        ('Expand item 3355'). These are what the CSV export writes out."""
        row_ids = []
        for row in self.get_rows():
            toggles = row.find_elements(
                By.XPATH,
                ".//button[starts-with(@aria-label,'Expand item')"
                " or starts-with(@aria-label,'Collapse item')]",
            )
            if not toggles:
                continue
            try:
                row_ids.append((toggles[0].get_attribute("aria-label") or "").split()[-1])
            except (IndexError, WebDriverException):
                continue
        return row_ids

    def get_types_in_view(self):
        return self._column_values(self.COLUMN_TYPE)

    def get_row_text(self):
        return [row.text.strip() for row in self.get_rows()]

    def get_item_id_from_row(self, row_index=1):
        """Item ID of the 1-based nth data row, or '' when the grid is empty."""
        item_ids = self.get_item_ids_in_view()
        if len(item_ids) < row_index:
            return ""
        return item_ids[row_index - 1]

    def is_item_present_in_table(self, item_id):
        return item_id in self.get_item_ids_in_view()

    def get_row_id_for_item(self, item_id):
        """Internal numeric id behind a displayed Item ID — this is what the
        retirement modal names."""
        row = self._row_for_item(item_id)
        toggles = row.find_elements(
            By.XPATH,
            ".//button[starts-with(@aria-label,'Expand item')"
            " or starts-with(@aria-label,'Collapse item')]",
        )
        if not toggles:
            return ""
        return (toggles[0].get_attribute("aria-label") or "").split()[-1]

    def find_items_matching(self, markers):
        """Item IDs on the current page whose question text carries one of the
        given markers. Used to pick automation residue for destructive checks
        instead of mutating a seeded item."""
        matches = []
        for row in self.get_rows():
            try:
                cells = row.find_elements(By.XPATH, "./td")
                item_id = cells[self.COLUMN_ITEM_ID - 1].text.strip()
                question = cells[self.COLUMN_ITEM - 1].text
            except (IndexError, WebDriverException):
                continue
            if any(marker.casefold() in question.casefold() for marker in markers):
                matches.append(item_id)
        return matches

    def get_showing_summary(self):
        """'Showing 1-10 of 67 items' — the grid's own record count."""
        try:
            return self.get_text(self.SHOWING_SUMMARY).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def get_total_item_count(self):
        """Total behind the current tab, parsed from the Showing summary.

        Matched on the 'of N items' clause specifically — the range prefix
        ('Showing 1-10') carries numbers of its own.
        """
        match = re.search(r"of\s+([\d,]+)\s+item", self.get_showing_summary())
        return int(match.group(1).replace(",", "")) if match else -1

    # --------------------------------------------------------- expanded item

    def _row_for_item(self, item_id):
        for row in self.get_rows():
            try:
                if row.find_elements(By.XPATH, "./td")[self.COLUMN_ITEM_ID - 1].text.strip() == item_id:
                    return row
            except (IndexError, WebDriverException):
                continue
        raise TimeoutException(f"Item {item_id!r} is not present in the current grid view.")

    def expand_item_view(self, item_id):
        """Open the accordion detail for an item via its View control."""
        row = self._row_for_item(item_id)
        toggle = row.find_element(By.XPATH, ".//button[starts-with(@aria-label,'Expand item')]")
        self.element_utils.scroll_to_element(toggle)
        self.pause_before_action()
        try:
            toggle.click()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", toggle)
        self.wait_utils.until_visible(self.EXPANDED_ROW, timeout=20)
        sleep(1)

    def collapse_expanded_item(self):
        for toggle in self.driver.find_elements(
            By.XPATH, "//table//tbody//button[starts-with(@aria-label,'Collapse item')]"
        ):
            try:
                self.driver.execute_script("arguments[0].click();", toggle)
                sleep(1)
            except WebDriverException:
                continue

    def is_item_expanded(self):
        return self.is_element_visible_quick(self.EXPANDED_ROW, timeout=10)

    def get_expanded_item_text(self):
        try:
            return self.get_text(self.EXPANDED_ROW).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def is_retire_button_visible(self):
        return self.is_element_visible_quick(self.RETIRE_ITEM_BTN, timeout=10)

    def is_retire_confirmation_visible(self, timeout=10):
        return self.is_element_visible_quick(self.RETIRE_CONFIRM_BTN, timeout=timeout)

    def open_retire_confirmation(self):
        """Press Retire Item and wait for the confirmation modal."""
        self.click_resilient(self.RETIRE_ITEM_BTN)
        if not self.is_retire_confirmation_visible(timeout=15):
            raise TimeoutException(
                "'Retire Item' did not raise its Cancel/Retire confirmation step."
            )

    def get_retire_confirmation_prompt(self):
        """The modal's warning line, e.g. 'You are about to retire item #3064.
        This action cannot be undone.'"""
        try:
            return self.get_text(self.RETIRE_CONFIRM_PROMPT).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def is_retire_reason_required(self):
        return self.is_element_visible_quick(self.RETIRE_REASON_INPUT, timeout=5)

    def confirm_retire(self, reason):
        """Supply the mandatory reason and confirm the retirement."""
        self.enter_text(self.RETIRE_REASON_INPUT, reason)
        confirm = self.wait_utils.until_clickable(self.RETIRE_CONFIRM_BTN, timeout=15)
        if confirm.get_attribute("disabled"):
            raise TimeoutException(
                "'Retire' stayed disabled after a retirement reason was entered."
            )
        self.click_resilient(self.RETIRE_CONFIRM_BTN)
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.is_element_visible_quick(self.RETIRE_CONFIRM_BTN, timeout=1),
                timeout=20,
            )
        except TimeoutException:
            raise TimeoutException("The retire confirmation stayed open after confirming.")
        sleep(3)

    def click_retire_item(self, reason="Automated retirement verification"):
        """Retire the expanded item end to end, via its confirmation modal."""
        self.open_retire_confirmation()
        self.confirm_retire(reason)

    def cancel_retire_item(self):
        """Back out of the confirmation without retiring anything."""
        if self.is_element_visible_quick(self.RETIRE_CANCEL_BTN, timeout=5):
            self.click_resilient(self.RETIRE_CANCEL_BTN)
            sleep(1)

    def get_toast_message(self, timeout=10):
        if not self.is_element_visible_quick(self.TOAST, timeout=timeout):
            return ""
        try:
            return self.get_text(self.TOAST).strip()
        except WebDriverException:
            return ""

    # ---------------------------------------------------------------- filters

    def _filter_control_locator(self, label):
        """Filter controls sit outside the grid, so exclude table descendants —
        every filter name is also a column header.

        The XPath string is double-quoted because "Bloom's Level" carries an
        apostrophe, which would terminate a single-quoted literal.
        """
        return (
            By.XPATH,
            f'//*[normalize-space()="{label}"][not(ancestor-or-self::table)]',
        )

    def toggle_filters_panel(self):
        self.click_resilient(self.FILTERS_BTN)
        sleep(2)

    def visible_filter_controls(self):
        return [
            label
            for label in self.FILTER_LABELS
            if self.is_element_visible_quick(self._filter_control_locator(label), timeout=3)
        ]

    def missing_filter_controls(self):
        visible = self.visible_filter_controls()
        return [label for label in self.FILTER_LABELS if label not in visible]

    # ----------------------------------------------------------------- export

    def get_download_dir(self):
        """Per-test download folder provisioned by the `setup` fixture."""
        return getattr(self.driver, "_download_dir", None)

    def export_file_and_wait(self, timeout=45):
        """Click Export and return the Path of the downloaded file."""
        download_dir = self.get_download_dir()
        if not download_dir:
            raise RuntimeError(
                "No download directory on the driver; the `setup` fixture must provision one."
            )
        directory = Path(download_dir)
        before = {path.name for path in directory.glob("*") if path.is_file()}

        self.click_resilient(self.EXPORT_BTN)

        deadline = time() + timeout
        while time() < deadline:
            current = {path.name for path in directory.glob("*") if path.is_file()}
            new_files = [name for name in current - before if not name.endswith((".crdownload", ".tmp"))]
            if new_files:
                return directory / new_files[0]
            sleep(1)
        raise TimeoutException(
            f"Export produced no file in {download_dir} within {timeout}s. "
            f"Directory contents: {sorted(directory.glob('*'))}"
        )

    # ------------------------------------------------------------ bulk select

    def toggle_master_checkbox(self):
        master = self.wait_utils.until_visible(self.MASTER_CHECKBOX, timeout=20)
        self.element_utils.scroll_to_element(master)
        self.pause_before_action()
        try:
            master.click()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", master)
        sleep(1.5)

    def get_row_checkboxes(self):
        return self.driver.find_elements(*self.ROW_CHECKBOXES)

    def get_checked_rows_count(self):
        checked = 0
        for checkbox in self.get_row_checkboxes():
            try:
                if checkbox.is_selected():
                    checked += 1
            except WebDriverException:
                continue
        return checked

    def get_selection_summary(self):
        """'10 of 67 row(s) selected.' — empty when nothing is selected."""
        if not self.is_element_visible_quick(self.SELECTION_SUMMARY, timeout=5):
            return ""
        try:
            return self.get_text(self.SELECTION_SUMMARY).strip()
        except WebDriverException:
            return ""

    # -------------------------------------------------------------- pagination

    def has_pagination_controls(self):
        return (
            self.is_element_visible_quick(self.ROWS_PER_PAGE, timeout=10)
            and self.is_element_visible_quick(self.NEXT_PAGE_BTN, timeout=10)
            and self.is_element_visible_quick(self.PAGE_INDICATOR, timeout=10)
        )

    def get_page_indicator(self):
        try:
            return self.get_text(self.PAGE_INDICATOR).strip().splitlines()[0]
        except (TimeoutException, WebDriverException, IndexError):
            return ""

    def go_to_next_page(self):
        before = self.get_page_indicator()
        self.click_resilient(self.NEXT_PAGE_BTN)
        try:
            self.wait_utils.until_condition(
                lambda driver: self.get_page_indicator() != before, timeout=20
            )
        except TimeoutException:
            pass
        return self.get_page_indicator()
