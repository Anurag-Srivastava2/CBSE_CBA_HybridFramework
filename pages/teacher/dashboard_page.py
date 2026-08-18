import re

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By

from pages.common.base_page import BasePage


class DashboardPage(BasePage):
    """The teacher landing dashboard.

    This page object carried a single locator (DASHBOARD_TEXT) while the screen
    itself renders seven stat cards, six charts, seven grid tabs, a ten-column
    item-set grid, pagination, the sidebar and the accessibility toolbar. A
    survey written against the old object would have reported "1/1 present" on a
    page that was 1 of ~55 — so the locators below were taken from a DOM census
    of the live QA environment rather than from what the tests already used.
    """

    # Kept exactly as it was: the smoke suite, test_teacher_login and
    # test_login_negative_cases all gate on is_dashboard_loaded(), so this
    # locator's behaviour must not change.
    DASHBOARD_TEXT = (
        By.XPATH,
        "//*[contains(normalize-space(),'Hello, teacher') "
        "or contains(normalize-space(),'Build Assessment') "
        "or contains(normalize-space(),'Create and manage your assessments')]",
    )

    # ------------------------------------------------------------------
    # Page header and primary call to action
    # ------------------------------------------------------------------
    PAGE_HEADER = (By.XPATH, "//h1[contains(normalize-space(),'Hello')]")
    # Scoped to the leaf that carries the text: an unscoped contains() also
    # matches every ancestor up to <body> (13 of them on this page), which makes
    # a "1 element present" check quietly mean "some container holds the text".
    PAGE_SUBTITLE = (
        By.XPATH,
        "//*[not(*)][contains(normalize-space(),'Create and manage your assessments')]",
    )
    CREATE_ITEM_SET_CTA = (
        By.XPATH,
        "//button[contains(normalize-space(),'Create an Item Set')]",
    )

    # ------------------------------------------------------------------
    # Stat cards
    #
    # Each card is a button whose aria-label reads "Filter My Item Sets by
    # <label>" — a far stabler handle than the visible text, which prefixes some
    # labels with a Material Symbols ligature ("published_with_changes 2 Needs
    # Improvement").
    # ------------------------------------------------------------------
    STAT_LABELS = (
        "All Items",
        "Drafts",
        "Under Review",
        "QAR Failed",
        "Needs Improvement",
        "Rejected",
        "Published",
    )
    STAT_CARDS = (By.CSS_SELECTOR, "button[aria-label^='Filter My Item Sets by']")

    # ------------------------------------------------------------------
    # Analytics sections
    # ------------------------------------------------------------------
    CHART_TITLES = (
        "Grade-wise & Subject-wise Item Creation",
        "Status Distribution",
        "Item Sets at Review Stage",
        "Progress Over Time",
        "Question Papers Published",
        "Items Submission Frequency",
    )
    CHART_SURFACES = (By.CSS_SELECTOR, "svg.recharts-surface")
    STATUS_DONUT_CENTRE = (By.CSS_SELECTOR, "[class*='donutCenter']")
    REVIEW_STAGE_PILL = (By.CSS_SELECTOR, "[class*='warningPill']")
    MORE_INFORMATION_TRIGGER = (By.CSS_SELECTOR, "button[aria-label='More information']")

    # ------------------------------------------------------------------
    # My Item Sets grid
    #
    # The teacher dashboard renders exactly one table (confirmed by the DOM
    # census), unlike the admin dashboard where a bare //table matched the wrong
    # grid — so these stay unscoped deliberately.
    # ------------------------------------------------------------------
    SECTION_MY_ITEM_SETS = (By.XPATH, "//*[normalize-space()='My Item Sets']")
    VIEW_ALL_LINK = (By.XPATH, "//a[@href='/item-sets'][contains(normalize-space(),'View All')]")
    TABLE = (By.TAG_NAME, "table")
    TABLE_HEADERS = (By.XPATH, "//table//th")
    TABLE_ROWS = (By.XPATH, "//table/tbody/tr")
    ITEM_SET_LINKS = (By.CSS_SELECTOR, "table a[href^='/item-sets/']")

    TAB_LIST = (By.CSS_SELECTOR, "[role='tablist']")
    TAB_LABELS = ("All", "QAR", "RWG", "PIT", "Published", "Disabled", "Draft-Items")

    # The grid re-columns itself per tab: the item-set tabs list item sets, while
    # Draft-Items lists individual items.
    ITEM_SET_COLUMNS = (
        "Item Set ID",
        "Grade",
        "Subject & Chapter",
        "Item Count",
        "Item Status",
        "Item Set Status",
        "Item Set Review Stage",
        "Last Updated",
        "Last Review Submit Date",
        "Uploaded File",
    )
    DRAFT_ITEM_COLUMNS = (
        "Item ID",
        "Item",
        "Grade",
        "Subject & Chapter",
        "Typology",
        "Bloom's Level",
        "Marks",
        "Created Via",
    )

    ROWS_PER_PAGE = (By.CSS_SELECTOR, "[role='combobox']")
    PREV_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='Previous page']")
    NEXT_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='Next page']")

    # ------------------------------------------------------------------
    # Application chrome
    # ------------------------------------------------------------------
    HEADER = (By.TAG_NAME, "header")
    SIDEBAR_NAV = (By.TAG_NAME, "nav")
    SIDEBAR_TOGGLE = (By.XPATH, "//button[contains(normalize-space(),'Toggle Sidebar')]")
    NOTIFICATION_BELL = (By.CSS_SELECTOR, "button[aria-label='Notifications']")

    # Sidebar destinations. Matched on the menu-button component class rather
    # than on text alone: 'Create' would otherwise also match the "Create an
    # Item Set" call to action in the page body.
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

    # ------------------------------------------------------------------
    # Accessibility / localisation toolbar
    # ------------------------------------------------------------------
    THEME_PICKER = (By.CSS_SELECTOR, "button[aria-label='Theme']")
    SCREEN_READER_TOGGLE = (
        By.CSS_SELECTOR,
        "button[aria-label='Toggle screen-reader hints']",
    )
    LANG_EN = (By.XPATH, "//button[normalize-space()='EN']")
    LANG_HI = (By.XPATH, "//button[normalize-space()='हिंदी']")
    FONT_SIZE_CONTROLS = (
        By.XPATH,
        "//button[normalize-space()='A−' or normalize-space()='A' "
        "or normalize-space()='A+' or normalize-space()='A++']",
    )

    LEADING_NUMBER = re.compile(r"(\d[\d,]*)")
    TRAILING_NUMBER = re.compile(r"(\d[\d,]*)\s*$")

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------

    def is_dashboard_loaded(self):
        return self.is_element_visible(self.DASHBOARD_TEXT)

    def wait_for_dashboard_ready(self, timeout=30):
        """Wait until the greeting and the item-set grid have both painted.

        The shell renders before the stat tiles have their counts, so a check
        that only waits for the greeting can read a card that has no number in
        it yet.
        """
        self.wait_utils.until_condition(
            lambda driver: bool(driver.find_elements(*self.PAGE_HEADER))
            and bool(driver.find_elements(*self.TAB_LIST)),
            timeout=timeout,
        )
        return True

    def body_text(self):
        try:
            return self.driver.find_element(By.TAG_NAME, "body").text
        except WebDriverException:
            return ""

    def get_greeting_text(self):
        try:
            return self.get_text(self.PAGE_HEADER)
        except (WebDriverException, AssertionError, ValueError):
            return ""

    # ------------------------------------------------------------------
    # Generic readers
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
            except WebDriverException:
                continue
        return count

    @staticmethod
    def xpath_literal(value):
        """Quote a value for use inside an XPath expression.

        Column and field labels on this screen include apostrophes ("Bloom's
        Level"), which terminate a single-quoted XPath early and raise
        InvalidSelectorException rather than simply failing to match.
        """
        text = str(value)
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        parts = "', \"'\", '".join(text.split("'"))
        return f"concat('{parts}')"

    @classmethod
    def _to_number(cls, text, pattern):
        match = pattern.search(text or "")
        if not match:
            return None
        return int(match.group(1).replace(",", ""))

    # ------------------------------------------------------------------
    # Stat cards
    # ------------------------------------------------------------------

    def stat_card_locator(self, label):
        return (By.CSS_SELECTOR, f"button[aria-label='Filter My Item Sets by {label}']")

    def get_stat_value(self, label):
        """The count on one stat card, or None when the card is absent.

        The visible text can be prefixed by an icon ligature, so the number is
        taken as the first integer in the label rather than the whole string.
        """
        try:
            text = self.driver.find_element(*self.stat_card_locator(label)).text
        except WebDriverException:
            return None
        return self._to_number(text, self.LEADING_NUMBER)

    def get_all_stat_values(self):
        return {label: self.get_stat_value(label) for label in self.STAT_LABELS}

    def missing_stat_cards(self):
        return [
            label
            for label in self.STAT_LABELS
            if not self.count_visible(self.stat_card_locator(label))
        ]

    # ------------------------------------------------------------------
    # Grid tabs
    # ------------------------------------------------------------------

    def tab_locator(self, label):
        return (
            By.XPATH,
            f"//*[@role='tab'][starts-with(normalize-space(),{self.xpath_literal(label)})]",
        )

    def get_tab_labels(self):
        labels = []
        for element in self.driver.find_elements(By.CSS_SELECTOR, "[role='tab']"):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if text:
                labels.append(text)
        return labels

    def missing_tabs(self):
        return [
            label
            for label in self.TAB_LABELS
            if not self.count_visible(self.tab_locator(label))
        ]

    def get_tab_badge_count(self, label):
        """The count badge on a tab ('All 66' -> 66), or None when absent."""
        try:
            text = self.driver.find_element(*self.tab_locator(label)).text
        except WebDriverException:
            return None
        return self._to_number(text.replace("\n", " ").strip(), self.TRAILING_NUMBER)

    def is_tab_active(self, label):
        try:
            state = self.driver.find_element(*self.tab_locator(label)).get_attribute(
                "data-state"
            )
        except WebDriverException:
            return False
        return state == "active"

    def switch_tab(self, label, timeout=20):
        """Activate a grid tab and wait for it to report itself active."""
        self.click_element(self.tab_locator(label))
        try:
            self.wait_utils.until_condition(
                lambda driver: self.is_tab_active(label), timeout=timeout
            )
        except TimeoutException:
            return False
        return True

    # ------------------------------------------------------------------
    # Grid contents
    # ------------------------------------------------------------------

    def get_table_headers(self):
        headers = []
        for element in self.driver.find_elements(*self.TABLE_HEADERS):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if text:
                headers.append(text)
        return headers

    def missing_columns(self, expected=None):
        expected = expected or self.ITEM_SET_COLUMNS
        headers = [header.casefold() for header in self.get_table_headers()]
        return [column for column in expected if column.casefold() not in headers]

    def get_table_row_count(self):
        return len(self.driver.find_elements(*self.TABLE_ROWS))

    def get_item_set_ids_in_view(self):
        ids = []
        for element in self.driver.find_elements(*self.ITEM_SET_LINKS):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if text:
                ids.append(text)
        return ids

    # ------------------------------------------------------------------
    # Chrome
    # ------------------------------------------------------------------

    def nav_item_locator(self, label):
        return (
            By.XPATH,
            "//button[contains(@class,'menu-button')]"
            f"[contains(normalize-space(),{self.xpath_literal(label)})]",
        )

    def missing_nav_items(self):
        return [
            label
            for label in self.NAV_ITEMS
            if not self.count_visible(self.nav_item_locator(label))
        ]

    def section_locator(self, title):
        return (
            By.XPATH,
            f"//*[self::h2 or self::h3][normalize-space()={self.xpath_literal(title)}]",
        )

    def missing_chart_sections(self):
        return [
            title
            for title in self.CHART_TITLES
            if not self.count_visible(self.section_locator(title))
        ]

    def get_notification_badge_text(self):
        try:
            return self.driver.find_element(*self.NOTIFICATION_BELL).text.strip()
        except WebDriverException:
            return ""
