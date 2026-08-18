import re

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By

from pages.common.base_page import BasePage


class AdminDashboardPage(BasePage):
    """Admin landing dashboard: KPI cards, filters, analytics sections and the
    published-items grid. Values are read dynamically so the assertions survive
    changing environment data."""

    PAGE_HEADER = (By.XPATH, "//*[self::h1 or self::h2][contains(normalize-space(),'Hello')]")

    # KPI cards — matched on the card label, then the whole card is read so the
    # number can be pulled out regardless of the label/value element order.
    METRIC_CARD_ALL_ITEMS = (By.XPATH, "//*[normalize-space()='All Items']/ancestor::*[self::div or self::a][1]")
    METRIC_CARD_ALL_SETS = (By.XPATH, "//*[normalize-space()='All Item Sets']/ancestor::*[self::div or self::a][1]")
    METRIC_CARD_TOTAL_USERS = (By.XPATH, "//*[normalize-space()='Total Users']/ancestor::*[self::div or self::a][1]")
    METRIC_CARD_QAR_FAILED = (By.XPATH, "//*[normalize-space()='QAR Failed']/ancestor::*[self::div or self::a][1]")

    # Filters. "Apply Filters" is rendered as a span inside its control rather
    # than a <button>, so the labels are matched on any element.
    FILTER_APPLY_BTN = (By.XPATH, "//*[normalize-space()='Apply Filters']")
    FILTER_RESET_BTN = (By.XPATH, "//*[normalize-space()='Reset Filters']")
    TIME_PERIOD_DROPDOWN = (
        By.XPATH,
        "//*[normalize-space()='TIME PERIOD']/following::*[self::select or self::button or @role='combobox'][1]"
        " | //*[contains(normalize-space(),'All Time')]",
    )
    GRADE_DROPDOWN = (
        By.XPATH,
        "//*[normalize-space()='GRADE']/following::*[self::select or self::button or @role='combobox'][1]"
        " | //*[contains(normalize-space(),'All Grades')]",
    )
    SUBJECT_DROPDOWN = (
        By.XPATH,
        "//*[normalize-space()='SUBJECT']/following::*[self::select or self::button or @role='combobox'][1]"
        " | //*[contains(normalize-space(),'All Subjects')]",
    )

    # Section headers
    SECTION_STATUS_DIST = (By.XPATH, "//*[self::h2 or self::h3][contains(normalize-space(),'Status Distribution')]")
    SECTION_PIPELINE = (By.XPATH, "//*[self::h2 or self::h3][contains(normalize-space(),'Pipeline Stage Breakdown')]")
    SECTION_ACTIVITY = (By.XPATH, "//*[self::h2 or self::h3][contains(normalize-space(),'User Activity')]")
    SECTION_PUBLISHED_GRID = (
        By.XPATH,
        "//*[self::h2 or self::h3][contains(normalize-space(),'Published Items by Grade')]",
    )

    # Sections the dashboard renders beyond the four above. Kept separate only
    # for readability — every one of them is part of the page.
    SECTION_REVIEW_TIME = (By.XPATH, "//*[self::h2 or self::h3][contains(normalize-space(),'Average Review Time')]")
    SECTION_THROUGHPUT = (By.XPATH, "//*[self::h2 or self::h3][contains(normalize-space(),'Platform Throughput')]")
    SECTION_ACTIVE_ASSIGNMENTS = (By.XPATH, "//*[self::h2 or self::h3][contains(normalize-space(),'Active Assignments')]")
    SECTION_QP_GRID = (
        By.XPATH,
        "//*[self::h2 or self::h3][contains(normalize-space(),'Question Papers by Grade')]",
    )

    # Report tabs
    TAB_PLATFORM_OVERVIEW = (By.XPATH, "//button[contains(normalize-space(),'Platform Overview')]")
    TAB_USER_PERFORMANCES = (By.XPATH, "//button[contains(normalize-space(),'User Performances')]")
    TAB_QAR_REPORTS = (By.XPATH, "//button[contains(normalize-space(),'QAR Reports')]")

    # Branding and page chrome
    LOGO = (By.XPATH, "//img[contains(@alt,'Aakalan') or contains(@alt,'Assessment')]")
    HEADER = (By.TAG_NAME, "header")
    SIDEBAR_NAV = (By.TAG_NAME, "nav")
    SIDEBAR_TOGGLE = (By.XPATH, "//button[contains(normalize-space(),'Toggle Sidebar')]")
    NOTIFICATION_BELL = (By.CSS_SELECTOR, "svg.lucide-bell.size-5")
    # Charts render as recharts SVG surfaces, not <canvas>.
    CHART_SURFACES = (By.CSS_SELECTOR, "svg.recharts-surface")

    # Sidebar navigation. Matched on the label prefix that survives the
    # sidebar's text truncation ('Workfl' is what a collapsed 'Workflow'
    # renders), so these hold whether the sidebar is expanded or not.
    NAV_ITEMS = {
        "Home": "Home",
        "Roles": "Roles",
        "User": "User",
        "Workflow": "Workfl",
        "Master": "Master",
        "Portal": "Portal",
        "QAR": "QAR",
        "Audit": "Audit",
        "Notifications": "Notifi",
        "Help": "Help",
        "Support": "Support",
        "Settings": "Settings",
    }

    # KPI card icons, keyed by the card they belong to.
    KPI_ICONS = {
        "All Items": "lucide-file-text",
        "All Item Sets": "lucide-file-stack",
        "Total Users": "lucide-users",
        "QAR Failed": "lucide-file-search",
    }

    # Accessibility / localisation toolbar
    THEME_PICKER = (By.XPATH, "//button[contains(normalize-space(),'Theme')]")
    SCREEN_READER_TOGGLE = (By.XPATH, "//button[contains(normalize-space(),'SR')]")
    LANG_EN = (By.XPATH, "//button[normalize-space()='EN']")
    LANG_HI = (By.XPATH, "//button[normalize-space()='हिंदी']")
    FONT_SIZE_CONTROLS = (
        By.XPATH,
        "//button[normalize-space()='A' or normalize-space()='A+' or normalize-space()='A++']",
    )

    # Dynamic content
    ACTIVITY_ITEMS = (
        By.XPATH,
        "//*[self::h2 or self::h3][contains(normalize-space(),'User Activity')]"
        "/following::*[self::p or self::li or self::div][position()<=40]",
    )
    # Scoped to its own heading: the dashboard renders two grids ('Published
    # Items by Grade & Subject' and 'Question Papers by Grade & Subject'), so a
    # bare //table matched whichever came first in the DOM rather than the one
    # these checks name.
    PUBLISHED_GRID_TABLE = (
        By.XPATH,
        "//*[self::h2 or self::h3][contains(normalize-space(),'Published Items by Grade')]"
        "/following::table[1]",
    )
    PUBLISHED_GRID_HEADERS = (
        By.XPATH,
        "//*[self::h2 or self::h3][contains(normalize-space(),'Published Items by Grade')]"
        "/following::table[1]//th",
    )
    QP_GRID_TABLE = (
        By.XPATH,
        "//*[self::h2 or self::h3][contains(normalize-space(),'Question Papers by Grade')]"
        "/following::table[1]",
    )
    QP_GRID_HEADERS = (
        By.XPATH,
        "//*[self::h2 or self::h3][contains(normalize-space(),'Question Papers by Grade')]"
        "/following::table[1]//th",
    )
    AUDIT_TRAIL_LINK = (
        By.XPATH,
        "//*[self::a or self::button][contains(normalize-space(),'Audit Trail')]",
    )

    RELATIVE_TIME_PATTERN = re.compile(
        r"(just now|\d+\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\s*ago)",
        re.IGNORECASE,
    )

    def wait_for_dashboard_ready(self, timeout=30):
        self.wait_utils.until_condition(
            lambda driver: "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
            timeout=timeout,
        )

    def body_text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def get_welcome_text(self):
        return self.get_text(self.PAGE_HEADER)

    def is_visible(self, locator, timeout=10):
        """Non-throwing visibility check used by the dashboard assertions."""
        return self.is_element_visible_quick(locator, timeout)

    def get_metric_value(self, locator, timeout=10):
        """Return the first integer rendered on a KPI card, or None when the
        card is absent — so the test reports a readable assertion instead of a
        raw Selenium timeout."""
        try:
            raw_text = self.wait_utils.until_visible(locator, timeout).text
        except (TimeoutException, WebDriverException):
            return None
        match = re.search(r"\d[\d,]*", raw_text)
        return int(match.group().replace(",", "")) if match else None

    def are_filters_interactive(self):
        return (
            self.is_visible(self.FILTER_APPLY_BTN)
            and self.is_visible(self.FILTER_RESET_BTN)
            and self.is_visible(self.TIME_PERIOD_DROPDOWN)
        )

    def missing_filter_controls(self):
        """Names of the filter controls that are not on screen — used to make
        a filter failure self-explanatory."""
        controls = {
            "Apply Filters": self.FILTER_APPLY_BTN,
            "Reset Filters": self.FILTER_RESET_BTN,
            "Time Period": self.TIME_PERIOD_DROPDOWN,
            "Grade": self.GRADE_DROPDOWN,
            "Subject": self.SUBJECT_DROPDOWN,
        }
        return [name for name, locator in controls.items() if not self.is_visible(locator)]

    def get_user_activity_logs(self):
        """Non-empty text entries rendered under the User Activity section."""
        entries = []
        for element in self.driver.find_elements(*self.ACTIVITY_ITEMS):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if text and text not in entries:
                entries.append(text)
        return entries

    def get_relative_timestamp_entries(self):
        return [log for log in self.get_user_activity_logs() if self.RELATIVE_TIME_PATTERN.search(log)]

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

    def nav_item_locator(self, label_prefix):
        return (By.XPATH, f"//button[contains(normalize-space(),'{label_prefix}')]")

    def icon_locator(self, icon_class):
        return (By.CSS_SELECTOR, f"svg.{icon_class}")

    def get_notification_badge_text(self):
        """Unread-notification badge next to the bell ('9+'), '' when absent."""
        for element in self.driver.find_elements(
            By.XPATH, "//button[string-length(normalize-space())<=3]"
        ):
            try:
                text = element.text.strip()
            except WebDriverException:
                continue
            if re.fullmatch(r"\d+\+?", text):
                return text
        return ""

    def get_grid_headers(self, locator):
        return [
            header.text.strip()
            for header in self.driver.find_elements(*locator)
            if header.text.strip()
        ]

    def get_published_grid_headers(self):
        return self.get_grid_headers(self.PUBLISHED_GRID_HEADERS)
