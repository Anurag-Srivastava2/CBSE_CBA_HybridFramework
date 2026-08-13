import re
from time import sleep

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class HelpdeskPage(BasePage):
    """Admin > Helpdesk (/admin/helpdesk).

    The global ticket queue every role's Help & Support submission lands in.
    Columns: Ticket ID | Subject | Raised By | Category | Priority | Status |
    Created | Resolved | Assigned To | SLA Breach | Actions.
    """

    PATH = "/admin/helpdesk"

    COLUMN_TICKET_ID = 1
    COLUMN_SUBJECT = 2
    COLUMN_RAISED_BY = 3
    COLUMN_CATEGORY = 4
    COLUMN_PRIORITY = 5
    COLUMN_STATUS = 6
    COLUMN_CREATED = 7
    COLUMN_RESOLVED = 8
    COLUMN_ASSIGNED_TO = 9
    COLUMN_SLA_BREACH = 10

    EXPECTED_COLUMNS = (
        "Ticket ID",
        "Subject",
        "Raised By",
        "Category",
        "Priority",
        "Status",
        "Created",
        "Resolved",
        "Assigned To",
        "SLA Breach",
        "Actions",
    )

    FILTER_LABELS = ("Category", "Assigned To", "Priority", "Status")
    QUEUE_TABS = ("All", "Open", "In Progress", "Resolved", "Overdue")

    # Tabs whose name is also the Status value each row must carry. 'All' mixes
    # statuses and 'Overdue' is an SLA bucket, so neither maps to one status.
    STATUS_TABS = ("Open", "In Progress", "Resolved")

    KPI_LABELS = ("Open Tickets", "Resolved Today", "Avg Resolution Time", "Overdue Tickets")
    # Avg Resolution Time renders as a duration ('0.1 h'), not a plain count.
    COUNT_KPI_LABELS = ("Open Tickets", "Resolved Today", "Overdue Tickets")

    TICKET_ID_PATTERN = re.compile(r"CBSE-HD-\d{4}-\d+")

    KNOWN_STATUSES = ("Open", "In Progress", "Resolved", "Closed")
    KNOWN_PRIORITIES = ("Auto Assign", "Low", "Medium", "High", "Critical")

    PAGE_HEADER = (By.XPATH, "//h1[normalize-space()='Helpdesk']")
    SUBTEXT = (By.XPATH, "//*[contains(normalize-space(),'Issue registration, tracking and resolution')]")
    SEARCH_INPUT = (By.XPATH, "//input[contains(@placeholder,'Search by Ticket ID')]")
    CREATE_TICKET_BTN = (By.XPATH, "//button[normalize-space()='Create Ticket']")

    TABLE = (By.XPATH, "//table")
    TABLE_HEADERS = (By.XPATH, "//table//th")
    TABLE_ROWS = (By.XPATH, "//table//tbody//tr[@data-slot='tbody-row']")
    EMPTY_STATE = (
        By.XPATH,
        "//table//tbody//tr[contains(normalize-space(),'No Data to display')]",
    )

    # Row kebab -> View / Assign. Assign opens an accordion row rather than a
    # modal, so the panel is a sibling <tr data-expanded-content>.
    ROW_ACTIONS_KEBAB = ".//button[@data-slot='dropdown-menu-trigger']"
    ACTION_ASSIGN = (By.XPATH, "//*[@role='menuitem'][normalize-space()='Assign']")
    ACTION_VIEW = (By.XPATH, "//*[@role='menuitem'][normalize-space()='View']")

    ASSIGN_PANEL = (By.XPATH, "//table//tbody//tr[@data-expanded-content='true']")
    ASSIGN_PANEL_TITLE = (
        By.XPATH,
        "//tr[@data-expanded-content='true']//h2[starts-with(normalize-space(),'Assign Ticket')]",
    )
    # The visible labels are upper-cased by CSS; the DOM reads 'Assign To (L2
    # Agent)' and 'Priority'. The id prefixes are the stable hook.
    ASSIGN_AGENT_SELECT = (By.XPATH, "//button[@role='combobox'][starts-with(@id,'agent-')]")
    ASSIGN_PRIORITY_SELECT = (By.XPATH, "//button[@role='combobox'][starts-with(@id,'priority-')]")
    ASSIGN_CONFIRM_BTN = (
        By.XPATH,
        "//tr[@data-expanded-content='true']//button[normalize-space()='Assign Ticket']",
    )
    ASSIGN_CANCEL_BTN = (
        By.XPATH,
        "//tr[@data-expanded-content='true']//button[normalize-space()='Cancel']",
    )

    # ------------------------------------------------------------------- setup

    def open(self, base_url):
        self.driver.get(base_url.rstrip("/") + self.PATH)
        self.wait_for_ready()

    def wait_for_ready(self, timeout=45, attempts=2):
        """Wait for the queue to render.

        The SPA can park on 'Loading admin dashboard…' indefinitely when the
        environment is slow, and it recovers on a reload rather than on its
        own — so a stalled load is refreshed instead of failing the test.
        """
        last_error = None
        for attempt in range(attempts):
            try:
                self.wait_utils.until_condition(
                    lambda driver: "loading"
                    not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
                    timeout=timeout,
                )
                self.wait_utils.until_visible(self.PAGE_HEADER, timeout=timeout)
                self.wait_utils.until_visible(self.TABLE, timeout=timeout)
                return
            except TimeoutException as error:
                last_error = error
                if attempt < attempts - 1:
                    self.driver.refresh()
                    sleep(3)
        raise TimeoutException(
            f"The Helpdesk queue did not finish loading after {attempts} attempts of "
            f"{timeout}s each."
        ) from last_error

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
        try:
            self.click_element(locator)
        except WebDriverException:
            self.dismiss_overlays()
            self.element_utils.js_click(locator)

    # --------------------------------------------------------------- kpi cards

    @staticmethod
    def _kpi_value_locator(label):
        """Each card renders its value *before* its label, so the value is
        reached through the card rather than as a following sibling."""
        return (
            By.XPATH,
            f"//article[contains(@class,'statCard')]"
            f"[.//*[contains(@class,'statLabel')][normalize-space()='{label}']]"
            f"//*[contains(@class,'statValue')]",
        )

    def is_kpi_visible(self, label):
        return self.is_element_visible_quick(self._kpi_value_locator(label), timeout=10)

    def missing_kpis(self):
        return [label for label in self.KPI_LABELS if not self.is_kpi_visible(label)]

    def get_kpi_text(self, label):
        """Raw card value — '18' for a count, '0.1 h' for Avg Resolution Time."""
        try:
            return self.get_text(self._kpi_value_locator(label)).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def get_kpi_value(self, label):
        """Whole-number card value, or -1 when the card is not a plain count."""
        match = re.fullmatch(r"\d+", self.get_kpi_text(label))
        return int(match.group()) if match else -1

    def get_all_kpi_text(self):
        return {label: self.get_kpi_text(label) for label in self.KPI_LABELS}

    # ------------------------------------------------------------------- table

    def get_table_headers(self):
        return [header.text.strip() for header in self.driver.find_elements(*self.TABLE_HEADERS) if header.text.strip()]

    def missing_columns(self):
        headers = self.get_table_headers()
        return [column for column in self.EXPECTED_COLUMNS if column not in headers]

    def get_rows(self):
        """Data rows only — the empty state renders a placeholder with no
        Ticket ID, which must not count as a ticket."""
        rows = []
        for row in self.driver.find_elements(*self.TABLE_ROWS):
            try:
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < self.COLUMN_STATUS:
                    continue
                if not cells[self.COLUMN_TICKET_ID - 1].text.strip():
                    continue
                rows.append(row)
            except WebDriverException:
                continue
        return rows

    def get_row_count(self):
        return len(self.get_rows())

    def get_row_values(self, row):
        cells = [cell.text.strip() for cell in row.find_elements(By.XPATH, "./td")]

        def cell(index):
            return cells[index - 1] if len(cells) >= index else ""

        return {
            "ticket_id": cell(self.COLUMN_TICKET_ID),
            "subject": cell(self.COLUMN_SUBJECT),
            "raised_by": cell(self.COLUMN_RAISED_BY),
            "category": cell(self.COLUMN_CATEGORY),
            "priority": cell(self.COLUMN_PRIORITY),
            "status": cell(self.COLUMN_STATUS),
            "created": cell(self.COLUMN_CREATED),
            "assigned_to": cell(self.COLUMN_ASSIGNED_TO),
            "sla_breach": cell(self.COLUMN_SLA_BREACH),
        }

    def _column_values(self, column_index):
        values = []
        for row in self.get_rows():
            try:
                values.append(row.find_elements(By.XPATH, "./td")[column_index - 1].text.strip())
            except (IndexError, WebDriverException):
                continue
        return values

    def get_ticket_ids_in_view(self):
        return self._column_values(self.COLUMN_TICKET_ID)

    def get_subjects_in_view(self):
        return self._column_values(self.COLUMN_SUBJECT)

    def get_statuses_in_view(self):
        return self._column_values(self.COLUMN_STATUS)

    def is_empty_state(self):
        """True when the grid is showing its 'No Data to display' placeholder."""
        return self.is_element_visible_quick(self.EMPTY_STATE, timeout=5)

    def get_newest_ticket(self):
        """Row values of the most recently raised ticket.

        The queue is ordered newest first, but ticket numbers are the
        authoritative ordering, so the highest sequence number wins.
        """
        rows = [self.get_row_values(row) for row in self.get_rows()]
        numbered = [
            values
            for values in rows
            if self.TICKET_ID_PATTERN.fullmatch(values["ticket_id"])
        ]
        if not numbered:
            return None
        return max(numbered, key=lambda values: int(values["ticket_id"].rsplit("-", 1)[-1]))

    # ------------------------------------------------------------------ search

    def search_ticket(self, term):
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

    def find_ticket(self, ticket_id):
        """Row values for a ticket number, or None when it is not in view."""
        for row in self.get_rows():
            try:
                values = self.get_row_values(row)
            except WebDriverException:
                continue
            if values["ticket_id"] == ticket_id:
                return values
        return None

    def is_ticket_present(self, ticket_id):
        return self.find_ticket(ticket_id) is not None

    # ------------------------------------------------------------ reassigning

    def get_assignees_in_view(self):
        return self._column_values(self.COLUMN_ASSIGNED_TO)

    def find_tickets_assigned_to(self, assignee):
        """Ticket numbers currently sitting with a given agent."""
        return [
            values["ticket_id"]
            for values in (self.get_row_values(row) for row in self.get_rows())
            if values["assigned_to"] == assignee
        ]

    def _row_for_ticket(self, ticket_id):
        for row in self.get_rows():
            try:
                if self.get_row_values(row)["ticket_id"] == ticket_id:
                    return row
            except WebDriverException:
                continue
        raise TimeoutException(f"Ticket {ticket_id!r} is not present in the current queue view.")

    def open_row_actions(self, ticket_id):
        """Open a row's kebab menu. Radix ignores synthetic clicks, so this
        must be a real pointer event on the trigger."""
        row = self._row_for_ticket(ticket_id)
        kebab = row.find_element(By.XPATH, self.ROW_ACTIONS_KEBAB)
        self.element_utils.scroll_to_element(kebab)
        self.pause_before_action()
        kebab.click()
        self.wait_utils.until_condition(
            lambda driver: kebab.get_attribute("data-state") == "open", timeout=15
        )
        sleep(0.5)

    def get_row_action_items(self, ticket_id):
        self.open_row_actions(ticket_id)
        items = [
            item.text.strip()
            for item in self.driver.find_elements(By.XPATH, "//*[@role='menuitem']")
            if item.text.strip()
        ]
        self.dismiss_overlays()
        return items

    def open_assign_panel(self, ticket_id):
        self.open_row_actions(ticket_id)
        self.click_element(self.ACTION_ASSIGN)
        self.wait_utils.until_visible(self.ASSIGN_PANEL_TITLE, timeout=20)
        sleep(1)

    def is_assign_panel_open(self):
        return self.is_element_visible_quick(self.ASSIGN_PANEL_TITLE, timeout=10)

    def get_assign_panel_title(self):
        try:
            return self.get_text(self.ASSIGN_PANEL_TITLE).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def _select_option(self, trigger, option_text):
        self.click_element(trigger)
        option = (By.XPATH, f"//*[@role='option'][normalize-space()='{option_text}']")
        element = self.wait_utils.until_visible(option, timeout=15)
        self.element_utils.scroll_to_element(element)
        element.click()
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*trigger).get_attribute("aria-expanded") != "true",
                timeout=15,
            )
        except (TimeoutException, WebDriverException):
            self.dismiss_overlays()
        sleep(1)

    def _list_options(self, trigger):
        self.click_element(trigger)
        sleep(1.5)
        options = [
            option.text.strip()
            for option in self.driver.find_elements(By.XPATH, "//*[@role='option']")
            if option.text.strip()
        ]
        self.dismiss_overlays()
        return options

    def get_agent_options(self):
        return self._list_options(self.ASSIGN_AGENT_SELECT)

    def get_priority_options(self):
        return self._list_options(self.ASSIGN_PRIORITY_SELECT)

    def get_selected_agent(self):
        try:
            return self.get_text(self.ASSIGN_AGENT_SELECT).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def select_agent(self, agent_name):
        self._select_option(self.ASSIGN_AGENT_SELECT, agent_name)

    def select_priority(self, priority):
        self._select_option(self.ASSIGN_PRIORITY_SELECT, priority)

    def is_assign_confirm_enabled(self):
        try:
            return not self.driver.find_element(*self.ASSIGN_CONFIRM_BTN).get_attribute("disabled")
        except WebDriverException:
            return False

    def confirm_assign(self):
        if not self.is_assign_confirm_enabled():
            raise TimeoutException(
                "'Assign Ticket' stayed disabled — no agent was accepted by the panel."
            )
        self.click_element(self.ASSIGN_CONFIRM_BTN)
        # The confirm button flips to 'Assigning...' while the write is in
        # flight and the panel only closes once it lands, which can take well
        # over 20s on this environment.
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.is_element_visible_quick(self.ASSIGN_PANEL_TITLE, timeout=1),
                timeout=60,
            )
        except TimeoutException:
            raise TimeoutException(
                "The assign panel stayed open 60s after confirming "
                f"(panel still reads {self.get_assign_panel_title()!r})."
            )
        sleep(2)

    def cancel_assign(self):
        if self.is_element_visible_quick(self.ASSIGN_CANCEL_BTN, timeout=5):
            self.click_element(self.ASSIGN_CANCEL_BTN)
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.is_element_visible_quick(self.ASSIGN_PANEL_TITLE, timeout=1),
                timeout=15,
            )
        except TimeoutException:
            self.dismiss_overlays()
        sleep(1)

    def reassign_ticket(self, ticket_id, agent_name, priority=None):
        """Move a ticket to another L2 agent and wait for the grid to catch up."""
        self.open_assign_panel(ticket_id)
        self.select_agent(agent_name)
        if priority:
            self.select_priority(priority)
        self.confirm_assign()
        try:
            self.wait_utils.until_condition(
                lambda driver: (self.find_ticket(ticket_id) or {}).get("assigned_to") == agent_name,
                timeout=25,
            )
        except TimeoutException:
            pass
        return (self.find_ticket(ticket_id) or {}).get("assigned_to", "")

    # ----------------------------------------------------------------- filters

    def _filter_trigger(self, label):
        """The queue filters are dropdown-menu triggers, not selects, and their
        label may sit in a nested span — so match either shape."""
        return (
            By.XPATH,
            f"//button[@aria-haspopup='menu' or @role='combobox']"
            f"[starts-with(normalize-space(),'{label}')"
            f" or .//span[starts-with(normalize-space(),'{label}')]]",
        )

    def is_filter_visible(self, label):
        return self.is_element_visible_quick(self._filter_trigger(label), timeout=10)

    def missing_filters(self):
        return [label for label in self.FILTER_LABELS if not self.is_filter_visible(label)]

    # -------------------------------------------------------------------- tabs

    @staticmethod
    def _tab_locator(label):
        return (By.XPATH, f"//*[@role='tab'][starts-with(normalize-space(),'{label}')]")

    def get_tab_count(self, label):
        """'Open 16' -> 16; -1 when the tab carries no count."""
        try:
            raw = self.get_text(self._tab_locator(label)).strip()
        except (TimeoutException, WebDriverException):
            return -1
        digits = "".join(char if char.isdigit() else " " for char in raw).split()
        return int(digits[-1]) if digits else -1

    def switch_tab(self, label):
        locator = self._tab_locator(label)
        self.click_resilient(locator)
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*locator).get_attribute("aria-selected") == "true",
                timeout=15,
            )
        except TimeoutException:
            raise TimeoutException(f"Helpdesk tab {label!r} did not become selected.")
        sleep(1.5)
