import base64
from pathlib import Path
import re
from time import monotonic, sleep

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from pages.common.base_page import BasePage
from pages.qar.qar_report_page import QARReportPage
from utilities.screenshot_utils import ScreenshotUtils
from utilities.read_config import ReadConfig


def _safe_print(message):
    """Print without crashing on consoles using a narrow codec (e.g. Windows cp1252)."""
    print(str(message).encode("ascii", errors="replace").decode("ascii"))


class UploadItemFilePage(BasePage):
    """SME upload item file page."""

    # --- Item creation navigation locators ---
    ITEM_CREATION_MENU_LOCATORS = [
        (
            By.XPATH,
            "//*[self::button or self::a][normalize-space()='Create' "
            "or .//*[normalize-space()='Create']]",
        ),
        (By.CSS_SELECTOR, ".lucide-pen-line"),
        (By.XPATH, "//button[.//*[name()='svg' and contains(@class,'lucide-pen-line')]]"),
        (By.XPATH, "(//div[@id='root']//ul/li[3]/button)[1]"),
    ]
    GLOBAL_LOADING_INDICATOR = (
        By.XPATH,
        "//*[starts-with(normalize-space(), 'Loading')]",
    )
    # --- Item creation navigation actions ---
    def close_popup_if_open(self):
        self.pause_before_action()
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def open_item_creation_module(self):
        last_error = None
        for attempt in range(3):
            self.wait_for_application_to_load()
            try:
                self.click_any_element(self.ITEM_CREATION_MENU_LOCATORS)
                state = self.wait_utils.until_condition(
                    lambda driver: (
                        "dynamic_import_error"
                        if "failed to fetch dynamically imported module"
                        in driver.find_element(By.TAG_NAME, "body").text.casefold()
                        else (
                            "ready"
                            if any(
                                element.is_displayed()
                                for locator in self.UPLOAD_ITEM_FILE_TAB_LOCATORS
                                for element in driver.find_elements(*locator)
                            )
                            else False
                        )
                    ),
                    timeout=30,
                )
                if state == "ready":
                    return
            except Exception as error:
                last_error = error
            if attempt < 2:
                self.driver.refresh()
        raise TimeoutException(
            "Item creation module did not load after retrying a dynamic-import failure."
        ) from last_error

    def wait_for_application_to_load(self):
        def loading_indicator_cleared(driver):
            if driver.find_elements(*self.GLOBAL_LOADING_INDICATOR):
                return False
            # A clear read straight after navigation can race the very first
            # paint (nothing rendered yet, so the indicator hasn't appeared).
            # Confirm it stays clear a moment later before trusting it.
            sleep(0.3)
            return not driver.find_elements(*self.GLOBAL_LOADING_INDICATOR)

        for attempt in range(2):
            try:
                self.wait_utils.until_condition(loading_indicator_cleared, timeout=45)
                return
            except TimeoutException:
                if attempt == 0:
                    self.driver.refresh()
        raise TimeoutException("Application remained on the global Loading screen after refresh.")

    # --- Upload item file locators ---
    UPLOAD_ITEM_FILE_TAB_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Upload Item File')]"),
        (By.XPATH, "//*[contains(normalize-space(),'Upload Item File')]"),
    ]

    FILE_INPUT = (
        By.XPATH,
        "//input[@type='file' and not(@disabled)]",
    )
    UPLOADED_FILE_DELETE_LOCATORS = [
        (
            By.XPATH,
            "//button[contains(@aria-label,'Delete') or contains(@aria-label,'Remove') "
            "or contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove')]",
        ),
        (
            By.XPATH,
            "//*[name()='svg' and (contains(@class,'trash') or contains(@class,'Trash'))]"
            "/ancestor::button[1]",
        ),
        (
            By.XPATH,
            "//button[.//*[name()='svg' and (contains(@class,'trash') or contains(@class,'Trash'))]]",
        ),
    ]
    DELETE_CONFIRM_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
            "//button[contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove') "
            "or contains(normalize-space(),'Confirm') or contains(normalize-space(),'Yes')]",
        ),
        (
            By.XPATH,
            "//button[contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove') "
            "or contains(normalize-space(),'Confirm') or contains(normalize-space(),'Yes')]",
        ),
    ]
    UPLOAD_SUCCESS_MESSAGE = (
        By.XPATH,
        "//*[contains(normalize-space(), 'All files uploaded and validated successfully') "
        "and contains(normalize-space(), 'Status: PASSED')]",
    )
    # .docx/.doc and .zip are listed alongside the spreadsheet extensions
    # because the Word ingestion path stages the document and its companion
    # image .zip through this same uploader. Without them the staged-file
    # assertion in upload_item_file_and_validate() cannot see a Word upload at
    # all and reports a missing element rather than the upload's real outcome.
    UPLOADED_FILE_NAME = (
        By.XPATH,
        "//*[contains(normalize-space(), '.xlsx') "
        "or contains(normalize-space(), '.xls') "
        "or contains(normalize-space(), '.csv') "
        "or contains(normalize-space(), '.docx') "
        "or contains(normalize-space(), '.doc') "
        "or contains(normalize-space(), '.zip')]",
    )
    UPLOAD_DOCUMENTS_HEADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'Upload Documents')]",
    )
    DOWNLOAD_TEMPLATE_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Download Template')]"),
        (By.XPATH, "//a[contains(normalize-space(),'Download Template')]"),
        (By.XPATH, "//*[contains(normalize-space(),'Download') and contains(normalize-space(),'Template')]"),
    ]
    # Download Template is a dropdown: clicking the trigger above only opens a
    # menu, and the download starts only once a format is chosen. Keyed by the
    # extension the option produces.
    TEMPLATE_FORMAT_OPTION_LOCATORS = {
        "xlsx": (
            By.XPATH,
            "//*[contains(normalize-space(),'Excel') and contains(normalize-space(),'.xlsx')]",
        ),
        "docx": (
            By.XPATH,
            "//*[contains(normalize-space(),'Word') and contains(normalize-space(),'.docx')]",
        ),
    }
    UPLOAD_HISTORY_ROWS = (
        By.XPATH,
        "//table[.//th[contains(translate(normalize-space(), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
        "'file upload status')]]//tbody/tr",
    )
    UPLOAD_REJECTION_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='alert' or @role='status' or contains(@class,'toast') "
            "or contains(@class,'Toast') or contains(@class,'error') or contains(@class,'Error')]"
            "[contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'invalid') "
            "or contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'failed') "
            "or contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'error')]",
        ),
        (
            By.XPATH,
            "//*[contains(normalize-space(),'Invalid file format') "
            "or contains(normalize-space(),'Upload Failed') "
            "or contains(normalize-space(),'Header row') "
            "or contains(normalize-space(),'Only .xlsx') "
            "or contains(normalize-space(),'Missing required columns') "
            "or contains(normalize-space(),'required columns')]",
        ),
    ]

    # --- Contribution workspace furniture -------------------------------
    #
    # Locators used by the element-presence surveys rather than by the upload
    # workflow itself. Taken from a DOM census of the live upload step, so the
    # survey reports against what the screen actually renders.

    WORKSPACE_TITLE = (By.XPATH, "//h1[normalize-space()='Create New Item Set']")
    BACK_BUTTON = (By.XPATH, "//button[contains(normalize-space(),'Back')]")

    # Both the mode switcher and the prerequisites card use role='tab', so these
    # match on exact text — a contains() would cross-match the two tablists.
    MODE_TAB_LABELS = ("Upload Item File", "Add Items Manually")
    WIZARD_STEP_LABELS = (
        "Download Template",
        "Upload File",
        "Review & Tag Metadata",
        "Confirm & Submit",
    )
    PREREQUISITE_TAB_LABELS = ("Required Columns", "Typology", "Validation Rules")

    # Scoped to the leaf carrying the text: unscoped, this also matched 20
    # ancestors up to <body>, so "present" would have meant almost nothing.
    DROPZONE = (
        By.XPATH,
        "//*[not(*)][contains(normalize-space(),'Drag and drop files') "
        "or contains(normalize-space(),'Browse')]",
    )
    ADD_ITEMS_INDIVIDUALLY_BTN = (
        By.XPATH,
        "//button[contains(normalize-space(),'Add items Individually')]",
    )
    INLINE_TEMPLATE_LINK = (
        By.XPATH,
        "//button[contains(normalize-space(),'download the template')]",
    )
    PREREQUISITES_HEADING = (By.XPATH, "//*[normalize-space()='Upload Prerequisites']")
    UPLOAD_HISTORY_HEADING = (
        By.XPATH,
        "//*[normalize-space()='Previously Uploaded Files']",
    )
    UPLOAD_HISTORY_TABLE = (
        By.XPATH,
        "//table[.//th[contains(translate(normalize-space(), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
        "'file upload status')]]",
    )
    UPLOAD_HISTORY_HEADERS = (
        By.XPATH,
        "//table[.//th[contains(translate(normalize-space(), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
        "'file upload status')]]//th",
    )
    UPLOAD_HISTORY_COLUMNS = (
        "File Name",
        "Uploaded On",
        "File Upload Status",
        "Items Detected",
        "Items Passed",
        "Items Rejected",
        "Actions",
    )
    UPLOAD_HISTORY_LOADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'Loading uploaded files')]",
    )

    # Application chrome, shared with the dashboard.
    HEADER = (By.TAG_NAME, "header")
    SIDEBAR_NAV = (By.TAG_NAME, "nav")
    SIDEBAR_TOGGLE = (By.XPATH, "//button[contains(normalize-space(),'Toggle Sidebar')]")
    NOTIFICATION_BELL = (By.CSS_SELECTOR, "button[aria-label='Notifications']")
    THEME_PICKER = (By.CSS_SELECTOR, "button[aria-label='Theme']")
    SCREEN_READER_TOGGLE = (
        By.CSS_SELECTOR,
        "button[aria-label='Toggle screen-reader hints']",
    )
    LANG_EN = (By.XPATH, "//button[normalize-space()='EN']")
    LANG_HI = (By.XPATH, "//button[normalize-space()='हिंदी']")

    # --- Contribution workspace readers ---------------------------------

    def is_visible(self, locator, timeout=5):
        return self.is_element_visible_quick(locator, timeout)

    def count_visible(self, locator):
        """How many matches are actually on screen — 0 when none are."""
        count = 0
        for element in self.driver.find_elements(*locator):
            try:
                if element.is_displayed():
                    count += 1
            except WebDriverException:
                continue
        return count

    @classmethod
    def tab_locator(cls, label):
        return (By.XPATH, f"//*[@role='tab'][normalize-space()={cls.xpath_literal(label)}]")

    @classmethod
    def wizard_step_locator(cls, label):
        return (
            By.XPATH,
            "//*[contains(@class,'stepItem')]"
            f"[contains(normalize-space(),{cls.xpath_literal(label)})]",
        )

    def missing_mode_tabs(self):
        return [
            label
            for label in self.MODE_TAB_LABELS
            if not self.count_visible(self.tab_locator(label))
        ]

    def missing_wizard_steps(self):
        return [
            label
            for label in self.WIZARD_STEP_LABELS
            if not self.count_visible(self.wizard_step_locator(label))
        ]

    def missing_prerequisite_tabs(self):
        return [
            label
            for label in self.PREREQUISITE_TAB_LABELS
            if not self.count_visible(self.tab_locator(label))
        ]

    def get_required_column_rules(self):
        """The Required Columns rail as {column name: the rule beside it}.

        This panel is the app stating its own upload contract on screen -
        "Book: The book within the grade-subject - required", "Unit/Theme:
        Unit / Theme (optional)" - so it is worth reading rather than only
        inferring the contract from a downloaded file.

        Read by walking the rail's rendered text rather than through per-chip
        locators: the chips carry no stable hook, and a layout tweak that
        renamed a class would otherwise report the whole contract as missing.
        Returns {} when the rail is not on screen, which the caller reports
        instead of mistaking for an empty contract.
        """
        return self.driver.execute_script(
            # Raw: the JS below needs its own backslashes ( \n , \. ) to survive
            # into the browser rather than being interpreted by Python first.
            r"""
            const heading = Array.from(document.querySelectorAll('*')).find(
                el => el.children.length === 0
                    && (el.textContent || '').trim() === 'Upload Prerequisites'
            );
            if (!heading) return {};
            // The rail is the nearest ancestor that also holds the chip list.
            let rail = heading.parentElement;
            while (rail && !/Chapter No\._Name/.test(rail.innerText || '')) {
                rail = rail.parentElement;
            }
            if (!rail) return {};
            const lines = (rail.innerText || '')
                .split('\n')
                .map(line => line.trim())
                .filter(Boolean);
            // Each column renders as a chip line followed by its rule; the rule
            // itself can wrap onto further lines, so text is accumulated until
            // the next known chip starts.
            const chips = new Set(lines.filter(line => /^[A-Z][A-Za-z0-9 ._\/']{0,40}$/.test(line)));
            const rules = {};
            let current = null;
            for (const line of lines) {
                if (chips.has(line) && line !== current) {
                    current = line;
                    if (!(current in rules)) rules[current] = '';
                } else if (current) {
                    rules[current] = (rules[current] + ' ' + line).trim();
                }
            }
            return rules;
            """
        ) or {}

    def get_required_column_rule(self, column):
        """The rule text for one Required Columns entry, matched loosely.

        The rail spells the fourth column "Unit/Theme" while the workbook header
        says "Unit", so callers name either and this resolves it.
        """
        rules = self.get_required_column_rules()
        wanted = "".join(ch for ch in column.casefold() if ch.isalnum())
        for name, rule in rules.items():
            normalized = "".join(ch for ch in name.casefold() if ch.isalnum())
            if normalized == wanted or normalized.startswith(wanted):
                return rule
        return ""

    def is_tab_active(self, label):
        try:
            state = self.driver.find_element(*self.tab_locator(label)).get_attribute(
                "data-state"
            )
        except WebDriverException:
            return False
        return state == "active"

    def switch_tab(self, label, timeout=15):
        """Activate a tab by its exact label and wait for it to report active."""
        self.click_element(self.tab_locator(label))
        try:
            self.wait_utils.until_condition(
                lambda driver: self.is_tab_active(label), timeout=timeout
            )
        except TimeoutException:
            return False
        return True

    def wait_for_upload_history(self, timeout=60):
        """Wait out the 'Loading uploaded files...' placeholder.

        The history table is fetched after the upload step paints, so a survey
        that samples it immediately records an absent table on an account that
        actually has one.
        """
        try:
            self.wait_utils.until_condition(
                lambda driver: bool(driver.find_elements(*self.UPLOAD_HISTORY_HEADERS))
                or not driver.find_elements(*self.UPLOAD_HISTORY_LOADING),
                timeout=timeout,
            )
        except TimeoutException:
            return False
        return bool(self.driver.find_elements(*self.UPLOAD_HISTORY_HEADERS))

    def get_upload_history_headers(self):
        headers = []
        for element in self.driver.find_elements(*self.UPLOAD_HISTORY_HEADERS):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if text:
                headers.append(text)
        return headers

    def missing_upload_history_columns(self):
        headers = [header.casefold() for header in self.get_upload_history_headers()]
        return [
            column
            for column in self.UPLOAD_HISTORY_COLUMNS
            if column.casefold() not in headers
        ]

    def get_upload_history_row_count(self):
        return len(self.driver.find_elements(*self.UPLOAD_HISTORY_ROWS))

    # --- Upload item file actions ---
    def open_upload_item_file_tab(self):
        self.click_any_element(self.UPLOAD_ITEM_FILE_TAB_LOCATORS)

    UPLOAD_FORMAT_TRIGGER = (
        By.XPATH,
        "//*[contains(normalize-space(),'Upload format')]"
        "//button[normalize-space()='Excel' or normalize-space()='Word']"
        " | //button[normalize-space()='Excel' or normalize-space()='Word']",
    )

    def get_selected_upload_format(self):
        """The format the Upload format selector currently shows."""
        for element in self.driver.find_elements(*self.UPLOAD_FORMAT_TRIGGER):
            if element.is_displayed():
                return element.text.strip()
        return ""

    def select_upload_format(self, upload_format, timeout=10):
        """Switch the upload step between Excel and Word.

        The step carries an "Upload format" listbox that defaults to Excel, and
        it is what drives the file input's `accept`: Excel advertises
        .xlsx/.xls/.csv and Word advertises .docx. A Word document therefore
        cannot be staged until this is switched -- Selenium's send_keys bypasses
        `accept`, so skipping this looks like the app silently dropping the
        file rather than the form being in the wrong mode.

        No-op when the wanted format is already selected. Returns True once the
        file input advertises the matching extension.
        """
        wanted = upload_format.strip().casefold()
        extension = {"word": ".docx", "excel": ".xlsx"}[wanted]
        if self.get_selected_upload_format().casefold() == wanted:
            if extension in (self.get_accepted_upload_extensions() or []):
                return True

        trigger = self.wait_utils.until_visible(self.UPLOAD_FORMAT_TRIGGER, timeout=timeout)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", trigger
        )
        # A JS click does not open this listbox -- it needs a real click.
        trigger.click()
        option = (
            By.XPATH,
            f"//*[@role='option'][normalize-space()='{upload_format.strip().title()}']",
        )
        self.wait_utils.until_visible(option, timeout=timeout).click()

        for _ in range(timeout * 2):
            if extension in (self.get_accepted_upload_extensions() or []):
                return True
            sleep(0.5)
        raise AssertionError(
            f"Upload format did not switch to {upload_format!r}: the file input still "
            f"advertises {self.get_accepted_upload_extensions()}."
        )

    def choose_template_format(self, file_format="xlsx", timeout=5):
        """Pick a format from the open Download Template menu.

        Returns False when no option ever appears, which is the older build
        where Download Template was a plain button that downloaded straight
        away -- the caller then just waits for the file as before.
        """
        locator = self.TEMPLATE_FORMAT_OPTION_LOCATORS[file_format]
        for _ in range(timeout * 4):
            options = [
                element
                for element in self.driver.find_elements(*locator)
                if element.is_displayed()
            ]
            if options:
                # The XPath matches every ancestor that contains the menu text
                # too; the option itself is the innermost, so the shortest text.
                min(options, key=lambda element: len(element.text)).click()
                return True
            sleep(0.25)
        return False

    def download_latest_template(self, download_directory, timeout=30, file_format="xlsx"):
        """Download the item template and return the saved file.

        Download Template is a dropdown offering Excel (.xlsx) and Word
        (.docx). Clicking the trigger alone only opens the menu, so a format
        must be chosen or no download is ever requested -- which presents as a
        silent timeout with the button sitting there enabled.
        """
        download_directory = Path(download_directory).resolve()
        download_directory.mkdir(parents=True, exist_ok=True)
        self.driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_directory)},
        )
        before = set(download_directory.glob("*"))
        self.click_any_element(self.DOWNLOAD_TEMPLATE_LOCATORS)
        self.choose_template_format(file_format)
        for _ in range(timeout * 2):
            candidates = [
                path for path in download_directory.glob(f"*.{file_format}")
                if path not in before and not path.name.endswith(".crdownload")
            ]
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime)
            sleep(0.5)
        raise TimeoutException(
            f"Latest item-upload template was not downloaded as .{file_format}. "
            "If the Download Template menu opened but no format was picked, the "
            "option locator no longer matches."
        )

    def get_upload_history_statuses(self, timeout=30):
        """Return the statuses shown in the Previously Uploaded Files table."""
        try:
            rows = self.wait_utils.until_condition(
                lambda driver: [
                    row
                    for row in driver.find_elements(*self.UPLOAD_HISTORY_ROWS)
                    if row.is_displayed()
                ]
                or False,
                timeout=timeout,
            )
        except TimeoutException:
            return []
        statuses = []
        for row in rows:
            row_lines = {line.strip().upper() for line in row.text.splitlines() if line.strip()}
            for status in ("PASSED", "FAILED"):
                if status in row_lines:
                    statuses.append(status)
                    break
        return statuses

    # Every history row offers exactly one download control, but which one is
    # decided by the rejected-item count rather than by the PASSED/FAILED
    # status: a partially-rejected upload still passes and offers the annotated
    # workbook, while a wholly-failed upload that produced no annotations offers
    # the plain file. Callers therefore ask for "this row's download action" and
    # let the page report which of the two it turned out to be, instead of
    # deriving the label from the status and timing out when the app disagrees.
    UPLOAD_HISTORY_DOWNLOAD_LABELS = ("Download Annotated File", "Download File")

    @classmethod
    def row_action_locator(cls, label):
        return (
            By.XPATH,
            ".//*[self::button or self::a]"
            f"[contains(normalize-space(), {cls.xpath_literal(label)})]",
        )

    def find_row_action(self, row, action_texts):
        """This row's first usable control, and the label it matched.

        Labels are tried in the order given, so the caller decides precedence.
        Returns ``(None, "")`` when the row offers none of them - an absent
        control is an answer here, not an error.
        """
        for label in action_texts:
            for action in row.find_elements(*self.row_action_locator(label)):
                try:
                    if action.is_displayed() and action.is_enabled():
                        return action, label
                except Exception:  # noqa: BLE001 - an unreadable control is an absent one
                    continue
        return None, ""

    @staticmethod
    def row_has_file_suffix(row_lines, file_suffix):
        """Whether a row's File Name ends in `file_suffix` (e.g. ".xlsx").

        Word uploads are accepted alongside Excel, and a row's download comes
        back in the format it was uploaded in, so a caller that needs a workbook
        has to pick an Excel row rather than whichever row comes first.

        The File Name and Uploaded On cells share one line of row text
        ("x.xlsx 24 Sept 2026, 3:19 pm"), so the suffix is matched per word.
        """
        suffix = file_suffix.casefold()
        return any(
            word.casefold().endswith(suffix)
            for line in row_lines
            for word in line.split()
        )

    def get_upload_history_row(self, status, action_text=None, timeout=30, file_suffix=None):
        normalized_status = str(status).strip().upper()
        if normalized_status not in ("PASSED", "FAILED"):
            raise ValueError(f"Unsupported upload-history status: {status!r}")
        action_texts = (
            (action_text,) if isinstance(action_text, str) else tuple(action_text or ())
        )

        def matching_row(driver):
            for row in driver.find_elements(*self.UPLOAD_HISTORY_ROWS):
                try:
                    if not row.is_displayed():
                        continue
                    row_lines = {
                        line.strip().upper()
                        for line in row.text.splitlines()
                        if line.strip()
                    }
                    if normalized_status not in row_lines:
                        continue
                    if file_suffix and not self.row_has_file_suffix(row_lines, file_suffix):
                        continue
                    if action_texts and not self.find_row_action(row, action_texts)[0]:
                        continue
                    return row
                except Exception:
                    continue
            return False

        return self.wait_utils.until_condition(matching_row, timeout=timeout)

    def get_upload_history_download_label(self, status, timeout=30, file_suffix=None):
        """Which download action the first `status` row actually offers."""
        row = self.get_upload_history_row(
            status,
            action_text=self.UPLOAD_HISTORY_DOWNLOAD_LABELS,
            timeout=timeout,
            file_suffix=file_suffix,
        )
        return self.find_row_action(row, self.UPLOAD_HISTORY_DOWNLOAD_LABELS)[1]

    # The history table pages at 20 rows, newest first, and its pager is the
    # only one on the upload step. A heavily exercised account runs to a dozen
    # pages or more, and a run's worth of passing uploads pushes its older
    # FAILED rows off page 1 entirely — sme2@dev.com's first FAILED row sits on
    # page 3 of 15. A caller looking for a particular status therefore pages
    # forward instead of concluding from page 1 that the status does not exist.
    UPLOAD_HISTORY_NEXT_PAGE = (By.CSS_SELECTOR, "button[aria-label='next page' i]")
    UPLOAD_HISTORY_PAGE_LABEL = (
        By.XPATH,
        "//*[starts-with(normalize-space(), 'Page ') and contains(normalize-space(), ' of ')]",
    )

    def get_upload_history_page_label(self):
        """The pager's "Page 3 of 15", or "" when the table does not page."""
        elements = self.driver.find_elements(*self.UPLOAD_HISTORY_PAGE_LABEL)
        return elements[0].text.strip() if elements else ""

    def go_to_next_upload_history_page(self, timeout=30):
        """Advance one history page; report whether there was one to go to.

        The rows are replaced in place rather than the table being torn down,
        so waiting for the table would return immediately and the caller would
        read the page it just left. This waits for the first row's text to
        change instead.
        """
        buttons = self.driver.find_elements(*self.UPLOAD_HISTORY_NEXT_PAGE)
        if not buttons or not buttons[0].is_enabled():
            return False
        rows = self.driver.find_elements(*self.UPLOAD_HISTORY_ROWS)
        first_row_before = rows[0].text if rows else ""
        self.driver.execute_script("arguments[0].click();", buttons[0])
        try:
            self.wait_utils.until_condition(
                lambda driver: bool(
                    (current := driver.find_elements(*self.UPLOAD_HISTORY_ROWS))
                    and current[0].text != first_row_before
                ),
                timeout=timeout,
            )
        except TimeoutException:
            return False
        return True

    def has_downloadable_upload_history_row(self, status, timeout=5, file_suffix=None):
        """Whether a `status` row exists that can actually be downloaded.

        Used to pick a usable account: an account whose history merely *shows*
        both statuses is not enough, because the row still has to carry a
        download control for the rest of the flow to have anything to click.
        """
        try:
            self.get_upload_history_row(
                status,
                action_text=self.UPLOAD_HISTORY_DOWNLOAD_LABELS,
                timeout=timeout,
                file_suffix=file_suffix,
            )
            return True
        except TimeoutException:
            return False

    def capture_upload_history_status_screenshot(
        self,
        status,
        screenshot_name,
        action_text=None,
        file_suffix=None,
    ):
        row = self.get_upload_history_row(
            status, action_text=action_text, file_suffix=file_suffix
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            row,
        )
        return ScreenshotUtils.capture(self.driver, screenshot_name)

    def download_upload_history_file(
        self, status, download_directory, timeout=45, file_suffix=None
    ):
        """Download the first PASSED or FAILED upload-history workbook."""
        normalized_status = str(status).strip().upper()
        if normalized_status not in ("PASSED", "FAILED"):
            raise ValueError(f"Unsupported upload-history status: {status!r}")

        download_directory = Path(download_directory).resolve()
        download_directory.mkdir(parents=True, exist_ok=True)
        self.driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_directory)},
        )
        before = {path.resolve() for path in download_directory.iterdir() if path.is_file()}

        row = self.get_upload_history_row(
            normalized_status,
            action_text=self.UPLOAD_HISTORY_DOWNLOAD_LABELS,
            timeout=timeout,
            file_suffix=file_suffix,
        )
        download_button, action_text = self.find_row_action(
            row, self.UPLOAD_HISTORY_DOWNLOAD_LABELS
        )
        if download_button is None:
            raise TimeoutException(
                "No download action was available for the "
                f"{normalized_status} upload row."
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            download_button,
        )
        self.pause_before_action()
        try:
            download_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", download_button)

        for _ in range(timeout * 2):
            candidates = [
                path
                for path in download_directory.iterdir()
                if path.is_file()
                and path.resolve() not in before
                and not path.name.casefold().endswith((".crdownload", ".tmp"))
                and path.stat().st_size > 0
            ]
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime)
            sleep(0.5)
        raise TimeoutException(
            f"The {normalized_status} upload-history workbook was not downloaded."
        )

    VIEW_ERRORS_DIALOG_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]",
        ),
    ]

    def get_upload_history_row_by_file_name(self, file_name, timeout=45):
        """Poll the Previously Uploaded Files table for a row for this file name.

        Used to confirm a just-uploaded file shows up in the history listing in
        real time (i.e. without needing a manual page refresh).
        """
        normalized_name = str(file_name).strip().casefold()

        def matching_row(driver):
            for row in driver.find_elements(*self.UPLOAD_HISTORY_ROWS):
                try:
                    if row.is_displayed() and normalized_name in row.text.casefold():
                        return row
                except Exception:
                    continue
            return False

        return self.wait_utils.until_condition(matching_row, timeout=timeout)

    @staticmethod
    def get_upload_history_row_status(row):
        row_lines = {line.strip().upper() for line in row.text.splitlines() if line.strip()}
        for status in ("PASSED", "FAILED"):
            if status in row_lines:
                return status
        return None

    def click_upload_history_row_action(self, row, action_text):
        buttons = row.find_elements(
            By.XPATH,
            ".//*[self::button or self::a]"
            f"[contains(normalize-space(), '{action_text}')]",
        )
        button = next(
            (button for button in buttons if button.is_displayed() and button.is_enabled()),
            None,
        )
        if button is None:
            raise TimeoutException(
                f"{action_text!r} was not available in the upload-history row."
            )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        self.pause_before_action()
        try:
            button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", button)
        return button

    def click_view_errors_and_get_message(self, row, timeout=20):
        """Click 'View Errors' on a FAILED row and return the error details shown."""
        self.click_upload_history_row_action(row, "View Errors")

        def error_content(driver):
            for locator in self.VIEW_ERRORS_DIALOG_LOCATORS:
                for element in driver.find_elements(*locator):
                    try:
                        if element.is_displayed() and element.text.strip():
                            return element.text.strip()
                    except Exception:
                        continue
            return False

        try:
            return self.wait_utils.until_condition(error_content, timeout=timeout)
        except TimeoutException:
            # Some layouts expand the error inline instead of opening a dialog.
            return row.text.strip()

    def close_view_errors_dialog(self):
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def download_file_from_upload_history_row(self, row, action_text, download_directory, timeout=45):
        """Click a row action (e.g. 'Download Annotated File') and return the downloaded path."""
        download_directory = Path(download_directory).resolve()
        download_directory.mkdir(parents=True, exist_ok=True)
        self.driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_directory)},
        )
        before = {path.resolve() for path in download_directory.iterdir() if path.is_file()}

        self.click_upload_history_row_action(row, action_text)

        for _ in range(timeout * 2):
            candidates = [
                path
                for path in download_directory.iterdir()
                if path.is_file()
                and path.resolve() not in before
                and not path.name.casefold().endswith((".crdownload", ".tmp"))
                and path.stat().st_size > 0
            ]
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime)
            sleep(0.5)
        raise TimeoutException(f"{action_text!r} did not produce a download.")

    def upload_file(self, file_path):
        upload_path = Path(file_path).expanduser().resolve()
        if not upload_path.exists():
            raise FileNotFoundError(f"Upload item file not found: {upload_path}")

        file_input = self.wait_utils.until_present(self.FILE_INPUT, timeout=20)
        self.driver.execute_script(
            """
            const input = arguments[0];
            input.style.display = 'block';
            input.style.visibility = 'visible';
            input.style.opacity = 1;
            input.style.height = '1px';
            input.style.width = '1px';
            """,
            file_input,
        )
        file_input.send_keys(str(upload_path))
        # Selenium's file-input send_keys operation already emits the native
        # input/change events. Dispatching them again makes the SPA enqueue the
        # same workbook twice and produces duplicated QAR rows (6 -> 12).
        self.confirm_switch_after_upload()
        return upload_path

    def confirm_switch_after_upload(self, timeout=4):
        """Confirm "Switch uploaded file?" if the new upload raised it.

        An account still holding an unfinished upload (e.g. the
        Valid_after_rejections.xlsx that the non-xlsx negative leaves on sme1)
        guards the new file behind this dialog the moment it is dropped, so
        nothing downstream ever renders until it is answered.
        """
        try:
            self.wait_utils.until_condition(
                lambda driver: self.confirm_switch_uploaded_file_if_prompted(),
                timeout=timeout,
            )
        except TimeoutException:
            pass  # no stale upload, no dialog - the normal case

    def upload_files(self, file_paths):
        """Stage several files through one uploader interaction.

        The Word ingestion path needs it: a document that references images by
        filename is only complete alongside its image .zip, and staging them in
        two separate send_keys calls makes the SPA treat the second as a new
        upload and drop the first. A single newline-joined send_keys is how a
        multiple-file input takes a set.

        Falls back to one-at-a-time when the input is not marked `multiple`, so
        a build that has not enabled multi-file selection still gets a useful
        failure from the assertion rather than an opaque Selenium error.
        """
        upload_paths = []
        for file_path in file_paths:
            upload_path = Path(file_path).expanduser().resolve()
            if not upload_path.exists():
                raise FileNotFoundError(f"Upload item file not found: {upload_path}")
            upload_paths.append(upload_path)

        file_input = self.wait_utils.until_present(self.FILE_INPUT, timeout=20)
        self.driver.execute_script(
            """
            const input = arguments[0];
            input.style.display = 'block';
            input.style.visibility = 'visible';
            input.style.opacity = 1;
            input.style.height = '1px';
            input.style.width = '1px';
            """,
            file_input,
        )

        if len(upload_paths) > 1 and not file_input.get_attribute("multiple"):
            for upload_path in upload_paths:
                file_input.send_keys(str(upload_path))
            self.confirm_switch_after_upload()
            return upload_paths

        file_input.send_keys("\n".join(str(path) for path in upload_paths))
        self.confirm_switch_after_upload()
        return upload_paths

    def get_accepted_upload_extensions(self):
        """The extensions the uploader advertises, lower-cased and dot-prefixed.

        Read off the file input's `accept` attribute rather than the visible
        "Accepted Formats" copy: the attribute is what actually gates the OS
        file picker, so a build whose wording and behaviour disagree is caught
        instead of being read as agreement.
        """
        file_input = self.wait_utils.until_present(self.FILE_INPUT, timeout=20)
        raw_accept = file_input.get_attribute("accept") or ""
        return [
            token.strip().casefold()
            for token in raw_accept.split(",")
            if token.strip()
        ]

    def get_active_upload_delete_button(self):
        return self.driver.execute_script(
            """
            const markers = Array.from(document.querySelectorAll('*')).filter(element =>
                (element.innerText || element.textContent || '')
                    .trim().toLowerCase() === 'currently working on this file.'
            );
            const marker = markers[0];
            if (!marker) return null;

            let card = marker.closest('li, [role="listitem"], tr');
            if (!card) {
                card = marker.parentElement;
                while (card && card !== document.body) {
                    const text = (card.innerText || card.textContent || '').trim();
                    if (/\\.xlsx?/i.test(text) && text.length < 1200) break;
                    card = card.parentElement;
                }
            }
            if (!card || card === document.body) return null;

            return Array.from(card.querySelectorAll('button, [role="button"]'))
                .find(button => {
                    const label = [
                        button.getAttribute('aria-label'),
                        button.getAttribute('title'),
                        button.innerText,
                        button.textContent,
                    ].filter(Boolean).join(' ').toLowerCase();
                    return /delete|remove|discard|trash/.test(label)
                        || Boolean(button.querySelector(
                            'svg[class*="trash" i], [data-lucide*="trash" i]'
                        ));
                }) || null;
            """
        )

    def discard_active_upload_if_present(self):
        self.pause_before_action()

        def has_active_upload(driver):
            return (
                "currently working on this file"
                in driver.find_element(By.TAG_NAME, "body").text.casefold()
            )

        if not has_active_upload(self.driver):
            return False

        for _ in range(20):
            if not has_active_upload(self.driver):
                break

            delete_button = self.get_active_upload_delete_button()
            if delete_button is None:
                for locator in self.UPLOADED_FILE_DELETE_LOCATORS:
                    delete_button = next(
                        (
                            button
                            for button in self.driver.find_elements(*locator)
                            if button.is_displayed() and button.is_enabled()
                        ),
                        None,
                    )
                    if delete_button is not None:
                        break

            if delete_button is None:
                raise AssertionError(
                    "A previous unfinished upload is still active and has no "
                    "available delete control. Refusing to read stale item rows."
                )

            visible_delete_ids_before = {
                button.id
                for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                for button in self.driver.find_elements(*locator)
                if button.is_displayed()
            }
            self.driver.execute_script("arguments[0].click();", delete_button)
            self.confirm_delete_uploaded_file_if_prompted()
            try:
                self.wait_utils.until_condition(
                    lambda driver: (
                        not has_active_upload(driver)
                        or len(
                            {
                                button.id
                                for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                                for button in driver.find_elements(*locator)
                                if button.is_displayed()
                            }
                        )
                        < len(visible_delete_ids_before)
                    ),
                    timeout=15,
                )
            except TimeoutException:
                pass
            self.pause_before_action()
        else:
            raise AssertionError(
                "The previous unfinished upload remained active after deleting "
                "all available stale rows."
            )

        if has_active_upload(self.driver):
            raise AssertionError(
                "The previous unfinished upload could not be fully discarded."
            )

        try:
            self.wait_for_upload_slot_ready()
        except TimeoutException:
            self.driver.refresh()
            self.wait_for_application_to_load()
            self.open_item_creation_module()
            self.open_upload_item_file_tab()
            self.open_upload_step()
        return True

    def discard_staged_upload_files(self):
        """Remove files left in the upload wizard by an interrupted test run."""
        removed_any = False
        for _ in range(20):
            delete_button = None
            for locator in self.UPLOADED_FILE_DELETE_LOCATORS:
                delete_button = next(
                    (
                        button
                        for button in self.driver.find_elements(*locator)
                        if button.is_displayed() and button.is_enabled()
                    ),
                    None,
                )
                if delete_button is not None:
                    break
            if delete_button is None:
                return removed_any

            visible_delete_ids_before = {
                button.id
                for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                for button in self.driver.find_elements(*locator)
                if button.is_displayed()
            }
            self.driver.execute_script("arguments[0].click();", delete_button)
            self.confirm_delete_uploaded_file_if_prompted()
            removed_any = True
            self.wait_utils.until_condition(
                lambda driver: len(
                    {
                        button.id
                        for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                        for button in driver.find_elements(*locator)
                        if button.is_displayed()
                    }
                )
                < len(visible_delete_ids_before),
                timeout=20,
            )
            self.pause_before_action()

        raise AssertionError(
            "Upload staging still contained files after 20 cleanup attempts."
        )

    def activate_uploaded_file(self, file_name):
        normalized_name = str(file_name).strip().casefold()

        def activate_exact_file(driver):
            # Clicking our card while a stale upload is "Currently working"
            # raises the "Switch uploaded file?" guard; unconfirmed, every
            # later poll clicks behind it and the wait times out.
            self.confirm_switch_uploaded_file_if_prompted()
            return driver.execute_script(
                """
                const expected = arguments[0];
                const labels = Array.from(document.querySelectorAll('*'))
                    .filter(element => {
                        const text = (element.innerText || element.textContent || '')
                            .trim().toLowerCase();
                        return text === expected
                            && !Array.from(element.children).some(child =>
                                (child.innerText || child.textContent || '')
                                    .trim().toLowerCase() === expected
                            );
                    });
                const label = labels[0];
                if (!label) return false;

                let card = label.closest('li, [role="listitem"], tr');
                if (!card) {
                    card = label.parentElement;
                    while (card && card !== document.body) {
                        const text = (card.innerText || card.textContent || '').trim();
                        if (/\\.xlsx?/i.test(text) && text.length < 1200) break;
                        card = card.parentElement;
                    }
                }
                if (!card || card === document.body) return false;
                const cardText = (card.innerText || card.textContent || '').toLowerCase();
                if (cardText.includes('currently working on this file')) return true;
                const pageText = (document.body.innerText || document.body.textContent || '')
                    .toLowerCase();
                if (!pageText.includes('currently working on this file')
                    && !pageText.includes('finish editing first file')
                    && cardText.includes(expected)) {
                    return true;
                }

                const target = label.closest('a, button, [role="button"], [tabindex]')
                    || card.closest('a, button, [role="button"], [tabindex]')
                    || label;
                target.scrollIntoView({block: 'center'});
                target.click();
                return false;
                """,
                normalized_name,
            )

        self.wait_utils.until_condition(activate_exact_file, timeout=60)
        return True

    def delete_uploaded_file_if_present(self):
        """Remove the current upload card so the next file starts from a clean state."""
        last_error = None
        for locator in self.UPLOADED_FILE_DELETE_LOCATORS:
            for button in self.driver.find_elements(*locator):
                try:
                    if not button.is_displayed() or not button.is_enabled():
                        continue
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        button,
                    )
                    self.pause_before_action()
                    self.driver.execute_script("arguments[0].click();", button)
                    self.confirm_delete_uploaded_file_if_prompted()
                    self.wait_for_upload_slot_ready()
                    return True
                except Exception as error:
                    last_error = error
                    continue
        if last_error:
            raise last_error
        return False

    def confirm_delete_uploaded_file_if_prompted(self):
        for locator in self.DELETE_CONFIRM_LOCATORS:
            try:
                confirm_button = self.wait_utils.until_clickable(locator, timeout=3)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", confirm_button)
                return True
            except Exception:
                continue
        return False

    def wait_for_upload_slot_ready(self):
        self.wait_utils.until_present(self.FILE_INPUT, timeout=20)
        self.pause_before_action()
        return True

    def reset_upload_step(self):
        """Prefer deleting the file card; fall back to reopening the upload step."""
        try:
            if self.delete_uploaded_file_if_present():
                return True
        except Exception:
            pass
        self.driver.refresh()
        self.wait_for_application_to_load()
        self.open_item_creation_module()
        self.open_upload_item_file_tab()
        self.open_upload_step()
        # The fresh navigation renders the file input before the SPA finishes
        # wiring its change handler up; send_keys() right after this refresh
        # path silently drops (input value never registers) unless the input
        # is given the same settle wait the delete-card path already gets.
        self.wait_for_upload_slot_ready()
        return True

    def wait_for_upload_validation_success(self):
        """Return the upload's validation-success message.

        Tries the primary UPLOAD_SUCCESS_MESSAGE locator (the multi-file
        wording), then a broader scan that also covers the single-file wording.
        Raises AssertionError if neither reports success -- callers assert on
        the returned text, so returning an assumed-success string here would
        make a rejected upload indistinguishable from an accepted one.
        """
        # Try primary success message locator
        try:
            element = self.wait_utils.until_visible(self.UPLOAD_SUCCESS_MESSAGE, timeout=20)
            return self.extract_upload_status_message(element.text)
        except TimeoutException:
            pass

        # Broader fallback: wait for any success/status text to appear in the body.
        # Deliberately no 'Upload Status' / 'File Upload Status' clause: that is the
        # header of the ever-present "Previously Uploaded Files" history table, so it
        # matches whether or not this upload succeeded and reports false-positive
        # success. Single-file uploads word it "All N rows added successfully"
        # rather than the multi-file "validated successfully", so both are listed.
        broad_success = (
            By.XPATH,
            "//*[contains(normalize-space(),'PASSED') "
            "or contains(normalize-space(),'validated successfully') "
            "or contains(normalize-space(),'added successfully') "
            "or contains(normalize-space(),'Validation Passed')]",
        )
        # The app answers a rejected file on the same line a success would use
        # ("11_CaseBased.docx: All 1 row(s) failed validation. See the
        # downloaded file for details."). Watching only for success waited the
        # full minute on that and then reported "no status message appeared",
        # which hid a clear rejection inside a page dump.
        def success_or_rejection(driver):
            for element in driver.find_elements(*broad_success):
                try:
                    if element.is_displayed():
                        return ("success", element.text)
                except Exception:
                    continue
            for line in driver.find_element(By.TAG_NAME, "body").text.splitlines():
                if "failed validation" in line.casefold() or line.strip().startswith("Upload failed"):
                    return ("rejected", line.strip())
            return False

        try:
            outcome, text = self.wait_utils.until_condition(success_or_rejection, timeout=60)
        except TimeoutException:
            pass
        else:
            if outcome == "success":
                return self.extract_upload_status_message(text)
            raise AssertionError(f"Upload was rejected by validation: {text}")

        # Nothing on screen reports success. This used to return a hardcoded
        # "All files uploaded and validated successfully Status: PASSED", which
        # is the exact wording callers assert on -- so a rejected upload passed
        # as a success. Raise instead: the caller wanted proof of validation and
        # there is none. Include what the page does say, since the app reports
        # row-level failures ("All 1 row(s) failed validation") right here.
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.strip()
        except Exception:
            page_text = ""
        raise AssertionError(
            "Upload did not report validation success: no status message "
            "appeared within the wait. Page text follows:\n"
            f"{page_text[:2000]}"
        )

    def wait_for_upload_rejection(self, timeout=30):
        def visible_rejection(driver):
            for locator in self.UPLOAD_REJECTION_LOCATORS:
                for element in driver.find_elements(*locator):
                    try:
                        if element.is_displayed() and element.text.strip():
                            return element.text.strip()
                    except Exception:
                        continue
            page_text = driver.find_element(By.TAG_NAME, "body").text
            if any(
                token in page_text.casefold()
                for token in (
                    "invalid file format",
                    "upload failed",
                    "header row",
                    "only .xlsx",
                    "missing required columns",
                    "required columns",
                )
            ):
                return page_text
            return False

        return self.wait_utils.until_condition(visible_rejection, timeout=timeout)

    @staticmethod
    def extract_upload_status_message(message_text):
        message_lines = [line.strip() for line in message_text.splitlines() if line.strip()]
        for index, line in enumerate(message_lines):
            if "All files uploaded and validated successfully" in line:
                if index + 1 < len(message_lines) and "Status:" in message_lines[index + 1]:
                    return f"{line} {message_lines[index + 1]}"
                return line
        # "File Upload Status" is a column heading in the uploaded-files history
        # table, not a status value -- matching it here returned the header row
        # ("File Name Uploaded On File Upload Status ...") as the success message.
        for line in message_lines:
            if "added successfully" in line or "Status:" in line:
                return line
        return message_text.strip()

    @staticmethod
    def extract_upload_id(message_text):
        match = re.search(r"Upload ID:\s*(\d+)", message_text)
        return match.group(1) if match else ""

    # --- Submit for QAR locators ---
    CONTINUE_BUTTON = (By.XPATH, "//button[contains(normalize-space(),'Continue')]")
    # NOTE: This locator MUST only match the QAR submission button on Step 4 of the wizard.
    # Do NOT broaden it to contain('Submit') — that matches metadata buttons on Step 3,
    # which causes the wizard to reset to Step 1.
    SUBMIT_FOR_QAR_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(),'Submit Set for QAR')"
        " or contains(normalize-space(),'Submit for QAR')"
        " or contains(normalize-space(),'Submit Set For QAR')]",
    )
    SUBMIT_CONFIRM_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
            "//button[(contains(normalize-space(),'Submit') or normalize-space()='Confirm' or normalize-space()='Yes') "
            "and not(@disabled)]",
        ),
        (By.XPATH, "//button[normalize-space()='Confirm' or normalize-space()='Yes']"),
    ]
    FILE_VALIDATION_PASSED = (
        By.XPATH,
        "//*[contains(normalize-space(),'File Validation Passed')]",
    )
    REVIEW_ITEM_ID_CELLS = (
        By.XPATH,
        "//table//tbody/tr/td[1]//*[normalize-space()] | //table//tbody/tr/td[1]",
    )
    QAR_RESULT_ITEM_ID_CELLS = (
        By.XPATH,
        "//table//tbody/tr/td[1]//*[normalize-space()] | //table//tbody/tr/td[1]",
    )
    OCR_SUCCESS_MESSAGE = (
        By.XPATH,
        "//*[contains(normalize-space(), 'QAR completed') "
        "or contains(normalize-space(), 'QAR ran') "
        "or contains(normalize-space(), 'returned') "
        "or contains(normalize-space(), 'Needs Revision')]",
    )
    QAR_RESULTS_HEADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'QAR Results')]",
    )

    # --- Submit for QAR actions ---
    def click_continue(self):
        """Click the Continue button using JS to avoid Selenium clickability issues.

        Waits for any global loading overlay to disappear, then locates the Continue
        button (or any visible button/link containing 'Continue') and triggers a JS
        click after scrolling it into view.
        """
        # Wait for loading overlay to clear first
        try:
            self.wait_utils.until_condition(
                lambda driver: not driver.find_elements(*self.GLOBAL_LOADING_INDICATOR),
                timeout=20,
            )
        except Exception:
            pass

        # Primary: explicit CONTINUE_BUTTON locator
        try:
            button = self.wait_utils.until_present(self.CONTINUE_BUTTON, timeout=15)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            self.driver.execute_script("arguments[0].click();", button)
            self.pause_before_action()
            return
        except Exception:
            pass

        # Fallback: any visible button or link containing 'Continue'
        generic = (By.XPATH, "//*[self::button or self::a][contains(normalize-space(),'Continue')]")
        try:
            button = self.wait_utils.until_present(generic, timeout=10)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            self.driver.execute_script("arguments[0].click();", button)
            self.pause_before_action()
            return
        except Exception:
            pass

        raise TimeoutException("Continue button not found or not clickable after all attempts")

    def click_submit_for_qar(self):
        # Use until_present instead of until_clickable — loading overlay blocks clickability check
        try:
            self.wait_utils.until_present(self.SUBMIT_FOR_QAR_BUTTON, timeout=30)
        except TimeoutException:
            # The SPA can accept the request and redirect between the caller's
            # presence check and this second lookup. That transition is success.
            if self.has_qar_results_or_progress(self.driver):
                return True
            raise
        self.pause_before_action()
        click_attempts = (
            self.click_visible_submit_button_with_action_chain,
            self.click_visible_submit_button,
            self.js_click_visible_submit_button,
            self.dispatch_pointer_events_to_visible_submit_button,
            self.press_enter_on_visible_submit_button,
        )
        for click_attempt in click_attempts:
            try:
                click_attempt()
                self.confirm_submit_if_prompted()
                # A successful request can take a while before React replaces
                # this step. Do not fire the remaining click fallbacks while
                # the first request may still be in flight; that can add the
                # same uploaded rows to a set more than once.
                try:
                    self.wait_utils.until_condition(
                        lambda driver: self.has_qar_results_or_progress(driver)
                        or not self.has_visible_submit_for_qar_button(driver),
                        timeout=45,
                    )
                    return True
                except TimeoutException:
                    # The click itself completed without an exception. Treat it
                    # as submitted and let the result wait report any timeout;
                    # clicking again can duplicate every uploaded item.
                    return True
            except Exception:
                continue
        return False

    def dispatch_pointer_events_to_visible_submit_button(self):
        clicked = self.driver.execute_script(
            """
            const button = Array.from(document.querySelectorAll('button')).find(candidate => {
                const rect = candidate.getBoundingClientRect();
                const style = getComputedStyle(candidate);
                const label = (candidate.innerText || candidate.textContent || '')
                    .trim().toLowerCase();
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && !candidate.disabled
                    && label.includes('submit set for qar');
            });
            if (!button) return false;
            button.scrollIntoView({block: 'center'});
            for (const eventName of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                button.dispatchEvent(new MouseEvent(eventName, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                }));
            }
            return true;
            """
        )
        if not clicked:
            raise TimeoutException("No enabled Submit Set for QAR button accepted pointer events.")

    def get_visible_submit_for_qar_button(self):
        buttons = self.driver.find_elements(*self.SUBMIT_FOR_QAR_BUTTON)
        for button in buttons:
            try:
                if button.is_displayed() and button.is_enabled():
                    label = button.text.strip().casefold()
                    if "submit set for qar" in label or "submit for qar" in label:
                        return button
            except Exception:
                continue
        return self.wait_utils.until_present(self.SUBMIT_FOR_QAR_BUTTON, timeout=10)

    def click_visible_submit_button_with_action_chain(self):
        submit_button = self.get_visible_submit_for_qar_button()
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        ActionChains(self.driver).move_to_element(submit_button).pause(0.2).click().perform()

    def click_visible_submit_button(self):
        submit_button = self.get_visible_submit_for_qar_button()
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        submit_button.click()

    def js_click_visible_submit_button(self):
        clicked = self.driver.execute_script(
            """
            const isVisible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return rect.width > 0
                    && rect.height > 0
                    && style.visibility !== 'hidden'
                    && style.display !== 'none'
                    && !element.disabled;
            };
            const button = [...document.querySelectorAll('button')]
                .find((candidate) => isVisible(candidate)
                    && candidate.innerText.trim().toLowerCase().includes('submit set for qar'));
            if (!button) return false;
            button.scrollIntoView({block: 'center'});
            button.click();
            return true;
            """
        )
        if not clicked:
            raise TimeoutException("No visible enabled Submit Set for QAR button found.")

    def press_enter_on_visible_submit_button(self):
        submit_button = self.get_visible_submit_for_qar_button()
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        submit_button.send_keys(Keys.ENTER)

    def did_leave_submit_step(self):
        try:
            self.wait_utils.until_condition(
                lambda driver: self.has_qar_results_or_progress(driver)
                or not self.has_visible_submit_for_qar_button(driver),
                timeout=8,
            )
            return True
        except Exception:
            return False

    def confirm_submit_if_prompted(self):
        def visible_submit_confirmation(driver):
            return driver.execute_script(
                """
                const visible = element => {
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return rect.width > 0
                        && rect.height > 0
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const isPopup = element => {
                    const role = (element.getAttribute('role') || '').toLowerCase();
                    const className = String(element.className || '').toLowerCase();
                    const style = getComputedStyle(element);
                    return role === 'dialog'
                        || role === 'alertdialog'
                        || element.getAttribute('aria-modal') === 'true'
                        || /(^|[\\s_-])(modal|dialog|popup|confirm)([\\s_-]|$)/.test(className)
                        || (style.position === 'fixed'
                            && Number.parseInt(style.zIndex || '0', 10) >= 10);
                };
                const priorities = [
                    'submit', 'confirm', 'yes', 'proceed', 'continue', 'ok'
                ];
                const candidates = Array.from(document.querySelectorAll(
                    'button:not([disabled]), [role="button"]'
                )).filter(button => {
                    if (!visible(button) || button.getAttribute('aria-disabled') === 'true') {
                        return false;
                    }
                    const label = (button.innerText || button.textContent || '')
                        .trim().toLowerCase();
                    if (/submit\\s+(set\\s+)?for\\s+qar/.test(label)) return false;
                    let container = button.parentElement;
                    while (container && container !== document.body) {
                        if (visible(container) && isPopup(container)) return true;
                        container = container.parentElement;
                    }
                    return false;
                });
                for (const priority of priorities) {
                    const exact = candidates.find(button =>
                        (button.innerText || button.textContent || '')
                            .trim().toLowerCase() === priority
                    );
                    if (exact) return exact;
                }
                return candidates.find(button => {
                    const text = (button.innerText || button.textContent || '')
                        .trim().toLowerCase();
                    return !/cancel|back|no|close/.test(text)
                        && /submit|confirm|yes|proceed|continue|ok/.test(text);
                }) || null;
                """
            )

        try:
            confirm_button = self.wait_utils.until_condition(
                visible_submit_confirmation,
                timeout=5,
            )
        except TimeoutException:
            return False
        confirm_label = (confirm_button.text or "").strip().casefold()
        if re.search(r"submit\s+(set\s+)?for\s+qar", confirm_label):
            return False
        self.pause_before_action()
        try:
            confirm_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", confirm_button)
        return True

    def get_visible_qar_submit_blocker(self):
        return self.driver.execute_script(
            """
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const candidates = Array.from(document.querySelectorAll(
                '[role="alert"], [role="alertdialog"], .toast, .Toastify__toast, '
                + '[class*="error"], [class*="Error"], [class*="snackbar"], [class*="Snackbar"]'
            )).filter(visible);
            return candidates
                .map(element => (element.innerText || element.textContent || '').trim())
                .filter(Boolean)
                .sort((left, right) => left.length - right.length)[0] || '';
            """
        )

    def recover_active_upload_submit_step(self):
        def reopen_active_file():
            return self.driver.execute_script(
                """
                const marker = Array.from(document.querySelectorAll('*')).find(element =>
                    (element.innerText || element.textContent || '')
                        .trim().toLowerCase() === 'currently working on this file.'
                );
                if (!marker) return false;
                const card = marker.closest('li, [role="listitem"], tr')
                    || marker.parentElement?.parentElement
                    || marker.parentElement;
                if (!card) return false;
                const fileLabel = Array.from(card.querySelectorAll('*')).find(element => {
                    const text = (element.innerText || element.textContent || '').trim();
                    return /\\.xlsx?$/i.test(text)
                        && !Array.from(element.children).some(child =>
                            /\\.xlsx?$/i.test((child.innerText || child.textContent || '').trim())
                        );
                });
                if (!fileLabel) return false;
                const target = fileLabel.closest('a, button, [role="button"], [tabindex]')
                    || fileLabel;
                target.scrollIntoView({block: 'center'});
                target.click();
                return true;
                """
            )

        if reopen_active_file():
            try:
                self.wait_utils.until_condition(
                    lambda driver: self.has_visible_submit_for_qar_button(driver),
                    timeout=15,
                )
                return True
            except TimeoutException:
                pass

        self.driver.refresh()
        self.wait_utils.wait_for_page_ready(timeout=30)
        reopen_active_file()
        try:
            self.wait_utils.until_condition(
                lambda driver: self.has_visible_submit_for_qar_button(driver),
                timeout=30,
            )
            return True
        except TimeoutException:
            return False

    # Which view the QAR verdict was finally read from. The two are not
    # interchangeable for evidence-gathering - the wizard shows a completion
    # toast and an inline results table, the item set's own page shows neither
    # - so callers are told which one they have been left on.
    QAR_OUTCOME_IN_PLACE = "in_place"
    QAR_OUTCOME_ITEM_SET_DETAIL = "item_set_detail"

    def click_submit_for_qar_and_wait_for_results(
        self,
        analysis_timeout=180,
        item_ids=(),
        item_set_id="",
        uploaded_file_name="",
        recovery_timeout=420,
    ):
        """Click Submit Set for QAR and wait for analysis to finish.

        analysis_timeout controls only the final "is QAR analysis complete"
        wait. Larger item sets (e.g. many real images going through Image
        Moderation) can legitimately take longer than the 180s default used
        by lighter-weight text-only item sets.

        Pass uploaded_file_name (the workbook just uploaded) to let a stalled
        wizard fall back to the item set's own page. item_ids alone is not
        enough: the review step numbers nothing, so IDs read there are
        "IS-G1-Mathematics-Ch29-i1" and name no set to look up - the set
        number is assigned only when QAR completes. The grid's "Uploaded File"
        column is what links an upload to the set it became. QAR runs asynchronously
        server-side and the wizard does not reliably follow it there: it can
        sit on "Analysis in progress" until the client stops polling, or drop
        straight back to Confirm & Submit with the button live again. Both
        leave the script nothing to wait on *while the run itself completes
        normally*, so the wizard going quiet is not evidence that QAR failed -
        on 2026-09-29/30 twelve sets reported this and every one that could
        still be read had completed correctly. Reading the verdict off the set
        record instead is purely read-only; the submit is never sent twice.

        Returns QAR_OUTCOME_IN_PLACE when the wizard rendered the results
        itself, or QAR_OUTCOME_ITEM_SET_DETAIL when they had to be recovered.
        """
        item_ids = tuple(item_ids or ())
        item_set_id = item_set_id or self.get_item_set_id_from_item_ids(item_ids)
        last_error = None
        for attempt in range(3):
            clicked = self.click_submit_for_qar()
            if not clicked:
                blocker = self.get_visible_qar_submit_blocker()
                last_error = TimeoutException(
                    "Submit Set for QAR remained on the confirmation step"
                    + (f": {blocker}" if blocker else ".")
                )
                if attempt < 2:
                    self.recover_active_upload_submit_step()
                continue
            try:
                # Each branch below records *what the wizard did* and then
                # defers the verdict to the item set itself. None of them is a
                # result in its own right: the wizard is only one of the places
                # a finished QAR run shows up, and it is the unreliable one.
                stall = None
                try:
                    self.wait_utils.until_condition(
                        lambda driver: self.has_qar_results_or_progress(driver),
                        timeout=90,
                    )
                except TimeoutException:
                    stall = (
                        "QAR submission produced no results, progress indicator, "
                        "or bounce within 90s"
                    )
                if stall is None:
                    try:
                        outcome = self.wait_utils.until_condition(
                            lambda driver: (
                                "complete" if self.is_qar_analysis_complete(driver)
                                else "bounced" if self.has_visible_submit_for_qar_button(driver)
                                else False
                            ),
                            timeout=analysis_timeout,
                        )
                    except TimeoutException:
                        # The wizard sat on "Analysis in progress" and never
                        # moved. Its client-side polling stops well before QAR
                        # does, so raising analysis_timeout does not help -
                        # only re-reading the set does.
                        stall = (
                            "QAR analysis started but never completed or bounced "
                            f"back within {analysis_timeout}s"
                        )
                    else:
                        if outcome == "bounced":
                            # Seen on QA 2026-09-29: the SPA drops back to
                            # Confirm & Submit with the button live again and
                            # no error shown, while the run carries on.
                            stall = (
                                "QAR analysis started but the app returned to "
                                "Confirm & Submit without results or an error message"
                            )
                if stall is None:
                    return self.QAR_OUTCOME_IN_PLACE
                if self.resolve_qar_outcome_from_item_set(
                    item_set_id,
                    item_ids,
                    timeout=recovery_timeout,
                    uploaded_file_name=uploaded_file_name,
                ):
                    return self.QAR_OUTCOME_ITEM_SET_DETAIL
                recovery_error = getattr(self, "last_qar_recovery_error", None)
                target = (
                    item_set_id
                    if self.item_set_id_is_numbered(item_set_id)
                    else Path(str(uploaded_file_name)).name
                )
                raise AssertionError(
                    f"{stall}, and "
                    + (
                        f"no QAR verdict appeared for {target} on the Sets grid "
                        f"within {recovery_timeout}s either, so the run genuinely "
                        "did not produce a result."
                        if target
                        else "neither a numbered item set ID nor the uploaded file "
                        "name was passed in, so the outcome could not be confirmed "
                        "from the set record - the run may well have completed "
                        "server-side."
                    )
                    + (f" Last lookup error: {recovery_error}" if recovery_error else "")
                )
            except Exception as error:
                last_error = error
                if clicked:
                    # Never issue a second submit after a click was accepted.
                    # A slow or failed response must surface as a timeout rather
                    # than mutating the item set a second time.
                    break
        blocker = self.get_visible_qar_submit_blocker()
        if blocker:
            raise TimeoutException(f"QAR submission was blocked: {blocker}") from last_error
        raise last_error

    # Text that means QAR is still running *right now*. Deliberately excludes
    # PENDING_QAR: that is the set's resting state once QAR has blocked every
    # item, so treating it as "still analysing" would wait out the whole
    # recovery window on exactly the sets this recovery exists for.
    QAR_ANALYSIS_IN_FLIGHT_MARKERS = (
        "analysis in progress",
        "qar analysis in progress",
        "processing qar",
        "running qar",
        "generating report",
        "analysing items",
        "analyzing items",
    )

    @staticmethod
    def item_set_id_is_numbered(item_set_id):
        """True when this ID carries the set number, e.g. "IS1405-G1-...".

        The review step renders item IDs *before* a number is assigned, as
        "IS-G1-Mathematics-Ch29-i1", so an ID derived from them names no set
        and cannot be looked one up by.
        """
        return bool(re.match(r"\s*IS\d+", str(item_set_id or ""), re.IGNORECASE))

    def find_item_set_id_by_uploaded_file(self, uploaded_file_name):
        """Which set an upload became, matched on its file name on the Sets grid.

        A set's number is assigned when QAR *completes*, not when the file is
        uploaded, so a run that loses the wizard before the result appears has
        no set ID to search for. The grid's "Uploaded File" column still names
        the workbook, and each run's workbook name is unique, which makes it the
        link from an upload to the set it became.

        Returns "" when no row names this file yet - the set is not listed until
        the backend has registered it.
        """
        wanted = Path(str(uploaded_file_name)).name.casefold()
        if not wanted:
            return ""
        for row in self.get_item_set_list_rows():
            if wanted in (row.get("uploaded_file") or "").casefold():
                candidate = row.get("item_set_id") or ""
                if self.item_set_id_is_numbered(candidate):
                    return candidate
        return ""

    def resolve_qar_outcome_from_item_set(
        self, item_set_id, item_ids=(), timeout=420, uploaded_file_name=""
    ):
        """Read a submitted set's QAR verdict off the set's own page.

        Called when the upload wizard stops reporting on a run it started.
        Read-only by design: it navigates and waits, and never re-submits.

        item_set_id may be unnumbered ("IS-G1-Mathematics-Ch29"), because the
        review step hands out item IDs before the set is numbered. Pass
        uploaded_file_name and the set is found by its workbook name instead.

        Returns True once this set's item rows carry statuses with no analysis
        still in flight - at which point the driver is left on a view showing
        the verdict, with the per-item report expanded where one exists.
        Returns False if that never happens, which is the only state that
        means the run really did not produce a result. On a False, whatever
        last went wrong is left on last_qar_recovery_error so the caller can
        say why rather than only that it gave up.
        """
        self.last_qar_recovery_error = None
        self.recovered_item_set_id = ""
        if not item_set_id and not uploaded_file_name:
            return False

        def verdict_rendered(resolved_id):
            def condition(driver):
                if self.is_item_set_detail_loading(driver):
                    return False
                page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
                if any(
                    marker in page_text
                    for marker in self.QAR_ANALYSIS_IN_FLIGHT_MARKERS
                ):
                    return False
                # Scoped to this set's own "-i<n>" rows, so a set-level table
                # left on screen cannot pass as this set's per-item verdict.
                return bool(self.get_qar_item_statuses(resolved_id))

            return condition

        deadline = monotonic() + timeout
        while True:
            # Each pass re-navigates rather than re-reading the page already on
            # screen. Trusting a view to update itself is what strands the
            # wizard in the first place, and the same SPA renders this page, so
            # a fresh fetch is the only thing that reliably reflects the
            # server. It also covers the set not being listed yet: a set
            # appears once the backend has registered it, so a miss is "not
            # yet", not "never".
            matched_by_file = False
            try:
                self.open_sets_module()
                resolved_id = item_set_id
                if not self.item_set_id_is_numbered(resolved_id):
                    # No number yet, so there is nothing to search the grid for.
                    # The workbook name is the only link back to this upload.
                    resolved_id = self.find_item_set_id_by_uploaded_file(
                        uploaded_file_name
                    )
                    if not resolved_id:
                        raise AssertionError(
                            "No item set on the Sets grid names the uploaded file "
                            f"{Path(str(uploaded_file_name)).name!r} yet."
                        )
                    matched_by_file = True
                self.open_item_set_from_sets_list(resolved_id)
                self.wait_utils.until_condition(
                    verdict_rendered(resolved_id),
                    timeout=min(30, max(5, int(deadline - monotonic()))),
                )
            except Exception as error:
                # Kept rather than discarded: "the set is not listed yet" and
                # "the lookup itself is broken" both land here, and only the
                # error text tells them apart once the window runs out.
                self.last_qar_recovery_error = error
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                sleep(min(15, remaining))
                continue
            if item_ids and not matched_by_file:
                # Confirms the rows on screen are this upload's items and not a
                # same-prefixed set's, before a caller reads evidence off them.
                # Skipped when the set was matched by workbook name: that name
                # is unique to this upload, and the caller's item IDs are the
                # unnumbered review-step ones, which cannot match the numbered
                # IDs this page renders.
                self.verify_items_in_opened_item_set(item_ids)
            self.recovered_item_set_id = resolved_id
            QARReportPage(self.driver).open_report_if_available()
            return True

    def has_visible_submit_for_qar_button(self, driver):
        for button in driver.find_elements(*self.SUBMIT_FOR_QAR_BUTTON):
            try:
                label = button.text.strip().casefold()
                if button.is_displayed() and button.is_enabled() and "submit set for qar" in label:
                    return True
            except Exception:
                continue
        return False

    def has_qar_results_or_progress(self, driver):
        if self.is_qar_submission_redirect(driver):
            return True
        if driver.find_elements(*self.QAR_RESULTS_HEADING):
            for element in driver.find_elements(*self.QAR_RESULTS_HEADING):
                try:
                    if element.is_displayed():
                        return True
                except Exception:
                    continue
        page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
        return any(
            marker in page_text
            for marker in (
                "qar completed",
                "qar ran",
                "qar analysis in progress",
                "analysis in progress",
                "total items",
                "average score",
                "exception report",
            )
        )

    @staticmethod
    def is_qar_submission_redirect(driver):
        page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
        return (
            "my item set" in page_text
            and "item set status" in page_text
            and "item set review stage" in page_text
            and any(
                status in page_text
                for status in ("under review", "qar failed", "published", "disabled")
            )
        )

    def is_qar_analysis_complete(self, driver):
        if self.is_qar_submission_redirect(driver):
            return True
        page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
        if "analysis in progress" in page_text or "qar analysis in progress" in page_text:
            return False
        return any(
            marker in page_text
            for marker in (
                "qar completed",
                "qar ran",
                "total items",
                "average score",
                "exception report",
            )
        )

    SWITCH_FILE_CONFIRM_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or @role='alertdialog' or contains(@class,'modal') "
            "or contains(@class,'Dialog')]"
            "[.//*[contains(normalize-space(),'Switch uploaded file')]]"
            "//button[normalize-space()='Continue' and not(@disabled)]",
        ),
    ]

    def confirm_switch_uploaded_file_if_prompted(self):
        """Confirm the app's "Switch uploaded file?" guard, if it is showing.

        An account left holding an unfinished upload ("Currently working on
        this file") makes the app guard any replacement behind this dialog.
        Cancel - and the ESCAPE that close_popup_if_open() sends - keeps the
        stale file, so the upload step never renders and
        discard_active_upload_if_present(), which exists to clear exactly
        that leftover, is never reached. Continue discards the stale draft,
        which is what a test starting a fresh upload wants.
        """
        for locator in self.SWITCH_FILE_CONFIRM_LOCATORS:
            for button in self.driver.find_elements(*locator):
                if button.is_displayed() and button.is_enabled():
                    self.driver.execute_script("arguments[0].click();", button)
                    return True
        # The dialog's container is not guaranteed a dialog role or a
        # modal/Dialog class, so fall back to the text: the enabled
        # "Continue" button whose nearest ancestor mentions the prompt.
        return bool(
            self.driver.execute_script(
                """
                const shown = el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };
                for (const button of document.querySelectorAll('button')) {
                    if ((button.innerText || '').trim() !== 'Continue'
                        || button.disabled || !shown(button)) continue;
                    let box = button.parentElement;
                    for (let hops = 0; box && hops < 6; hops++, box = box.parentElement) {
                        if ((box.innerText || '').includes('Switch uploaded file')) {
                            button.click();
                            return true;
                        }
                    }
                }
                return false;
                """
            )
        )

    def open_upload_step(self):
        self.click_continue()
        try:
            self.wait_utils.until_visible(self.UPLOAD_DOCUMENTS_HEADING, timeout=20)
            return
        except TimeoutException:
            # A leftover unfinished upload holds this step back in one of two
            # ways: the app guards the replacement behind a "Switch uploaded
            # file?" dialog, or it simply parks the wizard on the stale file's
            # later step with no dialog at all. Clear whichever it is.
            #
            # discard_active_upload_if_present() is the existing cleanup for
            # exactly this state - it just normally runs *after* this method,
            # so it was unreachable precisely when the leftover blocked the
            # step it is meant to unblock.
            recovered = self.confirm_switch_uploaded_file_if_prompted()
            try:
                recovered = self.discard_active_upload_if_present() or recovered
            except AssertionError:
                # The leftover could not be cleared. Report the original
                # "upload step never opened" timeout, which describes the
                # actual blockage, rather than the cleanup's own complaint.
                pass
            if not recovered:
                raise
        self.click_continue()
        self.wait_utils.until_visible(self.UPLOAD_DOCUMENTS_HEADING, timeout=20)

    def upload_item_file_and_validate(self, file_path):
        self.open_item_creation_module()
        self.open_upload_item_file_tab()
        self.open_upload_step()
        self.discard_active_upload_if_present()
        self.discard_staged_upload_files()
        upload_path = self.upload_file(file_path)
        self.activate_uploaded_file(upload_path.name)
        success_message = self.wait_for_upload_validation_success()
        self.wait.until(EC.visibility_of_element_located(self.UPLOADED_FILE_NAME))
        return upload_path, success_message

    def get_review_item_ids(self):
        """Wait for the review step to load, then collect item IDs from the table.

        Accepts any of the following as confirmation that the review step is ready:
        - Visible text matching FILE_VALIDATION_PASSED ("File Validation Passed")
        - The Submit for QAR button becoming clickable
        - A table row appearing in the DOM
        Falls back gracefully if the exact text is not present.
        """
        # Try the dedicated "File Validation Passed" indicator first
        validated = False
        try:
            self.wait_utils.until_visible(self.FILE_VALIDATION_PASSED, timeout=15)
            validated = True
        except Exception:
            pass

        if not validated:
            # Fallback 1: Submit for QAR button present means we reached the review step
            try:
                self.wait_utils.until_present(self.SUBMIT_FOR_QAR_BUTTON, timeout=15)
                validated = True
            except Exception:
                pass

        if not validated:
            # Fallback 2: Any table row present
            try:
                self.wait_utils.until_condition(
                    lambda driver: bool(driver.find_elements(By.XPATH, "//table//tbody/tr[.//td]"))
                    or bool(driver.find_elements(*self.FILE_VALIDATION_PASSED)),
                    timeout=30,
                )
            except Exception:
                pass  # Collect whatever is on the page

        item_ids = []
        for cell in self.driver.find_elements(*self.REVIEW_ITEM_ID_CELLS):
            text = cell.text.strip()
            if text and text.lower() != "item id" and text not in item_ids:
                item_ids.append(text)
        return item_ids

    # --- Step 3: Review & Tag Metadata -----------------------------------
    #
    # Every metadata value on this step is an inline Radix combobox living in
    # its own table cell - eight per row (Grade, Subject, Chapter, Typology,
    # Marks, Bloom's Level, Competency, Learning Outcome). Cells are addressed
    # by column heading rather than by index so that a reordered or newly
    # inserted column moves the lookup with it instead of silently reading the
    # neighbouring cell.
    #
    # Values are read through one JS snapshot rather than by holding element
    # references: the table re-renders as each wizard step loads, and a
    # reference taken a moment earlier goes stale mid-read. The snapshot also
    # scopes itself to the table carrying an "Item ID" heading, because the
    # upload history table on step 2 matches a bare //table just as well, and
    # it reads form-field values as well as text because Confirm & Submit
    # renders the very same metadata as inputs instead of as plain cells.

    ROW_COMBOBOX = (By.XPATH, ".//*[@role='combobox']")
    DROPDOWN_OPTION = (By.XPATH, "//*[@role='option']")
    REVIEW_TABLE_ROWS_XPATH = (
        "//table[.//th[normalize-space()='Item ID']]//tbody/tr[.//td]"
    )
    EDITABLE_METADATA_COLUMNS = (
        "Grade",
        "Subject",
        "Chapter",
        "Typology",
        "Marks",
        "Bloom's Level",
        "Competency",
        "Learning Outcome",
    )
    # The same metadata is headed differently at different stages - the review
    # step's "Learning Outcome" is "Learning Outcomes" on the created item set
    # - so callers name a column once and let this resolve it per stage.
    METADATA_COLUMN_ALIASES = {
        "Learning Outcome": ("Learning Outcome", "Learning Outcomes"),
        "Bloom's Level": ("Bloom's Level", "Blooms Level"),
        "Typology": ("Typology", "Item Type"),
    }
    REVIEW_TABLE_SNAPSHOT_SCRIPT = """
        const table = Array.from(document.querySelectorAll('table')).find(
            candidate => Array.from(candidate.querySelectorAll('th')).some(
                header => (header.innerText || '').trim() === 'Item ID'
            )
        );
        if (!table) { return null; }
        return {
            headers: Array.from(table.querySelectorAll('th'))
                .map(header => (header.innerText || '').trim()),
            rows: Array.from(table.querySelectorAll('tbody tr'))
                .filter(row => row.querySelector('td'))
                .map(row => Array.from(row.querySelectorAll('td')).map(cell => {
                    const text = (cell.innerText || '').trim();
                    if (text) { return text; }
                    // Confirm & Submit renders the same metadata as form
                    // fields rather than text, so their value never shows up
                    // in innerText.
                    const field = cell.querySelector('input, textarea, select');
                    return field ? (field.value || '').trim() : '';
                })),
        };
    """

    @staticmethod
    def metadata_cell_matches(cell_text, value):
        """True when a cell and a metadata label stand for the same value.

        Both sides ellipsize, independently and at different lengths: the
        review table truncates long values ("Identifies and extends simple
        ..."), the dropdown labels they are picked from truncate too, and
        Confirm & Submit renders the whole string in a form field. So neither
        side can be assumed to be the complete text - match on whichever
        visible prefix is shorter instead of on equality.
        """

        def visible(text):
            # The item detail screen Title-Cases what the review table shows
            # in sentence case, so the comparison has to ignore case too.
            return (
                (text or "").strip().rstrip("…").rstrip(". ").strip().casefold()
            )

        shown, wanted = visible(cell_text), visible(value)
        if not shown or not wanted:
            return False
        return shown.startswith(wanted) or wanted.startswith(shown)

    def get_review_snapshot(self):
        """Headers and cell text for the metadata table, or None if absent."""
        return self.driver.execute_script(self.REVIEW_TABLE_SNAPSHOT_SCRIPT)

    def get_review_headers(self):
        snapshot = self.get_review_snapshot()
        return snapshot["headers"] if snapshot else []

    def get_review_rows(self):
        """Live row elements, for interacting with a cell's combobox."""
        return [
            row
            for row in self.driver.find_elements(
                By.XPATH, self.REVIEW_TABLE_ROWS_XPATH
            )
            if row.is_displayed()
        ]

    def wait_for_review_step(self, timeout=90):
        """Block until the metadata table has rendered and settled.

        Rows keep streaming in for a moment after the loading banner clears,
        so a single read can catch a partial table - and a combobox clicked in
        a row that re-renders underneath the click silently does nothing at
        all. Only trust the table once two consecutive reads agree, the same
        guard submit_for_qar() applies to the item IDs it reads here.
        """
        previous = {"snapshot": None}

        def settled(driver):
            snapshot = self.get_review_snapshot()
            if not snapshot or not snapshot["rows"]:
                previous["snapshot"] = None
                return None
            if previous["snapshot"] == snapshot:
                return snapshot
            previous["snapshot"] = snapshot
            return None

        return self.wait_utils.until_condition(settled, timeout=timeout)

    def review_row_index_where(self, column, value):
        """Which review row carries `value` in `column`.

        Rows are not guaranteed to keep their order between the review step
        and the created item set, so every stage locates its row by content
        rather than reusing an index captured earlier.
        """
        snapshot = self.wait_for_review_step()
        headers = snapshot["headers"]
        heading = self.resolve_column(headers, column)
        assert heading, (
            f"No {column!r} column on screen; columns were {headers}."
        )
        target = headers.index(heading)
        for index, row in enumerate(snapshot["rows"]):
            if target < len(row) and self.metadata_cell_matches(row[target], value):
                return index
        raise AssertionError(
            f"No row has {value!r} under {column!r} among the "
            f"{len(snapshot['rows'])} row(s) on screen."
        )

    def review_row_index_for_item(self, item_id):
        """Which review row belongs to `item_id`.

        Only valid before the set is submitted: submission renumbers every
        item from the staged "IS-<chapter>-iN" into the created set's
        "IS<number>-<chapter>-iN", so an ID captured earlier will not be
        found afterwards. Track an item across that boundary by its question
        text instead.
        """
        return self.review_row_index_where("Item ID", item_id)

    def get_review_metadata(self, row_index=0):
        """Every value shown for one review row, keyed by column heading."""
        snapshot = self.wait_for_review_step()
        assert row_index < len(snapshot["rows"]), (
            f"Review step shows {len(snapshot['rows'])} row(s); row "
            f"{row_index} was requested."
        )
        return dict(zip(snapshot["headers"], snapshot["rows"][row_index]))

    @classmethod
    def resolve_column(cls, headers, column):
        """The heading this stage uses for `column`, or None if it has none."""
        for candidate in cls.METADATA_COLUMN_ALIASES.get(column, (column,)):
            if candidate in headers:
                return candidate
        return None

    def get_review_metadata_values(self, row_index, columns):
        """Values for `columns` on one row, resolving each stage's headings.

        A column the current stage does not render comes back as None, which
        callers can report as "not shown here" rather than as a wrong value.
        """
        row = self.get_review_metadata(row_index)
        return {
            column: row.get(self.resolve_column(list(row), column))
            for column in columns
        }

    ITEM_DETAIL_METADATA_SCRIPT = """
        const wanted = arguments[0];
        const found = {};
        const nodes = Array.from(
            document.querySelectorAll('div, section, li, td, p, dd, dl')
        );
        for (const label of wanted) {
            for (const node of nodes) {
                const text = (node.innerText || '').trim();
                if (!text.startsWith(label)) { continue; }
                const rest = text.slice(label.length).trim()
                    .split(String.fromCharCode(10))[0].trim();
                if (!rest) { continue; }
                // The most specific container wins: outer ones carry the
                // label plus every sibling field's text as well.
                if (!(label in found) || text.length < found[label].scope) {
                    found[label] = {value: rest, scope: text.length};
                }
            }
        }
        return Object.fromEntries(
            Object.entries(found).map(([label, hit]) => [label, hit.value])
        );
    """

    def get_item_detail_metadata(self, labels):
        """Metadata read off an opened item, keyed by the label beside it.

        The item detail screen does not use a table - each value sits under
        its own label - so the review-step readers do not apply here.
        """
        return self.driver.execute_script(
            self.ITEM_DETAIL_METADATA_SCRIPT, list(labels)
        )

    def get_review_metadata_value(self, column, row_index=0):
        return self.get_review_metadata(row_index).get(column, "")

    def review_metadata_cell(self, column, row_index=0):
        """The live cell element, re-found on each call so it is never stale."""
        headers = self.get_review_headers()
        heading = self.resolve_column(headers, column)
        assert heading, (
            f"{column!r} is not a column on the review step. Columns: {headers}"
        )
        rows = self.get_review_rows()
        assert row_index < len(rows), (
            f"Review step shows {len(rows)} row(s); row {row_index} was requested."
        )
        return rows[row_index].find_elements(By.XPATH, "./td")[headers.index(heading)]

    def open_metadata_dropdown(self, column, row_index=0, attempts=3):
        """Open one cell's dropdown and return its visible options.

        Retried because a JS click on a row that re-rendered a moment earlier
        raises nothing and simply never opens the list, which would otherwise
        surface as an unexplained timeout.
        """
        last_error = None
        for _ in range(attempts):
            self.wait_for_review_step()
            try:
                combobox = self.review_metadata_cell(
                    column, row_index
                ).find_element(*self.ROW_COMBOBOX)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", combobox
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", combobox)
                return self.wait_utils.until_condition(
                    lambda driver: [
                        option
                        for option in driver.find_elements(*self.DROPDOWN_OPTION)
                        if option.is_displayed() and option.text.strip()
                    ]
                    or None,
                    timeout=10,
                )
            except (TimeoutException, StaleElementReferenceException) as error:
                last_error = error
                self.close_metadata_dropdown()
        raise AssertionError(
            f"The {column!r} dropdown on review row {row_index} did not open "
            f"after {attempts} attempts."
        ) from last_error

    def close_metadata_dropdown(self):
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def get_review_metadata_options(self, column, row_index=0):
        options = [
            option.text.strip()
            for option in self.open_metadata_dropdown(column, row_index)
        ]
        self.close_metadata_dropdown()
        return options

    def set_review_metadata(self, column, value, row_index=0):
        """Pick `value` in this row's `column`, then wait for the cell to show it."""
        for option in self.open_metadata_dropdown(column, row_index):
            if option.text.strip() != value:
                continue
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'nearest'});", option
            )
            self.pause_before_action()
            self.driver.execute_script("arguments[0].click();", option)
            self.wait_utils.until_condition(
                lambda driver: self.metadata_cell_matches(
                    self.get_review_metadata_value(column, row_index), value
                ),
                timeout=20,
            )
            return value
        self.close_metadata_dropdown()
        raise AssertionError(
            f"{value!r} is not offered by the {column!r} dropdown on review row "
            f"{row_index}."
        )

    def change_review_metadata(self, column, row_index=0):
        """Switch this row's `column` to any value other than the current one.

        Returns (before, after). Choosing whatever the dropdown offers keeps
        the test free of environment-specific metadata values, which differ
        per grade-subject and would otherwise pin it to one data set.
        """
        before = self.get_review_metadata_value(column, row_index)
        options = self.get_review_metadata_options(column, row_index)
        alternatives = [
            option
            for option in options
            if option and not self.metadata_cell_matches(before, option)
        ]
        assert alternatives, (
            f"{column!r} offers no alternative to {before!r} on review row "
            f"{row_index}; the dropdown listed {options}."
        )
        return before, self.set_review_metadata(column, alternatives[0], row_index)

    def get_qar_result_item_ids(self):
        item_ids = []
        for cell in self.driver.find_elements(*self.QAR_RESULT_ITEM_ID_CELLS):
            text = cell.text.strip()
            if re.search(r"-i\d+$", text, re.IGNORECASE) and text not in item_ids:
                item_ids.append(text)
        return item_ids

    @staticmethod
    def get_item_set_id_from_item_ids(item_ids):
        if not item_ids:
            return ""
        match = re.match(r"(.+)-i\d+$", item_ids[0])
        return match.group(1) if match else ""

    def wait_for_ocr_success_message(self):
        if self.is_qar_submission_redirect(self.driver):
            return "QAR submission accepted; item set is under review."
        try:
            element = self.wait_utils.until_visible(self.OCR_SUCCESS_MESSAGE, timeout=120)
            return self.extract_ocr_success_message(element.text)
        except TimeoutException:
            self.wait_utils.until_visible(self.QAR_RESULTS_HEADING, timeout=20)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            return self.extract_ocr_success_message(page_text)

    @staticmethod
    def extract_ocr_success_message(message_text):
        message_lines = [line.strip() for line in message_text.splitlines() if line.strip()]
        for line in message_lines:
            if "QAR completed" in line or "QAR ran" in line or "OCR" in line:
                return line
        for line in message_lines:
            if "returned" in line or "Needs Revision" in line:
                return line
        for line in message_lines:
            if "successfully" in line or "submitted" in line:
                return line
        return message_text.strip()

    def submit_uploaded_item_set_for_qar(self):
        """Navigate through the upload wizard steps and trigger QAR submission.

        The app wizard flow can vary:
          - upload → [Continue] → review → [Continue] → submit
          - upload → [Continue] → review/submit combined (no second Continue)
        This method handles both cases adaptively.
        """
        # Step 1: Navigate from upload validation to the next wizard step
        self.click_continue()
        self.pause_before_action()

        # Step 2: Collect item IDs from the review table (best-effort)
        item_ids = self.get_review_item_ids()

        # Step 3: Check if Submit button already on page (some app versions combine steps)
        submit_already_present = bool(
            self.driver.find_elements(*self.SUBMIT_FOR_QAR_BUTTON)
        )

        if not submit_already_present:
            # Step 3b: Click Continue to move from review → submit step
            try:
                self.click_continue()
                self.pause_before_action()
            except TimeoutException:
                # No second Continue button — we may already be on the submit page
                pass

        # Step 4: Wait for the Submit for QAR button to appear
        # Only match QAR-specific buttons — broad 'Submit' matches step 3 metadata buttons
        submit_found = False
        for locator in [
            self.SUBMIT_FOR_QAR_BUTTON,
            (By.XPATH, "//button[contains(normalize-space(),'QAR')]"),
        ]:
            try:
                self.wait_utils.until_present(locator, timeout=20)
                submit_found = True
                break
            except TimeoutException:
                continue

        if not submit_found:
            # Capture current URL + page text to diagnose where we are
            url = self.driver.current_url
            body = self.driver.find_element(By.TAG_NAME, "body").text[:500]
            raise TimeoutException(
                f"Submit for QAR button not found. URL={url}\nPage preview:\n{body}"
            )

        self.click_submit_for_qar_and_wait_for_results()
        success_message = self.wait_for_ocr_success_message()
        final_item_ids = self.get_qar_result_item_ids()
        return final_item_ids or item_ids, success_message


    def upload_item_file_and_submit_for_qar(self, file_path):
        upload_path, upload_success_message = self.upload_item_file_and_validate(file_path)
        item_ids, ocr_success_message = self.submit_uploaded_item_set_for_qar()
        return upload_path, upload_success_message, item_ids, ocr_success_message

    # --- Evidence capture actions ---
    def capture_ocr_success_screenshot(self, test_name):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_ocr_success")

    def capture_sets_verification_screenshot(self, test_name):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_sets_verification")

    def capture_reviewer_approval_screenshot(self, test_name):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_reviewer_approval")

    # --- Sets verification locators ---
    # Older builds exposed a dedicated "Sets" menu item. Newer ones drop it and
    # render the "My Item Sets" table on the dashboard reached via "Home", so try
    # the explicit entries before falling back to a positional guess.
    SETS_MENU_LOCATORS = [
        (By.XPATH, "//*[normalize-space()='Sets']/ancestor::*[self::button or self::a][1]"),
        (By.XPATH, "//button[contains(normalize-space(),'Sets')]"),
        (By.XPATH, "//*[normalize-space()='Home']/ancestor::*[self::button or self::a][1]"),
        (By.XPATH, "(//div[@id='root']//ul/li[2]/button)[1]"),
    ]

    # --- Sets verification actions ---
    MY_ITEM_SETS_HEADING = (By.XPATH, "//*[contains(normalize-space(),'My Item Set')]")

    def open_sets_module(self):
        self.click_any_element(self.SETS_MENU_LOCATORS)
        try:
            self.wait_utils.until_visible(self.MY_ITEM_SETS_HEADING, timeout=30)
        except TimeoutException:
            # Builds without a "Sets" menu render the table on the dashboard, and
            # the sidebar click can be swallowed by an overlay on result screens.
            # Navigating straight there is deterministic either way.
            self.driver.get(ReadConfig.get_base_url().rstrip("/") + "/dashboard")
            self.wait_utils.until_visible(self.MY_ITEM_SETS_HEADING, timeout=30)

    ITEM_SET_LIST_ROWS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item Set ID')]]//tbody/tr[.//td]",
    )

    @staticmethod
    def xpath_literal(value):
        value = str(value)
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"

    # Field name -> the header spellings that mean it on the item-set grid.
    ITEM_SET_COLUMN_ALIASES = {
        "item_set_id": ("item set id",),
        "grade": ("grade",),
        "book": ("book",),
        "unit": ("unit",),
        "subject_chapter": ("subject & chapter", "subject and chapter", "subject"),
        "item_count": ("item count",),
        "item_status": ("item status",),
        "item_set_status": ("item set status",),
        "review_stage": ("item set review stage", "review stage"),
        "last_updated": ("last updated",),
        "uploaded_file": ("uploaded file",),
    }

    def item_set_column_indexes(self):
        """Field name -> column index, read from the grid's own header row.

        Read rather than assumed because Book and Unit were inserted at
        positions 2 and 3, moving Subject & Chapter from index 2 to 4. The old
        readers took "the cell after Grade" as the subject and so reported every
        row's subject as "Book 1" - which made the RBAC scope check fail for
        every set on screen, including ones it had always passed on.

        Returns {} when the header row cannot be read, which callers treat as
        "fall back" rather than as an empty grid.
        """
        headers = [
            header.text.strip()
            for header in self.driver.find_elements(*self.ITEM_SET_TABLE_HEADERS)
        ]
        resolved = {}
        for position, header in enumerate(headers):
            normalized = header.casefold()
            for field, aliases in self.ITEM_SET_COLUMN_ALIASES.items():
                if field not in resolved and normalized in aliases:
                    resolved[field] = position
        return resolved

    @staticmethod
    def item_set_numeric_prefix(item_set_id):
        """The stable 'IS<number>' portion of an item-set ID.

        The chapter segment is not stable between screens: the same set is
        "IS1158-G1-Mathematics-Ch29" on the QAR results and
        "IS1158-G1-Mathematics-CH-1" on this listing, so an exact match never
        fires. Same convention as ReviewQueuePage.item_set_numeric_prefix.
        """
        match = re.match(r"(IS\d+)", str(item_set_id), re.IGNORECASE)
        return match.group(1).upper() if match else str(item_set_id).strip().upper()

    def find_item_set_row(self, item_set_id, timeout=45):
        """The listing row for one item set, or None.

        Matched on the "IS<number>" prefix rather than the whole ID, for the
        reason item_set_numeric_prefix explains.

        The grid is ordered newest-first, so a set created moments ago is on the
        first page; no paging is done here, and a caller that gets None should
        say the row was not found rather than assume the set does not exist.
        """
        wanted = self.item_set_numeric_prefix(item_set_id)

        def matching(_driver):
            for row in self.get_item_set_list_rows():
                if self.item_set_numeric_prefix(row["item_set_id"]) == wanted:
                    return row
            return None

        try:
            return self.wait_utils.until_condition(matching, timeout=timeout)
        except TimeoutException:
            return None

    def get_item_set_list_rows(self):
        rows = self.wait_utils.until_condition(
            lambda driver: driver.find_elements(*self.ITEM_SET_LIST_ROWS) or False,
            timeout=30,
        )
        columns = self.item_set_column_indexes()
        results = []
        for row in rows:
            try:
                if not row.is_displayed():
                    continue
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < 7:
                    continue
                cell_lines = [
                    [line.strip() for line in cell.text.splitlines() if line.strip()]
                    for cell in cells
                ]

                def lines_for(field, default=()):
                    position = columns.get(field)
                    if position is None or position >= len(cell_lines):
                        return list(default)
                    return cell_lines[position]

                subject_chapter = lines_for("subject_chapter")
                item_set_id = lines_for("item_set_id")
                grade = lines_for("grade")
                book = lines_for("book")
                unit = lines_for("unit")
                results.append(
                    {
                        "item_set_id": item_set_id[0] if item_set_id else "",
                        "grade": grade[0] if grade else "",
                        "book": book[0] if book else "",
                        # The grid prints an em dash for a set with no unit;
                        # normalised to "" so callers test emptiness, not glyphs.
                        "unit": unit[0] if unit and unit[0] not in ("-", "—", "–") else "",
                        "subject": subject_chapter[0] if subject_chapter else "",
                        "chapter": subject_chapter[1] if len(subject_chapter) > 1 else "",
                        "item_status": " ".join(lines_for("item_status")),
                        "item_set_status": " ".join(lines_for("item_set_status")),
                        "review_stage": " ".join(lines_for("review_stage")),
                        "uploaded_file": " ".join(lines_for("uploaded_file")),
                    }
                )
            except Exception:
                continue
        return results

    # --- Uploaded File column on the full My Item Set list ---
    # open_sets_module() reaches the dashboard, whose "My Item Sets" widget only
    # previews a few sets and paints "Loading item sets..." first. The full list
    # -- and the only place the Uploaded File column renders -- is /item-sets,
    # behind the widget's "View All".
    ITEM_SETS_LIST_PATH = "/item-sets"
    ITEM_SET_TABLE_HEADERS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item Set ID')]]//th",
    )

    # --- My Item Set listing survey locators ----------------------------
    #
    # Taken from a DOM census of /item-sets under an SME account. The SME
    # sidebar differs from the teacher's (no QP Builder / My QP / Sets), and
    # this listing carries a Sr. RWG tab the teacher dashboard's grid does not.

    ITEM_SETS_HEADING = (By.XPATH, "//h1[normalize-space()='My Item Set']")
    ITEM_SETS_SUBTITLE = (
        By.XPATH,
        "//*[not(*)][contains(normalize-space(),'Track all your item sets')]",
    )
    ITEM_SET_FILTER_LABELS = ("Grade", "Subject", "Chapter", "Status")
    ITEM_SET_FILTER_BUTTONS = (By.CSS_SELECTOR, "button[class*='_filterBtn_']")
    ITEM_SET_TAB_LABELS = (
        "All",
        "QAR",
        "RWG",
        "Sr. RWG",
        "PIT",
        "Published",
        "Disabled",
        "Draft-Items",
    )
    ITEM_SET_TAB_LIST = (By.CSS_SELECTOR, "[role='tablist']")
    ITEM_SET_COLUMNS = (
        "Item Set ID",
        "Grade",
        # Book and Unit were inserted here, between Grade and Subject & Chapter,
        # which pushed every later column one to the right. Nothing reads this
        # grid by position any more - see item_set_column_indexes().
        "Book",
        "Unit",
        "Subject & Chapter",
        "Item Count",
        "Item Status",
        "Item Set Status",
        "Item Set Review Stage",
        "Last Updated",
        "Last Review Submit Date",
        "Uploaded File",
    )
    ITEM_SET_ROWS_PER_PAGE = (By.CSS_SELECTOR, "[role='combobox']")
    ITEM_SET_PREV_PAGE = (By.CSS_SELECTOR, "button[aria-label='Previous page']")
    ITEM_SET_NEXT_PAGE = (By.CSS_SELECTOR, "button[aria-label='Next page']")
    ITEM_SET_MORE_INFO = (By.CSS_SELECTOR, "button[aria-label='More information']")

    # SME sidebar destinations — deliberately not the teacher's list.
    SME_NAV_ITEMS = ("Home", "Repository", "Create", "Item", "Support", "Settings")

    @classmethod
    def item_set_tab_locator(cls, label):
        return (
            By.XPATH,
            f"//*[@role='tab'][starts-with(normalize-space(),{cls.xpath_literal(label)})]",
        )

    @classmethod
    def item_set_filter_locator(cls, label):
        return (
            By.XPATH,
            "//button[contains(@class,'_filterBtn_')]"
            f"[normalize-space()={cls.xpath_literal(label)}]",
        )

    @classmethod
    def sme_nav_locator(cls, label):
        """Locate a sidebar destination by its visible label.

        Matched on the label <span>, not on the button. Each nav button also
        carries a visually-hidden tooltip span, so the button's *textContent* —
        which is what XPath normalize-space() reads — is the tooltip and the
        label run together ("DashboardHome", "Item SetsItem"). An exact match on
        the button therefore never fires, and a contains() match is ambiguous:
        'Item' appears in Repository, Create and Item alike.
        """
        return (
            By.XPATH,
            "//button[contains(@class,'menu-button')]"
            f"[.//span[normalize-space()={cls.xpath_literal(label)}]]",
        )

    def missing_from(self, labels, locator_builder):
        """Which of `labels` has no visible match. Never raises."""
        missing = []
        for label in labels:
            try:
                present = self.count_visible(locator_builder(label))
            except Exception:  # noqa: BLE001 - an unreadable label is an absent one
                present = 0
            if not present:
                missing.append(label)
        return missing

    def get_item_set_table_headers(self):
        headers = []
        for element in self.driver.find_elements(*self.ITEM_SET_TABLE_HEADERS):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if text:
                headers.append(text)
        return headers

    def missing_item_set_columns(self):
        headers = [header.casefold() for header in self.get_item_set_table_headers()]
        return [
            column
            for column in self.ITEM_SET_COLUMNS
            if column.casefold() not in headers
        ]

    def get_item_set_row_count(self):
        return len(self.driver.find_elements(*self.ITEM_SET_LIST_ROWS))

    def is_item_set_tab_active(self, label):
        try:
            state = self.driver.find_element(
                *self.item_set_tab_locator(label)
            ).get_attribute("data-state")
        except WebDriverException:
            return False
        return state == "active"

    def switch_item_set_tab(self, label, timeout=20):
        """Activate an item-set tab and wait for it to report itself active."""
        self.click_element(self.item_set_tab_locator(label))
        try:
            self.wait_utils.until_condition(
                lambda driver: self.is_item_set_tab_active(label), timeout=timeout
            )
        except TimeoutException:
            return False
        return True
    # Sets authored manually have no source workbook and render an em dash.
    UPLOADED_FILE_EMPTY_MARKERS = {"", "—", "–", "-"}

    # The dashboard widget's link through to the full list.
    MY_ITEM_SETS_VIEW_ALL = (
        By.XPATH,
        "//*[normalize-space()='View All'][not(.//*[normalize-space()='View All'])]",
    )

    def open_item_sets_list(self, timeout=45):
        """Open the full My Item Set list and wait for its rows to render.

        Prefers the dashboard's "View All" link to navigating straight at
        /item-sets: a hard driver.get() reloads the SPA and lands on its global
        Loading screen, which this environment can sit on for longer than the
        wait. The direct URL stays as the fallback for builds without the link.
        """
        self.open_sets_module()
        try:
            link = self.wait_utils.until_clickable(self.MY_ITEM_SETS_VIEW_ALL, timeout=15)
            self.driver.execute_script("arguments[0].click();", link)
        except TimeoutException:
            self.driver.get(ReadConfig.get_base_url().rstrip("/") + self.ITEM_SETS_LIST_PATH)
        self.wait_utils.until_visible(self.MY_ITEM_SETS_HEADING, timeout=timeout)
        # Rows only exist once the "Loading item sets..." placeholder clears.
        self.wait_utils.until_condition(
            lambda driver: driver.find_elements(*self.ITEM_SET_LIST_ROWS) or False,
            timeout=timeout,
        )
        return True

    def get_uploaded_file_column_index(self, timeout=30):
        """1-based index of the 'Uploaded File' column, or 0 when it is absent.

        Resolved from the header rather than hard-coded: this list has gained
        columns across builds (Item Count, Last Review Submit Date), and a fixed
        td index silently reads a neighbouring cell when that happens.
        """
        headers = self.wait_utils.until_condition(
            lambda driver: driver.find_elements(*self.ITEM_SET_TABLE_HEADERS) or False,
            timeout=timeout,
        )
        for index, header in enumerate(headers, start=1):
            if "uploaded file" in header.text.casefold():
                return index
        return 0

    @classmethod
    def uploaded_file_name(cls, cell):
        """The full workbook name in an Uploaded File cell, or '' if it has none.

        Reads the title attribute rather than the cell text: long names are
        truncated for display ("smoke_item_set_b935079…"), so the visible text
        is not the file name. Cells for manually authored sets carry no title
        and hold an em dash, which yields ''.
        """
        for element in cell.find_elements(By.XPATH, ".//*[@title]"):
            title = (element.get_attribute("title") or "").strip()
            if title:
                return title
        text = cell.text.strip()
        return "" if text in cls.UPLOADED_FILE_EMPTY_MARKERS else text

    def get_item_set_uploaded_files(self):
        """Map item set ID -> source workbook name for rows that name one.

        Rows for manually authored sets are omitted, so an empty result means
        this page lists no uploaded sets rather than that the column failed.
        """
        column = self.get_uploaded_file_column_index()
        if not column:
            return {}
        uploads = {}
        for row in self.driver.find_elements(*self.ITEM_SET_LIST_ROWS):
            try:
                if not row.is_displayed():
                    continue
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < column:
                    continue
                set_id_lines = [
                    line.strip() for line in cells[0].text.splitlines() if line.strip()
                ]
                name = self.uploaded_file_name(cells[column - 1])
                if set_id_lines and name:
                    uploads[set_id_lines[0]] = name
            except Exception:
                continue
        return uploads

    def get_item_set_filter_trigger(self, filter_name, timeout=20):
        label = self.xpath_literal(filter_name)
        locator = (
            By.XPATH,
            "//*[self::button or @role='button']"
            f"[normalize-space()={label} or .//*[normalize-space()={label}]]",
        )
        for element in self.driver.find_elements(*locator):
            try:
                if element.is_displayed() and element.is_enabled():
                    return element
            except Exception:
                continue

        filter_order = {"Grade": 0, "Subject": 1, "Chapter": 2, "Status": 3}
        if filter_name not in filter_order:
            raise ValueError(f"Unsupported item-set filter: {filter_name!r}")
        funnel_buttons = (
            By.XPATH,
            "//button[.//*[name()='svg' and "
            "(contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'filter') "
            "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'funnel'))]]",
        )
        return self.wait_utils.until_condition(
            lambda driver: (
                buttons[filter_order[filter_name]]
                if len(
                    buttons := [
                        element
                        for element in driver.find_elements(*funnel_buttons)
                        if element.is_displayed() and element.is_enabled()
                    ]
                ) > filter_order[filter_name]
                else False
            ),
            timeout=timeout,
        )

    def open_item_set_filter(self, filter_name):
        trigger = self.get_item_set_filter_trigger(filter_name)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            trigger,
        )
        self.pause_before_action()
        try:
            trigger.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", trigger)
        return trigger

    def get_item_set_filter_option(self, option_text, timeout=15):
        expected_text = re.sub(r"\s+", " ", str(option_text)).strip().casefold()
        expected_prefix = expected_text.rstrip(".") if expected_text.endswith("...") else ""
        locator = (
            By.XPATH,
            "//*[@role='option' or @role='menuitem' or @role='menuitemcheckbox' "
            "or @role='checkbox']"
            " | //*[@role='listbox' or @role='menu']"
            "//*[self::button or @role='button']",
        )

        def matching_option(driver):
            for element in driver.find_elements(*locator):
                try:
                    if not element.is_displayed() or not element.is_enabled():
                        continue
                    actual_text = re.sub(r"\s+", " ", element.text or "").strip().casefold()
                    if actual_text == expected_text:
                        return element
                    if expected_prefix and actual_text.startswith(expected_prefix):
                        return element
                except Exception:
                    continue
            return False

        return self.wait_utils.until_condition(
            matching_option,
            timeout=timeout,
        )

    def close_item_set_filter(self):
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def apply_item_set_filter(self, filter_name, option_text):
        self.open_item_set_filter(filter_name)
        option = self.get_item_set_filter_option(option_text)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'nearest'});",
            option,
        )
        self.pause_before_action()
        try:
            option.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", option)
        self.close_item_set_filter()
        self.wait_utils.until_condition(
            lambda driver: bool(self.get_item_set_list_rows()),
            timeout=30,
        )
        return option_text

    @staticmethod
    def is_filter_option_element_selected(option):
        selected_values = {
            str(option.get_attribute("aria-selected") or "").casefold(),
            str(option.get_attribute("aria-checked") or "").casefold(),
            str(option.get_attribute("data-state") or "").casefold(),
        }
        if selected_values.intersection({"true", "checked", "selected", "on"}):
            return True
        inputs = option.find_elements(By.XPATH, ".//input[@type='checkbox' or @type='radio']")
        return any(input_element.is_selected() for input_element in inputs)

    def is_item_set_filter_option_selected(self, filter_name, option_text):
        trigger = self.get_item_set_filter_trigger(filter_name)
        trigger_text = re.sub(r"\s+", " ", trigger.text or "").strip().casefold()
        expected_text = re.sub(r"\s+", " ", option_text).strip().casefold()
        expected_prefix = expected_text.rstrip(".") if expected_text.endswith("...") else ""
        if expected_text in trigger_text or (
            expected_prefix and expected_prefix in trigger_text
        ):
            return True
        if trigger_text == filter_name.strip().casefold():
            return False

        self.open_item_set_filter(filter_name)
        try:
            option = self.get_item_set_filter_option(option_text)
            return self.is_filter_option_element_selected(option)
        finally:
            self.close_item_set_filter()

    def clear_item_set_filter(self, filter_name, option_text):
        self.open_item_set_filter(filter_name)
        clear_locators = [
            (
                By.XPATH,
                "//*[self::button or @role='button']"
                "[normalize-space()='Clear' or normalize-space()='Clear Filter' "
                "or normalize-space()='Clear filters' or normalize-space()='Reset']",
            ),
        ]
        cleared = False
        for locator in clear_locators:
            for element in self.driver.find_elements(*locator):
                try:
                    if element.is_displayed() and element.is_enabled():
                        self.driver.execute_script("arguments[0].click();", element)
                        cleared = True
                        break
                except Exception:
                    continue
            if cleared:
                break
        if not cleared:
            option = self.get_item_set_filter_option(option_text)
            if not self.is_filter_option_element_selected(option):
                self.close_item_set_filter()
                return True
            try:
                option.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", option)
        self.close_item_set_filter()
        return True

    def get_visible_item_set_scopes(self):
        """Grade and subject for each item set on screen.

        Reads the Subject & Chapter cell by *header*, not as "the line after
        Grade". Book and Unit now sit between the two, so the positional read
        returned the book ("Book 1") as every row's subject, and the RBAC scope
        check then failed on sets that were perfectly in scope.

        The positional scan is kept only for a grid whose header row cannot be
        read at all.
        """
        rows = self.wait_utils.until_condition(
            lambda driver: driver.find_elements(By.XPATH, "//table//tbody/tr[.//td]"),
            timeout=30,
        )
        columns = self.item_set_column_indexes()
        scopes = []
        for row in rows:
            row_text = row.text
            grade_match = re.search(r"\bGrade\s+\d+\b", row_text, re.IGNORECASE)
            if not grade_match:
                continue

            if columns.get("subject_chapter") is not None:
                cells = row.find_elements(By.XPATH, "./td")

                def cell_first_line(field, cells=cells):
                    position = columns.get(field)
                    if position is None or position >= len(cells):
                        return ""
                    lines = [
                        line.strip()
                        for line in cells[position].text.splitlines()
                        if line.strip()
                    ]
                    return lines[0] if lines else ""

                subject = cell_first_line("subject_chapter")
                if not subject:
                    continue
                scopes.append(
                    {
                        "item_set_id": cell_first_line("item_set_id"),
                        "grade": cell_first_line("grade"),
                        "subject": subject,
                        "book": cell_first_line("book"),
                    }
                )
                continue

            lines = [line.strip() for line in row_text.splitlines() if line.strip()]
            grade_index = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if re.fullmatch(r"Grade\s+\d+", line, re.IGNORECASE)
                ),
                None,
            )
            if grade_index is None or grade_index + 1 >= len(lines):
                continue
            scopes.append(
                {
                    "item_set_id": lines[0],
                    "grade": lines[grade_index],
                    "subject": lines[grade_index + 1],
                }
            )
        return scopes

    def verify_visible_item_sets_within_scope(self, allowed_pairs):
        """Every visible item set is inside the account's own grade-subject scope.

        `allowed_pairs` is an iterable of (grade, subject) the account is
        entitled to. It used to be a single grade and subject, taken from the
        sample row of the upload template — which held only as long as every
        set in the environment happened to be for that one subject. An SME
        scoped to three subjects who authors in two of them was then reported as
        a scope violation, so the entitlement is now passed in whole.
        """
        allowed = {
            (str(grade).strip().casefold(), str(subject).strip().casefold())
            for grade, subject in allowed_pairs
        }
        if not allowed:
            raise AssertionError("No grade-subject scope was supplied to check against.")

        scopes = self.get_visible_item_set_scopes()
        if not scopes:
            raise AssertionError("No item-set rows were visible for RBAC verification.")
        outside_scope = [
            scope
            for scope in scopes
            if (scope["grade"].strip().casefold(), scope["subject"].strip().casefold())
            not in allowed
        ]
        if outside_scope:
            raise AssertionError(
                "SME can see item sets outside the assigned grade-subject scope "
                f"{sorted(allowed)}: {outside_scope}"
            )
        return scopes

    FIND_LINK_BY_COLLAPSED_TEXT_JS = r"""
        const targetId = arguments[0].replace(/\s+/g, '');
        const links = Array.from(document.querySelectorAll('a'));
        return links.find(link => {
            const collapsed = (link.innerText || link.textContent || '').replace(/\s+/g, '');
            return collapsed === targetId || collapsed.includes(targetId);
        }) || null;
        """

    def find_item_set_link_by_id(self, item_set_id):
        """Locate the item-set link by comparing whitespace-collapsed text.

        Some environments wrap a long item-set ID across multiple lines
        inside the anchor (see get_item_set_list_rows(), which already
        splitlines() the cell text) - XPath's normalize-space() turns that
        internal line break into a single space, which breaks both the
        exact-match and contains() checks against the space-free
        item_set_id. Comparing with all whitespace stripped (via JS,
        matching how splitlines()-based scraping already treats this) finds
        the link regardless of how it wraps.
        """
        return self.driver.execute_script(
            self.FIND_LINK_BY_COLLAPSED_TEXT_JS, item_set_id
        )

    @staticmethod
    def item_set_numeric_prefix(item_set_id):
        """The 'IS<number>' portion of an item-set ID.

        Some environments render the same item set's ID with a different
        chapter-code suffix on the QAR results page (e.g. "...-Ch29") than
        on the "My Item Set" list page (e.g. "...-CH-1") for reasons that
        appear to be a backend metadata-resolution timing quirk, not a
        display bug - searching/matching on the full ID then reliably finds
        nothing. The "IS<number>" prefix is stable across both views, so
        it's used as a fallback identifier when the full-ID search comes up
        empty.
        """
        match = re.match(r"(IS\d+)", str(item_set_id), re.IGNORECASE)
        return match.group(1) if match else str(item_set_id)

    def open_item_set_from_sets_list(self, item_set_id):
        # A fresh item set isn't guaranteed to land on the default list's
        # first page (busy accounts can have 100+ sets across many pages) -
        # filter down to it via search first so the link scan below only
        # ever has to look at a single, small result set.
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        try:
            self.search_open_item_set(item_set_id)
        except Exception:
            pass
        link = self.find_item_set_link_by_id(item_set_id)
        if not link and numeric_prefix != item_set_id:
            # Full ID (with its chapter-code suffix) matched nothing - the
            # set may be rendered under a different chapter label here, so
            # retry scoped to just the stable numeric prefix.
            try:
                self.search_open_item_set(numeric_prefix)
            except Exception:
                pass
            link = self.wait_utils.until_condition(
                lambda driver: self.find_item_set_link_by_id(numeric_prefix),
                timeout=30,
            )
        elif not link:
            link = self.wait_utils.until_condition(
                lambda driver: self.find_item_set_link_by_id(item_set_id),
                timeout=30,
            )
        starting_url = self.driver.current_url
        target_url = link.get_attribute("href")
        try:
            link.click()
            self.wait_utils.until_condition(
                lambda driver: driver.current_url != starting_url,
                timeout=15,
            )
        except Exception:
            if target_url:
                self.driver.get(target_url)
            else:
                self.driver.execute_script("arguments[0].click();", link)
            self.wait_utils.until_condition(
                lambda driver: driver.current_url != starting_url,
                timeout=30,
            )
        self.wait_utils.until_condition(
            lambda driver: numeric_prefix in driver.find_element(By.TAG_NAME, "body").text,
            timeout=60,
        )
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=120,
        )

    ITEM_SET_SEARCH_INPUT = (
        By.XPATH,
        "//input[contains(@placeholder,'Search') or contains(@aria-label,'Search')]",
    )

    def search_open_item_set(self, search_text):
        search_input = self.wait_utils.until_visible(self.ITEM_SET_SEARCH_INPUT, timeout=20)
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        search_input.send_keys(search_text)
        search_input.send_keys(Keys.ENTER)
        self.wait_utils.until_condition(
            lambda driver: search_text in re.sub(
                r"\s+",
                "",
                self.get_rendered_page_text(driver),
            ),
            timeout=30,
        )

    def clear_open_item_set_search(self):
        try:
            search_input = self.wait_utils.until_visible(self.ITEM_SET_SEARCH_INPUT, timeout=5)
            search_input.send_keys(Keys.CONTROL, "a")
            search_input.send_keys(Keys.DELETE)
            search_input.send_keys(Keys.ENTER)
            self.pause_before_action()
        except Exception:
            return False
        return True

    @classmethod
    def item_id_loose_pattern(cls, item_id):
        """Regex matching an item ID's stable 'IS<number>' prefix and
        trailing 'i<number>' item-number suffix, with anything in between.

        Some environments render an item set's ID with a different
        chapter-code component on this detail page (e.g. "...-CH-1-i1")
        than the one captured right after upload (e.g. "...-Ch29-i1") -
        see item_set_numeric_prefix(). An exact compacted-ID substring
        match then never succeeds even though it's the same item, so this
        loosens the match to the two components that stay stable.
        """
        match = re.match(r"(IS\d+).*?[Ii](\d+)$", cls.compact_item_id(item_id))
        if not match:
            return None
        prefix, item_number = match.groups()
        return re.compile(
            rf"{re.escape(prefix)}.*?[Ii]{re.escape(item_number)}(?!\d)"
        )

    def verify_items_in_opened_item_set(self, item_ids):
        expected_item_ids = [self.compact_item_id(item_id) for item_id in item_ids]
        loose_patterns = {
            item_id: self.item_id_loose_pattern(item_id) for item_id in item_ids
        }

        def visible_item_ids(driver):
            if self.is_item_set_detail_loading(driver):
                return set()
            # Match against each row's own ID cell, not one compacted blob of
            # page text. Compacting the whole page glues an item ID to the
            # question text right after it ("...-i2" + "2 multiplied by...")
            # and the loose pattern's "not followed by a digit" boundary then
            # rejects the very row it is looking at.
            id_cells = self.get_rendered_item_id_cells(driver)
            normalized_page_text = self.compact_item_id(
                self.get_rendered_page_text(driver)
            )
            found = set()
            for original_id, item_id in zip(item_ids, expected_item_ids):
                if any(item_id == cell for cell in id_cells):
                    found.add(item_id)
                    continue
                pattern = loose_patterns.get(original_id)
                if pattern and any(pattern.search(cell) for cell in id_cells):
                    found.add(item_id)
                    continue
                # No ID cells at all (a non-table view): fall back to the
                # page-text match rather than reporting everything missing.
                if not id_cells and item_id in normalized_page_text:
                    found.add(item_id)
            return found

        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=120,
        )
        try:
            found_item_ids = self.wait_utils.until_condition(
                lambda driver: (
                    current_ids
                    if len(
                        current_ids := visible_item_ids(driver)
                    ) == len(expected_item_ids)
                    else False
                ),
                timeout=30,
            )
        except TimeoutException:
            found_item_ids = visible_item_ids(self.driver)

        if len(found_item_ids) != len(expected_item_ids) and item_ids:
            # Searching each missing item's full ID is unreliable here: the
            # detail page can render a different chapter-code component than
            # the ID captured after upload (see item_id_loose_pattern), so
            # that search matches nothing and just leaves the table filtered
            # empty. Search the stable "IS<number>" prefix instead, which
            # re-queries the same set and brings every row back.
            try:
                self.search_open_item_set(
                    self.item_set_numeric_prefix(item_ids[0])
                )
                found_item_ids.update(visible_item_ids(self.driver))
            except Exception:
                pass

        self.clear_open_item_set_search()
        try:
            # Re-check against the full, unfiltered table: a single read here
            # can land while the rows are still re-rendering after the search
            # was cleared and report items missing that are simply not painted
            # yet.
            found_item_ids.update(
                self.wait_utils.until_condition(
                    lambda driver: (
                        current_ids
                        if len(
                            current_ids := visible_item_ids(driver)
                        ) == len(expected_item_ids)
                        else False
                    ),
                    timeout=30,
                )
            )
        except TimeoutException:
            found_item_ids.update(visible_item_ids(self.driver))
        missing_item_ids = [
            item_id for item_id in expected_item_ids if item_id not in found_item_ids
        ]
        if missing_item_ids:
            raise AssertionError(
                f"Uploaded item IDs not found in opened item set: {missing_item_ids}"
            )
        return True

    @staticmethod
    def compact_item_id(value):
        return re.sub(r"[^A-Za-z0-9]", "", value or "")

    @classmethod
    def item_identity_key(cls, value):
        """Stable identity for a single item across screens: IS number + -i<n>.

        An item's chapter segment is not stable between views - the upload
        review step renders "...-Ch29-i1" where the QAR results page renders
        "...-CH-1-i1" for that same item. This is the per-item form of the
        backend quirk item_set_numeric_prefix() already documents at set
        level, so comparing whole compacted IDs matches nothing and every
        item reads as missing. Compare on the two parts that never move.

        Falls back to compact_item_id for anything without both parts, so
        set-level IDs (no "-i<n>" suffix) never collide with item rows.
        """
        text = str(value or "")
        set_match = re.match(r"\s*(IS\d+)", text, re.IGNORECASE)
        index_match = re.search(r"i(\d+)\s*$", text, re.IGNORECASE)
        if not (set_match and index_match):
            return cls.compact_item_id(text).casefold()
        return f"{set_match.group(1)}i{int(index_match.group(1))}".casefold()

    @staticmethod
    def get_rendered_page_text(driver):
        """Page text read through JS innerText.

        Selenium's element .text only returns text the browser considers
        rendered, which in headless Chrome can come back empty or partial
        for table rows below the viewport - table content then reads as
        "missing" when it is simply off-screen.
        """
        return driver.execute_script(
            "return document.body.innerText || document.body.textContent || '';"
        )

    @classmethod
    def get_rendered_item_id_cells(cls, driver):
        """Compacted text of every table row's first (item ID) cell."""
        cells = driver.execute_script(
            """
            return Array.from(document.querySelectorAll('table tbody tr'))
                .map(row => row.querySelector('td'))
                .filter(Boolean)
                .map(cell => (cell.innerText || cell.textContent || '').trim())
                .filter(text => text);
            """
        )
        return [cls.compact_item_id(cell) for cell in cells or []]

    @classmethod
    def is_item_set_detail_loading(cls, driver):
        page_text = cls.get_rendered_page_text(driver)
        return any(
            loading_text in page_text
            for loading_text in (
                "Loading item set",
                "Loading item set details",
            )
        )

    def open_item_set_detail(self, item_set_id):
        """Open one item set's own page, via the list rather than a captured URL.

        The status-count widget ("All / Pending / Approved / ...") only exists on
        the detail page. A URL captured earlier in a flow can still be pointing at
        the list, and the list also contains the item set ID - so a text-based
        load check cannot tell the two apart and the counts silently read as the
        list's own filter tallies instead.
        """
        self.open_sets_module()
        self.open_item_set_from_sets_list(item_set_id)
        # The click returns while the list is still painted: on UAT a read
        # straight after it got the list's own "All 166" and its Book column.
        # Wait until every table row belongs to this set.
        prefix = self.item_set_numeric_prefix(item_set_id)
        self.wait_utils.until_condition(
            lambda driver: driver.execute_script(
                """
                const rows = Array.from(document.querySelectorAll('table tbody tr'));
                return rows.length > 0 && rows.every(row =>
                    (row.cells[0]?.innerText || '').trim().toUpperCase()
                        .startsWith(arguments[0] + '-'));
                """,
                prefix,
            ),
            timeout=60,
        )

    def verify_item_set_from_sets_module(self, item_set_id, item_ids):
        self.open_sets_module()
        self.open_item_set_from_sets_list(item_set_id)
        return self.verify_items_in_opened_item_set(item_ids)

    # --- Assignee and status helpers ---
    def get_item_set_reviewer(self):
        return self.get_item_set_assignee("rwg")

    def get_item_set_sr_rwg(self):
        return self.get_item_set_assignee("sr_rwg")

    def get_scoped_item_set_assignee_text(self, role):
        """Read only the "Reviewer:"/"Assigned ..." label's own value text.

        Reading the whole page body text (as the regex fallback below does)
        can silently concatenate an unrelated adjacent number - e.g. a
        notification-badge count rendered right after "Reviewer: rwg 2" with
        no line break in the accessibility text tree - into the captured
        value (producing garbage like "rwg29"). Querying the label element
        directly and reading just its own text avoids that entirely.
        """
        label_words = {
            "rwg": ["reviewer", "assigned rwg", "rwg reviewer", "assigned to"],
            "sr_rwg": [
                "reviewer",
                "assigned sr rwg",
                "assigned srrwg",
                "sr rwg reviewer",
                "srrwg reviewer",
                "assigned to",
            ],
        }[role]
        return self.driver.execute_script(
            r"""
            const labelWords = arguments[0].map(word => word.toLowerCase());
            const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                    && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const candidates = Array.from(document.querySelectorAll('*')).filter(el => {
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                return visible(el) && labelWords.some(word => text === word + ':' || text === word);
            });
            for (const label of candidates) {
                // Value is usually the immediate next sibling, or a sibling
                // of the label's parent (label and value each in their own
                // small wrapper element).
                const siblingCandidates = [
                    label.nextElementSibling,
                    label.parentElement && label.parentElement.nextElementSibling,
                ].filter(Boolean);
                for (const sibling of siblingCandidates) {
                    const text = (sibling.innerText || sibling.textContent || '').trim();
                    if (text) return text;
                }
                // Fall back to text after the label within the same parent,
                // e.g. "Reviewer: rwg 2" as one text node's sibling text.
                const parentText = (label.parentElement?.innerText
                    || label.parentElement?.textContent || '').trim();
                const labelText = (label.innerText || label.textContent || '').trim();
                if (parentText.toLowerCase().startsWith(labelText.toLowerCase())) {
                    const remainder = parentText.slice(labelText.length).replace(/^[:\-\s]+/, '');
                    if (remainder) return remainder.split('\n')[0].trim();
                }
            }
            return '';
            """,
            label_words,
        )

    def get_item_set_assignee(self, role):
        scoped_text = self.get_scoped_item_set_assignee_text(role)
        if scoped_text:
            assignee = self.normalize_assignee_key(scoped_text)
            expected_pattern = {"rwg": r"rwg\d+", "sr_rwg": r"srrwg\d+"}[role]
            if re.fullmatch(expected_pattern, assignee):
                return assignee

        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        role_patterns = {
            "rwg": (
                r"(?:Assigned\s+RWG|RWG\s+Reviewer|Reviewer|Assigned\s+to)\s*[:\-]?\s*(?:\r?\n\s*)?([^\r\n]+)",
                r"\b(rwg[\s_-]*\d+)\b",
            ),
            "sr_rwg": (
                r"(?:Assigned\s+SR\s*RWG|Assigned\s+SRRWG|SR\s*RWG\s+Reviewer|SRRWG\s+Reviewer|Assigned\s+to)\s*[:\-]?\s*(?:\r?\n\s*)?([^\r\n]+)",
                r"\b(sr[\s_-]*rwg[\s_-]*\d+|srrwg[\s_-]*\d+)\b",
            ),
        }
        expected_pattern = {
            "rwg": r"rwg\d+",
            "sr_rwg": r"srrwg\d+",
        }[role]

        for pattern in role_patterns[role]:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if not match:
                continue
            assignee = self.normalize_assignee_key(match.group(1))
            if re.fullmatch(expected_pattern, assignee):
                return assignee
        return ""

    @staticmethod
    def normalize_assignee_key(value):
        normalized = re.sub(r"[^a-z0-9]", "", value.strip().lower())
        normalized = normalized.replace("srrwg", "srrwg")
        if normalized.startswith("srrwg"):
            return normalized
        if normalized.startswith("srrw"):
            return normalized.replace("srrw", "srrwg", 1)
        if normalized.startswith("sr") and "rwg" in normalized:
            return "srrwg" + re.sub(r"\D", "", normalized)
        if normalized.startswith("rwg"):
            return normalized
        return normalized

    def require_item_set_assignee(self, role):
        assignee = self.get_item_set_assignee(role)
        if not assignee:
            role_label = "SRRWG" if role == "sr_rwg" else "RWG"
            raise AssertionError(f"Could not detect assigned {role_label} from the item set page.")
        return assignee

    def open_item_set_url_and_wait(self, item_set_url, item_set_id):
        # Match on the stable "IS<number>" prefix, not the full item_set_id -
        # some environments render this page's chapter-code suffix
        # differently than the one captured right after upload (see
        # item_set_numeric_prefix()), so an exact-string check can time out
        # even once the right page has fully loaded.
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        self.driver.get(item_set_url)
        self.wait_utils.until_condition(
            lambda driver: numeric_prefix in driver.find_element(By.TAG_NAME, "body").text,
            timeout=60,
        )
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=120,
        )

    def get_item_set_status_count(self, status_name):
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        match = re.search(rf"{status_name}\s+(\d+)", page_text)
        return int(match.group(1)) if match else 0

    def get_visible_item_statuses(self):
        # Read all values in one browser-side snapshot so a React table
        # refresh cannot stale individual WebElements midway through the loop.
        # The Status column is found by its header: the Book and Unit columns
        # added on UAT pushed it from 3rd to 5th, and a fixed index then read
        # "Book 1" as the item's status.
        return self.driver.execute_script(
            """
            const headers = Array.from(document.querySelectorAll('table thead th'));
            let index = headers.findIndex(th =>
                (th.innerText || th.textContent || '').trim().toLowerCase().startsWith('status'));
            if (index < 0) index = 2;
            const statuses = Array.from(
                document.querySelectorAll(`table tbody tr td:nth-child(${index + 1})`)
            ).map(cell => (cell.innerText || cell.textContent || '').trim())
             .filter(Boolean);
            return Array.from(new Set(statuses));
            """
        )

    def get_item_set_status_summary(self):
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        status_counts = {}
        for status_name in (
            "All",
            "Pending",
            "Approved",
            "Need Improvement",
            "Needs Improvement",
            "Needs Revision",
            "Revise",
            "Rejected",
            "Revised",
        ):
            match = re.search(rf"{status_name}\s+(\d+)", page_text)
            if match:
                status_counts[status_name] = match.group(1)

        visible_statuses = self.get_visible_item_statuses()
        if visible_statuses:
            status_counts["Visible item statuses"] = ", ".join(visible_statuses)
        return status_counts

    @staticmethod
    def format_status_summary(status_summary):
        return ", ".join(
            f"{status_name}: {status_count}"
            for status_name, status_count in status_summary.items()
        )

    # --- User session locators ---
    USER_MENU_LOCATORS = [
        (By.XPATH, "//button[.//*[contains(@class,'avatar')]]"),
        (By.XPATH, "//button[contains(@class,'avatar') or contains(@class,'Avatar')]"),
        (By.XPATH, "//button[contains(normalize-space(),'SM') or contains(normalize-space(),'RWG')]"),
        (By.XPATH, "//*[normalize-space()='SM' or normalize-space()='RWG' or normalize-space()='RW']"),
    ]
    LOGOUT_LOCATORS = [
        (By.XPATH, "//*[self::button or self::div or self::span][contains(normalize-space(),'Logout')]"),
        (By.XPATH, "//*[self::button or self::div or self::span][contains(normalize-space(),'Sign out')]"),
        (By.XPATH, "//*[self::button or self::div or self::span][contains(normalize-space(),'Log out')]"),
    ]

    # --- User session actions ---
    def open_user_menu(self):
        last_error = None
        for locator in self.USER_MENU_LOCATORS:
            try:
                user_menu = self.wait_utils.until_visible(locator, timeout=8)
                clickable_target = user_menu
                ancestors = user_menu.find_elements(
                    By.XPATH,
                    "./ancestor::*[self::button or @role='button' or self::div][1]",
                )
                if ancestors:
                    clickable_target = ancestors[0]
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    clickable_target,
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", clickable_target)
                return
            except Exception as error:
                last_error = error
        raise last_error

    def logout(self):
        self.open_user_menu()
        self.click_any_element(self.LOGOUT_LOCATORS)
        self.wait_utils.until_visible((By.ID, "identifier"), timeout=30)

    def reset_browser_session_to_login(self, retries=2):
        """Retry once on any transport-level hiccup (e.g. a stalled WebDriver

        navigation command), since flaky infra shouldn't abort a multi-role
        E2E flow at a plain session reset.
        """
        last_error = None
        for attempt in range(retries):
            try:
                self.driver.delete_all_cookies()
                try:
                    # A freshly-launched browser (or one on a blank/chrome:
                    # page between sessions) has no http(s) document loaded
                    # yet, and localStorage access there is blocked by the
                    # browser itself ("Access is denied for this document")
                    # - there's nothing to clear in that case anyway, so
                    # this step is best-effort rather than fatal.
                    self.driver.execute_script(
                        "window.localStorage.clear(); window.sessionStorage.clear();"
                    )
                except Exception:
                    pass
                self.driver.get(ReadConfig.get_base_url())
                self.wait_utils.until_visible((By.ID, "identifier"), timeout=30)
                return
            except Exception as error:
                last_error = error
                if attempt == retries - 1:
                    break
                sleep(2)
        raise last_error

    # --- Revision item locators ---
    EDIT_ITEM_LOCATORS = [
        (By.XPATH, "//button[normalize-space()='Edit' or contains(normalize-space(),'Edit Item')]"),
        (By.XPATH, "//*[self::button or self::a][contains(normalize-space(),'Edit')]"),
    ]
    SAVE_REVISION_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Save Revision')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Save')]"),
    ]
    RERUN_QAR_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Re-run QAR')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Rerun QAR')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Run QAR')]"),
    ]
    TEACHER_RESUBMIT_REVIEW_LOCATORS = [
        (By.XPATH, "//button[normalize-space()='Resubmit set for review']"),
        (By.XPATH, "//button[contains(normalize-space(),'Resubmit') and contains(normalize-space(),'review')]"),
        # Not every build renders this control as a <button>: a live run found
        # "Resubmit set for review" on screen while both locators above missed
        # it, and an <a> or a div[role=button] would do exactly that. Matched
        # last so a real button still wins.
        (
            By.XPATH,
            "//*[self::a or @role='button' or self::div or self::span]"
            "[contains(normalize-space(),'Resubmit') "
            "and contains(normalize-space(),'review') "
            "and not(.//*[contains(normalize-space(),'Resubmit')])]",
        ),
    ]
    REVISION_NOTE_INPUT_LOCATORS = [
        (
            By.XPATH,
            "//*[contains(normalize-space(),'Revision Notes')]/following::textarea[1]",
        ),
        (
            By.XPATH,
            "//*[contains(normalize-space(),'Revision Notes')]/following::*[@contenteditable='true'][1]",
        ),
        (
            By.XPATH,
            "//textarea[contains(@placeholder,'Revision') or contains(@aria-label,'Revision')]",
        ),
    ]
    ITEM_CONTENT_EDITORS = [
        (By.CSS_SELECTOR, "[aria-label='itemContent'] .tiptap"),
        (By.CSS_SELECTOR, "[aria-label='itemContent'] [contenteditable='true']"),
        # Newer builds label the editor with its visible field name instead.
        (By.CSS_SELECTOR, "[aria-label='Statement'] .tiptap"),
        (By.CSS_SELECTOR, "[aria-label='Statement'] [contenteditable='true']"),
        (By.XPATH, "(//*[@contenteditable='true'])[1]"),
        (By.XPATH, "(//textarea)[1]"),
    ]
    # QAR blocks an item with either wording depending on how hard its checks
    # failed - a borderline item comes back "Needs Revision", a clear failure
    # (e.g. a strong duplicate match) "Rejected". Both mean the same thing to
    # the retry flow: the item did not pass and is offered for correction and
    # re-run, which the app's own "Re-run QAR (n)" control confirms by
    # counting the rejected items among the ones it will re-submit.
    QAR_RETRY_STATUS_LABELS = (
        "Need Improvement",
        "Needs Improvement",
        "Needs Revision",
        "Revise",
        "Rejected",
    )

    # --- Revision item actions ---
    def find_first_pending_item_link(self):
        return self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//table//tbody/tr[.//td[contains(normalize-space(),'Pending')]][1]"
                "//td[1]//*[self::a or self::button][normalize-space()][1]",
            ),
            timeout=20,
        )

    def get_item_ids_by_status(self, status_text):
        rows = self.driver.find_elements(
            By.XPATH,
            f"//table//tbody/tr[.//td[contains(normalize-space(),'{status_text}')]]",
        )
        item_ids = []
        for row in rows:
            try:
                item_cell = row.find_element(
                    By.XPATH,
                    ".//td[1]//*[normalize-space()] | .//td[1]",
                )
                item_id = item_cell.text.strip()
                if item_id and item_id.lower() != "item id" and item_id not in item_ids:
                    item_ids.append(item_id)
            except Exception:
                continue
        return item_ids

    def get_qar_item_statuses(self, item_set_id=None):
        """Return the visible QAR/RWG-facing status for every item table row.

        Pass item_set_id to keep only that set's own item rows. Set-level
        tables (the Sets list, upload history) render one row per item set,
        whose ID carries no "-i<n>" suffix and whose status is the set's, not
        an item's - a read taken while such a table is on screen otherwise
        reports unrelated sets' failures as this set's items.
        """
        rows = self.driver.execute_script(
            r"""
            const statusPattern = /\b(Needs? Improvement|Needs Revision|Revise|Rejected|Failed|Blocked|Approved|Passed|Pending|Revised)\b/i;
            return Array.from(document.querySelectorAll('table tbody tr')).map(row => {
                const cells = Array.from(row.querySelectorAll('td'));
                if (!cells.length) return null;
                const compactItemText = (cells[0].innerText || cells[0].textContent || '')
                    .replace(/\s+/g, '')
                    .trim();
                const uploadedItemMatch = compactItemText.match(
                    /IS\d+(?:-[A-Za-z0-9]+)*-i\d+/i
                );
                const itemId = uploadedItemMatch
                    ? uploadedItemMatch[0]
                    : compactItemText;
                const statusCells = cells.length > 2
                    ? [cells[2], ...cells.slice(1, 2), ...cells.slice(3)]
                    : cells.slice(1);
                const statusText = statusCells
                    .map(cell => (cell.innerText || cell.textContent || '').trim())
                    .find(text => statusPattern.test(text)) || '';
                const match = statusText.match(statusPattern);
                return itemId && match ? [itemId, match[1]] : null;
            }).filter(Boolean);
            """
        )
        statuses = dict(rows or [])
        if item_set_id is None:
            return statuses
        set_prefix = self.compact_item_id(
            self.item_set_numeric_prefix(item_set_id)
        ).casefold()
        return {
            row_item_id: status
            for row_item_id, status in statuses.items()
            if (compact := self.compact_item_id(row_item_id).casefold())
            and re.match(rf"{re.escape(set_prefix)}(?!\d)", compact)
            and re.search(r"i\d+$", compact)
        }

    def get_qar_need_improvement_item_ids(self):
        """Return every item that must be corrected before RWG routing."""
        retry_statuses = {
            status.casefold() for status in self.QAR_RETRY_STATUS_LABELS
        }
        return [
            item_id
            for item_id, status in self.get_qar_item_statuses().items()
            if status.casefold() in retry_statuses
        ]

    def click_item_by_id(self, item_id):
        self.pause_before_action()
        item_link = self.wait_utils.until_clickable(
            (
                By.XPATH,
                f"//table//tbody/tr//td[1]//*[normalize-space()='{item_id}' or normalize-space()=\"{item_id}\"]",
            ),
            timeout=20,
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item_link)
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", item_link)
        self.wait_utils.until_condition(
            lambda driver: item_id in driver.find_element(By.TAG_NAME, "body").text,
            timeout=30,
        )
        return item_id

    def click_edit_item(self):
        if any(
            self.wait_utils.is_visible(locator, timeout=1)
            for locator in self.SAVE_REVISION_LOCATORS
        ):
            return
        self.click_any_element(self.EDIT_ITEM_LOCATORS)

    def get_visible_element_from_locators(self, locators):
        for locator in locators:
            for element in self.driver.find_elements(*locator):
                try:
                    if element.is_displayed() and element.is_enabled():
                        return element
                except Exception:
                    continue
        return None

    @staticmethod
    def get_editable_element_text(element):
        if element.tag_name.lower() in ("input", "textarea"):
            return element.get_attribute("value") or ""
        return element.get_attribute("innerText") or element.text or ""

    def set_first_available_editor_text(self, value):
        editor = self.wait_utils.until_condition(
            lambda driver: self.get_visible_element_from_locators(self.ITEM_CONTENT_EDITORS),
            timeout=20,
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", editor)
        self.pause_before_action()
        try:
            editor.click()
            editor.send_keys(Keys.CONTROL, "a")
            editor.send_keys(Keys.BACKSPACE)
            editor.send_keys(value)
        except Exception:
            self.driver.execute_script(
                """
                const editor = arguments[0];
                const value = arguments[1];
                if ('value' in editor) editor.value = value;
                else editor.innerHTML = '<p>' + value + '</p>';
                editor.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    inputType: 'insertText',
                    data: value,
                }));
                editor.dispatchEvent(new Event('change', { bubbles: true }));
                editor.dispatchEvent(new Event('blur', { bubbles: true }));
                """,
                editor,
                value,
            )
        try:
            self.wait_utils.until_condition(
                lambda driver: value in self.get_editable_element_text(editor),
                timeout=15,
            )
        except TimeoutException:
            try:
                actual_text = self.get_editable_element_text(editor)
            except Exception as read_error:
                actual_text = f"<could not read editor text: {read_error}>"
            raise AssertionError(
                "set_first_available_editor_text: expected text not found in "
                f"editor after edit.\nExpected (value): {value!r}\n"
                f"Actual (editor text): {actual_text!r}"
            )

    def enter_revision_notes(self, note_text):
        last_error = None
        for locator in self.REVISION_NOTE_INPUT_LOCATORS:
            try:
                note_input = self.wait_utils.until_visible(locator, timeout=8)
                tag_name = note_input.tag_name.lower()
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", note_input)
                self.pause_before_action()
                if tag_name == "textarea":
                    note_input.clear()
                    note_input.send_keys(note_text)
                else:
                    self.driver.execute_script(
                        """
                        const input = arguments[0];
                        const value = arguments[1];
                        input.innerHTML = '<p>' + value + '</p>';
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        note_input,
                        note_text,
                    )
                return
            except Exception as error:
                last_error = error
        return False

    def get_teacher_revised_count(self):
        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r"\b(\d+)\s+items?\s+revised\b", body_text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def click_save_revision(self):
        last_error = None
        revised_count_before = self.get_teacher_revised_count()
        for locator in self.SAVE_REVISION_LOCATORS:
            try:
                save_button = self.wait_utils.until_clickable(locator, timeout=15)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    save_button,
                )
                self.pause_before_action()
                try:
                    save_button.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", save_button)
                self.wait_utils.until_condition(
                    lambda driver: self.get_teacher_revised_count() > revised_count_before
                    or not any(
                        self.wait_utils.is_visible(save_locator, timeout=1)
                        for save_locator in self.SAVE_REVISION_LOCATORS
                    ),
                    timeout=45,
                )
                return
            except Exception as error:
                last_error = error
        raise last_error

    ITEM_ID_PATTERN = re.compile(r"IS\d+(?:-[A-Za-z0-9]+)*-i\d+", re.IGNORECASE)

    @classmethod
    def _extract_item_id_key(cls, text):
        """Return a normalized item-id key from free text, or None if absent.

        Used to reconcile the table-row scan below with the broader
        card-based scan that follows it: both can surface the same
        underlying item through different DOM shapes (e.g. a single-item
        set that renders both a table row and a standalone detail card for
        the same item), and only a real item-id match reliably identifies
        that they're duplicates - a raw label/element-id does not.
        """
        match = cls.ITEM_ID_PATTERN.search(text or "")
        return cls.compact_item_id(match.group(0)).casefold() if match else None

    def get_revision_item_targets(self):
        targets = []
        seen = set()
        seen_item_ids = set()
        revision_rows = self.driver.find_elements(
            By.XPATH,
            "//table//tbody/tr[.//*[normalize-space()='Revise' "
            "or normalize-space()='Needs Revision' "
            "or normalize-space()='Need Improvement' "
            "or normalize-space()='Needs Improvement']]",
        )
        for row in revision_rows:
            try:
                if not row.is_displayed():
                    continue
                first_cell = row.find_element(By.XPATH, "./td[1]")
                item_label = re.sub(r"\s+", "", first_cell.text)
                links = first_cell.find_elements(
                    By.XPATH,
                    ".//*[self::a or self::button or @role='button']",
                )
                target = next(
                    (
                        link
                        for link in links
                        if link.is_displayed() and link.is_enabled()
                    ),
                    None,
                )
                if not target:
                    continue
                key = item_label or target.id
                if key in seen:
                    continue
                seen.add(key)
                item_id_key = self._extract_item_id_key(row.text)
                if item_id_key:
                    seen_item_ids.add(item_id_key)
                targets.append((target, item_label or "revision item"))
            except Exception:
                continue

        # Always also scan for card-rendered revision items and merge them in
        # (deduped via `seen`). A table-based match set can be legitimately
        # incomplete - e.g. an item whose typology renders a different card
        # layout - and returning early here would silently drop it instead
        # of falling through to the broader card-based scan below.
        status_elements = self.driver.find_elements(
            By.XPATH,
            "//*[normalize-space()='Revise' or normalize-space()='Needs Revision' "
            "or normalize-space()='Need Improvement' "
            "or normalize-space()='Needs Improvement']",
        )
        for status_element in status_elements:
            try:
                if not status_element.is_displayed():
                    continue
                target = self.driver.execute_script(
                    """
                    let node = arguments[0];
                    while (node && node !== document.body) {
                        const text = (node.innerText || '').trim();
                        const role = node.getAttribute && node.getAttribute('role');
                        const clickable = node.matches &&
                            node.matches('a, button, [role="button"], [tabindex]');
                        const compactItem = text.length > 10 && text.length < 600 &&
                            !/^Revise\\s+\\d+$/i.test(text);
                        if (clickable && compactItem) return node;
                        node = node.parentElement;
                    }
                    node = arguments[0];
                    while (node && node !== document.body) {
                        const text = (node.innerText || '').trim();
                        if (text.length > 10 && text.length < 600 &&
                            !/^Revise\\s+\\d+$/i.test(text)) return node;
                        node = node.parentElement;
                    }
                    return arguments[0];
                    """,
                    status_element,
                )
                item_id_key = self._extract_item_id_key(target.text)
                if item_id_key and item_id_key in seen_item_ids:
                    # Same underlying item already captured by the table scan
                    # above (e.g. a single-item set rendering both a table
                    # row and a standalone detail card) - not a second item.
                    continue

                key = target.id
                if key in seen:
                    continue
                seen.add(key)
                if item_id_key:
                    seen_item_ids.add(item_id_key)
                label_lines = [
                    line.strip()
                    for line in target.text.splitlines()
                    if line.strip() and line.strip() not in self.QAR_RETRY_STATUS_LABELS
                ]
                targets.append((target, label_lines[0] if label_lines else "revision item"))
            except Exception:
                continue
        return targets

    def click_first_revision_item(self):
        targets = self.get_revision_item_targets()
        if not targets:
            return ""
        target, item_label = targets[0]
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", target)
        self.wait_utils.until_condition(
            lambda driver: any(
                self.wait_utils.is_visible(locator, timeout=1)
                for locator in self.SAVE_REVISION_LOCATORS
            )
            or any(
                self.wait_utils.is_visible(locator, timeout=1)
                for locator in self.EDIT_ITEM_LOCATORS
            ),
            timeout=20,
        )
        return item_label

    @staticmethod
    def _find_image_file_input(driver):
        for el in driver.find_elements(By.XPATH, "//input[@type='file']"):
            accept = el.get_attribute("accept") or ""
            if "image" in accept or not accept:
                return el
        return None

    def attach_image_to_item_editor(self, image_path, allow_native_dialog_risk=True):
        """Attach an image to the currently-open item editor.

        Strategy (in order):
        1. Look for an already-mounted (but hidden) file <input type="file">
           and send_keys the path straight to it - no clicks at all, so this
           never triggers a native dialog. If none is mounted yet and
           `allow_native_dialog_risk` is True, click the toolbar image
           button (never "Upload from device" or any other menu entry
           whose handler is likely to call `fileInputRef.current.click()`
           directly - that specific click is what invokes a real native OS
           file-picker dialog, which Selenium cannot see or dismiss and
           hangs the whole browser session indefinitely behind it) to
           reveal the input, then retry. This produces a real `blob:` URL
           image that the app's own upload flow serializes and persists.
        2. Only if no file input can be found at all: fall back to
           injecting a <img data-test-image="true"> element directly into
           the editor via a base64 data-URI. This is pure DOM manipulation
           - safe, but NOT reliable: the app's rich-text editor (TipTap/
           ProseMirror) keeps its own internal document model and can
           silently drop a DOM node that was never part of one of its own
           transactions, so the image can appear to attach successfully in
           the browser and then vanish once the item is saved and reloaded.
           Only use this as an absolute last resort.
        """
        image_path = Path(image_path).resolve()
        assert image_path.exists(), f"Test image not found: {image_path}"

        # --- Attempt 1: locate an already-mounted file input, no clicks ---
        file_input = self._find_image_file_input(self.driver)

        # --- Reveal the input via the toolbar button only, if allowed ---
        if not file_input and allow_native_dialog_risk:
            image_toolbar_locators = [
                (By.XPATH, "//button[@aria-label='image' or @aria-label='Insert image' or @aria-label='Add image' or @title='Image' or @title='Insert image']"),
                (By.XPATH, "//button[.//*[contains(@class,'lucide-image') or contains(@class,'image-icon') or contains(@class,'photo')]]"),
                (By.CSS_SELECTOR, "button[title*='mage'], button[aria-label*='mage']"),
            ]
            for locator in image_toolbar_locators:
                try:
                    btn = self.wait_utils.until_visible(locator, timeout=2)
                    if btn.is_enabled():
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        self.driver.execute_script("arguments[0].click();", btn)
                        break
                except Exception:
                    continue

            try:
                file_input = self.wait_utils.until_condition(
                    self._find_image_file_input, timeout=5
                )
            except Exception:
                file_input = None

        if file_input:
            self.driver.execute_script(
                "arguments[0].style.display='block'; arguments[0].style.visibility='visible'; arguments[0].style.opacity='1';",
                file_input,
            )
            file_input.send_keys(str(image_path))

            # After selecting the file, the app shows a preview dialog with an
            # explicit "Insert" button that must be clicked to commit the image
            # into the editor — selecting the file alone does not insert it.
            insert_button_locators = [
                (
                    By.XPATH,
                    "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
                    "//button[normalize-space()='Insert' or normalize-space()='Insert Image' "
                    "or normalize-space()='Add' or normalize-space()='Upload' "
                    "or normalize-space()='Add Image' and not(@disabled)]",
                ),
                (
                    By.XPATH,
                    "//button[normalize-space()='Insert' or normalize-space()='Insert Image' "
                    "or normalize-space()='Add Image']",
                ),
            ]
            for locator in insert_button_locators:
                try:
                    insert_button = self.wait_utils.until_visible(locator, timeout=10)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", insert_button
                    )
                    self.pause_before_action()
                    self.driver.execute_script("arguments[0].click();", insert_button)
                    break
                except Exception:
                    continue

            # The app renders the inserted image as <img src="blob:..."> wrapped in
            # a `.rte-img-wrap` span (not a data-URI and not aria-label='itemContent').
            # Requiring img.complete && naturalWidth > 0 (not just a non-zero
            # bounding box) avoids racing ahead while the blob is still
            # loading - a placeholder/broken-image icon can already report a
            # non-zero rendered size before the real bytes have decoded.
            self.wait_utils.until_condition(
                lambda driver: bool(
                    driver.execute_script(
                        """
                        return Array.from(document.querySelectorAll(
                            "[contenteditable='true'] img"
                        )).some(function(img) {
                            const rect = img.getBoundingClientRect();
                            return !img.classList.contains('ProseMirror-separator')
                                && rect.width > 10
                                && rect.height > 10
                                && img.complete
                                && img.naturalWidth > 0;
                        });
                        """
                    )
                ),
                timeout=45,
            )
            return

        # --- Last resort: DOM injection (not guaranteed to persist) ---
        if not self._inject_image_data_uri(image_path):
            raise TimeoutException(
                "attach_image_to_item_editor: no file input could be found/revealed "
                "and DOM data-URI injection also failed (no visible contenteditable "
                "editor found)."
            )

    def _inject_image_data_uri(self, image_path, append=True):
        """Insert an <img data-test-image> into the item editor via pure DOM
        manipulation - no clicks, so this can never trigger a native OS
        file-picker dialog. Returns True on success, False if no visible
        contenteditable editor was found (caller decides how to fall back).

        When `append` is True (the default) the image is added alongside
        whatever is already in the editor rather than clearing it first -
        callers that want a from-scratch editor should clear it themselves
        before calling this.
        """
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        data_uri = f"data:{mime};base64," + base64.b64encode(image_path.read_bytes()).decode()

        inserted = self.driver.execute_script(
            """
            const dataUri = arguments[0];
            const selectors = [
                "[aria-label='itemContent'] .tiptap",
                "[aria-label='itemContent'] [contenteditable='true']",
                "[aria-label='Statement'] .tiptap",
                "[aria-label='Statement'] [contenteditable='true']",
                ".tiptap[contenteditable='true']",
                "[contenteditable='true']"
            ];
            let editor = null;
            for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) { editor = el; break; }
                }
                if (editor) break;
            }
            if (!editor) return false;
            editor.focus();
            const img = document.createElement('img');
            img.src = dataUri;
            img.setAttribute('data-test-image', 'true');
            img.setAttribute('alt', 'test-attachment');
            img.style.maxWidth = '200px';
            img.style.display = 'block';
            editor.appendChild(img);
            editor.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText'}));
            editor.dispatchEvent(new Event('change', {bubbles: true}));
            editor.dispatchEvent(new Event('blur', {bubbles: true}));
            return true;
            """,
            data_uri,
        )
        if not inserted:
            return False
        try:
            self.wait_utils.until_condition(
                lambda driver: bool(
                    driver.find_elements(
                        By.CSS_SELECTOR, "[contenteditable='true'] img[data-test-image]"
                    )
                ),
                timeout=10,
            )
        except TimeoutException:
            # A rich-text editor (TipTap/ProseMirror) can discard a raw DOM
            # node injected outside its own transaction system - e.g. on the
            # blur/change events dispatched above - so the node we just
            # appended may already be gone. Report failure so the caller can
            # fall back, rather than raising here.
            return False
        return True

    BLANK_MARKER = re.compile(r"_{3,}")
    # The Fill in the Blank editor counts a blank only as exactly four
    # underscores ("Use ____ (four underscores) to indicate each blank").
    EDITOR_BLANK = "____"
    REVISION_PREFIX = re.compile(r"^\s*Updated revision for [^:]+:\s*", re.IGNORECASE)

    FITB_TYPOLOGY_MARKERS = ("fill in the blank", "fill in blank", "fitb", "fib")

    def open_item_is_fill_in_the_blank(self):
        """True when the open item's Typology reads Fill in the Blank.

        Read from the labelled Typology field rather than from the page text:
        the item list renders a typology chip for every item, so a page-wide
        match would report the open item as FITB whenever any sibling was.
        """
        try:
            typology = (self.get_item_detail_metadata(["Typology"]) or {}).get(
                "Typology", ""
            )
        except Exception:
            return False
        return any(
            marker in str(typology).casefold() for marker in self.FITB_TYPOLOGY_MARKERS
        )

    def default_revision_question(self, item_id):
        """The question text a revision writes when the caller gives none.

        Normally a fixed comparison question. A Fill in the Blank item must
        keep a blank, written as exactly four underscores. Items uploaded from
        Excel carry three ("___"), which the upload accepts but the editor
        counts as zero blanks; against its one Blank Answer the item is then
        invalid and Save does nothing, with no message. On 2026-09-29/30 that
        left the FITB item un-revised, the set never went back to RWG, and the
        run failed as "not visible in any RWG queue".

        The typology is what decides this, not the text read back. Keying it on
        finding "___" in the current text meant that whenever that read came
        back empty - the editor locators miss on some builds - a FITB item
        silently got the fixed comparison question, which has no blank at all
        and is exactly the invalid state described above. Three live runs
        (2026-09-30) failed on the same FITB item for that reason, each time
        leaving its original text on screen.

        The "Updated revision for" prefix is kept either way - the
        reviewer-side check looks for it.
        """
        try:
            editor = self.wait_utils.until_condition(
                lambda driver: self.get_visible_element_from_locators(self.ITEM_CONTENT_EDITORS),
                timeout=20,
            )
            current = self.get_editable_element_text(editor).strip()
        except Exception:
            current = ""
        if self.BLANK_MARKER.search(current):
            text = self.BLANK_MARKER.sub(self.EDITOR_BLANK, self.REVISION_PREFIX.sub("", current))
            return f"Updated revision for {item_id}: {text}"
        if self.open_item_is_fill_in_the_blank():
            # Its own text was unreadable, so write a self-contained blank
            # rather than a question this typology cannot accept.
            return (
                f"Updated revision for {item_id}: A bus leaves at 8:00 and "
                f"arrives at 10:00. The journey lasts {self.EDITOR_BLANK} hours."
            )
        return f"Updated revision for {item_id}: Is 98765 > 12345?"

    def edit_open_revision_item(
        self,
        item_id,
        revised_question=None,
        revision_note=None,
        image_path=None,
    ):
        revised_count_before = self.get_teacher_revised_count()
        self.click_edit_item()
        # Read after opening the editor: the default depends on the item's
        # current text (see default_revision_question).
        revised_question = revised_question or self.default_revision_question(item_id)
        self.set_first_available_editor_text(revised_question)
        if image_path:
            try:
                self.attach_image_to_item_editor(image_path)
            except Exception as img_err:
                _safe_print(f"[WARN] Image attach skipped for {item_id}: {img_err}")
        self.enter_revision_notes(
            revision_note or f"Automation revision note for {item_id}."
        )
        self.click_save_revision()
        try:
            self.wait_utils.until_condition(
                lambda driver: self.get_teacher_revised_count() > revised_count_before,
                timeout=10,
            )
        except TimeoutException:
            # click_save_revision() can report success when the save button
            # merely disappears without the edit actually persisting (a
            # validation hiccup for some typologies). Don't fail here - the
            # caller re-checks QAR status and retries with a fresh
            # correction on the next round if this item is still flagged -
            # but say so, since a silent miss here once cost a whole run.
            _safe_print(
                f"[WARN] Revision save for {item_id} was not confirmed: the "
                "revised count did not go up within 10s."
            )
        return revised_question

    def revise_qar_need_improvement_items(
        self,
        item_set_id,
        expected_item_ids,
        correction_factory,
        retry_number,
        image_path_by_item_id=None,
    ):
        """Open and correct each currently retriable QAR item once."""
        expected_item_ids = tuple(dict.fromkeys(expected_item_ids))
        expected_by_key = {
            self.compact_item_id(item_id).casefold(): item_id
            for item_id in expected_item_ids
        }
        revised_item_ids = []
        # Track processed keys so we never re-edit an item whose UI status hasn't
        # refreshed yet (the status badge stays "Need Improvement" until QAR re-runs).
        processed_keys = set()
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=60,
        )

        while True:
            targets = self.get_revision_item_targets()

            # Find the first target whose normalized item-key has not been processed.
            next_item = None
            for target_elem, raw_label in targets:
                normalized = raw_label
                if not self.compact_item_id(raw_label).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", raw_label)
                    if m:
                        normalized = f"{item_set_id}-i{m.group(1)}"
                key = self.compact_item_id(normalized).casefold()
                if key not in processed_keys:
                    next_item = (target_elem, normalized, key)
                    break

            if next_item is None:
                break  # No unprocessed revision items remain.

            target_elem, item_label, item_key = next_item

            # Click the specific, unprocessed target element.
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target_elem
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", target_elem)
                self.wait_utils.until_condition(
                    lambda driver: any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.SAVE_REVISION_LOCATORS
                    ) or any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.EDIT_ITEM_LOCATORS
                    ),
                    timeout=20,
                )
            except Exception:
                # Element went stale — fall back to clicking whatever "first revision
                # item" is currently in the list and check it isn't already processed.
                fallback_label = self.click_first_revision_item()
                if not fallback_label:
                    break
                if not self.compact_item_id(fallback_label).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", fallback_label)
                    if m:
                        fallback_label = f"{item_set_id}-i{m.group(1)}"
                fb_key = self.compact_item_id(fallback_label).casefold()
                if fb_key in processed_keys:
                    break  # Only already-processed items left.
                item_label, item_key = fallback_label, fb_key

            canonical_item_id = expected_by_key.get(item_key, item_label)
            try:
                qar_feedback = QARReportPage(self.driver).inspect_item_feedback(
                    canonical_item_id
                )
            except Exception:
                # Some legacy/minimal review builds expose the actionable row
                # without rendering report cards. The correction still runs,
                # but full E2E builds retain the inspected report evidence.
                qar_feedback = {
                    "status": "",
                    "score": None,
                    "failure_reasons": {},
                }
            try:
                correction = correction_factory(
                    canonical_item_id,
                    retry_number,
                    qar_feedback,
                )
            except TypeError:
                correction = correction_factory(canonical_item_id, retry_number)
            if isinstance(correction, str):
                correction = {"question": correction}
            revised_question = correction.get("question", "").strip()
            if not revised_question:
                raise AssertionError(
                    f"Correction fixture returned no question for {canonical_item_id}."
                )
            feedback_parts = []
            if qar_feedback.get("status"):
                feedback_parts.append(f"status={qar_feedback['status']}")
            if qar_feedback.get("score") is not None:
                feedback_parts.append(f"score={qar_feedback['score']}%")
            feedback_parts.extend(qar_feedback.get("failure_reasons", {}).keys())
            revision_note = correction.get("revision_note") or (
                f"Automation QAR correction for {canonical_item_id}."
            )
            if feedback_parts:
                revision_note = (
                    f"{revision_note} QAR feedback reviewed: "
                    f"{', '.join(feedback_parts)}."
                )
            edit_arguments = {
                "revised_question": revised_question,
                "revision_note": revision_note,
            }
            image_path = (image_path_by_item_id or {}).get(canonical_item_id)
            if image_path:
                edit_arguments["image_path"] = image_path
            self.edit_open_revision_item(canonical_item_id, **edit_arguments)
            revised_item_ids.append(canonical_item_id)
            processed_keys.add(item_key)

            # Wait for the page to settle (NOT for the revision-list badge to update —
            # the app keeps "Need Improvement" until QAR is re-run).
            self.wait_utils.until_condition(
                lambda driver: not self.is_item_set_detail_loading(driver),
                timeout=30,
            )

        return revised_item_ids

    def is_rerun_qar_enabled(self):
        """Check if Re-run QAR button is enabled without clicking it."""
        for locator in self.RERUN_QAR_LOCATORS:
            try:
                rerun_button = self.wait_utils.until_visible(locator, timeout=5)
                if rerun_button.is_enabled() and not rerun_button.get_attribute("disabled") and rerun_button.get_attribute("aria-disabled") != "true":
                    return True
            except Exception:
                continue
        return False

    REVISED_COUNT_PATTERN = r"(\d+)\s+items?\s+revised"

    def get_revised_item_count(self):
        """How many items this screen says have been revised, or None.

        The item list on the revision screen shows each item's question text
        and badges but *not* its ID, so there is no per-item row to look an ID
        up in - an earlier attempt to confirm revisions that way reported every
        item as unsaved. The header's "N items revised" counter is what this
        screen actually renders, so it is what gets read.

        None means the counter is not on screen at all. Callers must treat that
        as "cannot tell", never as zero.
        """
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        match = re.search(self.REVISED_COUNT_PATTERN, page_text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    def revised_count_reached(self, expected_count, timeout=20):
        """Wait for the revised counter to reach expected_count.

        Returns True when it does, and also when the counter is absent: this
        check guards a loop that several suites already depend on, so a screen
        that does not render the counter must keep the old behaviour rather
        than fail every item on a signal that was never there.
        """
        try:
            return bool(
                self.wait_utils.until_condition(
                    lambda driver: (
                        self.get_revised_item_count() is None
                        or self.get_revised_item_count() >= expected_count
                    ),
                    timeout=timeout,
                )
            )
        except TimeoutException:
            return False

    def retry_revision_edit(self, item_label, edit_fn, expected_count, attempts=1):
        """Re-open an item whose edit did not stick and try it once more."""
        for _ in range(attempts):
            try:
                if not self.open_revision_item_by_label(item_label):
                    continue
                result = edit_fn(item_label)
            except Exception:
                continue
            self.wait_utils.until_condition(
                lambda driver: not self.is_item_set_detail_loading(driver),
                timeout=30,
            )
            if self.revised_count_reached(expected_count):
                return result
        return None

    def open_revision_item_by_label(self, item_label):
        """Click the revision target whose label matches item_label."""
        compact = self.compact_item_id(item_label).casefold()
        for target_elem, raw_label in self.get_revision_item_targets():
            candidate = self.compact_item_id(raw_label).casefold()
            number = re.match(r"\s*(\d+)\b", raw_label)
            matches = candidate == compact or (
                number is not None and compact.endswith(f"i{number.group(1)}")
            )
            if not matches:
                continue
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target_elem
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", target_elem)
                return True
            except Exception:
                return False
        return False

    def _revise_items_loop(self, item_set_id, edit_fn):
        """Core revision loop shared by revise_items_in_open_item_set variants.

        Iterates revision targets, skipping ones already processed, until none
        remain unprocessed.  The app keeps the 'Need Improvement' badge visible
        until QAR is re-run, so we track processed items ourselves instead of
        relying on the list to shrink.
        """
        results = []
        unconfirmed = []
        processed_keys = set()
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=60,
        )

        while True:
            targets = self.get_revision_item_targets()

            next_item = None
            for target_elem, raw_label in targets:
                normalized = raw_label
                if not self.compact_item_id(raw_label).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", raw_label)
                    if m:
                        normalized = f"{item_set_id}-i{m.group(1)}"
                key = self.compact_item_id(normalized).casefold()
                if key not in processed_keys:
                    next_item = (target_elem, normalized, key)
                    break

            if next_item is None:
                break

            target_elem, item_label, item_key = next_item
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target_elem
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", target_elem)
                self.wait_utils.until_condition(
                    lambda driver: any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.SAVE_REVISION_LOCATORS
                    ) or any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.EDIT_ITEM_LOCATORS
                    ),
                    timeout=20,
                )
            except Exception:
                fallback = self.click_first_revision_item()
                if not fallback:
                    break
                if not self.compact_item_id(fallback).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", fallback)
                    if m:
                        fallback = f"{item_set_id}-i{m.group(1)}"
                fb_key = self.compact_item_id(fallback).casefold()
                if fb_key in processed_keys:
                    break
                item_label, item_key = fallback, fb_key

            result = edit_fn(item_label)
            processed_keys.add(item_key)

            self.wait_utils.until_condition(
                lambda driver: not self.is_item_set_detail_loading(driver),
                timeout=30,
            )
            # Confirm the edit actually landed before counting it. An edit call
            # returning is not evidence the save persisted - a live run had this
            # loop report 4 items revised while the page header read "3 items
            # revised" and one item still carried its Revise badge, which then
            # surfaced minutes later as an unavailable resubmit control. One
            # retry per item, because a silently dropped save usually takes on
            # the second attempt.
            expected_count = len(results) + 1
            if self.revised_count_reached(expected_count):
                results.append(result)
                continue
            retried = self.retry_revision_edit(item_label, edit_fn, expected_count)
            if retried is not None:
                results.append(retried)
            else:
                unconfirmed.append(item_label)

        if unconfirmed:
            raise AssertionError(
                f"These items were edited but never showed as revised on "
                f"{item_set_id}: {unconfirmed}. The save was silently dropped, "
                "so the set cannot be resubmitted."
            )
        return results

    def revise_items_in_open_item_set(self, item_set_id):
        """Edit every revision item without leaving the open item-set screen."""
        return self._revise_items_loop(
            item_set_id,
            lambda label: (self.edit_open_revision_item(label), label)[1],
        )

    def revise_items_with_image_in_open_item_set(self, item_set_id, image_path):
        """Like revise_items_in_open_item_set but attaches image_path to every revised item."""
        def _edit_with_image(label):
            revised_question = self.edit_open_revision_item(label, image_path=image_path)
            return (label, revised_question)

        return self._revise_items_loop(item_set_id, _edit_with_image)

    def is_teacher_resubmit_present_but_disabled(self):
        """True when "Resubmit set for review" is on screen but not clickable.

        The app disables it until every item the reviewer flagged has actually
        been revised, so this state means "revisions are incomplete", which is
        a different problem from the control being missing. Without this the
        two were indistinguishable: until_clickable() simply fell through and
        reported the button as unavailable.
        """
        for locator in self.TEACHER_RESUBMIT_REVIEW_LOCATORS:
            for element in self.driver.find_elements(*locator):
                try:
                    if not element.is_displayed():
                        continue
                    if (
                        not element.is_enabled()
                        or element.get_attribute("disabled")
                        or element.get_attribute("aria-disabled") == "true"
                    ):
                        return True
                except Exception:
                    continue
        return False

    def rerun_qar_if_enabled(self):
        for locator in self.TEACHER_RESUBMIT_REVIEW_LOCATORS:
            try:
                submit_button = self.wait_utils.until_clickable(locator, timeout=10)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    submit_button,
                )
                self.pause_before_action()
                try:
                    submit_button.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", submit_button)
                self.confirm_submit_if_prompted()
                self.wait_utils.until_condition(
                    lambda driver: not any(
                        self.wait_utils.is_visible(submit_locator, timeout=1)
                        for submit_locator in self.TEACHER_RESUBMIT_REVIEW_LOCATORS
                    ),
                    timeout=30,
                )
                return "Teacher resubmitted the revised set for review."
            except Exception:
                continue

        disabled_found = False
        for locator in self.RERUN_QAR_LOCATORS:
            try:
                rerun_button = self.wait_utils.until_visible(locator, timeout=10)
                if not rerun_button.is_enabled() or rerun_button.get_attribute("disabled") or rerun_button.get_attribute("aria-disabled") == "true":
                    disabled_found = True
                    continue
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", rerun_button)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", rerun_button)
                return self.wait_for_ocr_success_message()
            except Exception:
                continue
        if disabled_found:
            return "Re-run QAR button found but disabled."
        if self.is_teacher_resubmit_present_but_disabled():
            return (
                "Resubmit set for review is on screen but disabled - the set "
                "still has items awaiting revision."
            )
        return "Re-run QAR button not available."

    def resubmit_revised_item_set_for_review(self):
        """Resubmit SME revisions without changing the legacy QAR helper contract."""
        result = self.rerun_qar_if_enabled()
        if "resubmitted" not in result.casefold():
            raise AssertionError(
                "The revised item set was not resubmitted for review. "
                f"Observed action result: {result}"
            )
        return result.replace("Teacher", "SME", 1)
