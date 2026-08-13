from time import sleep

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class AssignmentQueuePage(BasePage):
    """Admin > Assignment Queue (/admin/assignment).

    Columns: Set Code | Stage | Grade | Subject | Assigned To | Status | Due On | Actions.
    Only rows that are not Completed expose a kebab action, because the page
    exists to reassign *pending* work.
    """

    PATH = "/admin/assignment"

    COLUMN_SET_CODE = 1
    COLUMN_STAGE = 2
    COLUMN_GRADE = 3
    COLUMN_SUBJECT = 4
    COLUMN_ASSIGNED_TO = 5
    COLUMN_STATUS = 6
    COLUMN_DUE_ON = 7

    PAGE_HEADER = (By.XPATH, "//*[normalize-space()='Assignment Queue']")
    SUBTEXT = (By.XPATH, "//*[contains(normalize-space(),'Reassign pending work')]")
    SEARCH_INPUT = (By.XPATH, "//input[contains(@placeholder,'Search by set code')]")

    TABLE = (By.XPATH, "//table")
    TABLE_ROWS = (By.XPATH, "//table//tbody//tr")
    TABLE_HEADERS = (By.XPATH, "//table//th")

    # Filters are dropdown-menu triggers labelled by an inner <span>.
    FILTER_LABELS = ("Stage", "Status", "Grade", "Subject", "Chapter")

    # Reassign panel
    REASSIGN_TITLE = (By.XPATH, "//*[normalize-space()='Reassign Set']")
    REASSIGN_SET_CODE = (By.ID, "assignment-reassign-set-code")
    REASSIGN_REVIEWER_TRIGGER = (
        By.XPATH,
        "//*[normalize-space()='Reassign To']/following::button[@role='combobox'][1]",
    )
    REASSIGN_REASON = (By.ID, "reassignReason")
    REASSIGN_CONFIRM = (By.XPATH, "//button[normalize-space()='Confirm Reassign']")
    REASSIGN_CANCEL = (By.XPATH, "//button[normalize-space()='Cancel']")

    ROWS_PER_PAGE = (
        By.XPATH,
        "//*[contains(normalize-space(),'Rows per page')]/following::button[@role='combobox'][1]",
    )
    NEXT_PAGE_BTN = (
        By.XPATH,
        "//button[contains(normalize-space(),'chevron_right') or @aria-label='Go to next page']",
    )
    PREV_PAGE_BTN = (
        By.XPATH,
        "//button[contains(normalize-space(),'chevron_left') or @aria-label='Go to previous page']",
    )
    PAGE_INDICATOR = (By.XPATH, "//*[starts-with(normalize-space(),'Page ')]")

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

    def body_text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def is_on_page(self):
        return self.is_element_visible_quick(self.PAGE_HEADER, timeout=15) and self.is_element_visible_quick(
            self.SUBTEXT, timeout=10
        )

    def get_column_headers(self):
        return [h.text.strip() for h in self.driver.find_elements(*self.TABLE_HEADERS) if h.text.strip()]

    # ------------------------------------------------------------------ search

    def search(self, term):
        """Type into the queue search box. An empty term clears the filter."""
        last_error = None
        for _ in range(3):
            try:
                search_input = self.wait_utils.until_clickable(self.SEARCH_INPUT, timeout=20)
                self.element_utils.scroll_to_element(search_input)
                search_input.click()
                search_input.send_keys(Keys.CONTROL, "a")
                search_input.send_keys(Keys.DELETE)
                if term:
                    search_input.send_keys(term)
                sleep(2)
                return
            except WebDriverException as error:
                last_error = error
                sleep(2)
        raise last_error

    # ------------------------------------------------------------------- table

    def get_rows(self):
        """Data rows only — an empty result renders a single placeholder row
        with no Set Code, which must not be counted as data."""
        rows = []
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            try:
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < self.COLUMN_STATUS:
                    continue
                if not cells[self.COLUMN_SET_CODE - 1].text.strip():
                    continue
                rows.append(row)
            except WebDriverException:
                continue
        return rows

    def get_row_count(self):
        return len(self.get_rows())

    def _column_values(self, column_index):
        values = []
        for row in self.get_rows():
            try:
                values.append(row.find_elements(By.XPATH, "./td")[column_index - 1].text.strip())
            except (IndexError, WebDriverException):
                continue
        return values

    def get_set_codes_in_view(self):
        return self._column_values(self.COLUMN_SET_CODE)

    def get_assigned_users_in_view(self):
        return self._column_values(self.COLUMN_ASSIGNED_TO)

    def get_statuses_in_view(self):
        return self._column_values(self.COLUMN_STATUS)

    def get_stages_in_view(self):
        return self._column_values(self.COLUMN_STAGE)

    def get_row_values(self, row):
        cells = [c.text.strip() for c in row.find_elements(By.XPATH, "./td")]
        return {
            "set_code": cells[self.COLUMN_SET_CODE - 1],
            "stage": cells[self.COLUMN_STAGE - 1],
            "grade": cells[self.COLUMN_GRADE - 1],
            "subject": cells[self.COLUMN_SUBJECT - 1],
            "assigned_to": cells[self.COLUMN_ASSIGNED_TO - 1],
            "status": cells[self.COLUMN_STATUS - 1],
        }

    # ----------------------------------------------------------------- filters

    def _filter_trigger(self, label):
        return (
            By.XPATH,
            f"//button[@aria-haspopup='menu'][.//span[normalize-space()='{label}']]",
        )

    def is_filter_visible(self, label):
        return self.is_element_visible_quick(self._filter_trigger(label), timeout=10)

    def missing_filters(self):
        return [label for label in self.FILTER_LABELS if not self.is_filter_visible(label)]

    def click_resilient(self, locator):
        """Radix menus leave a click-swallowing overlay behind; clear it and
        retry via JS before giving up."""
        try:
            self.click_element(locator)
        except WebDriverException:
            self.dismiss_overlays()
            self.element_utils.js_click(locator)

    def apply_filter(self, label, option_text):
        """Open a filter menu and pick an option (menu items, not a select)."""
        trigger = self._filter_trigger(label)
        self.dismiss_overlays()
        self.click_resilient(trigger)
        option = (By.XPATH, f"//*[@role='menuitem'][normalize-space()='{option_text}']")
        self.wait_utils.until_visible(option, timeout=15)
        self.click_resilient(option)
        # Wait for the menu to actually close before the next interaction.
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*trigger).get_attribute("aria-expanded") != "true",
                timeout=15,
            )
        except (TimeoutException, WebDriverException):
            self.dismiss_overlays()
        sleep(2)

    def filter_by_stage(self, stage):
        self.apply_filter("Stage", stage)

    def filter_by_status(self, status):
        self.apply_filter("Status", status)

    def filter_by_grade(self, grade):
        self.apply_filter("Grade", grade)

    def filter_by_subject(self, subject):
        self.apply_filter("Subject", subject)

    def filter_by_chapter(self, chapter):
        self.apply_filter("Chapter", chapter)

    def get_filter_options(self, label):
        self.click_element(self._filter_trigger(label))
        sleep(1.5)
        options = [
            o.text.strip()
            for o in self.driver.find_elements(By.XPATH, "//*[@role='menuitem']")
            if o.text.strip()
        ]
        self.dismiss_overlays()
        return options

    def dismiss_overlays(self):
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            sleep(0.5)
        except WebDriverException:
            pass

    # -------------------------------------------------------------- reassigning

    def find_actionable_row(self):
        """First row that exposes a kebab action — i.e. work that is still
        pending. Returns (row, values) or (None, None)."""
        for row in self.get_rows():
            if row.find_elements(By.XPATH, ".//button[@aria-label='More actions']"):
                return row, self.get_row_values(row)
        return None, None

    def row_has_action(self, row):
        return bool(row.find_elements(By.XPATH, ".//button[@aria-label='More actions']"))

    def open_reassign_panel(self, row):
        row.find_element(By.XPATH, ".//button[@aria-label='More actions']").click()
        menu_item = (By.XPATH, "//*[@role='menuitem'][normalize-space()='Reassign']")
        self.wait_utils.until_visible(menu_item, timeout=15)
        self.click_element(menu_item)
        self.wait_utils.until_visible(self.REASSIGN_TITLE, timeout=20)

    @staticmethod
    def reviewer_display_name(option_text):
        """Picker options carry a workload suffix — 'pit 2 (Load: 50)' — while
        the Assigned To column shows just 'pit 2'."""
        return option_text.split("(")[0].strip()

    def get_reviewer_options(self):
        self.click_element(self.REASSIGN_REVIEWER_TRIGGER)
        sleep(1.5)
        options = [
            o.text.strip()
            for o in self.driver.find_elements(By.XPATH, "//*[@role='option']")
            if o.text.strip()
        ]
        self.dismiss_overlays()
        return options

    def select_reviewer(self, reviewer):
        self.click_element(self.REASSIGN_REVIEWER_TRIGGER)
        option = (By.XPATH, f"//*[@role='option'][contains(normalize-space(),'{reviewer}')]")
        element = self.wait_utils.until_visible(option, timeout=15)
        self.element_utils.scroll_to_element(element)
        try:
            element.click()
        except WebDriverException:
            self.element_utils.js_click(option)

    def confirm_reassign(self, reason="Automated reassignment verification"):
        self.enter_text(self.REASSIGN_REASON, reason)
        self.dismiss_overlays()
        confirm = self.wait_utils.until_visible(self.REASSIGN_CONFIRM, timeout=15)
        if confirm.get_attribute("disabled"):
            raise TimeoutException(
                "'Confirm Reassign' stayed disabled — reviewer and/or reason were not accepted."
            )
        try:
            confirm.click()
        except WebDriverException:
            self.element_utils.js_click(self.REASSIGN_CONFIRM)
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.is_element_visible_quick(self.REASSIGN_TITLE, timeout=1),
                timeout=25,
            )
        except TimeoutException:
            raise TimeoutException("Reassign panel stayed open after confirming.")
        sleep(2)

    def reassign_set(self, row, new_reviewer, reason="Automated reassignment verification"):
        self.open_reassign_panel(row)
        self.select_reviewer(new_reviewer)
        self.confirm_reassign(reason)

    def get_toast_message(self, timeout=10):
        if not self.is_element_visible_quick(self.TOAST, timeout=timeout):
            return ""
        try:
            return self.get_text(self.TOAST).strip()
        except WebDriverException:
            return ""

    # -------------------------------------------------------------- pagination

    def has_pagination_controls(self):
        return self.is_element_visible_quick(self.ROWS_PER_PAGE, timeout=10) and self.is_element_visible_quick(
            self.NEXT_PAGE_BTN, timeout=10
        )

    def get_page_indicator(self):
        try:
            return self.get_text(self.PAGE_INDICATOR).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def go_to_next_page(self):
        before = self.get_page_indicator()
        self.click_element(self.NEXT_PAGE_BTN)
        try:
            self.wait_utils.until_condition(
                lambda driver: self.get_page_indicator() != before, timeout=20
            )
        except TimeoutException:
            pass
        return self.get_page_indicator()
