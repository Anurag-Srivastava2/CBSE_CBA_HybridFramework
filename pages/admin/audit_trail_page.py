from pathlib import Path
from time import sleep, time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class AuditTrailPage(BasePage):
    """Admin > Audit Trail (/admin/audit).

    Columns: Timestamp | User | User ID | Role | Action | Entity | IP Address.
    The grid is append-only: rows carry no controls at all, which is what the
    immutability check relies on.
    """

    PATH = "/admin/audit"

    COLUMN_TIMESTAMP = 1
    COLUMN_USER = 2
    COLUMN_USER_ID = 3
    COLUMN_ROLE = 4
    COLUMN_ACTION = 5
    COLUMN_ENTITY = 6
    COLUMN_IP = 7

    EXPECTED_COLUMNS = ("Timestamp", "User", "User ID", "Role", "Action", "Entity", "IP Address")

    PAGE_HEADER = (By.XPATH, "//*[normalize-space()='Audit Trail']")
    SUBTEXT = (By.XPATH, "//*[contains(normalize-space(),'Tamper-proof user activity logs')]")
    SEARCH_INPUT = (By.XPATH, "//input[contains(@placeholder,'Search by user, ID, action')]")
    EVENT_TYPE_FILTER = (
        By.XPATH,
        "//button[@aria-haspopup='menu'][.//span[normalize-space()='Event Type']]",
    )
    EXPORT_BTN = (By.XPATH, "//button[normalize-space()='Export File']")

    TABLE = (By.XPATH, "//table")
    TABLE_HEADERS = (By.XPATH, "//table//th")
    TABLE_ROWS = (By.XPATH, "//table//tbody//tr")

    ROWS_PER_PAGE = (
        By.XPATH,
        "//*[contains(normalize-space(),'Rows per page')]/following::button[@role='combobox'][1]",
    )
    NEXT_PAGE_BTN = (
        By.XPATH,
        "//button[contains(normalize-space(),'chevron_right') or @aria-label='Go to next page']",
    )
    PAGE_INDICATOR = (By.XPATH, "//*[starts-with(normalize-space(),'Page ')]")

    # Anything that could mutate a log line. The grid should contain none.
    MUTATING_CONTROLS = (
        By.XPATH,
        "//table//tbody//button | //table//tbody//a[@href] | //table//tbody//input",
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

    # ------------------------------------------------------------------- table

    def get_table_headers(self):
        return [h.text.strip() for h in self.driver.find_elements(*self.TABLE_HEADERS) if h.text.strip()]

    def missing_columns(self):
        headers = self.get_table_headers()
        return [column for column in self.EXPECTED_COLUMNS if column not in headers]

    def get_rows(self):
        """Data rows only — the empty state renders a placeholder row with no
        timestamp, which must not count as a log entry."""
        rows = []
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            try:
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < self.COLUMN_IP or not cells[self.COLUMN_TIMESTAMP - 1].text.strip():
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

    def get_users_in_view(self):
        return self._column_values(self.COLUMN_USER)

    def get_actions_in_view(self):
        return self._column_values(self.COLUMN_ACTION)

    def get_entities_in_view(self):
        return self._column_values(self.COLUMN_ENTITY)

    def get_row_text(self):
        return [row.text.strip() for row in self.get_rows()]

    # ------------------------------------------------------------ search/filter

    def search_audit_log(self, term):
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

    def dismiss_overlays(self):
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            sleep(0.5)
        except WebDriverException:
            pass

    def click_resilient(self, locator):
        try:
            self.click_element(locator)
        except WebDriverException:
            self.dismiss_overlays()
            self.element_utils.js_click(locator)

    def get_event_type_options(self):
        self.click_resilient(self.EVENT_TYPE_FILTER)
        sleep(1.5)
        options = [
            o.text.strip()
            for o in self.driver.find_elements(By.XPATH, "//*[@role='menuitem']")
            if o.text.strip()
        ]
        self.dismiss_overlays()
        return options

    def filter_by_event_type(self, event_type):
        """Event types are enum codes (LOGIN_SUCCESS), not the humanised text
        shown in the Action column (Login Success)."""
        self.dismiss_overlays()
        self.click_resilient(self.EVENT_TYPE_FILTER)
        option = (By.XPATH, f"//*[@role='menuitem'][normalize-space()='{event_type}']")
        element = self.wait_utils.until_visible(option, timeout=15)
        self.element_utils.scroll_to_element(element)
        self.click_resilient(option)
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*self.EVENT_TYPE_FILTER).get_attribute("aria-expanded")
                != "true",
                timeout=15,
            )
        except (TimeoutException, WebDriverException):
            self.dismiss_overlays()
        sleep(2)

    @staticmethod
    def humanise_event_type(event_type):
        """LOGIN_SUCCESS -> 'Login Success', matching the Action column."""
        return " ".join(part.capitalize() for part in event_type.split("_"))

    # ------------------------------------------------------------ immutability

    def get_mutating_controls(self):
        """Any control inside the log grid that could alter a record."""
        controls = []
        for element in self.driver.find_elements(*self.MUTATING_CONTROLS):
            try:
                label = (
                    element.get_attribute("aria-label")
                    or element.text.strip()
                    or element.get_attribute("title")
                    or element.tag_name
                )
                controls.append(label)
            except WebDriverException:
                continue
        return controls

    def are_edit_or_delete_buttons_present(self):
        return bool(self.get_mutating_controls())

    def are_table_cells_editable(self):
        """A tamper-proof grid must not expose contenteditable cells either."""
        for cell in self.driver.find_elements(By.XPATH, "//table//tbody//td"):
            try:
                if (cell.get_attribute("contenteditable") or "").casefold() == "true":
                    return True
            except WebDriverException:
                continue
        return False

    # ------------------------------------------------------------------ export

    def get_download_dir(self):
        """Per-test download folder provisioned by the `setup` fixture."""
        return getattr(self.driver, "_download_dir", None)

    def click_export_file(self):
        self.click_resilient(self.EXPORT_BTN)

    def export_file_and_wait(self, timeout=45):
        """Click Export and return the Path of the downloaded file.

        The button downloads directly — there is no format menu — so this waits
        for a completed (non-.crdownload) file to appear.
        """
        download_dir = self.get_download_dir()
        if not download_dir:
            raise RuntimeError(
                "No download directory on the driver; the `setup` fixture must provision one."
            )
        directory = Path(download_dir)
        before = {path.name for path in directory.glob("*") if path.is_file()}

        self.click_export_file()

        deadline = time() + timeout
        while time() < deadline:
            current = {path.name for path in directory.glob("*") if path.is_file()}
            new_files = [
                name for name in current - before if not name.endswith((".crdownload", ".tmp"))
            ]
            if new_files:
                return directory / new_files[0]
            sleep(1)
        raise TimeoutException(
            f"Export produced no file in {download_dir} within {timeout}s. "
            f"Directory contents: {sorted(directory.glob('*'))}"
        )

    # -------------------------------------------------------------- pagination

    def get_page_indicator(self):
        try:
            return self.get_text(self.PAGE_INDICATOR).strip().splitlines()[0]
        except (TimeoutException, WebDriverException, IndexError):
            return ""

    def has_pagination_controls(self):
        return (
            self.is_element_visible_quick(self.ROWS_PER_PAGE, timeout=10)
            and self.is_element_visible_quick(self.NEXT_PAGE_BTN, timeout=10)
            and self.is_element_visible_quick(self.PAGE_INDICATOR, timeout=10)
        )

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
