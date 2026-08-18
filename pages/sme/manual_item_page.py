import re
from time import monotonic, sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from pages.common.base_page import BasePage
from utilities.screenshot_utils import ScreenshotUtils


class ManualItemPage(BasePage):
    """SME manual item creation page.

    Locators are extracted and cleaned from the BlazeMeter Selenium YAML recording.
    Some generated CSS classes may change, so each important action has fallback locators.
    """

    # FR-IBMM-06 defines seven controlled manual typologies. The current dev
    # manual-creation UI additionally exposes Case Based Question, Source
    # Based Question, Assertion and Reasoning, FA Activity, and Free
    # Response as distinct, independently selectable typologies (not
    # aliases of one another).
    SUPPORTED_MANUAL_ITEM_TYPOLOGIES = (
        "Multiple Choice Question",
        "Fill in the Blank",
        "Match the Following",
        "True or False",
        "Very Short Answer Question",
        "Short Answer Question",
        "Long Answer Question",
        "Case Based Question",
        "Source Based Question",
        "Assertion and Reasoning",
        "FA Activity",
        "Free Response",
    )
    MANUAL_TYPOLOGY_OPTION_ALIASES = {
        "Multiple Choice Question": ("Multiple Choice Question", "MCQ"),
        "Fill in the Blank": (
            "Fill in the Blank",
            "Fill in the Blanks",
            "Fill in Blanks",
            "FIB",
        ),
        "Match the Following": ("Match the Following", "MTF"),
        "True or False": ("True or False", "True/False", "T/F"),
        "Very Short Answer Question": (
            "Very Short Answer Question",
            "Very Short Answer",
            "VSA",
            "VSAQ",
        ),
        "Short Answer Question": ("Short Answer Question", "Short Answer", "SAQ"),
        "Long Answer Question": (
            "Long Answer Question",
            "Long Answer",
            "Long Essay",
            "LAQ",
            "LEQ",
        ),
        "Case Based Question": (
            "Case Based Question",
            "Case Based Questions",
            "CBQ",
        ),
        # The dev UI now exposes "Source Based Question" as its own
        # dropdown entry, separate from "Case Based Question". Kept
        # distinct rather than aliased so both are independently tested.
        "Source Based Question": ("Source Based Question", "Source Based Questions", "SBQ"),
        "Assertion and Reasoning": (
            "Assertion and Reasoning",
            "Assertion & Reasoning",
            "A&R",
        ),
        "FA Activity": ("FA Activity", "Formative Assessment Activity"),
        "Free Response": ("Free Response", "FR"),
    }
    MANUAL_TYPOLOGY_UI_LABELS = {
        "True or False": "True/False",
        "Source Based Questions": "Case Based Question",
        "Fill in Blanks": "Fill in the Blank",
    }

    # Sidebar/menu icon used in recording for item creation area
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

    # Tab/button to switch to manual item creation
    MANUAL_ITEM_TAB_LOCATORS = [
        (By.XPATH, "//button[.//span[contains(normalize-space(),'Manual')]]"),
        (By.XPATH, "//button[contains(normalize-space(),'Manual')]"),
        (By.XPATH, "(//main//button[2])[1]"),
    ]

    # Newer builds label the editor with its visible field name ("Statement")
    # where older ones used the internal name ("itemContent"), so match either.
    ITEM_CONTENT_CONTAINER = (
        By.CSS_SELECTOR,
        "[aria-label='itemContent'], [aria-label='Statement']",
    )
    ITEM_CONTENT_EDITOR = (
        By.CSS_SELECTOR,
        "[aria-label='itemContent'] .tiptap, [aria-label='Statement'] .tiptap",
    )
    ITEM_CONTENT_PLACEHOLDER = (
        By.CSS_SELECTOR,
        "[aria-label='itemContent'] p, [aria-label='Statement'] p",
    )

    TRUE_ANSWER_LOCATORS = [
        (By.XPATH, "//*[normalize-space()='True']/ancestor::button[1]"),
        (By.XPATH, "//button[@type='button' and normalize-space()='True']"),
        (
            By.XPATH,
            "//button[contains(normalize-space(),'True') "
            "and not(contains(normalize-space(),'False'))]",
        ),
        (By.CSS_SELECTOR, "[role='radiogroup'] > button:nth-of-type(1)"),
        (By.CSS_SELECTOR, "button._trueFalseButton_1pry0_245"),
    ]

    FALSE_ANSWER_LOCATORS = [
        (By.XPATH, "//*[normalize-space()='False']/ancestor::button[1]"),
        (By.XPATH, "//button[@type='button' and normalize-space()='False']"),
        (
            By.XPATH,
            "//button[contains(normalize-space(),'False') "
            "and not(contains(normalize-space(),'True'))]",
        ),
        (By.CSS_SELECTOR, "[role='radiogroup'] > button:nth-of-type(2)"),
    ]

    EXPLANATION_EDITOR = (
        By.XPATH,
        "(//*[@contenteditable='true' and not(ancestor::*[contains(@style,'display: none')])])[last()]",
    )
    EXPLANATION_PLACEHOLDER = (
        By.CSS_SELECTOR,
        "[aria-label='explanation'] p, [aria-label='Explanation for the Answer'] p",
    )
    VISIBLE_RICH_TEXT_EDITORS = (
        By.XPATH,
        "//*[@contenteditable='true' and not(ancestor::*[contains(@style,'display: none')])]",
    )
    SHORT_TEXT_INPUTS = (
        By.XPATH,
        "//input[not(@type='hidden') and not(@disabled)] | //textarea[not(@disabled)]",
    )
    # Match the Following renders this as a <textarea>, not an <input>, so an
    # input-only locator skipped past it and landed on the rich-text toolbar's
    # hidden <input type="color">. Waiting for that to become visible timed out
    # with an empty message, and the fields after it were never filled.
    ANSWER_KEY_INPUT = (
        By.XPATH,
        "//*[contains(normalize-space(),'Correct Answer') or contains(normalize-space(),'Answer Key')]"
        "/following::*[(self::textarea or (self::input and not(@type='hidden') and not(@type='color')))"
        " and not(@disabled)][1]",
    )
    CORRECT_ANSWER_DROPDOWN = (
        By.XPATH,
        "//*[contains(normalize-space(),'Correct Answer') or contains(normalize-space(),'Answer Key')]"
        "/following::button[1]",
    )
    CORRECT_ANSWER_SELECT = (
        By.XPATH,
        "//*[contains(normalize-space(),'Correct Answer') or contains(normalize-space(),'Answer Key')]"
        "/following::select[.//option[@value='A']][1]",
    )
    EXPLANATION_BY_LABEL_EDITOR = (
        By.XPATH,
        "//*[contains(normalize-space(),'Explanation') or contains(normalize-space(),'Notes')]"
        "/following::*[@contenteditable='true'][1]",
    )
    EXTRA_SOURCE_SUBQUESTION_DELETE_BUTTONS = (
        By.XPATH,
        "//button[contains(@aria-label, 'Delete sub-question')]",
    )
    FIRST_CORRECT_OPTION_LOCATORS = [
        (By.XPATH, "(//*[@role='radio' or @type='radio' or @type='checkbox'])[1]"),
        (By.XPATH, "(//button[normalize-space()='A' or normalize-space()='(A)' or normalize-space()='Option A'])[1]"),
        (By.XPATH, "(//*[normalize-space()='A']/ancestor::*[self::button or self::label][1])[1]"),
    ]

    ADD_ITEM_LOCATORS = [
        (
            By.XPATH,
            "//button[@type='button' and contains(normalize-space(), 'Add Item') "
            "and not(contains(normalize-space(), 'Add Items'))]",
        ),
    ]
    CLEAR_FORM_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(), 'Clear Form')]"),
        (By.XPATH, "//button[contains(normalize-space(), 'Clear')]"),
    ]

    CONTINUE_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Continue')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Continue →')]"),
    ]

    CONTINUE_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(),'Continue')]",
    )

    SUBMIT_FOR_QAR_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Submit Set for QAR')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Submit')]"),
    ]

    QAR_SUCCESS_POPUP_LOCATORS = [
        (
            By.XPATH,
            "//*[contains(normalize-space(), 'QAR completed') "
            "and contains(normalize-space(), 'set(s) passed')]",
        ),
        (
            By.XPATH,
            "//*[@role='alert' or @role='status' or contains(@class, 'toast') "
            "or contains(@class, 'Toast') or contains(@class, 'notification') "
            "or contains(@data-sonner-toast, '')]"
            "[contains(normalize-space(), 'QAR') or contains(normalize-space(), 'success') "
            "or contains(normalize-space(), 'submitted') or contains(normalize-space(), 'Submit')]",
        ),
        (
            By.XPATH,
            "//*[contains(normalize-space(), 'submitted') "
            "or contains(normalize-space(), 'successfully') "
            "or contains(normalize-space(), 'Submit Set for QAR')]",
        ),
    ]

    SUCCESS_OR_LIST_INDICATOR = (
        By.XPATH,
        "//*[contains(normalize-space(), 'QAR Results') "
        "or contains(normalize-space(), 'Quality Assurance Review') "
        "or contains(normalize-space(), 'Item set submitted')]",
    )

    ADDED_ITEMS_HEADING = (By.XPATH, "//*[contains(normalize-space(),'Added Items (')]")
    REVIEW_ITEM_ID_FOR_QUESTION = (
        By.XPATH,
        '//tr[.//td[contains(normalize-space(), "{question_text}")]]/td[1]//*[self::a or self::button or self::span][normalize-space()][1]',
    )
    REVIEW_TABLE_ROWS = (By.XPATH, "//tbody/tr[.//td]")
    REVIEW_ROW_ITEM_ID = (By.XPATH, "./td[1]//*[self::a or self::button or self::span][normalize-space()][1]")

    # --- Manual authoring furniture -------------------------------------
    #
    # Locators used by the element-presence surveys rather than by the
    # authoring workflow, taken from a DOM census of the live manual tab.

    WORKSPACE_TITLE = (By.XPATH, "//h1[normalize-space()='Create New Item Set']")
    METADATA_HEADING = (By.XPATH, "//*[normalize-space()='Metadata Tags']")

    # Field labels as the form renders them, asterisk included — the mandatory
    # marker is part of the contract this screen advertises.
    METADATA_FIELD_LABELS = (
        "Grade *",
        "Subject *",
        "Chapter *",
        "Curricular Goal",
        "Competency *",
        "Learning Outcome (NCERT) *",
        "Bloom's Level *",
        "Item Typology *",
        "Marks *",
    )
    CONTENT_FIELD_LABELS = (
        "Item Content *",
        "Correct Answer / Answer Key *",
        "Explanation for the Answer *",
    )
    MANUAL_WIZARD_STEP_LABELS = ("Add Items", "Review & Tag Metadata", "Confirm & Submit")

    METADATA_DROPDOWNS = (By.CSS_SELECTOR, "[role='combobox']")
    CLEAR_FORM_BUTTON = (By.XPATH, "//button[normalize-space()='Clear Form']")
    # Exact text: a contains() here also matches the 'Add Items Manually' tab.
    ADD_ITEM_BUTTON = (By.XPATH, "//button[normalize-space()='Add Item']")

    # Rich-text editor toolbar. Checked as a group rather than button by
    # button: it carries ~40 controls, and an absent one costs a full timeout.
    EDITOR_TOOLBAR_BUTTONS = (By.CSS_SELECTOR, "button[class*='_btn_']")
    EDITOR_SURFACES = (By.CSS_SELECTOR, "div.tiptap.ProseMirror")
    ANSWER_KEY_TEXTBOX = (
        By.CSS_SELECTOR,
        "input[placeholder='Enter correct answer...']",
    )

    # Per-item row controls. Observed absent from the DOM entirely on arrival
    # even with items staged — they are revealed by interacting with an item
    # card — so surveys deliberately leave them out rather than record a gap
    # for a control the page is right not to be showing yet.
    ADDED_ITEM_EDIT_BUTTONS = (By.CSS_SELECTOR, "button[aria-label='Edit item']")
    ADDED_ITEM_DELETE_BUTTONS = (By.CSS_SELECTOR, "button[aria-label='Delete item']")
    ADDED_ITEM_ACCORDION_BUTTONS = (By.CSS_SELECTOR, "button[aria-label='Show answer']")

    # Application chrome. Duplicated from UploadItemFilePage rather than
    # inherited: both page objects extend BasePage directly, and a survey helper
    # reads these attributes *outside* ElementChecks' guard, so a page object
    # missing them raises AttributeError and takes the whole test down instead
    # of recording one absent element.
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
    SME_NAV_ITEMS = ("Home", "Repository", "Create", "Item", "Support", "Settings")

    # --- Manual authoring readers ---------------------------------------

    @classmethod
    def sme_nav_locator(cls, label):
        """Locate a sidebar destination by its visible label.

        Matched on the label <span>: each nav button also carries a
        visually-hidden tooltip span, so the button's textContent — what XPath
        normalize-space() reads — is tooltip and label run together
        ("DashboardHome"), and an exact match on the button never fires.
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

    @staticmethod
    def xpath_literal(value):
        """Quote a value for use inside an XPath expression.

        Several field labels contain an apostrophe ("Bloom's Level *"), which
        terminates a single-quoted XPath string early and raises
        InvalidSelectorException rather than simply not matching — so it fails
        the whole reader instead of recording one absent element.
        """
        text = str(value)
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        parts = "', \"'\", '".join(text.split("'"))
        return f"concat('{parts}')"

    @classmethod
    def field_label_locator(cls, label):
        return (By.XPATH, f"//*[normalize-space()={cls.xpath_literal(label)}]")

    @classmethod
    def manual_wizard_step_locator(cls, label):
        return (
            By.XPATH,
            "//*[contains(@class,'stepItem')]"
            f"[contains(normalize-space(),{cls.xpath_literal(label)})]",
        )

    def missing_metadata_fields(self):
        return [
            label
            for label in self.METADATA_FIELD_LABELS
            if not self.count_visible(self.field_label_locator(label))
        ]

    def missing_content_fields(self):
        return [
            label
            for label in self.CONTENT_FIELD_LABELS
            if not self.count_visible(self.field_label_locator(label))
        ]

    def missing_manual_wizard_steps(self):
        return [
            label
            for label in self.MANUAL_WIZARD_STEP_LABELS
            if not self.count_visible(self.manual_wizard_step_locator(label))
        ]

    def open_item_creation_module(self):
        last_error = None
        for attempt in range(2):
            self.wait_for_application_to_load()
            try:
                self.click_any_element(self.ITEM_CREATION_MENU_LOCATORS)
                # The module lazy-loads behind its own "Loading create item
                # set..." screen. Under a parallel run that can outlast the
                # default element wait, so the caller's first click on a tab
                # lands on the spinner instead of the form. Only report the
                # module as open once the Manual tab has actually rendered
                # (the last MANUAL_ITEM_TAB_LOCATORS entry is a positional
                # fallback that can match while the module is still loading,
                # so it is deliberately excluded here).
                self.wait_utils.until_condition(
                    lambda driver: any(
                        element.is_displayed()
                        for locator in self.MANUAL_ITEM_TAB_LOCATORS[:2]
                        for element in driver.find_elements(*locator)
                    ),
                    timeout=60,
                )
                return
            except Exception as error:
                last_error = error
            if attempt == 0:
                self.driver.refresh()
        raise TimeoutException(
            "Item creation module stayed on its 'Loading create item set' screen."
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

    def open_manual_item_tab(self):
        self.click_any_element(self.MANUAL_ITEM_TAB_LOCATORS)

    def close_popup_if_open(self):
        self.pause_before_action()
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def select_dropdown_option(self, label, value):
        dropdown = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//*[normalize-space()=\"{label}\"]/following::button[1]")
            )
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", dropdown)
        option_locators = [
            (By.XPATH, f"//*[@role='option' and normalize-space()=\"{value}\"]"),
            (By.XPATH, f"//*[contains(@cmdk-item,'') and normalize-space()=\"{value}\"]"),
            # The dev build currently renders some Radix select entries as
            # buttons without role=option. Keep the exact-text fallback broad
            # and let click_dropdown_option filter it to displayed elements.
            (By.XPATH, f"//*[normalize-space()=\"{value}\"]"),
        ]
        if str(value).strip().lower() == "true/false":
            option_locators.insert(
                0,
                (
                    By.XPATH,
                    "//*[contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'true') "
                    "and contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'false')]",
                ),
            )
        self.click_dropdown_option(option_locators)

    def click_dropdown_option(self, option_locators):
        last_error = None
        for locator in option_locators:
            try:
                option = self._find_dropdown_option_with_scroll(locator)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'nearest'});", option)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", option)
                return
            except Exception as error:
                last_error = error
        raise last_error

    def _find_dropdown_option_with_scroll(self, locator):
        """Search for a dropdown option, scrolling the open listbox into view
        as needed. Newly added options can push earlier entries (e.g.
        "Multiple Choice Question") below the listbox's initial render
        window, so a plain find-and-wait can time out even though the
        option exists further down the scrollable popup.
        """
        last_error = None
        for _ in range(10):
            try:
                return self.wait_utils.until_condition(
                    lambda driver: (
                        visible_options[-1]
                        if (
                            visible_options := [
                                element
                                for element in driver.find_elements(*locator)
                                if element.is_displayed()
                            ]
                        ) else None
                    ),
                    timeout=2,
                )
            except TimeoutException as error:
                last_error = error
                scrolled = self.driver.execute_script(
                    """
                    const candidates = document.querySelectorAll(
                        "[cmdk-list], [role='listbox'], [data-radix-popper-content-wrapper]"
                    );
                    for (const el of candidates) {
                        if (el.scrollHeight > el.clientHeight) {
                            const before = el.scrollTop;
                            el.scrollTop = Math.min(
                                el.scrollTop + el.clientHeight * 0.8,
                                el.scrollHeight
                            );
                            if (el.scrollTop !== before) return true;
                        }
                    }
                    return false;
                    """
                )
                if not scrolled:
                    break
        raise last_error

    def select_dropdown_option_by_index(self, label, index=0):
        last_error = None
        for _ in range(3):
            try:
                dropdown = self.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//*[normalize-space()=\"{label}\"]/following::button[1]")
                    )
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", dropdown)
                options = self.wait.until(
                    EC.visibility_of_all_elements_located(
                        (By.XPATH, "//*[@role='option' and not(@aria-disabled='true')]")
                    )
                )
                option = options[index]
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", option)
                return
            except Exception as error:
                last_error = error
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        raise last_error

    def is_dropdown_option_available(self, label, value):
        dropdown = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//*[normalize-space()=\"{label}\"]/following::button[1]")
            )
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        dropdown.click()
        try:
            return self.wait_utils.until_condition(
                lambda driver: any(
                    element.is_displayed()
                    for element in driver.find_elements(
                        By.XPATH,
                        f"//*[normalize-space()=\"{value}\"]",
                    )
                ),
                timeout=3,
            ) is True
        except TimeoutException:
            return False
        finally:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def get_dropdown_page_text(self, label):
        dropdown = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//*[normalize-space()=\"{label}\"]/following::button[1]")
            )
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        dropdown.click()
        page_text = self.wait_utils.until_condition(
            lambda driver: (
                text
                if "multiple choice question" in (text := driver.find_element(By.TAG_NAME, "body").text).casefold()
                else False
            ),
            timeout=10,
        )
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        return page_text

    def get_manual_item_typology_options(self):
        """Read the actual controlled options currently rendered by the app."""
        dropdown = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[normalize-space()="Item Typology *"]/following::button[1]')
            )
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            dropdown,
        )
        self.driver.execute_script("arguments[0].click();", dropdown)
        try:
            options = self.wait_utils.until_condition(
                lambda driver: (
                    visible_options
                    if (
                        visible_options := driver.execute_script(
                            """
                            const toastSelector =
                                '[data-radix-toast-viewport], [role="status"], [role="alert"], ' +
                                '[data-sonner-toast], [class*="toast" i]';
                            return Array.from(document.querySelectorAll(
                                "[role='option'], [data-radix-collection-item], [cmdk-item]"
                            ))
                                .filter(el => el.getClientRects().length > 0 && el.innerText.trim())
                                .filter(el => !el.closest(toastSelector))
                                .map(el => el.innerText.trim());
                            """
                        )
                    )
                    else None
                ),
                timeout=10,
            )
            return tuple(dict.fromkeys(options))
        finally:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    @classmethod
    def canonical_manual_typology(cls, option_text):
        normalized_option = re.sub(r"[^a-z0-9]+", "", option_text.casefold())
        matches = []
        for typology, aliases in cls.MANUAL_TYPOLOGY_OPTION_ALIASES.items():
            for alias in aliases:
                normalized_alias = re.sub(r"[^a-z0-9]+", "", alias.casefold())
                if normalized_alias and normalized_alias in normalized_option:
                    matches.append((len(normalized_alias), typology))
        return max(matches)[1] if matches else ""

    def get_visible_required_field_labels(self):
        labels = self.driver.find_elements(
            By.XPATH,
            "//*[self::label or self::p or self::span or self::div]"
            "[contains(normalize-space(), '*') and string-length(normalize-space()) < 80]",
        )
        return list(
            dict.fromkeys(
                element.text.strip().rstrip("*").strip()
                for element in labels
                if element.is_displayed() and element.text.strip()
            )
        )

    def has_visible_field(self, field_name):
        expected = field_name.casefold()
        return any(
            expected in label.casefold()
            for label in self.get_visible_required_field_labels()
        )

    def get_form_text_for_typology(self, typology):
        self.select_typology(typology)
        self.pause_before_action()
        return self.driver.find_element(By.TAG_NAME, "body").text

    def get_form_signature_for_typology(self, typology):
        return {
            "text": self.get_form_text_for_typology(typology),
            "editor_count": len(self.get_visible_rich_text_editors()),
        }

    def clear_added_items(self):
        """Remove every staged item and confirm the list stays empty.

        The staged list is a server-side draft that hydrates asynchronously, so
        it can read as empty and then repopulate a moment later — deleting once
        and returning on the first zero leaves the next test looking at the
        previous test's item. Re-clear until the list is still empty after a
        settle window.
        """
        for _ in range(5):
            self._delete_all_added_items()
            if self._added_items_stay_empty():
                self.wait_for_toasts_to_clear()
                return
        raise AssertionError(
            "Could not isolate draft: staged items kept reappearing after deletion, "
            "so the saved draft never settled empty."
        )

    def _added_items_stay_empty(self, settle_seconds=6, poll_seconds=1):
        """True when the staged list holds at zero for the whole settle window."""
        deadline = monotonic() + settle_seconds
        while monotonic() < deadline:
            if int(self.get_added_items_count()) > 0:
                return False
            sleep(poll_seconds)
        return int(self.get_added_items_count()) == 0

    def _delete_all_added_items(self):
        for _ in range(100):
            count = int(self.get_added_items_count())
            if count == 0:
                return
            delete_buttons = [
                button
                for button in self.driver.find_elements(
                    By.XPATH,
                    "//*[contains(normalize-space(),'Added Items')]/following::*"
                    "[name()='svg' and contains(@class,'trash')]/ancestor::button[1]",
                )
                if button.is_displayed()
            ]
            if not delete_buttons:
                raise AssertionError(f"Could not isolate draft: {count} added item(s) could not be removed.")
            delete_buttons[0].click()
            confirm_delete = self.wait_utils.until_clickable(
                (
                    By.XPATH,
                    "//*[@role='dialog']//button[normalize-space()='Delete']"
                    " | //*[normalize-space()='Delete item']/following::button[normalize-space()='Delete'][1]",
                ),
                timeout=10,
            )
            confirm_delete.click()
            self.wait_utils.until_condition(
                lambda _: int(self.get_added_items_count()) < count,
                timeout=10,
            )
        raise AssertionError(
            "Could not isolate draft: more than 100 added item(s) remained after "
            "the cleanup retry budget was exhausted."
        )

    def wait_for_saved_draft_to_hydrate(self):
        self.wait_utils.until_visible(self.ADDED_ITEMS_HEADING, timeout=15)
        previous_count = int(self.get_added_items_count())
        for _ in range(3):
            sleep(2)
            current_count = int(self.get_added_items_count())
            if current_count == previous_count:
                return current_count
            previous_count = current_count
        return previous_count

    def wait_for_toasts_to_clear(self, timeout=8):
        """A just-dismissed toast (e.g. 'Draft item deleted.') can still be visible
        right after an action completes and gets misread as a dropdown option by
        broad option-scraping selectors. Give it a moment to auto-dismiss."""
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.get_visible_validation_messages(),
                timeout=timeout,
            )
        except TimeoutException:
            pass

    def get_visible_validation_messages(self):
        messages = self.driver.execute_script(
            """
            return Array.from(document.querySelectorAll(
                '[role="alert"], [role="status"], [class*="toast"], [data-sonner-toast]'
            )).filter(element => element.getClientRects().length > 0)
              .map(element => (element.innerText || element.textContent || '').trim())
              .filter(Boolean);
            """
        )
        return list(dict.fromkeys(messages))

    def add_incomplete_mcq_with_three_options(self, question, options, explanation):
        if len(options) != 3:
            raise ValueError("This negative test requires exactly three MCQ options.")
        self.select_manual_item_metadata("Multiple Choice Question", "1")
        values = [question] + list(options)
        for index, value in enumerate(values):
            self.set_visible_rich_text_editor_by_index(index, value)
        self.enter_answer_key("A")
        self.set_visible_rich_text_editor_by_index(
            len(self.get_visible_rich_text_editors()) - 1,
            explanation,
        )
        self.click_add_item()

    def open_repository_and_search(self, search_text):
        repository = self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//*[self::button or self::a][contains(normalize-space(),'Repository')]"
                " | //*[normalize-space()='Repository']/ancestor::*[self::button or self::a][1]",
            ),
            timeout=15,
        )
        repository.click()
        search_input = self.wait_utils.until_visible(
            (
                By.XPATH,
                "//input[contains(@placeholder,'Search') or contains(@aria-label,'Search')]",
            ),
            timeout=20,
        )
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        started = monotonic()
        search_input.send_keys(search_text)
        search_input.send_keys(Keys.ENTER)
        self.wait_utils.until_condition(
            lambda driver: "loading items" not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=20,
        )
        elapsed = monotonic() - started
        return self.driver.find_element(By.TAG_NAME, "body").text, elapsed

    def repository_has_exact_item(self, item_id):
        """Search Repository and match the item in result content, not the search box."""
        self.open_repository_and_search(item_id)
        return bool(
            self.driver.execute_script(
                r"""
                const expected = arguments[0].replace(/\s+/g, '').toLowerCase();
                const candidates = Array.from(document.querySelectorAll(
                    'table tbody tr, [role="row"], article, [data-testid*="item"], a[href*="item"]'
                ));
                return candidates.some(element => {
                    if (element.closest('thead')) return false;
                    const text = (element.innerText || element.textContent || '')
                        .replace(/\s+/g, '')
                        .toLowerCase();
                    return text.includes(expected);
                });
                """,
                item_id,
            )
        )

    def blur_empty_item_content(self):
        editor = self.wait_utils.until_visible(self.ITEM_CONTENT_EDITOR, timeout=10)
        editor.click()
        editor.send_keys(Keys.TAB)

    def get_required_field_errors(self):
        errors = self.wait_utils.until_condition(
            lambda driver: [
                element.text.strip()
                for element in driver.find_elements(
                    By.XPATH,
                    "//*[contains(translate(normalize-space(), "
                    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'required')]",
                )
                if element.is_displayed() and element.text.strip()
            ],
            timeout=8,
        )
        return list(dict.fromkeys(errors))

    def select_grade(self, grade):
        self.select_dropdown_option("Grade *", grade)

    def select_subject(self, subject):
        self.select_dropdown_option("Subject *", subject)

    def select_chapter(self, chapter):
        self.select_dropdown_option("Chapter *", chapter)

    def select_chapter_by_index(self, index=0):
        self.select_dropdown_option_by_index("Chapter *", index)

    def select_competency_by_index(self, index=0):
        self.select_dropdown_option_by_index("Competency *", index)

    def select_learning_outcome_by_index(self, index=0):
        self.select_dropdown_option_by_index("Learning Outcome (NCERT) *", index)

    def select_blooms_level(self, blooms_level):
        self.select_dropdown_option("Bloom's Level *", blooms_level)

    def select_blooms_level_by_index(self, index=0):
        self.select_dropdown_option_by_index("Bloom's Level *", index)

    def select_typology(self, typology):
        ui_label = self.MANUAL_TYPOLOGY_UI_LABELS.get(typology, typology)
        last_error = None
        for attempt in range(2):
            self.select_dropdown_option("Item Typology *", ui_label)
            try:
                self.wait_utils.until_visible(self.VISIBLE_RICH_TEXT_EDITORS, timeout=15)
                return
            except TimeoutException as error:
                # The typology-specific form occasionally lags behind the
                # dropdown selection in a long-lived single-page session.
                # Re-picking the same option gives the form one more chance
                # to render before we report a real failure.
                last_error = error
        raise last_error

    def select_marks(self, marks):
        self.select_dropdown_option("Marks *", marks)

    def select_true_false_item_type(self):
        last_error = None
        for _ in range(3):
            try:
                dropdown = self.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[normalize-space()=\"Item Typology *\"]/following::button[1]")
                    )
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", dropdown)

                candidates = self.wait.until(
                    lambda driver: [
                        element
                        for element in driver.find_elements(
                            By.CSS_SELECTOR,
                            "[role='option'], [role='menuitem'], [data-radix-collection-item], [cmdk-item]",
                        )
                        if element.is_displayed() and element.text.strip()
                    ]
                )
                for candidate in candidates:
                    text = candidate.text.strip().lower()
                    if "true" in text and "false" in text:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", candidate)
                        self.pause_before_action()
                        self.driver.execute_script("arguments[0].click();", candidate)
                        return

                options = [candidate.text.strip() for candidate in candidates]
                raise AssertionError(f"True/False typology option not found. Available options: {options}")
            except StaleElementReferenceException as error:
                last_error = error

        raise last_error

    def select_true_false_item_metadata(self):
        self.select_grade("Grade 1")
        self.select_subject("Mathematics")
        self.select_chapter_by_index()
        self.select_competency_by_index()
        self.select_learning_outcome_by_index()
        self.select_blooms_level_by_index()
        self.select_true_false_item_type()
        self.select_marks("1")

    def select_common_manual_item_metadata(self):
        self.select_grade("Grade 1")
        self.select_subject("Mathematics")
        self.select_chapter_by_index()
        self.select_competency_by_index()
        self.select_learning_outcome_by_index()
        self.select_blooms_level_by_index()

    def select_manual_item_metadata(self, typology, marks="1"):
        self.select_common_manual_item_metadata()
        self.select_typology(typology)
        self.select_marks(marks)

    def open_true_false_manual_item_form(self):
        self.open_item_creation_module()
        self.open_manual_item_tab()

    def add_true_false_manual_item(self, question_text, answer, explanation):
        self.select_true_false_item_metadata()
        self.add_true_false_manual_item_content(question_text, answer, explanation)

    def add_true_false_manual_item_content(self, question_text, answer, explanation):
        self.ensure_true_false_answer_controls()
        self.enter_question_text(question_text)
        self.select_answer(answer)
        self.enter_explanation(explanation)
        self.click_add_item_and_wait_for_count_increase()

    def create_true_false_manual_item(self, question_text, answer, explanation):
        self.open_true_false_manual_item_form()
        self.add_true_false_manual_item(question_text, answer, explanation)

    def create_true_false_manual_items(self, manual_items):
        self.open_true_false_manual_item_form()
        self.select_true_false_item_metadata()
        for manual_item in manual_items:
            self.add_true_false_manual_item_content(
                manual_item["question"],
                manual_item["answer"],
                manual_item["explanation"],
            )

    def open_manual_item_form_for_typology(self, typology, marks="1"):
        self.open_item_creation_module()
        self.open_manual_item_tab()
        self.select_manual_item_metadata(typology, marks)

    def get_visible_rich_text_editors(self):
        self.wait_utils.until_visible(self.VISIBLE_RICH_TEXT_EDITORS, timeout=15)
        return [
            editor
            for editor in self.driver.find_elements(*self.VISIBLE_RICH_TEXT_EDITORS)
            if editor.is_displayed()
        ]

    def set_visible_rich_text_editor_by_index(self, index, value):
        editors = self.get_visible_rich_text_editors()
        if index >= len(editors):
            raise AssertionError(
                f"Rich text editor index {index} not found. Visible editor count: {len(editors)}"
            )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", editors[index])
        self.pause_before_action()
        self.driver.execute_script(
            """
            const editor = arguments[0];
            const value = arguments[1];
            editor.innerHTML = '<p>' + value + '</p>';
            editor.dispatchEvent(new Event('input', { bubbles: true }));
            editor.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            editors[index],
            value,
        )

    def set_labeled_rich_text_editor_value(self, locator, value):
        editor = self.wait_utils.until_visible(locator, timeout=10)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", editor)
        self.pause_before_action()
        self.driver.execute_script(
            """
            const editor = arguments[0];
            const value = arguments[1];
            editor.innerHTML = '<p>' + value + '</p>';
            editor.dispatchEvent(new Event('input', { bubbles: true }));
            editor.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            editor,
            value,
        )

    def set_available_short_text_inputs(self, values):
        inputs = [
            element
            for element in self.driver.find_elements(*self.SHORT_TEXT_INPUTS)
            if element.is_displayed()
            and not element.get_attribute("readonly")
            and "file" != (element.get_attribute("type") or "").lower()
        ]
        for element, value in zip(inputs, values):
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            self.pause_before_action()
            element.clear()
            element.send_keys(value)
            self.driver.execute_script(
                """
                const input = arguments[0];
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.blur();
                """,
                element,
            )

    def select_first_correct_option_if_present(self):
        for locator in self.FIRST_CORRECT_OPTION_LOCATORS:
            try:
                option = self.wait_utils.until_clickable(locator, timeout=3)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", option)
                return True
            except Exception:
                continue
        return False

    def enter_answer_key(self, answer_key):
        answer_input = self.wait_utils.until_visible(self.ANSWER_KEY_INPUT, timeout=10)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", answer_input)
        self.pause_before_action()
        answer_input.clear()
        answer_input.send_keys(answer_key)
        self.driver.execute_script(
            """
            const input = arguments[0];
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.blur();
            """,
            answer_input,
        )

    def select_correct_answer_dropdown(self, answer_key):
        try:
            self.wait_utils.until_present(self.CORRECT_ANSWER_SELECT, timeout=5)
            self.pause_before_action()
            self.driver.execute_script(
                """
                const value = arguments[0];
                const selects = [...document.querySelectorAll('select')]
                    .filter(select => [...select.options].some(option => option.value === value));
                for (const select of selects) {
                    select.value = value;
                    select.dispatchEvent(new Event('input', { bubbles: true }));
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    select.blur();
                }
                """,
                answer_key,
            )
            return
        except Exception:
            pass

        dropdown = self.wait_utils.until_clickable(self.CORRECT_ANSWER_DROPDOWN, timeout=10)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        self.pause_before_action()
        try:
            dropdown.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", dropdown)
        option_labels = (answer_key, f"Option {answer_key}", f"({answer_key})")
        try:
            self.click_dropdown_option(
                [
                    (
                        By.XPATH,
                        "//*[@role='option' and ("
                        + " or ".join(f"normalize-space()=\"{label}\"" for label in option_labels)
                        + ")]",
                    ),
                    (
                        By.XPATH,
                        "//*[@data-radix-collection-item='' and ("
                        + " or ".join(f"normalize-space()=\"{label}\"" for label in option_labels)
                        + ")]",
                    ),
                    (By.XPATH, "(//*[@role='option' and not(@aria-disabled='true')])[1]"),
                    (By.XPATH, "(//*[@data-radix-collection-item='' and not(@aria-disabled='true')])[1]"),
                ]
            )
        except Exception:
            pass

        try:
            selected_text = self.wait_utils.until_visible(self.CORRECT_ANSWER_DROPDOWN, timeout=3).text.strip()
        except Exception:
            selected_text = ""

        if not selected_text or selected_text.lower() == "select":
            for _ in range(3):
                dropdown = self.wait_utils.until_clickable(self.CORRECT_ANSWER_DROPDOWN, timeout=5)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
                self.pause_before_action()
                try:
                    dropdown.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", dropdown)
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_DOWN)
                body.send_keys(Keys.ENTER)
                self.pause_before_action()
                selected_text = self.wait_utils.until_visible(self.CORRECT_ANSWER_DROPDOWN, timeout=3).text.strip()
                if selected_text and selected_text.lower() != "select":
                    return

    def set_explanation_by_label(self, explanation):
        self.set_labeled_rich_text_editor_value(self.EXPLANATION_BY_LABEL_EDITOR, explanation)

    def fill_multiple_choice_question(self, question_text, options, explanation):
        values = [question_text] + options
        for index, value in enumerate(values):
            self.set_visible_rich_text_editor_by_index(index, value)
        try:
            self.enter_answer_key("A")
        except Exception:
            self.select_correct_answer_dropdown("A")
        self.set_explanation_by_label(explanation)

    def fill_short_answer_question(self, question_text, answer_text, explanation):
        self.set_visible_rich_text_editor_by_index(0, question_text)
        editor_values = [answer_text, explanation]
        editors = self.get_visible_rich_text_editors()
        for offset, value in enumerate(editor_values, start=1):
            if offset < len(editors):
                self.set_visible_rich_text_editor_by_index(offset, value)
        self.set_available_short_text_inputs(["80"])

    def fill_fill_in_the_blank_question(self, question_text, answer_text, explanation):
        self.set_visible_rich_text_editor_by_index(0, question_text)
        self.enter_blank_answer(answer_text)
        self.set_explanation_by_label(explanation)

    def enter_blank_answer(self, answer_text, blank_index=1):
        """Fill the native 'Answer for blank N' input. This typology's answer field
        is a plain text input, not a rich text editor or an 'Answer Key'/'Correct
        Answer'-labeled field, so it needs its own locator rather than reusing
        enter_answer_key() or the rich text editor helpers."""
        locator = (By.XPATH, f"//input[@placeholder='Answer for blank {blank_index}']")
        blank_input = self.wait_utils.until_visible(locator, timeout=10)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", blank_input)
        self.pause_before_action()
        blank_input.clear()
        blank_input.send_keys(answer_text)
        self.driver.execute_script(
            """
            const input = arguments[0];
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.blur();
            """,
            blank_input,
        )

    def fill_very_short_answer_question(self, question_text, answer_text, explanation):
        self.fill_short_answer_question(question_text, answer_text, explanation)

    def fill_long_answer_question(self, question_text, answer_text, explanation):
        self.fill_short_answer_question(question_text, answer_text, explanation)

    MTF_COLUMN_A_DELETE_BUTTONS = (
        By.XPATH, "//button[starts-with(@aria-label, 'Remove Column A (Items) entry')]"
    )
    MTF_COLUMN_B_DELETE_BUTTONS = (
        By.XPATH, "//button[starts-with(@aria-label, 'Remove Column B (Matches) entry')]"
    )

    def _trim_match_the_following_column(self, locator, target_count):
        for _ in range(10):
            buttons = [button for button in self.driver.find_elements(*locator) if button.is_displayed()]
            if len(buttons) <= target_count:
                return
            button = buttons[-1]
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            self.pause_before_action()
            self.driver.execute_script("arguments[0].click();", button)

    def remove_extra_match_the_following_rows(self, target_count):
        """Column A (Items) and Column B (Matches) are independently numbered lists,
        not a single set of paired rows, and the form defaults to 4 entries in each.
        Sequentially filling fewer pairs than that leaves trailing rows empty and
        blocks Add Item, so trim both columns down to the pair count first."""
        self._trim_match_the_following_column(self.MTF_COLUMN_A_DELETE_BUTTONS, target_count)
        self._trim_match_the_following_column(self.MTF_COLUMN_B_DELETE_BUTTONS, target_count)

    def fill_match_the_following_question(self, question_text, pairs, explanation):
        self.set_visible_rich_text_editor_by_index(0, question_text)
        self.remove_extra_match_the_following_rows(len(pairs))
        # The editors are grouped by column -- [0] stem, then every Column A
        # cell, then every Column B cell -- not interleaved pair by pair.
        # Writing them interleaved put each pair's match into a Column A slot.
        column_a = [left_value for left_value, _ in pairs]
        column_b = [right_value for _, right_value in pairs]
        editors = self.get_visible_rich_text_editors()
        for offset, value in enumerate(column_a + column_b, start=1):
            if offset < len(editors):
                self.set_visible_rich_text_editor_by_index(offset, value)
        # Column B keeps the pair order, so item N matches the Nth letter.
        # Derived from the pairs rather than hardcoded to three rows.
        self.enter_answer_key(
            ", ".join(
                f"{index} - {chr(ord('A') + index - 1)}"
                for index in range(1, len(pairs) + 1)
            )
        )
        self.set_explanation_by_label(explanation)

    def fill_assertion_and_reasoning_question(
        self, assertion_text, reasoning_text, answer_option="A", explanation=None
    ):
        self.set_visible_rich_text_editor_by_index(0, assertion_text)
        self.set_visible_rich_text_editor_by_index(1, reasoning_text)
        self.select_correct_answer_dropdown(answer_option)
        # "Explanation for the Answer" is required here as it is for every other
        # typology; leaving it blank silently blocks Add Item.
        if explanation:
            self.set_explanation_by_label(explanation)

    def fill_fa_activity_question(self, instructions_text, rubric_text):
        self.set_visible_rich_text_editor_by_index(0, instructions_text)
        editors = self.get_visible_rich_text_editors()
        if len(editors) > 1:
            self.set_visible_rich_text_editor_by_index(1, rubric_text)
        # The form also has an "Assessment Criteria" editor (index 2) that is
        # required despite showing no visible asterisk — leaving it empty
        # blocks Add Item with "Item content is required".
        if len(editors) > 2:
            self.set_visible_rich_text_editor_by_index(2, rubric_text)

    def fill_free_response_question(self, question_text, sample_answer_text, marking_scheme_text, word_limit=None):
        self.set_visible_rich_text_editor_by_index(0, question_text)
        self.set_visible_rich_text_editor_by_index(1, sample_answer_text)
        self.set_visible_rich_text_editor_by_index(2, marking_scheme_text)
        if word_limit:
            self.set_available_short_text_inputs([str(word_limit)])

    def fill_source_based_question(self, source_text, sub_question_text, options, explanation):
        self.remove_extra_source_subquestions()
        values = [source_text, sub_question_text] + options + [explanation]
        for index, value in enumerate(values):
            self.set_visible_rich_text_editor_by_index(index, value)
        self.select_correct_answer_dropdown("A")
        self.set_explanation_by_label(explanation)

    def remove_extra_source_subquestions(self):
        for _ in range(5):
            delete_buttons = [
                button
                for button in self.driver.find_elements(*self.EXTRA_SOURCE_SUBQUESTION_DELETE_BUTTONS)
                if button.is_displayed()
            ]
            if not delete_buttons:
                return
            button = delete_buttons[0]
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            self.pause_before_action()
            self.driver.execute_script("arguments[0].click();", button)

    def create_manual_item_for_typology(self, item_data):
        self.open_manual_item_form_for_typology(
            item_data["typology"],
            item_data.get("marks", "1"),
        )
        self.add_manual_item_for_typology(item_data)

    NATIVE_COLOR_INPUT_SET_JS = """
        const input = arguments[0];
        const value = arguments[1];
        const proto = window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        setter.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    """
    FIND_TOOLBAR_CONTAINER_JS = """
        let el = arguments[0];
        while (el && el !== document.body) {
            el = el.parentElement;
            if (!el) break;
            if (el.querySelector('[role="toolbar"]')) return el;
        }
        return null;
    """
    INSERT_IMAGE_DIALOG_HEADING = (By.XPATH, "//*[normalize-space()='Insert image']")
    INSERT_IMAGE_CONFIRM_BUTTON = (By.XPATH, "//button[normalize-space()='Insert']")

    def _toolbar_container_for_editor(self, editor):
        container = self.driver.execute_script(self.FIND_TOOLBAR_CONTAINER_JS, editor)
        if container is None:
            raise AssertionError("No formatting toolbar found for the given rich text editor.")
        return container

    def _select_all_text_in_editor(self, editor):
        self.driver.execute_script(
            """
            const editor = arguments[0];
            const range = document.createRange();
            range.selectNodeContents(editor);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            """,
            editor,
        )

    def apply_bold_and_italic(self, editor_index=0):
        """Select all text in the given editor and toggle Bold + Italic. Returns the editor's innerHTML."""
        editor = self.get_visible_rich_text_editors()[editor_index]
        container = self._toolbar_container_for_editor(editor)
        self._select_all_text_in_editor(editor)
        for title in ("Bold (Ctrl+B)", "Italic (Ctrl+I)"):
            button = container.find_element(By.XPATH, f".//button[@title='{title}']")
            self.driver.execute_script("arguments[0].click();", button)
            self.pause_before_action()
        return editor.get_attribute("innerHTML")

    def _apply_toolbar_color(self, editor_index, button_title, hex_color, expected_marker):
        """Select all text in the given editor and set a color via the given toolbar
        swatch (Text color / Highlight color). Retries once, since these fire in quick
        succession right after other toolbar actions and can occasionally race the
        editor's re-render. Returns the editor's innerHTML."""
        editor = self.get_visible_rich_text_editors()[editor_index]
        last_html = ""
        for _ in range(2):
            container = self._toolbar_container_for_editor(editor)
            self._select_all_text_in_editor(editor)
            button = container.find_element(By.XPATH, f".//button[@title='{button_title}']")
            self.driver.execute_script("arguments[0].click();", button)
            self.pause_before_action()
            color_input = container.find_element(
                By.XPATH, f".//button[@title='{button_title}']/following-sibling::input[@type='color']"
            )
            self.driver.execute_script(self.NATIVE_COLOR_INPUT_SET_JS, color_input, hex_color)
            self.pause_before_action()
            last_html = editor.get_attribute("innerHTML")
            if expected_marker in last_html:
                break
        return last_html

    def apply_text_color(self, editor_index=0, hex_color="#ff0000"):
        """Select all text in the given editor and set its text color. Returns the editor's innerHTML."""
        return self._apply_toolbar_color(editor_index, "Text color", hex_color, "color:")

    def apply_highlight_color(self, editor_index=0, hex_color="#ffff00"):
        """Select all text in the given editor and set its highlight/background color. Returns the editor's innerHTML."""
        return self._apply_toolbar_color(editor_index, "Highlight color", hex_color, "background-color")

    def insert_image_into_editor(self, editor_index, image_path):
        """Upload an image from disk into the given editor via the toolbar's Insert image dialog.

        Always leaves the dialog closed, even on failure — a stuck open dialog
        would otherwise block every later action (e.g. Add Item) for this item.
        """
        editor = self.get_visible_rich_text_editors()[editor_index]
        container = self._toolbar_container_for_editor(editor)
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", editor)
            self.pause_before_action()
            self.driver.execute_script("arguments[0].click();", editor)
            image_button = container.find_element(By.XPATH, ".//button[@title='Insert image']")
            self.driver.execute_script("arguments[0].click();", image_button)
            file_input = self.wait_utils.until_present((By.CSS_SELECTOR, "input[type='file']"), timeout=10)
            file_input.send_keys(image_path)
            insert_button = self.wait_utils.until_clickable(self.INSERT_IMAGE_CONFIRM_BUTTON, timeout=10)
            insert_button.click()
            self.wait_utils.until_condition(
                lambda driver: not any(
                    element.is_displayed()
                    for element in driver.find_elements(*self.INSERT_IMAGE_DIALOG_HEADING)
                ),
                timeout=30,
            )
            return editor.get_attribute("innerHTML")
        except Exception:
            self._close_insert_image_dialog_if_open()
            raise

    def _close_insert_image_dialog_if_open(self):
        for _ in range(3):
            dialog_open = any(
                element.is_displayed()
                for element in self.driver.find_elements(*self.INSERT_IMAGE_DIALOG_HEADING)
            )
            if not dialog_open:
                return
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            self.pause_before_action()

    def add_manual_item_for_typology(self, item_data, before_submit=None):
        typology = item_data["typology"]
        if "true" in typology.lower() and "false" in typology.lower():
            self.ensure_true_false_answer_controls()
            self.enter_question_text(item_data["question"])
            self.select_answer(item_data["answer"])
            self.enter_explanation(item_data["explanation"])
        elif typology == "Multiple Choice Question":
            self.fill_multiple_choice_question(
                item_data["question"],
                item_data["options"],
                item_data["explanation"],
            )
        elif typology == "Fill in the Blank":
            self.fill_fill_in_the_blank_question(
                item_data["question"],
                item_data["answer"],
                item_data["explanation"],
            )
        elif typology == "Very Short Answer Question":
            self.fill_very_short_answer_question(
                item_data["question"],
                item_data["answer"],
                item_data["explanation"],
            )
        elif typology == "Short Answer Question":
            self.fill_short_answer_question(
                item_data["question"],
                item_data["answer"],
                item_data["explanation"],
            )
        elif typology == "Long Answer Question":
            self.fill_long_answer_question(
                item_data["question"],
                item_data["answer"],
                item_data["explanation"],
            )
        elif typology == "Match the Following":
            self.fill_match_the_following_question(
                item_data["question"],
                item_data["pairs"],
                item_data["explanation"],
            )
        elif typology in ("Case Based Question", "Source Based Question", "Source Based Questions"):
            self.fill_source_based_question(
                item_data["source"],
                item_data["question"],
                item_data["options"],
                item_data["explanation"],
            )
        elif typology == "Assertion and Reasoning":
            self.fill_assertion_and_reasoning_question(
                item_data["assertion"],
                item_data["reasoning"],
                item_data.get("answer", "A"),
                item_data.get("explanation"),
            )
        elif typology == "FA Activity":
            self.fill_fa_activity_question(
                item_data["instructions"],
                item_data.get("rubric", item_data["instructions"]),
            )
        elif typology == "Free Response":
            self.fill_free_response_question(
                item_data["question"],
                item_data["answer"],
                item_data["marking_scheme"],
                item_data.get("word_limit"),
            )
        else:
            raise ValueError(f"Unsupported manual item typology: {typology}")
        if before_submit:
            before_submit()
        self.click_add_item_and_wait_for_count_increase()

    def add_manual_items_for_typologies(self, item_data_list, before_submit=None):
        if not item_data_list:
            raise ValueError("At least one manual item is required.")

        for index, item_data in enumerate(item_data_list):
            if index > 0:
                self.clear_form_if_available()
            self.select_common_manual_item_metadata()
            self.select_typology(item_data["typology"])
            self.select_marks(item_data.get("marks", "1"))
            hook = (lambda data=item_data: before_submit(data)) if before_submit else None
            self.add_manual_item_for_typology(item_data, before_submit=hook)

    def create_manual_items_for_typologies(self, item_data_list, reset_draft=False):
        if not item_data_list:
            raise ValueError("At least one manual item is required.")

        self.open_item_creation_module()
        self.open_manual_item_tab()
        if reset_draft:
            self.wait_for_saved_draft_to_hydrate()
            self.clear_added_items()
        self.add_manual_items_for_typologies(item_data_list)

    def get_added_item_card_text(self, question_text, typology):
        tag_aliases = self.MANUAL_TYPOLOGY_OPTION_ALIASES[typology]
        return self.driver.execute_script(
            r"""
            const expected = arguments[0].replace(/\s+/g, ' ').trim().toLowerCase();
            const aliases = arguments[1].map(alias => alias.toLowerCase());
            const visible = element => element.getClientRects().length > 0;
            const candidates = Array.from(document.querySelectorAll('article, li, section, div'))
                .filter(element => {
                    if (!visible(element)) return false;
                    const text = (element.innerText || element.textContent || '')
                        .replace(/\s+/g, ' ').trim();
                    return text.toLowerCase().includes(expected)
                        && aliases.some(alias => text.toLowerCase().includes(alias))
                        && text.length < 1800;
                })
                .sort((left, right) => {
                    const a = (left.innerText || left.textContent || '').length;
                    const b = (right.innerText || right.textContent || '').length;
                    return a - b;
                });
            return candidates[0]
                ? (candidates[0].innerText || candidates[0].textContent || '').trim()
                : '';
            """,
            question_text,
            list(tag_aliases),
        )

    def wait_for_added_item_card_text(self, question_text, typology, timeout=10):
        """The Added Items card can lag a beat behind the count increment (React
        re-render), so poll instead of reading it exactly once right after Add Item."""
        try:
            return self.wait_utils.until_condition(
                lambda _: self.get_added_item_card_text(question_text, typology) or None,
                timeout=timeout,
            )
        except TimeoutException:
            return ""

    @classmethod
    def typology_tag_is_visible(cls, typology, card_text):
        normalized_card = card_text.casefold()
        return any(
            re.search(
                rf"(?<![a-z0-9]){re.escape(alias.casefold())}(?![a-z0-9])",
                normalized_card,
            )
            for alias in cls.MANUAL_TYPOLOGY_OPTION_ALIASES[typology]
        )

    def click_add_item_if_enabled(self):
        buttons = self.driver.find_elements(*self.ADD_ITEM_LOCATORS[0])
        button = next((element for element in buttons if element.is_displayed()), None)
        if not button:
            return False
        enabled = (
            button.is_enabled()
            and not button.get_attribute("disabled")
            and button.get_attribute("aria-disabled") != "true"
        )
        if not enabled:
            return False
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        self.driver.execute_script("arguments[0].click();", button)
        return True

    def get_visible_required_validation_messages(self):
        locator = (
            By.XPATH,
            "//*[contains(translate(normalize-space(), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'required')]",
        )
        # React re-renders the validation state right after Add Item is
        # clicked, which can invalidate elements mid-iteration. Re-query on
        # a stale reference instead of letting the whole check blow up.
        for _ in range(3):
            texts = []
            try:
                for message in self.driver.find_elements(*locator):
                    if message.is_displayed() and message.text.strip():
                        texts.append(message.text.strip())
                return list(dict.fromkeys(texts))
            except StaleElementReferenceException:
                continue
        return []

    def enter_item_content(self, question_text):
        self.enter_question_text(question_text)

    def enter_question_text(self, question_text):
        self.set_rich_text_editor_value(self.ITEM_CONTENT_EDITOR, question_text)

    def select_answer(self, answer):
        expected = str(answer).strip().lower()
        opposite = "false" if expected == "true" else "true"
        answer_control = self.wait_utils.until_condition(
            lambda driver: driver.execute_script(
                """
                const expected = arguments[0];
                const opposite = arguments[1];
                const candidates = document.querySelectorAll(
                    'button, input, label, [role="button"], [role="radio"], [tabindex]'
                );
                return Array.from(candidates).find((element) => {
                    const style = window.getComputedStyle(element);
                    const visible = element.getClientRects().length > 0 &&
                        style.visibility !== 'hidden' && style.display !== 'none';
                    const text = [
                        element.innerText,
                        element.textContent,
                        element.getAttribute('aria-label'),
                        element.getAttribute('value'),
                        element.getAttribute('title'),
                    ].filter(Boolean).join(' ').trim().toLowerCase();
                    return visible && text.includes(expected) && !text.includes(opposite);
                }) || null;
                """,
                expected,
                opposite,
            ),
            timeout=10,
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", answer_control)
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", answer_control)

    def ensure_true_false_answer_controls(self):
        if any(self.wait_utils.is_visible(locator, timeout=1) for locator in self.TRUE_ANSWER_LOCATORS):
            return
        self.select_true_false_item_type()

    def enter_explanation(self, explanation):
        self.set_rich_text_editor_value(self.EXPLANATION_EDITOR, explanation)

    def click_add_item(self):
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        add_item_button = self.wait.until(EC.element_to_be_clickable(self.ADD_ITEM_LOCATORS[0]))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_item_button)
        self.pause_before_action()
        add_item_button.click()

    def click_add_item_and_wait_for_count_increase(self):
        existing_items_count = int(self.get_added_items_count())
        last_error = None

        for _ in range(3):
            try:
                self.click_add_item()
            except WebDriverException as error:
                # A rich-text editor or other overlay can momentarily sit above
                # the Add Item button (e.g. right after an image upload closes
                # its dialog), intercepting the click. An intercepted click
                # never reaches the button, so the item was not added; confirm
                # that before retrying with a fresh scroll+click.
                last_error = error
                if int(self.get_added_items_count()) > existing_items_count:
                    return
                continue
            try:
                self.wait_utils.until_condition(
                    lambda _: int(self.get_added_items_count()) > existing_items_count
                    ,
                    timeout=8,
                )
                return
            except TimeoutException as error:
                last_error = error

        raise last_error

    def clear_form_if_available(self):
        for locator in self.CLEAR_FORM_LOCATORS:
            try:
                clear_button = self.wait_utils.until_clickable(locator, timeout=3)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", clear_button)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", clear_button)
                return True
            except Exception:
                continue
        return False

    def click_continue(self):
        self.driver.execute_script("window.scrollTo(0, 0);")
        self.click_any_element(self.CONTINUE_LOCATORS)

    def is_continue_enabled(self):
        continue_button = self.wait_utils.until_visible(self.CONTINUE_BUTTON, timeout=15)
        return (
            continue_button.is_enabled()
            and not continue_button.get_attribute("disabled")
            and continue_button.get_attribute("aria-disabled") != "true"
        )

    def click_submit_for_qar(self):
        self.driver.execute_script("window.scrollTo(0, 0);")
        self.click_any_element(self.SUBMIT_FOR_QAR_LOCATORS)

    def get_review_item_id_for_question(self, question_text):
        escaped_question = question_text.replace('"', '\\"')
        item_id_locator = (
            self.REVIEW_ITEM_ID_FOR_QUESTION[0],
            self.REVIEW_ITEM_ID_FOR_QUESTION[1].format(question_text=escaped_question),
        )
        try:
            return self.wait_utils.until_visible(item_id_locator, timeout=8).text.strip()
        except TimeoutException:
            return self.get_review_item_id_from_visible_rows(question_text)

    def get_review_item_id_from_visible_rows(self, question_text):
        expected_text = self.normalize_review_text(question_text)
        rows = self.wait_utils.until_all_visible(self.REVIEW_TABLE_ROWS, timeout=10)

        for row in rows:
            row_text = self.normalize_review_text(row.text)
            if expected_text in row_text:
                try:
                    item_id = row.find_element(*self.REVIEW_ROW_ITEM_ID).text.strip()
                except Exception:
                    item_id = row.find_elements(By.TAG_NAME, "td")[0].text.strip()
                if item_id:
                    return item_id

        # Some typologies (e.g. Assertion and Reasoning, whose content includes an
        # auto-generated options table) can't be rendered as row text at all — the
        # review table shows a generic "Expand to view the item content" placeholder
        # instead. When there's exactly one row, it can only be this item.
        if len(rows) == 1:
            try:
                item_id = rows[0].find_element(*self.REVIEW_ROW_ITEM_ID).text.strip()
            except Exception:
                item_id = rows[0].find_elements(By.TAG_NAME, "td")[0].text.strip()
            if item_id:
                return item_id

        raise TimeoutException(f"Review row not found for question: {question_text}")

    def get_review_item_ids_for_questions(self, question_texts):
        question_texts = list(question_texts)
        if not question_texts:
            return []

        rows = self.wait_utils.until_all_visible(self.REVIEW_TABLE_ROWS, timeout=10)
        run_marker = self.get_question_run_marker(question_texts)
        item_ids = []

        for row in rows:
            row_text = self.normalize_review_text(row.text)
            if run_marker and run_marker not in row_text:
                continue
            if not run_marker and not any(
                self.normalize_review_text(question_text) in row_text
                for question_text in question_texts
            ):
                continue
            try:
                item_id = row.find_element(*self.REVIEW_ROW_ITEM_ID).text.strip()
            except Exception:
                cells = row.find_elements(By.TAG_NAME, "td")
                item_id = cells[0].text.strip() if cells else ""
            if item_id:
                item_ids.append(item_id)
            if len(item_ids) == len(question_texts):
                break

        while len(item_ids) < len(question_texts):
            item_ids.append("ID not found before QAR submit")
        return item_ids

    @staticmethod
    def get_question_run_marker(question_texts):
        for question_text in question_texts:
            match = re.search(r"\brun\s+([a-zA-Z0-9]+)", question_text or "")
            if match:
                return f"run {match.group(1).lower()}"
        return None

    @staticmethod
    def normalize_review_text(value):
        return re.sub(r"\s+", " ", value or "").strip().lower()

    QAR_RESULTS_ITEM_ID_PATTERN = re.compile(r"IS\d+[-\w]*")

    def get_qar_results_item_id_for_question(self, question_text):
        """Read the real, numbered item ID (e.g. "IS413-G1-Mathematics-Ch38-i1")
        from the QAR Results table, which only appears after QAR analysis
        finishes. The Review & Tag Metadata step (before QAR runs) shows an
        unnumbered placeholder ID instead (e.g. "IS-G1-Mathematics-Ch38") -
        reading from there, as get_review_item_id_for_question does, silently
        returns that placeholder rather than a real ID."""
        expected_text = self.normalize_review_text(question_text)
        rows = self.wait_utils.until_all_visible(self.REVIEW_TABLE_ROWS, timeout=15)

        for row in rows:
            row_text = row.text
            if expected_text in self.normalize_review_text(row_text):
                match = self.QAR_RESULTS_ITEM_ID_PATTERN.search(row_text)
                if match:
                    return match.group(0)

        if len(rows) == 1:
            match = self.QAR_RESULTS_ITEM_ID_PATTERN.search(rows[0].text)
            if match:
                return match.group(0)

        raise TimeoutException(f"QAR Results row not found for question: {question_text}")

    def get_qar_results_item_ids_for_questions(self, question_texts):
        question_texts = list(question_texts)
        if not question_texts:
            return []

        rows = self.wait_utils.until_all_visible(self.REVIEW_TABLE_ROWS, timeout=15)
        run_marker = self.get_question_run_marker(question_texts)
        item_ids = []

        for row in rows:
            row_text = row.text
            normalized_row_text = self.normalize_review_text(row_text)
            if run_marker and run_marker not in normalized_row_text:
                continue
            if not run_marker and not any(
                self.normalize_review_text(question_text) in normalized_row_text
                for question_text in question_texts
            ):
                continue
            match = self.QAR_RESULTS_ITEM_ID_PATTERN.search(row_text)
            if match:
                item_ids.append(match.group(0))
            if len(item_ids) == len(question_texts):
                break

        while len(item_ids) < len(question_texts):
            item_ids.append("ID not found after QAR submit")
        return item_ids

    def submit_item_set_for_qar(self, question_text):
        self.click_continue()
        self.click_continue()
        self.click_submit_for_qar()
        self.wait_for_qar_success_popup()
        return self.get_qar_results_item_id_for_question(question_text)

    def submit_item_set_for_qar_for_questions(self, question_texts):
        self.click_continue()
        self.click_continue()
        self.click_submit_for_qar()
        self.wait_for_qar_success_popup()
        try:
            return self.get_qar_results_item_ids_for_questions(question_texts)
        except TimeoutException:
            return ["ID not found after QAR submit" for _ in question_texts]

    def is_submission_successful(self):
        return self.is_element_visible(self.SUCCESS_OR_LIST_INDICATOR)

    def wait_for_qar_success_popup(self):
        for locator in self.QAR_SUCCESS_POPUP_LOCATORS:
            try:
                element = self.wait_utils.until_visible(locator, timeout=15)
                message = self.extract_qar_success_message(element.text)
                if message:
                    return message
            except Exception:
                continue

        success_element = self.wait.until(EC.visibility_of_element_located(self.SUCCESS_OR_LIST_INDICATOR))
        success_text = success_element.text.strip()
        if "QAR Results" in success_text or "Quality Assurance Review" in success_text:
            return "QAR Results page displayed after submitting the item set for QAR."
        return success_text

    @staticmethod
    def extract_qar_success_message(message_text):
        message_lines = [line.strip() for line in message_text.splitlines() if line.strip()]
        for line in message_lines:
            if "QAR completed" in line and "set(s) passed" in line:
                return line
        for line in message_lines:
            if "QAR ran" in line or "item sets were returned" in line:
                return line
        for line in message_lines:
            if "QAR" in line and ("passed" in line or "failed" in line or "returned" in line):
                return line
        return message_text.strip()

    def capture_qar_success_screenshot(self, test_name):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_qar_success")

    def get_added_items_count(self):
        heading = ""
        for _ in range(3):
            heading = self.get_text(self.ADDED_ITEMS_HEADING)
            match = re.search(r"Added Items \((\d+)\)", heading)
            if match:
                return match.group(1)
            self.pause_before_action()
        raise AssertionError(
            f"Could not read a numeric 'Added Items (N)' count from heading text: {heading!r}"
        )

    def get_settled_added_items_count(self, timeout=20):
        """The staged-item count once it stops moving.

        The list is fetched after the form renders, so a single read can catch
        the heading at "Added Items (0)" while items already staged on this
        account are still loading - a baseline taken there is wrong by however
        many arrive next.
        """
        deadline = monotonic() + timeout
        previous = None
        while True:
            current = self.get_added_items_count()
            if current == previous:
                return current
            previous = current
            if monotonic() >= deadline:
                return current
            sleep(0.75)
