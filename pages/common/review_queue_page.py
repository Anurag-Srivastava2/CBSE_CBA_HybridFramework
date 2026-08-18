import logging
import re
from pathlib import Path
from time import sleep
from urllib.parse import urlsplit

from selenium.common.exceptions import NoSuchWindowException, StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage
from utilities.screenshot_utils import ScreenshotUtils

logger = logging.getLogger(__name__)


class BaseReviewQueuePage(BasePage):
    """Shared review-queue navigation and item-review behavior."""

    @staticmethod
    def item_set_numeric_prefix(item_set_id):
        """The 'IS<number>' portion of an item-set ID.

        Some environments render the same item set's ID with a different
        chapter-code suffix on different pages (e.g. "...-Ch29" right after
        upload vs "...-CH-1" once it's in a reviewer's queue) - an exact
        full-ID match then never succeeds even though it's the same item.
        The "IS<number>" prefix is stable everywhere, so it's used as the
        match target instead.
        """
        match = re.match(r"(IS\d+)", str(item_set_id), re.IGNORECASE)
        return match.group(1) if match else str(item_set_id)

    @classmethod
    def loose_item_id_key(cls, item_id):
        """A chapter-code-insensitive identity for an item ID.

        Pairs the stable "IS<number>" prefix with the trailing item number so
        IDs scraped from two different pages compare equal even when they
        disagree on the chapter-code segment in between (e.g.
        "IS833-G1-Mathematics-Ch29-i1" vs "IS833-G1-Mathematics-CH-1-i1") -
        see item_set_numeric_prefix(). Use this instead of comparing scraped
        IDs to captured ones directly.
        """
        text = str(item_id).strip()
        item_number_match = re.search(r"-i(\d+)$", text, re.IGNORECASE)
        if not item_number_match:
            return text.casefold()
        item_number = int(item_number_match.group(1))
        return f"{cls.item_set_numeric_prefix(text).upper()}-i{item_number}"

    ITEM_SET_READY_SIGNALS = (
        "Item Response Sheet",
        "Evaluation Criteria",
        "Submitted by:",
    )

    QUEUE_MENU_LOCATORS = [
        (By.XPATH, "//*[normalize-space()='Queue']/ancestor::*[self::button or self::a][1]"),
        (By.XPATH, "//button[contains(normalize-space(),'Queue')]"),
        (By.XPATH, "//*[contains(normalize-space(),'Review Queue')]"),
    ]
    QUEUE_HEADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'Review Queue') or contains(normalize-space(),'Queue')]",
    )
    SEARCH_INPUT = (
        By.XPATH,
        "//input[contains(@placeholder,'Search') or contains(@aria-label,'Search')]",
    )

    # ------------------------------------------------------------------
    # Survey locators
    #
    # Taken from a DOM census of the live review queue. None of these drive a
    # review: reviewer votes are one-time workflow actions per set, so a survey
    # must never consume one.
    #
    # The three roles do NOT render the same grid. What is below is the RWG
    # shape; Sr. RWG and PIT override QUEUE_COLUMNS / QUEUE_TAB_LABELS with
    # their own. Surveying all three against one expected set filed FAILED rows
    # for columns each screen is correct not to have.
    # ------------------------------------------------------------------

    QUEUE_PAGE_HEADING = (By.XPATH, "//h1[normalize-space()='Review Queue']")
    QUEUE_SUBTITLE = (
        By.XPATH,
        "//*[not(*)][contains(normalize-space(),'provide structured feedback')]",
    )
    QUEUE_LOADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'Loading Review Queue')]",
    )
    QUEUE_FILTER_LABELS = ("Grade", "Subject", "Chapter", "Type")
    QUEUE_TAB_LABELS = (
        "All",
        "Pending Review",
        "Revision Needed",
        "Rejected",
        "Approved",
        "Published",
    )
    QUEUE_COLUMNS = (
        "Item Set ID",
        "Grade",
        "Subject & Chapter",
        "Item Count",
        "Submitted By",
        "Type",
        "Iteration",
        "Item Set Status",
        "Last Updated",
        "Last Review Submit Date",
        "Due On",
    )
    QUEUE_TABLE = (By.XPATH, "//table[.//th[contains(normalize-space(),'Item Set ID')]]")
    QUEUE_TABLE_HEADERS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item Set ID')]]//th",
    )
    QUEUE_TABLE_ROWS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item Set ID')]]//tbody/tr[.//td]",
    )

    # Opened item set (/review-queue/<id>)
    ITEM_SET_TITLE = (By.CSS_SELECTOR, "[class*='_title_']")
    ITEM_SET_BACK_BUTTON = (By.CSS_SELECTOR, "button[class*='_backBtn_']")
    ITEM_SET_FILTER_LABELS = ("Item Type", "Marks", "Bloom's Level")
    ITEM_SET_REVIEW_TAB_LABELS = ("All", "Review", "Approved", "Needs Revision", "Rejected")
    ITEM_SET_ITEM_COLUMNS = (
        "Item ID",
        "Item",
        "Status",
        "Typology",
        "Marks",
        "Bloom's Level",
        "Competency",
        "Learning Outcomes",
    )
    ITEM_SET_ITEM_TABLE = (By.XPATH, "//table[.//th[contains(normalize-space(),'Item ID')]]")
    ITEM_SET_ITEM_HEADERS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item ID')]]//th",
    )
    ITEM_SET_ITEM_ROWS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item ID')]]//tbody/tr[.//td]",
    )
    DOWNLOAD_QAR_REPORT_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(),'Download QAR Report')]",
    )

    FILTER_BUTTONS = (By.CSS_SELECTOR, "button[class*='_filterBtn_']")
    ROWS_PER_PAGE = (By.CSS_SELECTOR, "[role='combobox']")
    PREV_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='Previous page']")
    NEXT_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='Next page']")

    # Reviewer chrome — a shorter sidebar than the SME's or the teacher's.
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
    REVIEWER_NAV_ITEMS = ("Queue", "Home", "Support", "Settings")

    # --- Survey readers -------------------------------------------------

    @staticmethod
    def survey_xpath_literal(value):
        """Quote a label for XPath. 'Bloom's Level' contains an apostrophe,
        which would otherwise raise InvalidSelectorException out of the reader
        rather than recording one absent element."""
        text = str(value)
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        parts = "', \"'\", '".join(text.split("'"))
        return f"concat('{parts}')"

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
    def queue_tab_locator(cls, label):
        return (
            By.XPATH,
            f"//*[@role='tab'][starts-with(normalize-space(),{cls.survey_xpath_literal(label)})]",
        )

    @classmethod
    def queue_filter_locator(cls, label):
        return (
            By.XPATH,
            "//button[contains(@class,'_filterBtn_')]"
            f"[normalize-space()={cls.survey_xpath_literal(label)}]",
        )

    @classmethod
    def reviewer_nav_locator(cls, label):
        # Matched on the label span: each nav button also carries a hidden
        # tooltip span, so the button's textContent is tooltip+label run
        # together and an exact match on the button never fires.
        return (
            By.XPATH,
            "//button[contains(@class,'menu-button')]"
            f"[.//span[normalize-space()={cls.survey_xpath_literal(label)}]]",
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

    def wait_for_queue_to_load(self, timeout=60):
        """Wait for the queue's own content, not merely for its spinner to go.

        open_queue_module() returns while 'Loading Review Queue…' is still on
        screen, and the placeholder clears a few seconds *before* the tabs,
        grid and pagination paint. Waiting only on the placeholder therefore
        surveyed an empty shell and reported the whole queue missing — while a
        tab click moments later worked fine. Wait for the tablist and the grid.
        """
        try:
            self.wait_utils.until_condition(
                lambda driver: (
                    not driver.find_elements(*self.QUEUE_LOADING)
                    and driver.find_elements(By.CSS_SELECTOR, "[role='tablist']")
                    and driver.find_elements(*self.QUEUE_TABLE_ROWS)
                ),
                timeout=timeout,
            )
        except TimeoutException:
            # An empty queue legitimately has no rows; settle for the tablist.
            return bool(self.driver.find_elements(By.CSS_SELECTOR, "[role='tablist']"))
        return True

    def get_headers_text(self, locator):
        headers = []
        for element in self.driver.find_elements(*locator):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if text:
                headers.append(text)
        return headers

    def missing_queue_columns(self):
        headers = [h.casefold() for h in self.get_headers_text(self.QUEUE_TABLE_HEADERS)]
        return [c for c in self.QUEUE_COLUMNS if c.casefold() not in headers]

    def missing_item_set_item_columns(self):
        headers = [h.casefold() for h in self.get_headers_text(self.ITEM_SET_ITEM_HEADERS)]
        return [c for c in self.ITEM_SET_ITEM_COLUMNS if c.casefold() not in headers]

    def get_queue_row_count(self):
        return len(self.driver.find_elements(*self.QUEUE_TABLE_ROWS))

    def get_item_set_item_row_count(self):
        return len(self.driver.find_elements(*self.ITEM_SET_ITEM_ROWS))

    def is_queue_tab_active(self, label):
        try:
            state = self.driver.find_element(
                *self.queue_tab_locator(label)
            ).get_attribute("data-state")
        except WebDriverException:
            return False
        return state == "active"

    def switch_queue_tab(self, label, timeout=20):
        """Activate a queue tab and wait for it to report itself active.

        Read-only: tabs re-scope the listing and never cast a review vote.
        """
        self.click_element(self.queue_tab_locator(label))
        try:
            self.wait_utils.until_condition(
                lambda driver: self.is_queue_tab_active(label), timeout=timeout
            )
        except TimeoutException:
            return False
        return True
    YES_LOCATORS = [
        (By.XPATH, "//button[normalize-space()='Yes']"),
        (By.XPATH, "//*[self::label or self::button][contains(normalize-space(),'Yes')]"),
        (By.XPATH, "//input[@type='radio' and (@value='yes' or @value='true')]/following::label[1]"),
    ]

    # FIX #7: Split the expensive XPath union into two separate locators so the
    # first match short-circuits and avoids running both DOM traversals every call.
    _CRITERIA_YES_PRIMARY = (
        By.XPATH,
        "//*[normalize-space()='1st Version (Current)' or contains(normalize-space(),'Current Version')]"
        "/ancestor::*[.//*[contains(normalize-space(),'Evaluation Criteria') or contains(normalize-space(),'Criteria')] "
        "and .//*[self::button or self::label or self::div or self::span or self::input or @role='button' or @role='radio' or @role='checkbox']"
        "[normalize-space()='Y' or normalize-space()='Yes' or @data-value='Y' or @data-value='Yes' "
        "or @value='Y' or @value='Yes' or @aria-label='Y' or @aria-label='Yes' or @title='Y' or @title='Yes'][not(@disabled)]][1]"
        "//*[self::button or self::label or self::div or self::span or self::input or @role='button' or @role='radio' or @role='checkbox']"
        "[normalize-space()='Y' or normalize-space()='Yes' or @data-value='Y' or @data-value='Yes' "
        "or @value='Y' or @value='Yes' or @aria-label='Y' or @aria-label='Yes' or @title='Y' or @title='Yes'][not(@disabled)]",
    )
    _CRITERIA_YES_SECONDARY = (
        By.XPATH,
        "//*[contains(normalize-space(),'Evaluation Criteria') or contains(normalize-space(),'Item Response Sheet') "
        "or contains(normalize-space(),'Criteria')]"
        "/following::*[self::button or self::label or self::div or self::span or self::input or @role='button' or @role='radio' or @role='checkbox']"
        "[normalize-space()='Y' or normalize-space()='Yes' or @data-value='Y' or @data-value='Yes' "
        "or @value='Y' or @value='Yes' or @aria-label='Y' or @aria-label='Yes' or @title='Y' or @title='Yes'][not(@disabled)]",
    )
    # Kept for external callers that reference this name directly (e.g. approve_item_set_as_rwg tests).
    CURRENT_VERSION_CRITERIA_YES_CONTROLS = _CRITERIA_YES_PRIMARY

    CRITERIA_ROOT_JS = r"""
        // Prefer the actual "<Nth> Version (Current)" label as the anchor -
        // an item revised one or more times renders every prior version's
        // criteria panel on the same page (read-only), all inside the same
        // flat wrapper with no size difference to key off of. The version
        // label itself is the only reliable, always-present marker of
        // which panel is the current, editable one.
        const versionLabel = Array.from(document.querySelectorAll('*')).find(el => {
            const text = (el.innerText || el.textContent || '').trim();
            return /^\d+(st|nd|rd|th)\s+version\s*\(current\)$/i.test(text)
                && el.children.length === 0;
        });
        if (versionLabel) {
            let node = versionLabel;
            for (let i = 0; i < 12 && node; i++) {
                const text = node.innerText || '';
                if (text.includes('Item Response Sheet') && text.includes('Evaluation Criteria')) {
                    return node;
                }
                node = node.parentElement;
            }
        }
        // Fallback (no version label found - typically a first-ever review
        // with nothing else on the page to disambiguate from): smallest
        // block containing both signal phrases.
        const roots = Array.from(document.querySelectorAll('section, article, main, div'))
            .filter(element => {
                const text = element.innerText || '';
                return text.includes('Item Response Sheet') && text.includes('Evaluation Criteria');
            });
        roots.sort((left, right) =>
            left.getBoundingClientRect().height - right.getBoundingClientRect().height);
        return roots[0] || null;
        """

    NO_CONTROL_RELATIVE_XPATH = (
        ".//*[self::button or self::label or self::div or self::span or self::input "
        "or @role='button' or @role='radio' or @role='checkbox']"
        "[normalize-space()='N' or normalize-space()='No' or @data-value='N' or @data-value='No' "
        "or @value='N' or @value='No' or @aria-label='N' or @aria-label='No' or @title='N' or @title='No']"
        "[not(@disabled)]"
    )

    def get_criteria_root(self):
        """The smallest element wrapping both "Item Response Sheet" and
        "Evaluation Criteria" text - i.e. just the current, editable
        version's panel, not any earlier read-only version rendered
        alongside it (an item revised once or more, e.g. one already
        through RWG/SRRWG by the time it reaches PIT, shows several
        version panels on the same page). Page-wide XPath queries for "No"
        controls sweep every version's controls, wildly over-counting and
        making completion checks impossible to satisfy; scoping to this
        root first avoids that.
        """
        try:
            return self.driver.execute_script(self.CRITERIA_ROOT_JS)
        except Exception:
            return None

    def get_scoped_no_controls(self):
        root = self.get_criteria_root()
        if root is None:
            return self.driver.find_elements(*self.CURRENT_VERSION_CRITERIA_NO_CONTROLS)
        return root.find_elements(By.XPATH, self.NO_CONTROL_RELATIVE_XPATH)

    CURRENT_VERSION_CRITERIA_NO_CONTROLS = (
        By.XPATH,
        "("
        "//*[normalize-space()='1st Version (Current)' or contains(normalize-space(),'Current Version')]"
        "/ancestor::*[.//*[contains(normalize-space(),'Evaluation Criteria') or contains(normalize-space(),'Criteria')] "
        "and .//*[self::button or self::label or self::div or self::span or self::input or @role='button' or @role='radio' or @role='checkbox']"
        "[normalize-space()='N' or normalize-space()='No' or @data-value='N' or @data-value='No' "
        "or @value='N' or @value='No' or @aria-label='N' or @aria-label='No' or @title='N' or @title='No'][not(@disabled)]][1]"
        "//*[self::button or self::label or self::div or self::span or self::input or @role='button' or @role='radio' or @role='checkbox']"
        "[normalize-space()='N' or normalize-space()='No' or @data-value='N' or @data-value='No' "
        "or @value='N' or @value='No' or @aria-label='N' or @aria-label='No' or @title='N' or @title='No'][not(@disabled)]"
        ") | ("
        "//*[contains(normalize-space(),'Evaluation Criteria') or contains(normalize-space(),'Item Response Sheet') "
        "or contains(normalize-space(),'Criteria')]"
        "/following::*[self::button or self::label or self::div or self::span or self::input or @role='button' or @role='radio' or @role='checkbox']"
        "[normalize-space()='N' or normalize-space()='No' or @data-value='N' or @data-value='No' "
        "or @value='N' or @value='No' or @aria-label='N' or @aria-label='No' or @title='N' or @title='No'][not(@disabled)]"
        ")"
        " | //button[normalize-space()='N' or normalize-space()='No']"
        " | //*[self::button or self::label or self::span or @role='button' or @role='radio']"
        "[normalize-space()='N' or normalize-space()='No'][not(@disabled)]",
    )
    CURRENT_VERSION_CRITERIA_YES_FALLBACK = (
        By.XPATH,
        "(//*[contains(normalize-space(),'Evaluation Criteria') or contains(normalize-space(),'Item Response Sheet') "
        "or contains(normalize-space(),'Criteria')]/ancestor::*[1] | "
        "//*[contains(normalize-space(),'Evaluation Criteria') or contains(normalize-space(),'Item Response Sheet') "
        "or contains(normalize-space(),'Criteria')]/following::*)"
        "[self::button or self::label or self::div or self::span or self::input or @role='button' or @role='radio' or @role='checkbox']"
        "[not(@disabled)]"
        "[(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='y' "
        "or translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='yes' "
        "or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' yes ') "
        "or translate(normalize-space(@value), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='y' "
        "or translate(normalize-space(@data-value), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='y' "
        "or translate(normalize-space(@aria-label), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='y' "
        "or translate(normalize-space(@title), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='y' "
        "or translate(normalize-space(@value), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='yes' "
        "or translate(normalize-space(@data-value), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='yes' "
        "or translate(normalize-space(@aria-label), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='yes' "
        "or translate(normalize-space(@title), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='yes')]"
        " | //button[normalize-space()='Y' or normalize-space()='Yes']"
        " | //*[self::button or self::label or self::span or @role='button' or @role='radio']"
        "[normalize-space()='Y' or normalize-space()='Yes'][not(@disabled)]",
    )
    APPROVE_ITEM_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(),'Approve') and not(@disabled)]",
    )
    SEND_BACK_ITEM_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Mark for Revision') and not(@disabled)]"),
        (By.XPATH, "//button[normalize-space()='Revise' and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Send Back') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Needs Revision') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Revision') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Reject') and not(@disabled)]"),
    ]
    OPEN_REVISION_FORM_LOCATORS = [
        (By.XPATH, "//button[normalize-space()='Revise' and not(@disabled)]"),
        (By.XPATH, "//*[self::button or @role='button'][normalize-space()='Revise' and not(@disabled)]"),
    ]
    MARK_FOR_REVISION_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Mark for Revision') and not(@disabled)]"),
        (By.XPATH, "//*[self::button or @role='button'][contains(normalize-space(),'Mark for Revision') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Submit Revision') and not(@disabled)]"),
    ]
    REVISION_REMARK_LOCATORS = [
        (By.XPATH, "//textarea[contains(@placeholder,'comment') or contains(@placeholder,'remark') or contains(@placeholder,'reason') or contains(@aria-label,'comment') or contains(@aria-label,'remark')]"),
        (By.XPATH, "//input[contains(@placeholder,'comment') or contains(@placeholder,'remark') or contains(@placeholder,'reason') or contains(@aria-label,'comment') or contains(@aria-label,'remark')]"),
        (By.XPATH, "//*[contains(normalize-space(),'Comment') or contains(normalize-space(),'Remark') or contains(normalize-space(),'Reason')]/following::textarea[1]"),
        (By.XPATH, "//*[@contenteditable='true'][ancestor::*[contains(normalize-space(),'Comment') or contains(normalize-space(),'Remark') or contains(normalize-space(),'Reason')]]"),
        (By.XPATH, "//textarea[not(@disabled)]"),
        (By.XPATH, "//*[@contenteditable='true' and not(@disabled)]"),
    ]
    REVISION_COMMENT_TRIGGER_LOCATORS = [
        (
            By.XPATH,
            "//*[normalize-space()='1st Version (Current)']"
            "/ancestor::*[.//*[normalize-space()='Evaluation Criteria']][1]"
            "//*[self::button or @role='button'][.//*[name()='svg'] or contains(normalize-space(),'Comment')]",
        ),
        (
            By.XPATH,
            "//*[normalize-space()='1st Version (Current)']"
            "/ancestor::*[.//*[normalize-space()='Evaluation Criteria']][1]"
            "//*[self::button or @role='button'][last()]",
        ),
    ]
    ITEM_RESPONSE_SHEET = (
        By.XPATH,
        "//*[contains(normalize-space(),'Item Response Sheet') or contains(normalize-space(),'Mark Yes')]",
    )
    ITEM_DETAIL_LOADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'Loading item details')]",
    )
    SAVE_ITEM_REVIEW_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Save') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Approve') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Next') and not(@disabled)]"),
    ]
    CONFIRM_LOCATORS = [
        (
            By.XPATH,
            # Scope covers role='dialog' as well as the native <dialog>
            # element (matched via self::dialog and @aria-modal='true'),
            # since some overlays (e.g. the "Redirect for minor edits"
            # confirmation) use <dialog aria-modal="true"> with a class name
            # that doesn't contain "modal"/"Dialog" at all - the old
            # case-sensitive class-substring-only check silently matched
            # nothing for those, leaving the dialog open to intercept the
            # next click.
            "//*[self::dialog or @role='dialog' or @aria-modal='true' "
            "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'modal') "
            "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dialog') "
            "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'overlay')]"
            "//*[self::button or @role='button']"
            "[(normalize-space()='Approve' or normalize-space()='Authorise' "
            "or normalize-space()='Revise' or normalize-space()='Reject' "
            "or contains(normalize-space(),'Send for Revision') "
            "or contains(normalize-space(),'Mark for Revision') "
            "or contains(normalize-space(),'Redirect') "
            "or normalize-space()='Send Back' or normalize-space()='Confirm' or normalize-space()='Yes') "
            "and not(@disabled)]",
        ),
        (By.XPATH, "//button[normalize-space()='Confirm' or normalize-space()='Yes']"),
        (By.XPATH, "//button[contains(normalize-space(),'Submit') or contains(normalize-space(),'Done')]"),
    ]
    APPROVE_CONFIRM_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
            "//button[(normalize-space()='Approve' or normalize-space()='Confirm' or normalize-space()='Yes') "
            "and not(@disabled)]",
        ),
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
            "//button[contains(normalize-space(),'Approve') and not(@disabled)]",
        ),
        (
            By.XPATH,
            "//*[@aria-modal='true' or @role='alertdialog' "
            "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dialog') "
            "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'modal')]"
            "//*[self::button or @role='button']"
            "[contains(normalize-space(),'Confirm') or normalize-space()='Yes' "
            "or contains(normalize-space(),'Approve')][not(@disabled)]",
        ),
        (
            By.XPATH,
            "//*[self::button or @role='button']"
            "[(contains(normalize-space(),'Confirm') and contains(normalize-space(),'Approve')) "
            "or contains(normalize-space(),'Yes, Approve') "
            "or contains(normalize-space(),'Yes Approve')][not(@disabled)]",
        ),
    ]

    def open_queue_module(self):
        self.click_any_element(self.QUEUE_MENU_LOCATORS)
        self.wait_utils.until_visible(self.QUEUE_HEADING, timeout=30)

    def get_queue_body_text(self):
        self.open_queue_module()
        self.wait_utils.until_condition(
            lambda driver: "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=30,
        )
        return self.driver.find_element(By.TAG_NAME, "body").text

    def open_first_queue_item_set(self):
        queue_text = self.get_queue_body_text()
        item_set_ids = list(
            dict.fromkeys(
                re.findall(r"\bIS\d+(?:-[A-Za-z0-9]+)*\b", queue_text, re.IGNORECASE)
            )
        )
        if not item_set_ids:
            raise TimeoutException("No item set IDs were visible in the review queue.")

        last_error = None
        for item_set_id in item_set_ids:
            try:
                self.open_review_item_set(item_set_id)
                self.wait_utils.until_condition(
                    lambda driver: self.review_set_has_items(driver, item_set_id),
                    timeout=30,
                )
                return self.driver.find_element(By.TAG_NAME, "body").text
            except TimeoutException as error:
                last_error = error

        raise TimeoutException(
            "No populated item set could be opened from the review queue."
        ) from last_error

    def open_first_item_in_first_queue_set(self):
        set_text = self.open_first_queue_item_set()
        item_ids = re.findall(r"\bIS\d+(?:-[A-Za-z0-9]+)*-i\d+\b", set_text, re.IGNORECASE)
        if not item_ids:
            raise TimeoutException("The selected review set did not expose an item ID.")
        self.click_item(item_ids[0])
        return self.driver.find_element(By.TAG_NAME, "body").text

    @staticmethod
    def review_set_has_items(driver, item_set_id):
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if "Loading item details" in page_text or "Failed to load items" in page_text:
            return False
        return bool(
            re.search(
                rf"\b{re.escape(item_set_id)}-i\d+\b",
                page_text,
                re.IGNORECASE,
            )
        )

    @classmethod
    def is_review_item_set_loaded_without_id(cls, driver):
        page_text = driver.find_element(By.TAG_NAME, "body").text
        return any(
            marker in page_text
            for marker in cls.ITEM_SET_READY_SIGNALS
        )

    def is_submit_review_enabled(self):
        default_locator = (
            By.XPATH,
            "//button[contains(normalize-space(),'Submit') and contains(normalize-space(),'Review')]",
        )
        locators = getattr(self, "SUBMIT_REVIEW_LOCATORS", None) or [default_locator]
        for locator in locators:
            for button in self.driver.find_elements(*locator):
                try:
                    if (
                        button.is_displayed()
                        and button.is_enabled()
                        and not button.get_attribute("disabled")
                        and button.get_attribute("aria-disabled") != "true"
                    ):
                        return True
                except StaleElementReferenceException:
                    continue
        return False

    def search_item_set(self, item_set_id):
        # Search on the stable "IS<number>" prefix, not the full item_set_id -
        # this queue's search appears to do an exact/prefix match server-side,
        # and this environment can render an item's chapter-code segment
        # differently than the one captured right after upload (see
        # item_set_numeric_prefix()); searching the full (wrong-suffix) ID
        # then reliably returns zero results regardless of which reviewer
        # account is logged in.
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        last_error = None
        for _ in range(3):
            try:
                search_input = self.wait_utils.until_visible(self.SEARCH_INPUT, timeout=30)
                search_input.send_keys(Keys.CONTROL, "a")
                search_input.send_keys(Keys.DELETE)
                search_input.send_keys(numeric_prefix)
                search_input.send_keys(Keys.ENTER)
                break
            except StaleElementReferenceException as error:
                last_error = error
        else:
            raise last_error
        self.wait_utils.until_condition(
            lambda driver: numeric_prefix in driver.find_element(By.TAG_NAME, "body").text,
            timeout=30,
        )

    @staticmethod
    def item_set_target_locators(match_text):
        return [
            (
                By.XPATH,
                f"//*[self::a or self::button][contains(normalize-space(),'{match_text}')]",
            ),
            (
                By.XPATH,
                f"//tr[.//*[contains(normalize-space(),'{match_text}')] or contains(normalize-space(),'{match_text}')]",
            ),
            (
                By.XPATH,
                f"//*[contains(normalize-space(),'{match_text}')]/ancestor::*[@role='row' or self::tr][1]",
            ),
        ]

    def open_item_set_from_queue(self, item_set_id):
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        try:
            self.click_first_available_target(
                self.item_set_target_locators(item_set_id), timeout=8
            )
        except Exception:
            if numeric_prefix == item_set_id:
                raise
            # Full ID (with its chapter-code suffix) matched nothing - the
            # set may be rendered under a different chapter label in this
            # queue, so retry scoped to just the stable numeric prefix.
            self.click_first_available_target(
                self.item_set_target_locators(numeric_prefix), timeout=8
            )
        self.wait_utils.until_condition(
            lambda driver: self.is_review_item_set_ready(driver, item_set_id),
            timeout=15,
        )

    def is_review_item_set_ready(self, driver, item_set_id):
        page_text = driver.find_element(By.TAG_NAME, "body").text
        compact_page_text = re.sub(r"\s+", "", page_text)
        compact_item_set_id = re.sub(r"\s+", "", item_set_id)
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        if compact_item_set_id not in compact_page_text and numeric_prefix not in compact_page_text:
            return False
        return any(
            ready_signal in page_text
            for ready_signal in self.ITEM_SET_READY_SIGNALS
        ) or "/items/" in driver.current_url

    def click_first_available_target(self, locators, timeout=10):
        last_error = None
        for locator in locators:
            try:
                element = self.wait_utils.until_clickable(locator, timeout=timeout)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                self.pause_before_action()
                try:
                    element.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", element)
                return element
            except Exception as error:
                last_error = error
        raise last_error

    def open_queue_item_set(self, item_set_id):
        self.open_queue_module()
        self.search_item_set(item_set_id)
        self.open_item_set_from_queue(item_set_id)

    def open_review_item_set(self, item_set_id, item_set_url=""):
        try:
            self.open_queue_item_set(item_set_id)
            return
        except TimeoutException:
            pass

        numeric_id = re.match(r"IS(\d+)", item_set_id, re.IGNORECASE)
        if numeric_id:
            current_url = urlsplit(self.driver.current_url)
            review_url = (
                f"{current_url.scheme}://{current_url.netloc}"
                f"/review-queue/{numeric_id.group(1)}"
            )
        elif item_set_url:
            review_url = item_set_url
        else:
            raise TimeoutException(
                f"Could not derive a review URL for item set {item_set_id}."
            )

        last_error = None
        max_attempts = 3
        for attempt in range(max_attempts):
            self.driver.get(review_url) if attempt == 0 else self.driver.refresh()
            try:
                self.wait_utils.until_condition(
                    lambda driver: self.is_review_item_set_ready(driver, item_set_id),
                    timeout=15,
                )
                return
            except TimeoutException as error:
                last_error = error
                if attempt < max_attempts - 1:
                    # A brief backend lag right after a review-stage handoff
                    # (e.g. SRRWG -> PIT) can surface as "Failed to load items
                    # for this item set."; a short pause before refreshing
                    # covers that without masking a real "not allotted" case,
                    # which callers (e.g. the PIT quorum loop) treat as
                    # expected and skip to the next candidate reviewer.
                    sleep(3)
        raise TimeoutException(
            f"Review item set {item_set_id} did not become available for this role."
        ) from last_error

    LOOSE_ITEM_ROW_MATCH_JS = r"""
        const numericPrefix = arguments[0].toLowerCase();
        const itemNumber = arguments[1];
        const suffixPattern = new RegExp('i' + itemNumber + '(?!\\d)', 'i');
        const row = Array.from(document.querySelectorAll('table tbody tr')).find(candidate => {
            const firstCell = candidate.querySelector('td');
            const text = (firstCell?.innerText || firstCell?.textContent || '').trim();
            return text.toLowerCase().includes(numericPrefix) && suffixPattern.test(text);
        });
        if (!row) return null;
        const cells = row.querySelectorAll('td');
        const clickable = row.querySelector('a, button') || row;
        return {
            link: clickable,
            title: (cells[1]?.innerText || cells[1]?.textContent || '').trim(),
        };
        """

    def find_item_row_loosely(self, item_id):
        """Find an item's row by its stable 'IS<number>' + 'i<item-number>'
        components, ignoring the chapter-code segment in between.

        Some environments render an item's chapter-code differently on this
        queue page (e.g. "...-CH-1-i1") than the ID captured right after
        upload (e.g. "...-Ch29-i1") - see
        BaseReviewQueuePage.item_set_numeric_prefix(). An exact item_id
        match then never finds the row even though it's the same item.
        """
        numeric_prefix = self.item_set_numeric_prefix(item_id)
        item_number_match = re.search(r"-i(\d+)$", item_id, re.IGNORECASE)
        if not item_number_match:
            return None
        result = self.driver.execute_script(
            self.LOOSE_ITEM_ROW_MATCH_JS, numeric_prefix, item_number_match.group(1)
        )
        return result

    def click_item(self, item_id):
        loose_match = self.find_item_row_loosely(item_id)
        if loose_match:
            expected_title = loose_match["title"]
            try:
                loose_match["link"].click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", loose_match["link"])
        else:
            expected_title = self.driver.execute_script(
                """
                const itemId = arguments[0].trim().toLowerCase();
                const row = Array.from(document.querySelectorAll('table tbody tr'))
                    .find(candidate => {
                        const firstCell = candidate.querySelector('td');
                        const text = (firstCell?.innerText || firstCell?.textContent || '')
                            .trim().toLowerCase();
                        return text.includes(itemId);
                    });
                if (!row) return '';
                const cells = row.querySelectorAll('td');
                return (cells[1]?.innerText || cells[1]?.textContent || '').trim();
                """,
                item_id,
            )
            item_link = (
                By.XPATH,
                f"//*[self::a or self::button][contains(normalize-space(),'{item_id}')]",
            )
            try:
                self.wait_utils.until_clickable(item_link, timeout=8).click()
            except TimeoutException:
                self.search_visible_table(item_id)
                self.wait_utils.until_clickable(item_link, timeout=20).click()
        self.current_item_id = item_id
        self.current_item_set_id = item_id.rsplit("-i", 1)[0]
        self.current_item_title = expected_title

        def intended_item_is_ready(driver):
            if not self.is_review_item_ready(driver):
                return False
            if not expected_title:
                return True
            open_title = self.get_open_item_title(expected_title)
            return (
                re.sub(r"\s+", " ", expected_title).strip().casefold()
                == re.sub(r"\s+", " ", open_title).strip().casefold()
            )

        try:
            self.wait_utils.until_condition(intended_item_is_ready, timeout=15)
        except TimeoutException:
            # Some review builds render the split view with the first card
            # selected before applying the clicked row selection.  Re-select
            # the exact question card and verify its title before touching IRS.
            if not expected_title or not self.click_left_item_by_title(expected_title):
                raise TimeoutException(
                    f"Review split view did not open the intended item {item_id}."
                )
            self.wait_utils.until_condition(intended_item_is_ready, timeout=30)

    def is_review_item_ready(self, driver):
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if not self.wait_utils.is_visible(self.ITEM_RESPONSE_SHEET, timeout=1):
            return False
        progress_counts = re.findall(r"(\d+)\s*/\s*(\d+)", page_text)
        if any(int(total) > 0 for _, total in progress_counts):
            return True
        if "Loading item details" in page_text or "No item selected" in page_text:
            return False
        return bool(self.get_visible_yes_controls(driver))

    def search_visible_table(self, search_text):
        search_input = self.wait_utils.until_visible(self.SEARCH_INPUT, timeout=20)
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        search_input.send_keys(search_text)
        search_input.send_keys(Keys.ENTER)
        self.wait_utils.until_condition(
            lambda driver: search_text in re.sub(
                r"\s+",
                "",
                driver.find_element(By.TAG_NAME, "body").text,
            ),
            timeout=30,
        )

    def clear_visible_table_search(self):
        try:
            search_input = self.wait_utils.until_visible(self.SEARCH_INPUT, timeout=5)
            search_input.send_keys(Keys.CONTROL, "a")
            search_input.send_keys(Keys.DELETE)
            search_input.send_keys(Keys.ENTER)
            self.pause_before_action()
        except Exception:
            return False
        return True

    def click_yes_for_open_item(self):
        self.click_any_element(self.YES_LOCATORS)

    def mark_all_criteria_yes(self):
        self.wait_utils.until_condition(
            lambda driver: self.has_visible_yes_criteria_controls(driver),
            timeout=30,
        )

        # FIX #1: Added sleep(0.3) after each scroll so the DOM has time to
        # react before the next iteration re-checks and re-clicks controls.
        for _ in range(35):
            if self.are_all_criteria_marked_yes(self.driver):
                return

            self.click_first_yes_for_each_visible_section()
            self.click_all_visible_yes_controls()
            self.scroll_criteria_panel()
            sleep(0.3)

        self.wait_utils.until_condition(self.are_all_criteria_marked_yes, timeout=30)

    def get_visible_yes_controls(self, driver=None):
        # FIX #7: Use the split locators so the cheaper primary XPath is tried
        # first; only fall back to the secondary (and then the fallback) when
        # no elements are found, avoiding two full DOM traversals on every call.
        driver = driver or self.driver
        controls = driver.find_elements(*self._CRITERIA_YES_PRIMARY)
        if controls:
            return controls
        controls = driver.find_elements(*self._CRITERIA_YES_SECONDARY)
        if controls:
            return controls
        return driver.find_elements(*self.CURRENT_VERSION_CRITERIA_YES_FALLBACK)

    def click_all_visible_yes_controls(self):
        clicked_any = False
        for yes_button in self.get_visible_yes_controls():
            try:
                if not yes_button.is_displayed() or not yes_button.is_enabled():
                    continue
                if not self.is_yes_control_candidate(yes_button):
                    continue
                if self.is_yes_control_selected(yes_button):
                    continue
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    yes_button,
                )
                sleep(0.2)
                try:
                    yes_button.click()
                except WebDriverException:
                    pass

                if not self.is_yes_control_selected(yes_button):
                    try:
                        self.driver.execute_script("arguments[0].click();", yes_button)
                    except Exception as exc:
                        # FIX #2: Log JS-click failures instead of silently swallowing them.
                        logger.debug("JS click failed for yes_button: %s", exc)

                if not self.is_yes_control_selected(yes_button):
                    result = self.driver.execute_script(
                        """
                        const control = arguments[0];
                        const input = control.querySelector('input[type="radio"], input[type="checkbox"]');
                        if (input) {
                            input.checked = true;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            return true;
                        }
                        const htmlFor = control.getAttribute('for');
                        if (htmlFor) {
                            const linked = document.getElementById(htmlFor);
                            if (linked) {
                                linked.checked = true;
                                linked.dispatchEvent(new Event('input', { bubbles: true }));
                                linked.dispatchEvent(new Event('change', { bubbles: true }));
                                return true;
                            }
                        }
                        if (control.tagName.toLowerCase() === 'input') {
                            control.checked = true;
                            control.dispatchEvent(new Event('input', { bubbles: true }));
                            control.dispatchEvent(new Event('change', { bubbles: true }));
                            return true;
                        }
                        const label = control.closest('label');
                        if (label) {
                            const linkedInput = label.querySelector('input[type="radio"], input[type="checkbox"]');
                            if (linkedInput) {
                                linkedInput.checked = true;
                                linkedInput.dispatchEvent(new Event('input', { bubbles: true }));
                                linkedInput.dispatchEvent(new Event('change', { bubbles: true }));
                                return true;
                            }
                        }
                        return false;
                        """,
                        yes_button,
                    )
                    # FIX #2: Log when even the JS fallback could not select the control.
                    if not result:
                        logger.debug(
                            "All three click strategies failed for yes_button; "
                            "control may be decorative or not yet interactive."
                        )

                if self.is_yes_control_selected(yes_button):
                    clicked_any = True
                    continue
                continue
            except StaleElementReferenceException:
                return True
            except NoSuchWindowException:
                raise
        return clicked_any

    def click_first_yes_for_each_visible_section(self):
        return self.driver.execute_script(
            """
            const isYes = (control) => {
                if (!control || control.disabled || control.getAttribute('aria-disabled') === 'true') return false;
                const text = (control.innerText || control.textContent || '').trim();
                const value = (control.value || '').trim();
                const dataValue = (control.getAttribute('data-value') || '').trim();
                const aria = (
                    control.getAttribute('aria-label') ||
                    control.getAttribute('title') ||
                    ''
                ).trim();
                if (/^(N\\/A|NA|Not Applicable)$/i.test(text) || /^(N\\/A|NA|Not Applicable)$/i.test(aria)) return false;
                return /^(Y|Yes)$/i.test(text) || /^(Y|Yes)$/i.test(value) || /^(Y|Yes)$/i.test(dataValue) || /^(Y|Yes)$/i.test(aria) || /Mark\\s+Yes/i.test(aria) || /Mark\\s+all\\s+as\\s+Y/i.test(aria);
            };
            const isSelected = (control) => {
                const className = String(control.className || '').toLowerCase();
                const htmlFor = control.getAttribute('for');
                const linkedInput = htmlFor ? document.getElementById(htmlFor) : null;
                const nestedInput = control.querySelector &&
                    control.querySelector('input[type="radio"], input[type="checkbox"]');
                const bg = getComputedStyle(control).backgroundColor;
                return Boolean((linkedInput && linkedInput.checked) ||
                    (nestedInput && nestedInput.checked) ||
                    control.checked ||
                    control.getAttribute('aria-pressed') === 'true' ||
                    control.getAttribute('aria-checked') === 'true' ||
                    ['checked', 'active', 'selected'].includes(control.getAttribute('data-state')) ||
                    className.includes('selected') ||
                    className.includes('active') ||
                    className.includes('checked') ||
                    className.includes('pressed') ||
                    className.includes('bg-green') ||
                    className.includes('text-white') ||
                    bg.includes('22, 163, 74') ||
                    bg.includes('34, 197, 94') ||
                    bg.includes('0, 128, 0'));
            };
            const clickControl = (control) => {
                control.scrollIntoView({block: 'center', inline: 'center'});
                control.click();
                const htmlFor = control.getAttribute('for');
                const linkedInput = htmlFor ? document.getElementById(htmlFor) : null;
                const nestedInput = control.querySelector &&
                    control.querySelector('input[type="radio"], input[type="checkbox"]');
                const input = linkedInput || nestedInput ||
                    (['radio', 'checkbox'].includes(control.type) ? control : null);
                if (input && !input.checked) {
                    input.checked = true;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            };
            const criteriaRoot = Array.from(document.querySelectorAll('section, article, main, div'))
                .filter((element) => {
                    const text = element.innerText || '';
                    return text.includes('Item Response Sheet') && text.includes('Evaluation Criteria');
                })
                .sort((left, right) => left.getBoundingClientRect().height - right.getBoundingClientRect().height)[0] ||
                document.body;
            const sectionRows = Array.from(criteriaRoot.querySelectorAll('tr, [role="row"], div'))
                .filter((row) => {
                    const rect = row.getBoundingClientRect();
                    const text = (row.innerText || '').trim();
                    const criterionNumbers = text.match(/\\b\\d+\\.\\s+/g) || [];
                    return rect.width > 0 &&
                        rect.height > 0 &&
                        criterionNumbers.length === 1 &&
                        /\\bY\\b/.test(text) &&
                        /\\bN\\b/.test(text) &&
                        /\\bNA\\b/.test(text);
                })
                .sort((left, right) => left.getBoundingClientRect().top - right.getBoundingClientRect().top);
            let clicked = 0;
            for (const row of sectionRows) {
                const yesControls = Array.from(
                    row.querySelectorAll('button, label, input, [role="button"], [role="radio"], [role="checkbox"], span, div')
                ).filter(isYes)
                    .sort((left, right) => left.getBoundingClientRect().left - right.getBoundingClientRect().left);
                const firstYes = yesControls[0];
                if (!firstYes || isSelected(firstYes)) continue;
                clickControl(firstYes);
                clicked += 1;
            }
            return clicked;
            """
        )

    def scroll_criteria_panel(self):
        self.driver.execute_script(
            """
            const roots = Array.from(document.querySelectorAll('section, article, main, div'))
                .filter((element) => {
                    const text = element.innerText || '';
                    return text.includes('Item Response Sheet') && text.includes('Evaluation Criteria');
                });
            const scroller = roots
                .flatMap((root) => [root, ...root.querySelectorAll('div')])
                .filter((element) => element.scrollHeight > element.clientHeight + 20)
                .sort((left, right) => (right.scrollHeight - right.clientHeight) - (left.scrollHeight - left.clientHeight))[0];
            if (scroller) {
                scroller.scrollTop += Math.floor(scroller.clientHeight * 0.75);
                return true;
            }
            window.scrollBy(0, Math.floor(window.innerHeight * 0.65));
            return false;
            """
        )

    def is_yes_control_candidate(self, control):
        return self.driver.execute_script(
            """
            const control = arguments[0];
            const text = (control.innerText || control.textContent || '').trim();
            const value = (control.value || '').trim();
            const dataValue = (control.getAttribute('data-value') || '').trim();
            const aria = (
                control.getAttribute('aria-label') ||
                control.getAttribute('title') ||
                ''
            ).trim();
            if (/^(N\\/A|NA|Not Applicable)$/i.test(text) || /^(N\\/A|NA|Not Applicable)$/i.test(aria)) return false;
            return /^(Y|Yes)$/i.test(text) || /^(Y|Yes)$/i.test(value) || /^(Y|Yes)$/i.test(dataValue) || /^(Y|Yes)$/i.test(aria) || /Mark\\s+Yes/i.test(aria) || /Mark\\s+all\\s+as\\s+Y/i.test(aria);
            """,
            control,
        )

    def mark_first_criterion_no(self):
        self.wait_utils.until_condition(
            lambda driver: self.has_visible_no_criteria_controls(driver),
            timeout=30,
        )
        for no_control in self.driver.find_elements(*self.CURRENT_VERSION_CRITERIA_NO_CONTROLS):
            try:
                if not no_control.is_displayed() or not no_control.is_enabled():
                    continue
                self.driver.execute_script(
                    """
                    arguments[0].scrollIntoView({block: 'center'});
                    arguments[0].click();
                    """,
                    no_control,
                )
                return
            except StaleElementReferenceException:
                continue
        raise TimeoutException("No visible enabled No criterion was available for revision.")

    def are_all_criteria_marked_no(self, driver):
        # Scoped to just the current version's root, not the whole page -
        # a page-wide "X Yes ... Y No" regex search can match an unrelated
        # summary/counter elsewhere on the page (observed: matched (5, 0)
        # while the real current-version tally was ~24 items), which would
        # either falsely short-circuit this check or just be noise.
        root = self.get_criteria_root()
        root_text = (
            root.text if root is not None else driver.find_element(By.TAG_NAME, "body").text
        )
        page_text = re.sub(r"\s+", " ", root_text)
        summary_match = re.search(
            r"(\d+)\s+Yes\b.*?\b(\d+)\s+No\b",
            page_text,
            re.IGNORECASE,
        )
        if summary_match:
            yes_count = int(summary_match.group(1))
            no_count = int(summary_match.group(2))
            if yes_count == 0 and no_count > 0:
                return True

        no_controls = self.get_scoped_no_controls()
        if not no_controls:
            return False
        visible_no_controls = 0
        for control in no_controls:
            try:
                if not control.is_displayed():
                    continue
                # An item that's already been revised once or more (e.g. a
                # PIT-stage item that already went through RWG/SRRWG
                # revision rounds) renders earlier versions' criteria
                # panels alongside the current one, read-only. Those
                # disabled "No" controls can never be selected, so counting
                # them here would make this check impossible to satisfy -
                # only the current, editable version's controls count.
                if not control.is_enabled():
                    continue
                if not self.is_no_control_candidate(control):
                    continue
                visible_no_controls += 1
                if not self.is_yes_control_selected(control):
                    return False
            except StaleElementReferenceException:
                return False
        if visible_no_controls == 0:
            return False
        return True

    def is_no_control_candidate(self, control):
        return self.driver.execute_script(
            """
            const control = arguments[0];
            // Some review pages render read-only status badges/history
            // pills that happen to contain the literal text "No"/"N" (a
            // small summary label, or a version-history cell showing what
            // a prior reviewer recorded) alongside the actual interactive
            // toggle. Clicking those never changes anything since they
            // were never meant to be clickable - exclude known decorative
            // class-name patterns so only genuine controls remain.
            const cls = (control.className || '').toString();
            if (/_statLabel_|_pill_|_verCell_|statusLabel|readonly|read-only/i.test(cls)) {
                return false;
            }
            const values = [
                control.innerText || control.textContent || '',
                control.value || '',
                control.getAttribute('data-value') || '',
                control.getAttribute('aria-label') || '',
                control.getAttribute('title') || '',
            ].map(value => value.trim());
            return values.some(value => /^(N|No)$/i.test(value));
            """,
            control,
        )

    def click_all_visible_no_controls(self):
        clicked_any = False
        for no_button in self.get_scoped_no_controls():
            try:
                if not no_button.is_displayed() or not no_button.is_enabled():
                    continue
                if not self.is_no_control_candidate(no_button):
                    continue
                if self.is_yes_control_selected(no_button):
                    continue
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    no_button,
                )
                sleep(0.2)
                try:
                    no_button.click()
                except WebDriverException:
                    self.driver.execute_script("arguments[0].click();", no_button)
                if not self.is_yes_control_selected(no_button):
                    self.driver.execute_script("arguments[0].click();", no_button)
                clicked_any = clicked_any or self.is_yes_control_selected(no_button)
            except StaleElementReferenceException:
                return True
            except NoSuchWindowException:
                raise
        return clicked_any

    def click_first_no_for_each_visible_section(self):
        return self.driver.execute_script(
            """
            const isNo = control => {
                if (!control || control.disabled
                    || control.getAttribute('aria-disabled') === 'true') return false;
                const values = [
                    control.innerText || control.textContent || '',
                    control.value || '',
                    control.getAttribute('data-value') || '',
                    control.getAttribute('aria-label') || '',
                    control.getAttribute('title') || '',
                ].map(value => value.trim());
                return values.some(value => /^(N|No)$/i.test(value));
            };
            const criteriaRoot = Array.from(
                document.querySelectorAll('section, article, main, div')
            ).filter(element => {
                const text = element.innerText || '';
                return text.includes('Item Response Sheet')
                    && text.includes('Evaluation Criteria');
            }).sort((left, right) =>
                left.getBoundingClientRect().height - right.getBoundingClientRect().height
            )[0] || document.body;
            const sectionRows = Array.from(
                criteriaRoot.querySelectorAll('tr, [role="row"], div')
            ).filter(row => {
                const rect = row.getBoundingClientRect();
                const text = (row.innerText || '').trim();
                const sectionNumbers = text.match(/\\b\\d+\\.\\s+/g) || [];
                return rect.width > 0
                    && rect.height > 0
                    && sectionNumbers.length === 1
                    && /\bY\b/.test(text)
                    && /\bN\b/.test(text)
                    && /\bNA\b/.test(text);
            }).sort((left, right) =>
                left.getBoundingClientRect().top - right.getBoundingClientRect().top
            );
            let clicked = 0;
            for (const row of sectionRows) {
                const noControl = Array.from(row.querySelectorAll(
                    'button, label, input, [role="button"], [role="radio"], '
                    + '[role="checkbox"], span, div'
                )).filter(isNo).sort((left, right) =>
                    left.getBoundingClientRect().left - right.getBoundingClientRect().left
                )[0];
                if (!noControl) continue;
                noControl.scrollIntoView({block: 'center', inline: 'center'});
                noControl.click();
                clicked += 1;
            }
            return clicked;
            """
        )

    def mark_all_criteria_no(self):
        self.wait_utils.until_condition(
            lambda driver: self.has_visible_no_criteria_controls(driver),
            timeout=45,
        )

        for _ in range(60):
            if self.are_all_criteria_marked_no(self.driver):
                return

            self.click_first_no_for_each_visible_section()
            self.click_all_visible_no_controls()
            self.scroll_criteria_panel()
            sleep(0.3)

        try:
            self.wait_utils.until_condition(self.are_all_criteria_marked_no, timeout=45)
        except TimeoutException:
            self.log_criteria_diagnostic_state()
            raise

    def log_criteria_diagnostic_state(self):
        """One-shot diagnostic dump for mark_all_criteria_no() failures.

        Logs enough about the actual "No" controls on the page (count,
        displayed/enabled state, and any Yes/No summary text) to tell apart
        a locator/scoping problem from a genuine UI issue, without having
        to reproduce the failure interactively.
        """
        try:
            root = self.get_criteria_root()
            try:
                dump_dir = Path(__file__).resolve().parents[2] / "screenshots"
                dump_dir.mkdir(parents=True, exist_ok=True)
                dump_path = dump_dir / "criteria_root_dump.html"
                full_html = self.driver.execute_script(
                    "return arguments[0] ? arguments[0].outerHTML : "
                    "document.body.outerHTML;",
                    root,
                )
                dump_path.write_text(full_html or "", encoding="utf-8")
                logger.warning(
                    "mark_all_criteria_no diagnostic: full criteria root HTML "
                    "dumped to %s (%d chars)",
                    dump_path,
                    len(full_html or ""),
                )
            except Exception as dump_error:
                logger.warning(
                    "mark_all_criteria_no diagnostic: HTML dump failed: %s",
                    dump_error,
                )
            buttons_near_no = self.driver.execute_script(
                r"""
                const root = arguments[0] || document.body;
                const isNoText = t => /^(N|No)$/i.test((t || '').trim());
                const rows = Array.from(root.querySelectorAll('tr, [role="row"], div'))
                    .filter(row => {
                        const text = row.innerText || '';
                        return /\bY\b/.test(text) && /\bN\b/.test(text);
                    });
                const found = [];
                for (const row of rows.slice(0, 3)) {
                    const buttons = Array.from(
                        row.querySelectorAll('button, [role="button"], input, [role="radio"]')
                    );
                    for (const b of buttons) {
                        found.push({
                            tag: b.tagName,
                            cls: (b.className || '').toString().slice(0, 100),
                            text: (b.innerText || '').trim().slice(0, 30),
                            ariaLabel: b.getAttribute('aria-label'),
                            outerHTML: b.outerHTML.slice(0, 300),
                        });
                    }
                }
                return found.slice(0, 15);
                """,
                root,
            )
            logger.warning(
                "mark_all_criteria_no diagnostic: buttons/inputs found near Y/N rows: %s",
                buttons_near_no,
            )
            controls = self.get_scoped_no_controls()
            logger.warning(
                "mark_all_criteria_no diagnostic: %d matched No-control(s) (scoped)",
                len(controls),
            )
            for index, control in enumerate(controls):
                try:
                    logger.warning(
                        "  [%d] tag=%s displayed=%s enabled=%s text=%r "
                        "is_no_candidate=%s is_selected=%s",
                        index,
                        control.tag_name,
                        control.is_displayed(),
                        control.is_enabled(),
                        control.text,
                        self.is_no_control_candidate(control),
                        self.is_yes_control_selected(control)
                        if control.is_displayed()
                        else "n/a",
                    )
                    if index < 2:
                        outer_html = self.driver.execute_script(
                            "return arguments[0].outerHTML;", control
                        )
                        parent_html = self.driver.execute_script(
                            "return arguments[0].parentElement ? "
                            "arguments[0].parentElement.outerHTML : null;",
                            control,
                        )
                        logger.warning(
                            "  [%d] outerHTML=%s",
                            index,
                            (outer_html or "")[:600],
                        )
                        logger.warning(
                            "  [%d] parentOuterHTML=%s",
                            index,
                            (parent_html or "")[:900],
                        )
                except StaleElementReferenceException:
                    logger.warning("  [%d] stale element", index)
            page_text = re.sub(
                r"\s+",
                " ",
                self.driver.execute_script(
                    "return document.body.innerText || document.body.textContent || '';"
                ),
            )
            summary_match = re.search(
                r"(\d+)\s+Yes\b.*?\b(\d+)\s+No\b", page_text, re.IGNORECASE
            )
            logger.warning(
                "mark_all_criteria_no diagnostic: Yes/No summary match=%s",
                summary_match.groups() if summary_match else None,
            )
        except Exception as diagnostic_error:
            logger.warning(
                "mark_all_criteria_no diagnostic logging itself failed: %s",
                diagnostic_error,
            )

    def has_visible_yes_criteria_controls(self, driver):
        # get_visible_yes_controls already runs 3 XPath queries that require
        # elements to be in the DOM; a redundant is_displayed() loop adds latency
        # without benefit.  Any non-empty result means controls are present.
        try:
            return bool(self.get_visible_yes_controls(driver))
        except StaleElementReferenceException:
            return False

    def has_visible_no_criteria_controls(self, driver):
        for control in self.get_scoped_no_controls():
            try:
                if control.is_displayed():
                    return True
            except StaleElementReferenceException:
                continue
        return False

    def enter_revision_remark_if_available(self, remark):
        if len(remark) <= 50:
            remark = (
                f"{remark} Please revise this teacher contributed item because the selected "
                "criterion was marked No by reviewer automation."
            )

        def fill_visible_remark():
            for locator in self.REVISION_REMARK_LOCATORS:
                try:
                    remark_input = self.wait_utils.until_visible(locator, timeout=3)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        remark_input,
                    )
                    self.pause_before_action()
                    if remark_input.tag_name.lower() in {"textarea", "input"}:
                        remark_input.clear()
                        remark_input.send_keys(remark)
                        entered_text = remark_input.get_attribute("value") or ""
                    else:
                        entered_text = self.driver.execute_script(
                            """
                            const input = arguments[0];
                            const value = arguments[1];
                            input.innerHTML = '';
                            input.textContent = value;
                            input.dispatchEvent(new InputEvent('input', {
                                bubbles: true,
                                inputType: 'insertText',
                                data: value,
                            }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            return (input.innerText || input.textContent || '').trim();
                            """,
                            remark_input,
                            remark,
                        )
                    if len(entered_text.strip()) > 50:
                        return True
                except Exception:
                    continue
            return False

        # Selecting N can render the remark box automatically.  Fill that box
        # before clicking any comment trigger so the active question stays put.
        if fill_visible_remark():
            return True
        if self.open_revision_comment_box_if_available() and fill_visible_remark():
            return True
        return False

    def open_revision_comment_box_if_available(self):
        for locator in self.REVISION_COMMENT_TRIGGER_LOCATORS:
            for trigger in self.driver.find_elements(*locator):
                try:
                    if not trigger.is_displayed() or not trigger.is_enabled():
                        continue
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
                    self.pause_before_action()
                    self.driver.execute_script("arguments[0].click();", trigger)
                    if any(
                        self.wait_utils.is_visible(remark_locator, timeout=2)
                        for remark_locator in self.REVISION_REMARK_LOCATORS
                    ):
                        return True
                except Exception:
                    continue
        return False

    def open_revision_form(self):
        for locator in self.OPEN_REVISION_FORM_LOCATORS:
            try:
                revise_button = self.wait_utils.until_clickable(locator, timeout=10)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    revise_button,
                )
                self.pause_before_action()
                try:
                    revise_button.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", revise_button)
                self.wait_utils.until_condition(
                    lambda driver: any(
                        self.wait_utils.is_visible(remark_locator, timeout=1)
                        for remark_locator in self.REVISION_REMARK_LOCATORS
                    ),
                    timeout=15,
                )
                return True
            except Exception:
                continue
        return False

    def is_yes_control_selected(self, control):
        return self.driver.execute_script(
            """
            const control = arguments[0];
            const className = String(control.className || '').toLowerCase();
            const ariaPressed = control.getAttribute('aria-pressed');
            const ariaChecked = control.getAttribute('aria-checked');
            const dataState = control.getAttribute('data-state');
            const htmlFor = control.getAttribute('for');
            const linkedInput = htmlFor ? document.getElementById(htmlFor) : null;
            const nestedInput = control.querySelector &&
                control.querySelector('input[type="radio"], input[type="checkbox"]');
            const bg = getComputedStyle(control).backgroundColor;
            return Boolean((linkedInput && linkedInput.checked) ||
                (nestedInput && nestedInput.checked) ||
                ariaPressed === 'true' ||
                ariaChecked === 'true' ||
                dataState === 'checked' ||
                dataState === 'active' ||
                dataState === 'selected' ||
                className.includes('selected') ||
                className.includes('active') ||
                className.includes('checked') ||
                className.includes('pressed') ||
                className.includes('bg-green') ||
                className.includes('text-white') ||
                bg.includes('22, 163, 74') ||
                bg.includes('34, 197, 94') ||
                bg.includes('0, 128, 0'));
            """,
            control,
        )

    def are_all_criteria_completed(self, driver):
        # Use JS innerText so this works in headless Chrome where body.text is empty.
        page_text = re.sub(
            r"\s+", " ",
            driver.execute_script("return document.body.innerText || document.body.textContent || '';"),
        )
        progress_counts = re.findall(r"\b(\d+)\s*/\s*(\d+)\b", page_text)
        valid_progress_counts = [
            (int(done), int(total))
            for done, total in progress_counts
            if int(total) > 0
        ]
        if valid_progress_counts:
            return all(done == total for done, total in valid_progress_counts)

        # FIX #3: When no Yes controls are visible at all the criteria panel
        # is still loading or uses a layout the locators cannot reach.  Return
        # False (not complete) rather than True, and raise a distinct error if
        # callers need to distinguish "not found" from "found but incomplete".
        visible_yes_controls = 0
        for control in self.get_visible_yes_controls(driver):
            try:
                if not control.is_displayed():
                    continue
                visible_yes_controls += 1
                if not self.is_yes_control_selected(control):
                    return False
            except StaleElementReferenceException:
                return False

        if visible_yes_controls == 0:
            # No controls found: criteria panel is not ready yet.
            return False
        return True

    def are_all_criteria_marked_yes(self, driver):
        if not self.are_all_criteria_completed(driver):
            return False

        # FIX #4: Scope the "No count" search to the criteria summary line only
        # (e.g. "3 Yes  0 No  1 NA") to avoid matching unrelated UI text such
        # as "1 No items found" or navigation labels that contain the word "No".
        # Use JS innerText so this works in headless Chrome where body.text is empty.
        page_text = re.sub(
            r"\s+", " ",
            driver.execute_script("return document.body.innerText || document.body.textContent || '';"),
        )

        # Pattern: a summary line that contains both Yes and No counts together,
        # typical of IRS progress indicators like "3 Yes · 0 No · 1 NA".
        summary_match = re.search(
            r"(\d+)\s+Yes\b.*?\b(\d+)\s+No\b",
            page_text,
        )
        if summary_match:
            yes_count = int(summary_match.group(1))
            no_count = int(summary_match.group(2))
            return yes_count > 0 and no_count == 0

        # Fallback: look for a standalone "N No" pattern but only when it is
        # immediately preceded or followed by a Yes/NA count on the same line,
        # which strongly implies it is a criteria-summary context.
        for line in page_text.splitlines():
            line = line.strip()
            if re.search(r"\bYes\b", line) and re.search(r"\bNo\b", line):
                yes_match = re.search(r"\b(\d+)\s+Yes\b", line)
                no_match = re.search(r"\b(\d+)\s+No\b", line)
                if yes_match and no_match:
                    return int(yes_match.group(1)) > 0 and int(no_match.group(1)) == 0

        # No summary line found — do NOT assume True here.  If the IRS panel
        # has visible, selected Yes controls, treat criteria as marked yes;
        # otherwise report incomplete so the caller keeps waiting.
        for control in self.get_visible_yes_controls(driver):
            try:
                if control.is_displayed() and not self.is_yes_control_selected(control):
                    return False
            except StaleElementReferenceException:
                return False
        # All visible Yes controls are selected (or there are none visible yet);
        # only return True when at least one control was confirmed selected.
        return self.has_visible_yes_criteria_controls(driver)

    def approve_open_item(self):
        starting_url = self.driver.current_url
        starting_title = self.get_open_item_title()
        starting_evaluated_count = self.get_evaluated_item_count()

        def approval_is_saved(driver):
            return (
                self.is_open_item_approved(
                    driver,
                    starting_url,
                    starting_title,
                )
                or self.get_evaluated_item_count() > starting_evaluated_count
            )

        def wait_for_approval_save(timeout):
            try:
                self.wait_utils.until_condition(approval_is_saved, timeout=timeout)
                return True
            except TimeoutException:
                return False

        self.wait_utils.until_condition(
            lambda driver: self.are_all_criteria_marked_yes(driver),
            timeout=15,
        )
        approve_button = self.get_approve_button()
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            approve_button,
        )
        self.pause_before_action()
        try:
            approve_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", approve_button)

        # The confirmation is rendered asynchronously.  Give React half a
        # second to mount it before looking for its controls.
        sleep(0.5)
        # Dev saves an RWG approval immediately and auto-advances to the next
        # item without showing a confirmation modal.  Wait briefly for that
        # state transition before probing for a dialog; otherwise the dialog
        # locators spend several seconds on the newly opened next item and the
        # fallback click can approve the wrong question.
        approval_saved = wait_for_approval_save(timeout=5)
        confirmation_completed = False
        if not approval_saved:
            confirmation_completed = self.confirm_approve_if_prompted()
            if confirmation_completed:
                approval_saved = wait_for_approval_save(timeout=30)

        # The approval can finish while the optional-dialog locators are being
        # tried.  Re-check before attempting a second click so an SPA
        # auto-advance is never mistaken for a failed first click.
        if not approval_saved:
            approval_saved = approval_is_saved(self.driver)

        # Selenium can report a native click as successful even when a
        # transient overlay consumes it.  Retry once through the DOM only
        # when the first click produced neither a popup nor a saved approval.
        if not confirmation_completed and not approval_saved:
            approve_button = self.get_approve_button()
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();",
                approve_button,
            )
            sleep(0.5)
            approval_saved = wait_for_approval_save(timeout=5)
            if not approval_saved:
                confirmation_completed = self.confirm_approve_if_prompted()
                if confirmation_completed:
                    approval_saved = wait_for_approval_save(timeout=30)

        if not confirmation_completed and not approval_saved:
            raise TimeoutException(
                "Approve was clicked, but neither confirmation nor an Approved state appeared."
            )
        if not wait_for_approval_save(timeout=30):
            raise TimeoutException(
                "Approve completed, but the saved approval state was not retained."
            )

    def get_approve_button(self):
        """Return the active review pane's Approve button."""
        expected_title = getattr(self, "current_item_title", "")
        if expected_title:
            try:
                return self.wait_utils.until_condition(
                    lambda driver: driver.execute_script(
                        """
                        const expected = arguments[0].trim().toLowerCase();
                        const titles = Array.from(
                            document.querySelectorAll('input, textarea, div, p, span')
                        ).filter(element => {
                            const rect = element.getBoundingClientRect();
                            const text = (element.value || element.innerText
                                || element.textContent || '').trim().toLowerCase();
                            return rect.width > 0
                                && rect.height > 0
                                && rect.right > window.innerWidth * 0.45
                                && rect.left < window.innerWidth * 0.82
                                && text === expected;
                        }).sort((left, right) => {
                            const leftRect = left.getBoundingClientRect();
                            const rightRect = right.getBoundingClientRect();
                            return (leftRect.width * leftRect.height)
                                - (rightRect.width * rightRect.height);
                        });

                        for (const title of titles) {
                            let container = title.parentElement;
                            while (container && container !== document.body) {
                                const text = container.innerText || container.textContent || '';
                                if (text.includes('Item Response Sheet')) {
                                    const approve = Array.from(
                                        container.querySelectorAll('button')
                                    ).find(button => {
                                        const rect = button.getBoundingClientRect();
                                        return rect.width > 0
                                            && rect.height > 0
                                            && /^Approve$/i.test(
                                                (button.innerText
                                                    || button.textContent || '').trim()
                                            )
                                            && !button.disabled
                                            && button.getAttribute('aria-disabled') !== 'true';
                                    });
                                    if (approve) return approve;
                                }
                                container = container.parentElement;
                            }
                        }
                        return null;
                        """,
                        expected_title,
                    ),
                    timeout=15,
                )
            except TimeoutException:
                pass
        return self.wait_utils.until_clickable(
            self.APPROVE_ITEM_BUTTON,
            timeout=30,
        )

    def get_evaluated_item_count(self):
        page_text = self.driver.execute_script(
            "return document.body.innerText || document.body.textContent || '';"
        )
        match = re.search(r"(\d+)\s+evaluated\b", page_text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def is_open_item_approved(self, driver, starting_url, starting_title=""):
        open_title = self.get_open_item_title()

        # Auto-navigation alone is not success: dev can open the next card
        # while the original action is still Pending.  Require the original
        # card itself to show Approved.
        if starting_title and driver.execute_script(
            """
            const normalize = value => (value || '')
                .replace(/\\s+/g, ' ')
                .trim()
                .toLowerCase();
            const title = normalize(arguments[0]);
            return Array.from(
                document.querySelectorAll('button, a, [role="button"], div')
            ).some(element => {
                const rect = element.getBoundingClientRect();
                const text = normalize(element.innerText || element.textContent || '');
                return rect.width > 80
                    && rect.width < window.innerWidth * 0.40
                    && rect.height > 30
                    && rect.height < 260
                    && rect.left < window.innerWidth * 0.40
                    && text.includes(title)
                    && /\bapproved\b/i.test(text);
            });
            """,
            starting_title,
        ):
            return True

        if driver.current_url != starting_url:
            item_id = getattr(self, "current_item_id", "")
            if not item_id:
                return False
            return driver.execute_script(
                """
                const itemId = arguments[0].toLowerCase();
                const controls = Array.from(
                    document.querySelectorAll('a, button, [role="button"]')
                ).filter(control =>
                    (control.innerText || control.textContent || '')
                        .trim().toLowerCase() === itemId
                );
                for (const control of controls) {
                    let container = control.parentElement;
                    while (container && container !== document.body) {
                        const text = (container.innerText || container.textContent || '').trim();
                        if (/\\b(Approved|Pending|Under\\s+Review|Revise|Rejected)\\b/i.test(text)) {
                            return /\\bApproved\\b/i.test(text);
                        }
                        container = container.parentElement;
                    }
                }
                return false;
                """,
                item_id,
            )
        
        expected_title = starting_title or getattr(self, "current_item_title", "")
        # Only treat a title mismatch as "not this item" when a title could
        # actually be read. get_open_item_title() recognises the question
        # wordings this suite uploads; an item whose left-hand card shows the
        # "Expand to view the item content (image or table...)" placeholder
        # resolves to an empty title, and failing closed there means an
        # approval that did happen is never detected.
        if expected_title and open_title and (
            expected_title.casefold() not in open_title.casefold()
        ):
            return False

        # Check only the current item-detail pane.  The left item list can
        # contain Approved badges for earlier questions, so its badges must
        # never decide the state of the open question.
        return driver.execute_script(
            """
            const elements = Array.from(document.querySelectorAll('span, div, p, button'))
                .filter(el => {
                    const rect = el.getBoundingClientRect();
                    const text = (el.innerText || el.textContent || '').trim();
                    return rect.left > window.innerWidth * 0.45 &&
                           rect.left < window.innerWidth * 0.95 &&
                           rect.width > 0 && 
                           rect.height > 0 && 
                           /^Approved$/i.test(text);
                });
            return elements.length > 0;
            """
        )

    def send_open_item_back_for_revision(self, item_id):
        remark = (
            f"Automation revision requested for {item_id}: please update the item stem and explanation. "
            "This comment is intentionally longer than fifty characters for validation."
        )
        return self.send_open_item_back_for_revision_with_comment(item_id, remark)

    def send_open_item_back_for_revision_with_comment(self, item_id, revision_comment):
        """Mark the open item for revision while preserving caller-supplied audit text."""
        revision_comment = str(revision_comment or "").strip()
        if len(revision_comment) <= 50:
            raise ValueError("PIT revision comments must contain more than 50 characters.")
        starting_url = self.driver.current_url
        starting_title = self.get_open_item_title()
        self.mark_all_criteria_no()
        self.open_revision_form()
        if not self.enter_revision_remark_if_available(revision_comment):
            raise TimeoutException(
                f"A revision remark longer than 50 characters was not entered for {item_id}."
            )
        self.click_required_and_confirm(
            self.MARK_FOR_REVISION_LOCATORS,
            "Mark for Revision",
            timeout=15,
        )
        # Confirm the same question card changed state.  The QAR Timeline's
        # permanent "Revision Requested" entry is not evidence of send-back.
        self.wait_utils.until_condition(
            lambda driver: self.is_open_item_sent_back_for_revision(
                driver,
                starting_url,
                starting_title,
            ),
            timeout=30,
        )
        return revision_comment

    def is_open_item_sent_back_for_revision(
        self,
        driver,
        starting_url,
        starting_title="",
    ):
        if not starting_title:
            return False
        return bool(
            driver.execute_script(
                """
                const normalize = value => (value || '')
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .toLowerCase();
                const title = normalize(arguments[0]);
                const tableRowConfirmed = Array.from(
                    document.querySelectorAll('table tbody tr')
                ).some(row => {
                    const text = normalize(row.innerText || row.textContent || '');
                    return text.includes(title)
                        && /\\b(revise|revision|needs revision|sent back|changes requested)\\b/i.test(text);
                });
                if (tableRowConfirmed) return true;
                return Array.from(
                    document.querySelectorAll('button, a, [role="button"], div')
                ).some(element => {
                    const rect = element.getBoundingClientRect();
                    const text = normalize(element.innerText || element.textContent || '');
                    return rect.width > 80
                        && rect.width < window.innerWidth * 0.40
                        && rect.height > 30
                        && rect.height < 260
                        && rect.left < window.innerWidth * 0.40
                        && text.includes(title)
                        && /\\b(revise|revision|needs revision|sent back|changes requested)\\b/i.test(text);
                });
                """,
                starting_title,
            )
        ) or bool(
            driver.execute_script(
                """
                const text = (document.body.innerText || document.body.textContent || '')
                    .replace(/\\s+/g, ' ');
                const summary = text.match(/(\\d+)\\s+Yes\\b.*?\\b(\\d+)\\s+No\\b/i);
                if (!summary || Number(summary[1]) !== 0 || Number(summary[2]) <= 0) {
                    return false;
                }
                const activeRevisionAction = Array.from(
                    document.querySelectorAll('button, [role="button"]')
                ).some(button => {
                    const rect = button.getBoundingClientRect();
                    const label = (button.innerText || button.textContent || '').trim();
                    return rect.width > 0
                        && rect.height > 0
                        && !button.disabled
                        && button.getAttribute('aria-disabled') !== 'true'
                        && /^(Revise|Mark for Revision|Send for Revision)$/i.test(label);
                });
                return !activeRevisionAction;
                """
            )
        )

    def save_open_item_review(self):
        self.click_any_element(self.SAVE_ITEM_REVIEW_LOCATORS)
        self.confirm_if_prompted()

    def confirm_if_prompted(self):
        # FIX #6: Removed hardcoded sleep(1) from inside the retry loop.
        # The until_clickable timeout already handles waiting for the element;
        # an extra unconditional sleep per attempt wastes up to 9 s per call.
        for locator in self.CONFIRM_LOCATORS:
            for attempt in range(3):
                try:
                    confirm_button = self.wait_utils.until_clickable(locator, timeout=4)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        confirm_button,
                    )
                    try:
                        confirm_button.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", confirm_button)
                    return True
                except StaleElementReferenceException:
                    if attempt == 2:
                        break
                except Exception:
                    break
        return False

    def confirm_approve_if_prompted(self):
        for locator in self.APPROVE_CONFIRM_LOCATORS:
            for attempt in range(3):
                try:
                    confirm_button = self.wait_utils.until_clickable(locator, timeout=5)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        confirm_button,
                    )
                    sleep(0.5)
                    try:
                        confirm_button.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", confirm_button)
                    if self.wait_for_approval_modal_to_close():
                        return True
                except StaleElementReferenceException:
                    if attempt == 2:
                        break
                except Exception:
                    break
        return False

    def wait_for_approval_modal_to_close(self, timeout=10):
        try:
            self.wait_utils.until_condition(
                lambda driver: all(
                    not any(
                        element.is_displayed()
                        for element in driver.find_elements(*locator)
                    )
                    for locator in self.APPROVE_CONFIRM_LOCATORS
                ),
                timeout=timeout,
            )
            return True
        except TimeoutException:
            return False

    def return_to_item_set_if_needed(self, item_set_id):
        if not item_set_id:
            if "/items/" not in self.driver.current_url:
                return
            self.driver.back()
            self.wait_utils.until_condition(
                lambda driver: "/items/" not in driver.current_url,
                timeout=30,
            )
            return

        # Use JS innerText instead of body.text — body.text is empty in headless Chrome.
        _js_text = "return document.body.innerText || document.body.textContent || '';"
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        page_text = self.driver.execute_script(_js_text)
        if numeric_prefix in page_text and "/items/" not in self.driver.current_url:
            return
        if "/items/" not in self.driver.current_url:
            return
        self.driver.back()
        self.wait_utils.until_condition(
            lambda driver: (
                numeric_prefix in (driver.execute_script(_js_text) or "")
                and "/items/" not in driver.current_url
            ),
            timeout=30,
        )
        self.clear_visible_table_search()

    def click_left_side_item_by_position(self, item_position):
        previous_title = self.get_open_item_title()
        clicked_text = self.driver.execute_script(
            """
            const itemPosition = arguments[0];
            const seenTops = new Set();
            const cards = Array.from(document.querySelectorAll('button, a, [role="button"], div'))
                .filter((element) => {
                    const rect = element.getBoundingClientRect();
                    const text = (element.innerText || '').trim();
                    if (!text || rect.width < 80 || rect.height < 35) return false;
                    if (rect.left > window.innerWidth * 0.45 || rect.top < 80) return false;
                    if (!/\\b(Pending|Approved|Revise|Rejected)\\b/i.test(text)) return false;
                    if (!/(Upload run|T\\/F|1m|True|False)/i.test(text)) return false;
                    const topKey = Math.round(rect.top / 8) * 8;
                    if (seenTops.has(topKey)) return false;
                    seenTops.add(topKey);
                    return true;
                })
                .sort((left, right) => left.getBoundingClientRect().top - right.getBoundingClientRect().top);

            const card = cards[itemPosition];
            if (!card) return '';
            card.scrollIntoView({block: 'center'});
            card.click();
            return card.innerText || '';
            """,
            item_position,
        )
        if not clicked_text:
            clicked_text = self.click_next_left_side_pending_item()
        if not clicked_text:
            raise TimeoutException("Next left-side pending item card was not available.")
        self.wait_utils.until_condition(
            lambda driver: (
                self.is_review_item_ready(driver)
                and (not previous_title or self.get_open_item_title() != previous_title)
            ),
            timeout=30,
        )

    def click_next_left_side_pending_item(self):
        return self.driver.execute_script(
            """
            const cards = Array.from(document.querySelectorAll('button, a, [role="button"], div'))
                .filter((element) => {
                    const rect = element.getBoundingClientRect();
                    const text = (element.innerText || '').trim();
                    if (!text || rect.width < 80 || rect.height < 35) return false;
                    if (rect.left > window.innerWidth * 0.45 || rect.top < 80) return false;
                    return /\\b(Pending|Under\\s+Review)\\b/i.test(text);
                })
                .sort((left, right) => left.getBoundingClientRect().top - right.getBoundingClientRect().top);
            const card = cards[0];
            if (!card) return '';
            card.scrollIntoView({block: 'center'});
            card.click();
            return card.innerText || '';
            """
        )

    def get_open_item_title(self, expected_title=""):
        expected_title = expected_title or getattr(self, "current_item_title", "")
        try:
            return self.driver.execute_script(
                """
                const expectedOriginal = String(arguments[0] || '').trim();
                const expected = expectedOriginal.toLowerCase().replace(/\\s+/g, ' ');
                const candidates = Array.from(
                    document.querySelectorAll('input, textarea, div, p, span')
                ).filter(element => {
                    const rect = element.getBoundingClientRect();
                    return rect.width > 0
                        && rect.height > 0
                        && !element.closest('table')
                        && rect.right > window.innerWidth * 0.45
                        && rect.left < window.innerWidth * 0.82;
                }).map(element =>
                    (element.value || element.innerText || element.textContent || '').trim()
                ).filter(Boolean);

                if (expected) {
                    const exactMatch = candidates
                        .filter(text => {
                            const normalized = text.toLowerCase().replace(/\\s+/g, ' ');
                            return normalized === expected || normalized.includes(expected);
                        })
                        .sort((left, right) => left.length - right.length)[0];
                    if (exactMatch) return expectedOriginal;
                }

                return candidates
                    .filter(text => /^Is\\s+/i.test(text)
                        || /^Updated revision\\b/i.test(text)
                        || text.includes('Upload run'))
                    .sort((left, right) => left.length - right.length)[0] || '';
                """,
                expected_title,
            )
        except Exception:
            return ""

    def approve_items_with_yes(self, item_set_id, item_ids):
        if not item_ids:
            return []

        approved_item_ids = []
        self.return_to_item_set_if_needed(item_set_id)

        for item_id in item_ids:
            self.return_to_item_set_if_needed(item_set_id)
            self.click_item(item_id)
            self.mark_all_criteria_yes()
            self.approve_open_item()
            approved_item_ids.append(item_id)

        # Keep the final completed item/split view open.  The dev UI exposes
        # Submit Review there after every item has been evaluated; navigating
        # back to the item-set table hides that control and the table rows stay
        # "Under Review" until the review itself is submitted.

        # Approving auto-advances to the next card, so a retry click inside
        # approve_open_item() can land on the item that was advanced to and
        # leave the intended one Pending - which keeps Submit Review disabled
        # even though every item was visited. Sweep up whatever is still
        # Pending (items marked for revision show Revise, not Pending, so
        # they are never picked up here).
        for _ in range(len(item_ids) + 2):
            if self.is_submit_review_enabled():
                break
            if not self.click_next_left_side_pending_item():
                break
            try:
                self.wait_utils.until_condition(
                    lambda driver: self.is_review_item_ready(driver),
                    timeout=30,
                )
                self.mark_all_criteria_yes()
                self.approve_open_item()
            except TimeoutException:
                break

        self.wait_utils.until_condition(
            lambda driver: self.is_submit_review_enabled(),
            timeout=30,
        )
        return approved_item_ids

    def navigate_to_next_item(self, next_item_id):
        if self.click_next_left_side_pending_item():
            self.wait_utils.until_condition(
                lambda driver: next_item_id in driver.find_element(By.TAG_NAME, "body").text,
                timeout=30,
            )
            return True

        self.click_item(next_item_id)
        return True

    def has_enabled_approve_button(self):
        for button in self.driver.find_elements(*self.APPROVE_ITEM_BUTTON):
            try:
                if button.is_displayed() and button.is_enabled():
                    return True
            except StaleElementReferenceException:
                continue
        return False

    def has_enabled_submit_button(self):
        return self.is_submit_review_enabled()

    def send_items_back_for_revision(self, item_set_id, item_ids):
        revised_item_ids = []
        for item_id in item_ids:
            self.return_to_item_set_if_needed(item_set_id)
            self.click_item(item_id)
            if not self.has_actionable_review_items():
                raise TimeoutException(
                    f"Reviewer send-back action is not available for {item_id}. "
                    "This item set may already have been actioned by this reviewer role; use a fresh item set."
                )
            self.send_open_item_back_for_revision(item_id)
            revised_item_ids.append(item_id)
        return revised_item_ids

    def send_items_back_for_revision_with_comment(
        self,
        item_set_id,
        item_ids,
        revision_comment,
    ):
        """Send selected items back with one traceable, test-owned audit comment."""
        revised_item_ids = []
        for item_id in item_ids:
            self.return_to_item_set_if_needed(item_set_id)
            self.click_item(item_id)
            if not self.has_actionable_review_items():
                raise TimeoutException(
                    f"Reviewer send-back action is not available for {item_id}. "
                    "This item set may already have been actioned by this reviewer role; use a fresh item set."
                )
            self.send_open_item_back_for_revision_with_comment(
                item_id,
                revision_comment,
            )
            revised_item_ids.append(item_id)
        return revised_item_ids

    def revise_some_items_and_approve_rest(self, item_set_id, item_ids, revision_count=2):
        revision_count = max(1, min(int(revision_count), len(item_ids)))
        revision_item_ids = item_ids[:revision_count]
        approval_item_ids = item_ids[revision_count:]

        revised_item_ids = self.send_items_back_for_revision(item_set_id, revision_item_ids)
        approved_item_ids = self.approve_items_with_yes(item_set_id, approval_item_ids)
        return revised_item_ids, approved_item_ids

    def ensure_reviewer_action_available(self, role_name):
        """Guard one-time reviewer workflows from reusing an actioned set."""
        item_set_has_actionable_review_items = self.has_actionable_review_items()
        if not item_set_has_actionable_review_items:
            raise TimeoutException(
                f"{role_name} action is not available for this item set. "
                "The item set may already have been actioned by this role; use a fresh item set."
            )
        return item_set_has_actionable_review_items

    def has_actionable_review_items(self):
        if self.is_submit_review_enabled():
            return True
        for control in self.get_visible_yes_controls(self.driver):
            try:
                if control.is_displayed() and control.is_enabled():
                    return True
            except StaleElementReferenceException:
                continue
        for button in self.driver.find_elements(*self.APPROVE_ITEM_BUTTON):
            try:
                if button.is_displayed() and button.is_enabled():
                    return True
            except StaleElementReferenceException:
                continue
        return False

    def wait_until_review_items_approved(self):
        self.wait_utils.until_condition(
            lambda driver: (
                self.are_review_items_approved(driver)
                or self.is_submit_review_enabled()
            ),
            timeout=30,
        )

    @staticmethod
    def are_review_items_approved(driver):
        # Use JS innerText so this works in headless Chrome where body.text is empty.
        page_text = driver.execute_script(
            "return document.body.innerText || document.body.textContent || '';"
        )
        evaluated_match = re.search(r"(\d+)\s+items\s*·\s*0\s+flagged\s*·\s*(\d+)\s+evaluated", page_text)
        if evaluated_match and evaluated_match.group(1) == evaluated_match.group(2):
            return True

        item_count_match = re.search(r"(\d+)\s+Items", page_text)
        if item_count_match:
            item_count = int(item_count_match.group(1))
            approved_count = len(re.findall(r"\bApproved\b", page_text))
            if item_count > 0 and approved_count >= item_count:
                return True

        return "Approved" in page_text and "Review Completed" in page_text

    def click_optional_and_confirm(self, locators, timeout=5):
        for locator in locators:
            try:
                element = self.wait_utils.until_clickable(locator, timeout=timeout)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                self.pause_before_action()
                # Removed hardcoded sleep(1) — until_clickable already waits for
                # the element to be ready; pause_before_action provides the settle time.
                try:
                    element.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", element)
                sleep(1)
                self.confirm_if_prompted()
                return True
            except Exception:
                continue
        return False

    def click_required_and_confirm(self, locators, button_name, timeout=15):
        if self.click_optional_and_confirm(locators, timeout=timeout):
            return True
        raise TimeoutException(f"{button_name} button was not available after all items were approved.")

    def capture_review_screenshot(self, test_name, suffix):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_{suffix}")

    def get_open_item_image_count(self):
        """Count content images in the right-pane review panel (excludes UI icons/logos)."""
        return self.driver.execute_script(
            """
            return Array.from(document.querySelectorAll('img')).filter(img => {
                const rect = img.getBoundingClientRect();
                const src = img.src || img.currentSrc || '';
                return rect.width > 10
                    && rect.height > 10
                    && rect.right > window.innerWidth * 0.4
                    && rect.left < window.innerWidth * 0.95
                    && !img.closest('[role="navigation"]')
                    && !img.closest('header')
                    && !src.includes('favicon')
                    && !src.includes('logo')
                    && img.naturalWidth > 30;
            }).length;
            """
        )

    def verify_images_visible_to_reviewer(self, item_set_id, item_ids):
        """Open each item and assert at least one content image is visible in the review pane."""
        results = {}
        for item_id in item_ids:
            self.return_to_item_set_if_needed(item_set_id)
            try:
                self.click_item(item_id)
                self.pause_before_action()
                img_count = self.get_open_item_image_count()
                results[item_id] = img_count
                assert img_count > 0, (
                    f"Expected at least one image in review pane for {item_id} "
                    f"but found {img_count}."
                )
            except Exception as error:
                results[item_id] = f"IMAGE VERIFICATION ERROR: {error}"
                raise
        return results

    def get_open_item_question_text(self):
        """Return the question text visible in the right-pane review panel."""
        return self.driver.execute_script(
            """
            const candidates = Array.from(
                document.querySelectorAll('div, p, span, textarea, input')
            ).filter(element => {
                const rect = element.getBoundingClientRect();
                return rect.width > 0
                    && rect.height > 0
                    && rect.right > window.innerWidth * 0.45
                    && rect.left < window.innerWidth * 0.82
                    && !element.closest('table');
            }).map(element =>
                (element.value || element.innerText || element.textContent || '').trim()
            ).filter(text =>
                text.length > 10
                && !/^(Approve|Submit|Cancel|Yes|No|NA|Y|N|Authorise)$/.test(text)
                && !/^\\d+$/.test(text)
            );
            return candidates.sort((a, b) => b.length - a.length)[0] || '';
            """
        )

    def verify_revised_items_visible_to_reviewer(
        self,
        item_set_id,
        revised_item_ids,
        expected_revision_prefix="Updated revision for",
    ):
        """
        Open each revised item from the reviewer's perspective and verify the
        teacher's revised content is visible.  Returns a dict of
        {item_id: visible_question_text} so callers can print or assert on it.
        """
        visible_contents = {}
        for item_id in revised_item_ids:
            self.return_to_item_set_if_needed(item_set_id)
            try:
                self.click_item(item_id)
                question_text = self.get_open_item_title(expected_revision_prefix) or self.get_open_item_question_text()
                visible_contents[item_id] = question_text
                assert question_text, (
                    f"No question text was visible in the review pane for {item_id}."
                )
                assert expected_revision_prefix.casefold() in question_text.casefold(), (
                    f"Revised content not visible to reviewer for {item_id}. "
                    f"Expected prefix: '{expected_revision_prefix}'. "
                    f"Visible text: '{question_text[:200]}'"
                )
            except Exception as error:
                visible_contents[item_id] = f"VERIFICATION ERROR: {error}"
                raise
        return visible_contents

    def is_image_visible_in_open_item(self):
        """Return True if a real content image is visible in the open item's
        review/edit panel (excludes UI icons/logos/nav chrome).

        Uses the same geometric + naturalWidth filtering as
        get_open_item_image_count so it recognizes images inserted through the
        app's real "Insert" flow (rendered as <img src="blob:..."> wrapped in
        a `.rte-img-wrap` span) as well as the data-URI JS-injection fallback.
        """
        return bool(
            self.driver.execute_script(
                """
                return Array.from(document.querySelectorAll('img')).some(function(img) {
                    const src = img.src || img.currentSrc || '';
                    const rect = img.getBoundingClientRect();
                    return rect.width > 10
                        && rect.height > 10
                        && rect.right > window.innerWidth * 0.4
                        && rect.left < window.innerWidth * 0.95
                        && !img.closest('[role="navigation"]')
                        && !img.closest('header')
                        && !src.includes('favicon')
                        && !src.includes('logo')
                        && img.naturalWidth > 30;
                });
                """
            )
        )

    def verify_image_visible_for_items(self, item_set_id, item_ids):
        """Open each item in the reviewer queue and assert an image is visible.

        Returns a dict of {item_id: True/False} recording visibility per item.
        """
        results = {}
        for item_id in item_ids:
            self.return_to_item_set_if_needed(item_set_id)
            try:
                self.click_item(item_id)
                visible = self.is_image_visible_in_open_item()
                results[item_id] = visible
                assert visible, (
                    f"Image not visible to reviewer for item {item_id}. "
                    "Expected an <img> element with a non-empty src in the review panel."
                )
            except Exception as error:
                results[item_id] = False
                raise AssertionError(
                    f"Image verification failed for {item_id}: {error}"
                ) from error
        return results
