from time import monotonic, sleep

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class QuestionPaperBuilderPage(BasePage):
    QP_BUILDER_NAV = (
        By.XPATH,
        "//*[self::button or self::a][normalize-space()='QP Builder' "
        "or .//*[normalize-space()='QP Builder']]",
    )
    CONTINUE_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(),'Continue')]"
        " | //button[contains(normalize-space(),'Confirm')]",
    )

    # ------------------------------------------------------------------
    # Survey locators
    #
    # Used by the element-presence surveys rather than by the build workflow,
    # which finds most of its controls dynamically through JS. Taken from a DOM
    # census of the live builder, My QP listing and paper preview.
    # ------------------------------------------------------------------

    # --- Application chrome (shared across every QP screen) ---
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
    NAV_ITEMS = (
        "Home",
        "QP Builder",
        "My QP",
        "Create",
        "Repository",
        "Sets",
        "Support",
        "Settings",
    )

    # --- Assessment Builder shell ---
    BUILDER_HEADING = (By.XPATH, "//h1[normalize-space()='Assessment Builder']")
    # Scoped to the heading element: an unscoped normalize-space() match also
    # returns each wrapping ancestor, so "1 present" would not mean the heading.
    ASSESSMENT_CONFIG_HEADING = (
        By.XPATH,
        "//*[self::h1 or self::h2 or self::h3][normalize-space()='Assessment Configuration']",
    )
    WORKFLOW_OVERVIEW_HEADING = (
        By.XPATH,
        "//*[self::h1 or self::h2 or self::h3][normalize-space()='Workflow Overview']",
    )
    MODE_TAB_LABELS = ("Manual Build", "Auto Generator")

    # The builder shows a different wizard depending on the mode: Manual Build
    # is a three-step flow, Auto Generator collapses Build Paper away.
    MANUAL_STEP_LABELS = ("Configure Meta Data", "Build Paper", "Preview & Publish")
    AUTO_STEP_LABELS = ("Configure Meta Data", "Preview & Publish")

    # Manual Build configuration form. Labels carry no asterisk here; the Auto
    # Generator spells the same fields with one, so the two sets are separate.
    MANUAL_CONFIG_LABELS = (
        "Paper Title",
        "Grade",
        "Subject",
        "Assessment Type",
        "Chapters",
        "Exam Duration (in Minutes)",
        "Total Marks",
        "No. of Sections",
        "Number of Sets",
        "General Instructions",
    )
    CFG_DURATION_INPUT = (By.ID, "cfg-duration")
    CFG_MARKS_INPUT = (By.ID, "cfg-marks")
    CFG_SECTIONS_INPUT = (By.ID, "cfg-sections")

    # Auto Generator configuration form.
    AUTO_CONFIG_LABELS = (
        "Paper Title*",
        "Grade*",
        "Subject*",
        "Assessment Type*",
        "Chapters*",
        "Exam Duration (in Minutes)*",
        "Number of Section*",
        "Total Marks*",
        "Number of Sets*",
        "Select Question Distribution*",
        "General Instructions",
    )
    GENERATION_LEVEL_HEADING = (
        By.XPATH,
        "//*[self::h2 or self::h3][normalize-space()='Choose Generation Level']",
    )
    GENERATION_LEVEL_SECTION = (
        By.XPATH,
        "//*[self::h3 or self::h4][normalize-space()='Section Level']",
    )
    GENERATION_LEVEL_ITEM = (
        By.XPATH,
        "//*[self::h3 or self::h4][normalize-space()='Item Level']",
    )
    QP_DETAILS_HEADING = (
        By.XPATH,
        "//*[self::h2 or self::h3][normalize-space()='Question Paper Details']",
    )
    DISTRIBUTION_SAME = (
        By.XPATH,
        "//*[not(*)][normalize-space()='All sets contain the same questions']",
    )
    DISTRIBUTION_DIFFERENT = (
        By.XPATH,
        "//*[not(*)][normalize-space()='Each set contains different questions']",
    )
    AUTO_DURATION_INPUT = (By.ID, "auto-gen-exam-duration")
    AUTO_SECTIONS_INPUT = (By.ID, "auto-gen-number-of-section")
    AUTO_MARKS_INPUT = (By.ID, "auto-gen-total-marks")

    COMBOBOXES = (By.CSS_SELECTOR, "[role='combobox']")
    RICH_TEXT_EDITOR = (By.CSS_SELECTOR, "div.tiptap.ProseMirror")

    # --- My QP listing ---
    MY_QP_HEADING = (By.XPATH, "//h1[normalize-space()='My Question Paper']")
    MY_QP_SUBTITLE = (
        By.XPATH,
        "//*[not(*)][contains(normalize-space(),'Click any paper to open it')]",
    )
    CREATE_NEW_PAPER_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(),'Create New Paper')]",
    )
    MY_QP_SEARCH_INPUT = (By.CSS_SELECTOR, "input[placeholder='Search by ID, Title']")
    MY_QP_FILTER_LABELS = ("Type", "Subject", "Grade", "Status")
    MY_QP_FILTER_BUTTONS = (By.CSS_SELECTOR, "button[class*='_filterBtn_']")
    MY_QP_TABLE = (By.TAG_NAME, "table")
    MY_QP_TABLE_HEADERS = (By.XPATH, "//table//th")
    MY_QP_TABLE_ROWS = (By.XPATH, "//table/tbody/tr")
    MY_QP_COLUMNS = (
        "Question Paper ID",
        "Title",
        "Type",
        "Subject",
        "Grade",
        "No. of Sets",
        "Marks per set",
        "No. of Sections",
        "Duration",
        "Created On",
        "Published Date",
        "Status",
        "Delete",
    )
    MY_QP_DELETE_BUTTONS = (By.CSS_SELECTOR, "button[class*='_deleteIconButton_']")
    # A published paper's delete control is disabled and says so — the listing's
    # own statement of the "published papers are immutable" rule.
    MY_QP_DELETE_BLOCKED = (
        By.CSS_SELECTOR,
        "button[aria-label='Published question papers cannot be deleted']",
    )
    ROWS_PER_PAGE = (By.CSS_SELECTOR, "[role='combobox']")
    PREV_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='Previous page']")
    NEXT_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='Next page']")

    # --- Paper preview ---
    PREVIEW_PAPER_HEADING = (By.CSS_SELECTOR, "[class*='_paperHeading_']")
    # Matched on its component class, not its text: the heading is styled
    # `text-transform: uppercase`, so it reads GENERAL INSTRUCTIONS on screen
    # while the DOM — and therefore XPath — only ever sees "General
    # Instructions". A text locator taken from the rendered page never matches.
    PREVIEW_INSTRUCTIONS_HEADING = (
        By.CSS_SELECTOR,
        "[class*='_instructionsHeading_']",
    )
    PREVIEW_SECTION_TITLES = (By.CSS_SELECTOR, "[class*='_sectionTitle_']")
    PREVIEW_METRIC_CHIPS = (By.CSS_SELECTOR, "[class*='_metricChip_']")
    PREVIEW_BACK_BUTTON = (By.CSS_SELECTOR, "button[class*='_backButton_']")
    PREVIEW_PRINT_BUTTON = (By.XPATH, "//button[normalize-space()='Print']")
    PREVIEW_DOWNLOAD_BUTTON = (By.XPATH, "//button[normalize-space()='Download']")
    PREVIEW_DOWNLOAD_WITH_KEY_BUTTON = (
        By.XPATH,
        "//button[normalize-space()='Download with Answer Key']",
    )
    PREVIEW_SUMMARY_FIELDS = (
        "Subject",
        "Subject Code",
        "Class",
        "Assessment Type",
        "Total Marks",
        "Time Allowed",
    )
    PREVIEW_END_MARKER = (
        By.XPATH,
        "//*[not(*)][contains(normalize-space(),'End of Question Paper')]",
    )

    # ------------------------------------------------------------------
    # Survey readers
    # ------------------------------------------------------------------

    def is_visible(self, locator, timeout=5):
        return self.is_element_visible_quick(locator, timeout)

    def count_visible(self, locator):
        """How many matches are actually on screen — 0 when none are."""
        count = 0
        for element in self.driver.find_elements(*locator):
            try:
                if element.is_displayed():
                    count += 1
            except Exception:  # noqa: BLE001 - a stale match is simply not visible
                continue
        return count

    @staticmethod
    def xpath_literal_text(value):
        """Quote a label for use inside an XPath expression.

        Field labels here are safe today, but quoting them keeps a future label
        containing an apostrophe from raising InvalidSelectorException out of
        the reader instead of recording one absent element.
        """
        text = str(value)
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        parts = "', \"'\", '".join(text.split("'"))
        return f"concat('{parts}')"

    @classmethod
    def label_locator(cls, label):
        return (By.XPATH, f"//label[normalize-space()={cls.xpath_literal_text(label)}]")

    @classmethod
    def tab_locator(cls, label):
        return (
            By.XPATH,
            f"//*[@role='tab'][normalize-space()={cls.xpath_literal_text(label)}]",
        )

    @classmethod
    def wizard_step_locator(cls, label):
        return (
            By.XPATH,
            "//*[contains(@class,'stepItem')]"
            f"[contains(normalize-space(),{cls.xpath_literal_text(label)})]",
        )

    @classmethod
    def filter_button_locator(cls, label):
        return (
            By.XPATH,
            "//button[contains(@class,'_filterBtn_')]"
            f"[normalize-space()={cls.xpath_literal_text(label)}]",
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

    def missing_mode_tabs(self):
        return self.missing_from(self.MODE_TAB_LABELS, self.tab_locator)

    def missing_nav_items(self):
        return self.missing_from(
            self.NAV_ITEMS,
            lambda label: (
                By.XPATH,
                "//button[contains(@class,'menu-button')]"
                f"[contains(normalize-space(),{self.xpath_literal_text(label)})]",
            ),
        )

    def missing_my_qp_filters(self):
        return self.missing_from(self.MY_QP_FILTER_LABELS, self.filter_button_locator)

    def is_tab_active(self, label):
        try:
            state = self.driver.find_element(*self.tab_locator(label)).get_attribute(
                "data-state"
            )
        except Exception:  # noqa: BLE001 - an unreadable tab is not the active one
            return False
        return state == "active"

    def switch_mode_tab(self, label, timeout=20):
        """Activate a builder mode tab and wait for it to report itself active."""
        self.wait_utils.until_clickable(self.tab_locator(label), timeout=timeout).click()
        try:
            self.wait_utils.until_condition(
                lambda driver: self.is_tab_active(label), timeout=timeout
            )
        except TimeoutException:
            return False
        return True

    def get_table_headers(self, locator=None):
        headers = []
        for element in self.driver.find_elements(*(locator or self.MY_QP_TABLE_HEADERS)):
            try:
                text = element.text.strip()
            except Exception:  # noqa: BLE001
                continue
            if text:
                headers.append(text)
        return headers

    def missing_my_qp_columns(self):
        headers = [header.casefold() for header in self.get_table_headers()]
        return [
            column for column in self.MY_QP_COLUMNS if column.casefold() not in headers
        ]

    def get_my_qp_row_count(self):
        return len(self.driver.find_elements(*self.MY_QP_TABLE_ROWS))

    def get_my_qp_paper_ids(self):
        ids = []
        for element in self.driver.find_elements(
            By.CSS_SELECTOR, "button[class*='_paperId_']"
        ):
            try:
                text = element.text.strip()
            except Exception:  # noqa: BLE001
                continue
            if text:
                ids.append(text)
        return ids

    # The listing clears its rows while a debounced search is in flight, so a
    # stability poll started immediately sees the empty intermediate state twice
    # and returns it — reporting "no matches" for a query that does match. Hold
    # for the debounce before believing any result set.
    MY_QP_SEARCH_DEBOUNCE_SECONDS = 1.5

    def _wait_for_my_qp_rows_to_settle(self, timeout=15, settle_polls=2):
        """Return the paper IDs once the listing has stopped changing."""
        sleep(self.MY_QP_SEARCH_DEBOUNCE_SECONDS)
        previous = None
        stable = 0
        deadline = monotonic() + timeout
        while True:
            current = self.get_my_qp_paper_ids()
            stable = stable + 1 if current == previous else 0
            previous = current
            if stable >= settle_polls or monotonic() >= deadline:
                return current
            sleep(0.4)

    def search_my_qp(self, query):
        """Type into the My QP search box and return the settled paper IDs."""
        box = self.wait_utils.until_visible(self.MY_QP_SEARCH_INPUT, timeout=15)
        box.clear()
        box.send_keys(Keys.CONTROL, "a")
        box.send_keys(Keys.DELETE)
        box.send_keys(query)
        return self._wait_for_my_qp_rows_to_settle()

    def clear_my_qp_search(self):
        """Empty the search box and return the settled, unfiltered paper IDs."""
        box = self.wait_utils.until_visible(self.MY_QP_SEARCH_INPUT, timeout=15)
        box.send_keys(Keys.CONTROL, "a")
        box.send_keys(Keys.DELETE)
        return self._wait_for_my_qp_rows_to_settle()

    def get_header_chip_texts(self):
        """The preview toolbar's duration / marks / questions chips.

        get_header_metadata_text() matches every element whose text contains
        'Marks' or 'Questions', which on a question paper is essentially the
        whole document — so `'marks' in get_header_metadata_text()` is true of
        any paper page and asserts nothing. These are the chips themselves.
        """
        texts = []
        for element in self.driver.find_elements(*self.PREVIEW_METRIC_CHIPS):
            try:
                text = element.text.strip()
            except Exception:  # noqa: BLE001
                continue
            if text:
                texts.append(text)
        return texts

    def missing_preview_summary_fields(self, summary=None):
        summary = summary if summary is not None else self.get_paper_summary_metadata()
        return [field for field in self.PREVIEW_SUMMARY_FIELDS if field not in summary]

    def open(self):
        self.wait_utils.until_clickable(self.QP_BUILDER_NAV, timeout=20).click()
        self.wait_utils.until_condition(
            lambda driver: (
                "assessment configuration"
                in driver.find_element(By.TAG_NAME, "body").text.casefold()
                and "loading assessment builder"
                not in driver.find_element(By.TAG_NAME, "body").text.casefold()
            ),
            timeout=30,
        )

    def body_text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def body_text_casefold(self):
        return self.body_text().casefold()

    def get_creation_modes(self):
        text = self.body_text().casefold()
        modes = set()
        if "manual build" in text or "manual mode" in text:
            modes.add("Manual")
        if "auto generator" in text or "automated mode" in text:
            modes.add("Automated")
        if "hybrid" in text:
            modes.add("Hybrid")
        return modes

    def open_auto_generator(self):
        tab = self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//button[contains(normalize-space(),'Auto Generator')]"
                " | //*[@role='tab' and contains(normalize-space(),'Auto Generator')]",
            ),
            timeout=20,
        )
        tab.click()
        self.wait_utils.until_condition(
            lambda driver: (
                "auto" in driver.find_element(By.TAG_NAME, "body").text.casefold()
                and "generate" in driver.find_element(By.TAG_NAME, "body").text.casefold()
                and "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold()
            ),
            timeout=30,
        )

    def click_continue(self):
        self.driver.execute_script("window.scrollTo(0, 0);")
        button = self.wait_utils.until_condition(
            lambda driver: next(
                (
                    candidate
                    for candidate in driver.find_elements(*self.CONTINUE_BUTTON)
                    if candidate.is_displayed() and candidate.is_enabled()
                ),
                False,
            ),
            timeout=15,
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", button
        )
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        try:
            self.driver.execute_script("arguments[0].click();", button)
        except Exception:
            clicked = self.driver.execute_script(
                """
                const button = Array.from(document.querySelectorAll('button'))
                    .find(candidate => candidate.offsetParent !== null
                        && !candidate.disabled
                        && /Continue|Confirm/i.test(candidate.innerText || ''));
                if (!button) return false;
                button.scrollIntoView({block: 'center'});
                button.click();
                return true;
                """
            )
            if not clicked:
                raise

    def is_still_on_configuration_step(self):
        text = self.body_text().casefold()
        return "configure meta data" in text and "assessment configuration" in text

    def get_validation_messages(self):
        return [
            element.text.strip()
            for element in self.driver.find_elements(
                By.XPATH,
                "//*[@role='alert' or contains(@class,'error') "
                "or contains(@class,'invalid')]",
            )
            if element.is_displayed() and element.text.strip()
        ]

    def select_first_available_option(self, label, occurrence=1):
        last_error = None
        for _ in range(5):
            try:
                self.close_open_popovers()
                control = self.find_control_near_label(
                    label, occurrence=occurrence, selector="button, [role='combobox']"
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", control
                )
                self.safe_click(control)
                option = self.wait_utils.until_condition(
                    lambda driver: next(
                        (
                            candidate
                            for candidate in driver.find_elements(
                                By.XPATH,
                                "//*[@role='option' or @cmdk-item]",
                            )
                            if candidate.is_displayed()
                            and candidate.is_enabled()
                            and (candidate.text or "").strip()
                        ),
                        False,
                    ),
                    timeout=15,
                )
                value = self.driver.execute_script(
                    "return (arguments[0].innerText || arguments[0].textContent || '').trim();",
                    option,
                )
                self.safe_click(option)
                self.close_open_popovers()
                return value
            except (StaleElementReferenceException, TimeoutException) as error:
                last_error = error
                self.close_open_popovers()
                self.pause_before_action()
        raise last_error

    def safe_click(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        try:
            element.click()
        except ElementClickInterceptedException:
            self.driver.execute_script("arguments[0].click();", element)

    def close_open_popovers(self):
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            return False
        return True

    NEAREST_CONTROL_FOR_LABEL_SCRIPT = """
        const label = arguments[0].trim().toLowerCase();
        const occurrence = arguments[1];
        const selector = arguments[2];
        const candidates = Array.from(document.querySelectorAll('*')).filter(el =>
            el.children.length === 0 &&
            (el.innerText || el.textContent || '').trim().toLowerCase() === label &&
            el.getClientRects().length > 0
        );
        const target = candidates[occurrence - 1];
        if (!target) return null;
        let container = target;
        for (let depth = 0; depth < 8 && container; depth++) {
            const match = container.querySelector(selector);
            if (match) return match;
            container = container.parentElement;
        }
        return null;
        """

    def find_control_near_label(self, label, occurrence=1, selector="input"):
        return self.wait_utils.until_condition(
            lambda driver: driver.execute_script(
                self.NEAREST_CONTROL_FOR_LABEL_SCRIPT, label, occurrence, selector
            ),
            timeout=15,
        )

    def fill_input_after_label(self, label, value, occurrence=1):
        field = self.find_control_near_label(
            label, occurrence=occurrence, selector="input:not([type='hidden'])"
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", field
        )
        self.driver.execute_script(
            """
            const field = arguments[0];
            const value = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(field, value);
            field.dispatchEvent(new Event('input', {bubbles: true}));
            field.dispatchEvent(new Event('change', {bubbles: true}));
            field.dispatchEvent(new Event('blur', {bubbles: true}));
            """,
            field,
            str(value),
        )

    def configure_assessment(
        self, select_all_chapters=False, total_marks=1, number_of_sections=1
    ):
        selections = {}
        for label in ("Paper Title", "Assessment Type", "Grade", "Subject"):
            selections[label] = self.select_first_available_option(label)
        try:
            if select_all_chapters:
                selections["Chapters"] = self.select_all_checkbox_option("Chapters")
            else:
                selections["Chapters"] = self.select_first_checkbox_option("Chapters")
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            selections["Chapters"] = "Not required"

        self.fill_input_after_label("Total Marks", str(total_marks))
        self.fill_input_after_label("No. of Sections", str(number_of_sections))
        editors = [
            editor
            for editor in self.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
            if editor.is_displayed()
        ]
        if editors:
            self.driver.execute_script(
                """
                arguments[0].innerHTML = '<p>Answer all questions. Show working where required.</p>';
                arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
                arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
                """,
                editors[0],
            )
        return selections

    def open_item_bank_for_configured_assessment(self):
        self.configure_assessment()
        self.continue_to_build_paper()

    def get_item_bank_filter_labels(self):
        text = self.body_text()
        labels = set()
        for label in (
            "Chapter",
            "Typology",
            "Marks",
            "Difficulty",
            "Bloom's Level",
            "Competency",
            "Learning Outcome",
        ):
            if label.casefold() in text.casefold():
                labels.add(label)
        return labels

    def search_item_bank(self, query="true"):
        search_input = self.wait_utils.until_condition(
            lambda driver: next(
                (
                    candidate
                    for candidate in driver.find_elements(
                        By.XPATH,
                        "//input[contains(@placeholder,'Search') and not(@disabled)]",
                    )
                    if candidate.is_displayed() and candidate.is_enabled()
                ),
                False,
            ),
            timeout=20,
        )
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        started = monotonic()
        search_input.send_keys(query)
        self.wait_utils.until_condition(
            lambda driver: (
                "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold()
                and search_input.get_attribute("value").casefold() == query.casefold()
            ),
            timeout=10,
        )
        return monotonic() - started

    def visible_item_bank_status_text(self):
        return self.body_text_casefold()

    def configure_auto_generator(
        self,
        total_marks=1,
        number_of_sections=1,
        number_of_sets=1,
        select_all_chapters=False,
    ):
        selections = {}
        for label in (
            "Paper Title*",
            "Grade*",
            "Subject*",
            "Assessment Type*",
        ):
            selections[label] = self.select_first_available_option(label)
        if select_all_chapters:
            selections["Chapters*"] = self.select_all_checkbox_option("Chapters*")
        else:
            selections["Chapters*"] = self.select_first_auto_chapter()
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        self.fill_input_after_label("Exam Duration (in Minutes)*", "30")
        self.fill_input_after_label("Number of Section*", str(number_of_sections))
        self.fill_input_after_label("Total Marks*", str(total_marks))
        selections["Number of Sets*"] = self.select_option_with_exact_text(
            "Number of Sets*", str(number_of_sets)
        )
        return selections

    def select_first_auto_chapter(self):
        return self.select_first_checkbox_option("Chapters*")

    def open_checkbox_control(self, label, occurrence=1):
        self.close_open_popovers()
        control = self.find_control_near_label(
            label, occurrence=occurrence, selector="button, [role='combobox']"
        )
        self.safe_click(control)
        return control

    def select_all_checkbox_option(self, label, occurrence=1):
        last_error = None
        for _ in range(3):
            try:
                self.open_checkbox_control(label, occurrence=occurrence)
                select_all_node = self.wait_utils.until_condition(
                    lambda driver: driver.execute_script(
                        """
                        const nodes = Array.from(document.querySelectorAll('*'));
                        return nodes.find(node =>
                            node.getClientRects().length > 0 &&
                            (node.innerText || node.textContent || '').trim() === 'Select All'
                        ) || null;
                        """
                    ),
                    timeout=30,
                )
                self.driver.execute_script("arguments[0].click();", select_all_node)
                # Selecting hundreds of checkboxes (e.g. Learning Outcome
                # lists) can take the UI a moment to render/commit.
                self.pause_before_action()
                self.close_open_popovers()
                return "All options"
            except TimeoutException as error:
                last_error = error
                self.close_open_popovers()
                self.pause_before_action()
        raise last_error

    def select_option_with_exact_text(self, label, text, occurrence=1):
        self.close_open_popovers()
        control = self.find_control_near_label(
            label, occurrence=occurrence, selector="button, [role='combobox']"
        )
        self.safe_click(control)
        option = self.wait_utils.until_condition(
            lambda driver: next(
                (
                    candidate
                    for candidate in driver.find_elements(
                        By.XPATH,
                        "//*[@role='option' or @cmdk-item]",
                    )
                    if candidate.is_displayed()
                    and candidate.is_enabled()
                    and (candidate.text or "").strip() == text
                ),
                False,
            ),
            timeout=15,
        )
        self.safe_click(option)
        self.close_open_popovers()
        return text

    def select_first_checkbox_option(self, label, occurrence=1):
        self.close_open_popovers()
        control = self.find_control_near_label(
            label, occurrence=occurrence, selector="button, [role='combobox']"
        )
        self.safe_click(control)
        chapter_option = self.wait_utils.until_condition(
            lambda driver: driver.execute_script(
                """
                const nodes = Array.from(document.querySelectorAll('*'));
                const selectAll = nodes.find(node =>
                    node.getClientRects().length > 0 &&
                    (node.innerText || node.textContent || '').trim() === 'Select All'
                );
                if (!selectAll) return null;
                const anchor = selectAll.getBoundingClientRect();
                const candidates = nodes.filter(node => {
                    const text = (node.innerText || node.textContent || '').trim();
                    const rect = node.getBoundingClientRect();
                    return node.getClientRects().length > 0 &&
                        text && text !== 'Select All' && text.length < 150 &&
                        rect.top >= anchor.bottom && rect.top < anchor.bottom + 160 &&
                        rect.left >= anchor.left - 40 && rect.left < anchor.left + 500;
                });
                candidates.sort((a, b) =>
                    a.getBoundingClientRect().top - b.getBoundingClientRect().top ||
                    a.getBoundingClientRect().width - b.getBoundingClientRect().width
                );
                return candidates[0] || null;
                """
            ),
            timeout=15,
        )
        label_text = self.driver.execute_script(
            """
            return (arguments[0].innerText || arguments[0].textContent || '').trim();
            """,
            chapter_option,
        )
        self.driver.execute_script("arguments[0].click();", chapter_option)
        self.close_open_popovers()
        return label_text or "First available chapter"

    def configure_auto_section_rules(self):
        rules = {}
        for label in (
            "CURRICULUM GOAL*",
            "COMPETENCY*",
            "LEARNING OUTCOME*",
            "ITEM TYPOLOGY*",
            "BLOOM'S LEVEL*",
            "DIFFICULTY LEVEL*",
        ):
            rules[label] = self.select_first_checkbox_option(label)
        self.fill_input_after_label("MARKS PER QUESTION*", "1")
        self.fill_input_after_label("NUMBER OF QUESTIONS*", "1")
        return rules

    def configure_auto_section_rules_for_sections(self, section_count, total_marks):
        """Fill each of the repeated per-section rule blocks (Number of
        Section* renders one rule block per section) rather than only the
        first one, so every section actually gets a typology/marks rule."""
        questions_per_section = max(1, total_marks // section_count)
        all_rules = []
        for section_index in range(1, section_count + 1):
            rules = {}
            for label in (
                "CURRICULUM GOAL*",
                "COMPETENCY*",
                "LEARNING OUTCOME*",
                "ITEM TYPOLOGY*",
                "BLOOM'S LEVEL*",
                "DIFFICULTY LEVEL*",
            ):
                rules[label] = self.select_all_checkbox_option(
                    label, occurrence=section_index
                )
            self.fill_input_after_label(
                "MARKS PER QUESTION*", "1", occurrence=section_index
            )
            self.fill_input_after_label(
                "NUMBER OF QUESTIONS*",
                str(questions_per_section),
                occurrence=section_index,
            )
            all_rules.append(rules)
        return all_rules

    def select_item_level(self):
        card = self.wait_utils.until_clickable(
            (By.XPATH, "//*[normalize-space()='Item Level']"),
            timeout=20,
        )
        self.safe_click(card)
        self.wait_utils.until_condition(
            lambda driver: "question paper details"
            in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=20,
        )

    def configure_item_level_generator(
        self,
        total_marks=1,
        number_of_sections=1,
        number_of_sets=1,
        select_all_chapters=False,
    ):
        """Item Level shares the same 'Question Paper Details' fields as
        Section Level (Paper Title/Grade/Subject/Assessment Type/Chapters/
        Duration/Number of Section/Total Marks/Number of Sets)."""
        return self.configure_auto_generator(
            total_marks=total_marks,
            number_of_sections=number_of_sections,
            number_of_sets=number_of_sets,
            select_all_chapters=select_all_chapters,
        )

    # Column header text repeats once per section (occurrence == section
    # index). Rather than trying to isolate a per-section DOM container (the
    # ancestor climb proved unreliable — it kept including every section) or
    # a fixed row-position index (breaks under viewport-driven layout shifts),
    # we anchor on the specific header instance for this column/section and
    # take the closest control below it, restricted to a short vertical
    # window so a control from a different section's row can't be mistaken
    # for this one's.
    FIND_TABLE_CELL_CONTROL_SCRIPT = """
        const columnLabel = arguments[0].trim().toUpperCase();
        const occurrence = arguments[1];
        const selector = arguments[2];
        const widthMin = arguments[3];
        const headers = Array.from(document.querySelectorAll('*')).filter(el =>
            el.getClientRects().length > 0 &&
            (el.innerText || '').trim().toUpperCase() === columnLabel
        );
        const header = headers[occurrence - 1];
        if (!header) return null;
        const hRect = header.getBoundingClientRect();
        const hCenter = hRect.left + hRect.width / 2;
        const candidates = Array.from(document.querySelectorAll(selector)).filter(el => {
            const r = el.getBoundingClientRect();
            return r.width >= widthMin && r.top > hRect.bottom && r.top < hRect.bottom + 250;
        });
        let best = null;
        let bestDistance = Infinity;
        for (const el of candidates) {
            const r = el.getBoundingClientRect();
            const distance = Math.abs((r.left + r.width / 2) - hCenter);
            if (distance < bestDistance) {
                bestDistance = distance;
                best = el;
            }
        }
        return best;
        """

    def find_table_cell_control(self, section_occurrence, column_label, selector, width_min=0):
        return self.wait_utils.until_condition(
            lambda driver: driver.execute_script(
                self.FIND_TABLE_CELL_CONTROL_SCRIPT,
                column_label,
                section_occurrence,
                selector,
                width_min,
            ),
            timeout=15,
        )

    def fill_table_cell_input(self, section_occurrence, column_label, value):
        # Restrict to type=number: the section name field (e.g. "Section A")
        # is itself an editable text input and would otherwise be picked up
        # as a false match.
        field = self.find_table_cell_control(
            section_occurrence, column_label, "input[type='number']"
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", field
        )
        self.driver.execute_script(
            """
            const field = arguments[0];
            const value = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(field, value);
            field.dispatchEvent(new Event('input', {bubbles: true}));
            field.dispatchEvent(new Event('change', {bubbles: true}));
            field.dispatchEvent(new Event('blur', {bubbles: true}));
            """,
            field,
            str(value),
        )

    def _open_table_cell_dropdown(self, section_occurrence, column_label):
        control = self.find_table_cell_control(
            section_occurrence, column_label, "button, [role='combobox']", width_min=60
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", control
        )
        self.safe_click(control)

    def select_all_in_table_cell(self, section_occurrence, column_label):
        """Select-all when the cell's dropdown offers a 'Select All' checkbox
        option; otherwise (e.g. a plain single-select dropdown) fall back to
        picking the first available option."""
        last_error = None
        for _ in range(3):
            try:
                self.close_open_popovers()
                self._open_table_cell_dropdown(section_occurrence, column_label)
                outcome = self.wait_utils.until_condition(
                    lambda driver: driver.execute_script(
                        """
                        const nodes = Array.from(document.querySelectorAll('*'))
                            .filter(node => node.getClientRects().length > 0);
                        const selectAll = nodes.find(node =>
                            (node.innerText || node.textContent || '').trim() === 'Select All'
                        );
                        if (selectAll) return {type: 'select-all', node: selectAll};
                        const option = nodes.find(node =>
                            (node.getAttribute('role') === 'option' || node.hasAttribute('cmdk-item')) &&
                            (node.innerText || node.textContent || '').trim()
                        );
                        if (option) return {type: 'option', node: option};
                        return null;
                        """
                    ),
                    timeout=15,
                )
                self.driver.execute_script("arguments[0].click();", outcome["node"])
                self.pause_before_action()
                self.close_open_popovers()
                return "All options" if outcome["type"] == "select-all" else "First available"
            except TimeoutException as error:
                last_error = error
                self.close_open_popovers()
                self.pause_before_action()
        raise last_error

    def select_first_in_table_cell(self, section_occurrence, column_label):
        """Pick the first available option in a single-select cell dropdown
        (no 'Select All' checkbox)."""
        last_error = None
        for _ in range(3):
            try:
                self.close_open_popovers()
                self._open_table_cell_dropdown(section_occurrence, column_label)
                option = self.wait_utils.until_condition(
                    lambda driver: next(
                        (
                            candidate
                            for candidate in driver.find_elements(
                                By.XPATH, "//*[@role='option' or @cmdk-item]"
                            )
                            if candidate.is_displayed()
                            and candidate.is_enabled()
                            and (candidate.text or "").strip()
                        ),
                        False,
                    ),
                    timeout=15,
                )
                value = self.driver.execute_script(
                    "return (arguments[0].innerText || arguments[0].textContent || '').trim();",
                    option,
                )
                self.safe_click(option)
                self.close_open_popovers()
                return value
            except TimeoutException as error:
                last_error = error
                self.close_open_popovers()
                self.pause_before_action()
        raise last_error

    def configure_item_level_rows(self, section_configs):
        """Fill the single item-typology row rendered per section in Item
        Level mode. `section_configs` is a list of
        {"number_of_items": int, "marks_per_item": int} dicts, one per
        section, applied in order (Section A, Section B, ...).

        All six rule dropdowns use 'Select All' (Difficulty/Competency turned
        out to be the same checkbox-list widget as the others — there's no
        distinct single-select variant — so select_all_in_table_cell's
        fallback-to-first-option path is what actually applies there when
        needed).
        """
        select_all_columns = (
            "ITEM TYPOLOGY*",
            "DIFFICULTY*",
            "BLOOM'S LEVEL*",
            "CURRICULAR GOAL*",
            "COMPETENCY*",
            "LEARNING OUTCOME*",
        )
        all_rows = []
        for section_index, config in enumerate(section_configs, start=1):
            row = {}
            for label in select_all_columns:
                row[label] = self.select_all_in_table_cell(section_index, label)
            self.fill_table_cell_input(
                section_index, "NUMBER OF ITEMS*", str(config["number_of_items"])
            )
            self.fill_table_cell_input(
                section_index, "MARKS PER ITEM*", str(config["marks_per_item"])
            )
            all_rows.append(row)
        return all_rows

    def generate_auto_paper(self):
        generate = self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//button[contains(normalize-space(),'Generate Paper')]",
            ),
            timeout=20,
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", generate
        )
        started = monotonic()
        self.driver.execute_script("arguments[0].click();", generate)
        try:
            self.wait_utils.until_condition(
                lambda driver: (
                    "select set to preview"
                    in driver.find_element(By.TAG_NAME, "body").text.casefold()
                    and "select metadata"
                    not in driver.find_element(By.TAG_NAME, "body").text.casefold()
                ),
                timeout=30,
            )
        except TimeoutException as error:
            messages = [
                element.text.strip()
                for element in self.driver.find_elements(
                    By.XPATH,
                    "//*[@role='alert' or @role='status' or contains(@class,'toast')]",
                )
                if element.is_displayed() and element.text.strip()
            ]
            raise AssertionError(
                "Auto Generator submitted the configuration but did not open "
                f"the generated-paper preview. Visible messages: {messages}"
            ) from error
        return monotonic() - started

    def continue_to_build_paper(self):
        self.click_continue()
        self.wait_utils.until_condition(
            lambda driver: all(
                token in driver.find_element(By.TAG_NAME, "body").text.casefold()
                for token in ("item bank", "question paper")
            ),
            timeout=45,
        )

    def wait_for_item_bank_ready(self):
        """Wait for the Item Bank panel to finish loading and confirm it
        actually has published questions for the chosen grade/subject."""
        self.wait_utils.until_condition(
            lambda driver: "loading" not in driver.find_element(
                By.TAG_NAME, "body"
            ).text.casefold(),
            timeout=45,
        )
        try:
            self.wait_utils.until_condition(
                lambda driver: "no published questions found"
                not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
                timeout=30,
            )
        except TimeoutException as error:
            raise AssertionError(
                "Item Bank reported no published questions for the selected "
                "grade/subject/chapter combination."
            ) from error

    def add_first_available_item(self):
        self.wait_for_item_bank_ready()
        self.remove_selected_question_paper_items()
        self.wait_for_item_bank_to_render()
        # Each Item Bank card carries an icon-only "Add to section" button
        # (aria-label), which opens a section picker. There is no visible
        # "Add" text to match on.
        add_button = self.wait_utils.until_clickable(
            (By.XPATH, "(//button[@aria-label='Add to section'])[1]"),
            timeout=30,
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", add_button
        )
        self.safe_click(add_button)
        section_option = self.wait_utils.until_condition(
            lambda driver: next(
                (
                    candidate
                    for candidate in driver.find_elements(
                        By.XPATH,
                        "//*[@role='option' or @role='menuitem' or @cmdk-item]"
                        "[contains(normalize-space(),'Section A')]",
                    )
                    if candidate.is_displayed()
                ),
                False,
            ),
            timeout=10,
        )
        self.driver.execute_script("arguments[0].click();", section_option)
        self.wait_utils.until_condition(
            lambda driver: "0 items" not in driver.find_element(
                By.TAG_NAME, "body"
            ).text.casefold(),
            timeout=20,
        )
        self.wait_for_add_to_section_menu_to_close()

    def get_marks_allocation(self):
        """Read the 'Marks Allocated vs Target' banner as (allocated, target)."""
        return self.driver.execute_script(
            """
            const node = Array.from(document.querySelectorAll('*'))
                .filter(el => el.getClientRects().length > 0)
                .map(el => (el.innerText || '').trim())
                .find(text => /^\\d+\\s*\\/\\s*\\d+\\s*M$/.test(text));
            if (!node) return null;
            const [allocated, target] = node.match(/\\d+/g).map(Number);
            return [allocated, target];
            """
        )

    ITEM_BANK_ADD_BUTTON_SELECTOR = "button[aria-label='Add to section']"

    # Returns {index, text, marks} rather than the element itself: the Item
    # Bank re-renders after every add, so an element handle captured here
    # goes stale. The caller re-resolves the button by index immediately
    # before clicking.
    FIND_ADD_BUTTON_WITHIN_MARKS_SCRIPT = """
        const remaining = arguments[0];
        const used = new Set(arguments[1]);
        const buttons = Array.from(
            document.querySelectorAll("button[aria-label='Add to section']")
        ).filter(button => button.getClientRects().length > 0);
        for (let index = 0; index < buttons.length; index++) {
            // Climb to the largest ancestor that still wraps only THIS
            // card's add button — climbing by "contains some NM text"
            // instead would stop at a shared container and read another
            // item's marks badge.
            let card = buttons[index];
            while (
                card.parentElement &&
                card.parentElement.querySelectorAll(
                    "button[aria-label='Add to section']"
                ).length === 1
            ) {
                card = card.parentElement;
            }
            const text = (card.innerText || '').replace(/\\s+/g, ' ').trim();
            // Added items stay listed in the Item Bank, and re-adding one is
            // a no-op, so skip anything already placed in the paper.
            if (used.has(text)) continue;
            const match = text.match(/\\b(\\d+)M\\b/);
            if (!match) continue;
            if (Number(match[1]) > remaining) continue;
            return {index: index, text: text, marks: Number(match[1])};
        }
        return null;
        """

    def wait_for_add_to_section_menu_to_close(self, timeout=5):
        """Picking a section does not always dismiss the "Add to section"
        menu. Left open, the next add re-uses that stale menu instead of
        opening a fresh one for the newly chosen card, so no further item is
        ever added. Escape it before continuing."""
        def menu_is_gone(driver):
            return not driver.execute_script(
                """
                return Array.from(document.querySelectorAll("[role='menu']"))
                    .some(element => element.getClientRects().length > 0 &&
                        /ADD TO SECTION/i.test(element.innerText || ''));
                """
            )

        for _ in range(3):
            try:
                return self.wait_utils.until_condition(menu_is_gone, timeout=timeout)
            except TimeoutException:
                self.close_open_popovers()
        return menu_is_gone(self.driver)

    def wait_for_item_bank_to_render(self, timeout=30):
        """The Item Bank list re-renders after every add and briefly drops to
        zero cards. Probing during that window finds no add buttons (and
        grabbing one mid-render yields a detached node whose click never
        opens the section picker), so wait for cards to be present again."""
        return self.wait_utils.until_condition(
            lambda driver: driver.execute_script(
                "return document.querySelectorAll("
                f"{self.ITEM_BANK_ADD_BUTTON_SELECTOR!r}).length > 0;"
            ),
            timeout=timeout,
        )

    def add_one_item_within_marks(self, remaining, used_cards=()):
        """Add a single Item Bank item worth <= `remaining` marks to Section A,
        skipping any card in `used_cards`. Returns the added card's text, or
        None when no eligible item remains."""
        for _ in range(3):
            self.close_open_popovers()
            try:
                self.wait_for_item_bank_to_render()
            except TimeoutException:
                return None
            candidate = self.driver.execute_script(
                self.FIND_ADD_BUTTON_WITHIN_MARKS_SCRIPT, remaining, list(used_cards)
            )
            if not candidate:
                return None
            try:
                buttons = [
                    button
                    for button in self.driver.find_elements(
                        By.CSS_SELECTOR, self.ITEM_BANK_ADD_BUTTON_SELECTOR
                    )
                    if button.is_displayed()
                ]
                add_button = buttons[candidate["index"]]
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", add_button
                )
                self.safe_click(add_button)
                section_option = self.wait_utils.until_condition(
                    lambda driver: next(
                        (
                            candidate
                            for candidate in driver.find_elements(
                                By.XPATH,
                                "//*[@role='option' or @role='menuitem' or @cmdk-item]"
                                "[contains(normalize-space(),'Section A')]",
                            )
                            if candidate.is_displayed()
                        ),
                        False,
                    ),
                    timeout=10,
                )
                self.driver.execute_script("arguments[0].click();", section_option)
                self.wait_for_add_to_section_menu_to_close()
                self.pause_before_action()
                return candidate["text"]
            except (
                TimeoutException,
                StaleElementReferenceException,
                IndexError,
            ):
                # Clicked a card that the re-render detached underneath us;
                # dismiss any half-open popover and pick a fresh one.
                self.close_open_popovers()
                self.pause_before_action()
        return None

    def add_items_until_marks_target_met(self, max_items=30):
        """Manual Build gates 'Continue to Confirm' until allocated marks
        equal the configured target, so a single item is rarely enough. Fills
        the paper by adding Item Bank items whose marks fit in the remaining
        budget (e.g. 1- and 2-mark questions to reach 10) until the target is
        met exactly. Returns the final (allocated, target)."""
        self.wait_for_item_bank_ready()
        self.remove_selected_question_paper_items()
        used_cards = []
        for _ in range(max_items):
            allocation = self.get_marks_allocation()
            if not allocation:
                return None
            allocated, target = allocation
            if allocated >= target:
                return allocation
            added_card = self.add_one_item_within_marks(
                target - allocated, used_cards
            )
            if not added_card:
                return self.get_marks_allocation()
            used_cards.append(added_card)
            # Guard against a click that silently did not register, so the
            # loop cannot spin for its full budget making no progress.
            try:
                self.wait_utils.until_condition(
                    lambda _: (self.get_marks_allocation() or [allocated])[0] > allocated,
                    timeout=10,
                )
            except TimeoutException:
                return self.get_marks_allocation()
        return self.get_marks_allocation()

    def remove_selected_question_paper_items(self):
        for _ in range(10):
            removed = self.driver.execute_script(
                """
                const cards = Array.from(document.querySelectorAll('*')).filter(node => {
                    const text = (node.innerText || '').trim();
                    const rect = node.getBoundingClientRect();
                    return rect.width > 100
                        && rect.height > 30
                        && /True or False|Multiple Choice|Short Answer|\\b\\d+M\\b/i.test(text)
                        && node.querySelector('button')
                        && text.length < 500;
                });
                cards.sort((a, b) => a.getBoundingClientRect().width - b.getBoundingClientRect().width);
                const card = cards[0];
                if (!card) return false;
                const buttons = Array.from(card.querySelectorAll('button'))
                    .filter(button => button.offsetParent !== null);
                const deleteButton = buttons.find(button =>
                    /delete|remove|trash/i.test(button.getAttribute('aria-label') || button.title || button.innerText || '')
                ) || buttons[buttons.length - 1];
                if (!deleteButton) return false;
                deleteButton.click();
                return true;
                """
            )
            if not removed:
                return
            self.confirm_if_prompted()
            self.pause_before_action()

    def confirm_if_prompted(self):
        for locator in (
            (By.XPATH, "//*[@role='dialog']//button[contains(normalize-space(),'Confirm') or contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove') or contains(normalize-space(),'Yes')]"),
            (By.XPATH, "//button[contains(normalize-space(),'Confirm') or contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove') or contains(normalize-space(),'Yes')]"),
        ):
            try:
                button = self.wait_utils.until_clickable(locator, timeout=2)
                self.driver.execute_script("arguments[0].click();", button)
                return True
            except Exception:
                continue
        return False

    def continue_to_preview(self):
        self.click_continue()
        self.wait_utils.until_condition(
            lambda driver: (
                (
                    "preview" in driver.find_element(By.TAG_NAME, "body").text.casefold()
                    or "confirm" in driver.find_element(By.TAG_NAME, "body").text.casefold()
                    or any(
                        button.is_displayed()
                        for button in driver.find_elements(
                            By.XPATH,
                            "//button[contains(normalize-space(),'Finalise') "
                            "or contains(normalize-space(),'Publish') "
                            "or contains(normalize-space(),'Save')]",
                        )
                    )
                )
                and "item bank" not in driver.find_element(By.TAG_NAME, "body").text.casefold()
            ),
            timeout=45,
        )

    def finalise_or_publish(self):
        button = self.wait_utils.until_condition(
            lambda driver: next(
                (
                    candidate
                    for candidate in driver.find_elements(
                        By.XPATH,
                        "//button[contains(normalize-space(),'Finalise') "
                        "or contains(normalize-space(),'Publish') "
                        "or contains(normalize-space(),'Save')]",
                    )
                    if candidate.is_displayed() and candidate.is_enabled()
                ),
                False,
            ),
            timeout=30,
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", button
        )
        button.click()
        confirm_buttons = [
            candidate
            for candidate in self.driver.find_elements(
                By.XPATH,
                "//*[@role='dialog']//button[contains(normalize-space(),'Confirm') "
                "or contains(normalize-space(),'Publish') "
                "or contains(normalize-space(),'Finalise')]",
            )
            if candidate.is_displayed() and candidate.is_enabled()
        ]
        if confirm_buttons:
            confirm_buttons[-1].click()
        self.wait_utils.until_condition(
            lambda driver: "published successfully"
            in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=30,
        )
        for locator in (
            (By.XPATH, "//*[@role='dialog']//button[contains(normalize-space(),'Close')]"),
            (By.XPATH, "//button[contains(normalize-space(),'Close')]"),
        ):
            try:
                close_button = self.wait_utils.until_clickable(locator, timeout=3)
                self.driver.execute_script("arguments[0].click();", close_button)
                break
            except Exception:
                continue

    def open_my_qp(self):
        nav = self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//*[self::button or self::a][normalize-space()='My QP' "
                "or .//*[normalize-space()='My QP']]",
            ),
            timeout=20,
        )
        nav.click()
        self.wait_utils.until_condition(
            lambda driver: "my qp"
            in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=30,
        )
        self.wait_utils.until_condition(
            lambda driver: "loading"
            not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=30,
        )

    def open_new_paper(self):
        """Navigating to 'QP Builder' directly can resume whatever draft was
        last left in progress (e.g. an abandoned/never-published one from an
        earlier run), pre-filling metadata with stale values. Going via My QP
        -> 'Create New Paper' guarantees a genuinely blank Assessment
        Configuration form."""
        self.open_my_qp()
        create_button = self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//button[contains(normalize-space(),'Create New Paper')]",
            ),
            timeout=20,
        )
        create_button.click()
        self.wait_utils.until_condition(
            lambda driver: (
                "assessment configuration"
                in driver.find_element(By.TAG_NAME, "body").text.casefold()
                and "loading assessment builder"
                not in driver.find_element(By.TAG_NAME, "body").text.casefold()
            ),
            timeout=30,
        )

    def open_first_qp_preview(self):
        """The My QP list has no explicit 'Preview' button per row — the page
        subtitle says 'Click any paper to open it', so click the first (most
        recently created) data row of the table."""
        row = self.wait_utils.until_condition(
            lambda driver: driver.execute_script(
                """
                const rows = Array.from(document.querySelectorAll('tr')).filter(row =>
                    row.querySelector('td') && row.getClientRects().length > 0
                );
                return rows[0] || null;
                """
            ),
            timeout=20,
        )
        self.safe_click(row)
        # Wait on the paper's own metadata table, which every published
        # preview renders. The "Select Set" tab bar only appears for
        # multi-set papers, so a manual single-set paper would never match it.
        self.wait_utils.until_condition(
            lambda driver: "total marks:"
            in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=30,
        )
        # Let the preview panel (marks/questions/sets) finish rendering before
        # reading it back for verification.
        self.pause_before_action()
        self.wait_utils.until_condition(
            lambda driver: "loading"
            not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=20,
        )

    def get_paper_summary_metadata(self):
        """Parse the preview page's 'Label: Value' fields (Subject, Class,
        Total Marks, Assessment Type, Time Allowed, ...) into a dict."""
        pairs = self.driver.execute_script(
            """
            const pattern = /^[A-Za-z][A-Za-z ]*:\\s*\\S.*$/s;
            const cells = Array.from(document.querySelectorAll('*'))
                .filter(el => el.getClientRects().length > 0)
                .map(el => (el.innerText || '').trim())
                .filter(text => text && text.split('\\n').length <= 2 && pattern.test(text));
            return Array.from(new Set(cells));
            """
        )
        metadata = {}
        for pair in pairs:
            label, _, value = pair.partition(":")
            metadata[label.strip()] = " ".join(value.split())
        return metadata

    def get_section_headings(self):
        """Distinct 'Section A' / 'Section B' headings on the preview page
        (matched on exact short text so we don't also match the whole
        section container, whose text includes every question in it)."""
        headings = self.driver.execute_script(
            """
            const pattern = /^Section [A-Z0-9]+$/;
            const matches = Array.from(document.querySelectorAll('*'))
                .filter(el => el.getClientRects().length > 0)
                .map(el => (el.innerText || '').trim())
                .filter(text => pattern.test(text));
            return Array.from(new Set(matches));
            """
        )
        return headings

    def get_set_tab_labels(self):
        return [
            element.text.strip()
            for element in self.driver.find_elements(
                By.XPATH,
                "//*[self::button or @role='tab']"
                "[contains(translate(normalize-space(), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),"
                "'set ')]",
            )
            if element.is_displayed() and element.text.strip()
        ]

    def switch_to_set(self, label):
        tab = self.wait_utils.until_clickable(
            (
                By.XPATH,
                f"//*[self::button or @role='tab'][contains(normalize-space(),'{label}')]",
            ),
            timeout=15,
        )
        self.safe_click(tab)
        self.wait_utils.until_condition(
            lambda driver: "loading" not in driver.find_element(
                By.TAG_NAME, "body"
            ).text.casefold(),
            timeout=15,
        )

    def get_header_metadata_text(self):
        return " ".join(
            element.text.strip()
            for element in self.driver.find_elements(
                By.XPATH,
                "//*[contains(normalize-space(),'Marks') "
                "or contains(normalize-space(),'Questions')]",
            )
            if element.is_displayed() and element.text.strip()
        )

    def is_download_button_visible(self):
        return any(
            candidate.is_displayed()
            for candidate in self.driver.find_elements(
                By.XPATH, "//button[contains(normalize-space(),'Download')]"
            )
        )

    def click_back_from_preview(self):
        back_button = self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//button[contains(normalize-space(),'Back')]"
                " | //a[contains(normalize-space(),'Back')]",
            ),
            timeout=15,
        )
        self.safe_click(back_button)
        self.wait_utils.until_condition(
            lambda driver: "my qp"
            in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=20,
        )
