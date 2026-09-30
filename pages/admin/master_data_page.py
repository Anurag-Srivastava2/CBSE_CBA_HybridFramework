from time import monotonic, sleep

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.admin.admin_portal_page import AdminPortalPage
from utilities.read_config import ReadConfig


class MasterDataPage(AdminPortalPage):
    """Admin > Master Data Management (/admin/masterdata).

    Tabs: Grades, Subjects, Chapters, Curricular Goals, Competencies, Learning
    Outcomes, Bloom's Levels, Typologies.

    The Subjects grid lists Code / Subject / Applicable Grades and nothing
    else - there is no Actions column, so a subject can be added from here but
    never removed. Anything this page creates is permanent in the environment.
    """

    PATH = "/admin/masterdata"

    PAGE_HEADING = (
        By.XPATH,
        "//*[self::h1 or self::h2][normalize-space()='Master Data Management']",
    )
    SEARCH_INPUT = (By.XPATH, "//input[contains(@placeholder,'Search by ID')]")
    TABS = (By.XPATH, "//*[@role='tab']")
    TABLE_ROWS = (By.XPATH, "//table//tbody/tr[count(td) > 1]")

    ADD_SUBJECT_BUTTON = (By.XPATH, "//button[normalize-space()='Add Subject']")
    SUBJECT_NAME_INPUT = (By.ID, "subjectName")
    SUBJECT_CODE_INPUT = (By.ID, "subjectCode")
    GRADES_TRIGGER = (By.XPATH, "//button[normalize-space()='Select Grades']")
    ADD_BUTTON = (By.XPATH, "//button[normalize-space()='Add']")
    CANCEL_BUTTON = (By.XPATH, "//button[normalize-space()='Cancel']")

    def open(self, base_url=None):
        base = (base_url or ReadConfig.get_base_url()).rstrip("/")
        self.driver.get(base + self.PATH)
        self.wait_for_application_ready()
        self.wait_utils.until_visible(self.PAGE_HEADING, timeout=30)
        return self

    @staticmethod
    def tab_locator(label):
        return (
            By.XPATH,
            f"//*[@role='tab'][normalize-space()='{label}' or starts-with(normalize-space(),'{label}')]",
        )

    def open_tab(self, label):
        self.click_element(self.tab_locator(label))
        self.wait_for_application_ready()
        return self

    def search(self, value, timeout=15):
        """Type into the grid search box and wait for the grid to re-query.

        The search is debounced: wait_for_application_ready() returns while the
        old rows are still on screen, so a caller that read straight afterwards
        got the *previous* result set. That made is_subject_listed() report
        False for a subject that exists, which in turn made the caller try to
        create a duplicate.

        Settling is judged on the rendered rows rather than a fixed sleep: the
        row set is polled until it stops changing.
        """
        search_input = self.wait_utils.until_visible(self.SEARCH_INPUT, timeout=20)
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        search_input.send_keys(value)
        self.wait_for_application_ready()
        self.wait_for_rows_to_settle(timeout=timeout)

    def wait_for_rows_to_settle(self, timeout=15, stable_for=2):
        """Poll the grid until the rows stop changing, or the timeout expires."""
        deadline = monotonic() + timeout
        previous = None
        unchanged = 0
        while monotonic() < deadline:
            current = self.listed_rows()
            if current == previous:
                unchanged += 1
                if unchanged >= stable_for:
                    return current
            else:
                unchanged = 0
                previous = current
            sleep(0.5)
        return self.listed_rows()

    def listed_rows(self):
        """Every visible row as a list of cell strings.

        Read in a single scripted pass rather than element by element: the
        grid re-renders as its query settles, and walking WebElements across
        that re-render raises StaleElementReferenceException part-way through
        a read that had already half succeeded.
        """
        return (
            self.driver.execute_script(
                """
                return Array.from(document.querySelectorAll('table tbody tr'))
                    .filter(row => row.querySelectorAll('td').length > 1)
                    .map(row => Array.from(row.querySelectorAll('td'))
                        .map(cell => (cell.innerText || '').trim()));
                """
            )
            or []
        )

    def is_subject_listed(self, subject_name):
        self.search(subject_name)
        return any(
            subject_name.casefold() in cell.casefold()
            for row in self.listed_rows()
            for cell in row
        )

    def has_row_action_control(self):
        """True when the grid offers any per-row action (delete, archive, edit).

        The Subjects tab renders three plain text columns, so this is False on
        this build - which is exactly what a "deleting a linked subject is
        blocked" contract needs to know before it can be asserted at all.
        """
        return bool(
            self.driver.find_elements(
                By.XPATH,
                "//table//tbody//tr//button | //table//thead//th[normalize-space()='Actions']",
            )
        )

    def add_subject(self, subject_name, subject_code, grades=("Grade 5",)):
        """Create a subject from the Subjects tab.

        The form is rendered inline under the grid rather than in a dialog.
        """
        self.click_element(self.ADD_SUBJECT_BUTTON)
        self.wait_utils.until_visible(self.SUBJECT_NAME_INPUT, timeout=20)
        self.enter_text(self.SUBJECT_NAME_INPUT, subject_name)
        self.enter_text(self.SUBJECT_CODE_INPUT, subject_code)
        # Radix dropdown-menu: it opens on pointerdown, so this needs a real
        # click, and its entries are role="menuitem" - not menuitemcheckbox -
        # even though they behave as a multi-select. Matching the label exactly
        # matters too: contains() for "Grade 1" also hits Grade 10, 11 and 12.
        self.click_element(self.GRADES_TRIGGER)
        for grade in grades:
            option = (
                By.XPATH,
                "//*[@role='menuitem' or @role='menuitemcheckbox' or @role='option']"
                f"[normalize-space()='{grade}']",
            )
            if not self.is_element_visible_quick(option, timeout=10):
                raise TimeoutException(
                    f"{grade!r} is not offered by the Applicable Grades menu."
                )
            self.click_element(option)
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        self.click_element(self.ADD_BUTTON)
        self.wait_utils.until_condition(
            lambda driver: not self.is_element_visible_quick(self.SUBJECT_NAME_INPUT, timeout=1),
            timeout=30,
        )
        self.wait_for_application_ready()

    def cancel_subject_form(self):
        if self.is_element_visible_quick(self.SUBJECT_NAME_INPUT, timeout=3):
            self.click_element(self.CANCEL_BUTTON)
            self.wait_for_application_ready()
