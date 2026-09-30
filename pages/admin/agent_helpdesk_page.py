"""The L1 / L2 helpdesk agent workspace (/l1/helpdesk, /l2/helpdesk).

A helpdesk agent does not use the admin queue. Signing in as helpdesk1@dev.com
lands on `/l1/helpdesk` and as the L2 agent on `/l2/helpdesk` - separate routes
with their own grids, which `HelpdeskPage` cannot reach because its `PATH` is
hardcoded to `/admin/helpdesk`. That is why nothing in M2 exercised an agent
working a ticket until now.

Three differences from the admin queue, all confirmed against QA 2026-09-08:

- **The columns differ per tier.** L1 renders nine columns and no `Resolved`;
  L2 renders ten, adding `Resolved` between `Created` and `Assigned To`. The
  admin grid adds `SLA Breach` on top. Fixed column indices are therefore
  wrong for at least one tier, so every cell here is read by *header name*.
- **Resolving lives in the View panel, not the row menu.** The row kebab offers
  only `View` and `Assign` for L1; the panel it opens carries a comment box and
  a `Resolve & Close Ticket` button. (L2's row menu does surface `Resolve`, but
  the panel route works for both tiers, so it is the one used here.)
- **L2 never sees the raw queue.** Its `Open` tab reads 0: L2 only holds work
  escalated to it. Asserting that boundary is part of the point.
"""

from time import sleep

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By

from pages.admin.helpdesk_page import HelpdeskPage


class AgentHelpdeskPage(HelpdeskPage):
    """One helpdesk tier's workspace. `tier` is "l1" or "l2"."""

    # The agent workspaces title themselves per tier - "L1 Helpdesk", "L2
    # Helpdesk" - so the admin page's exact-match header never resolves here
    # and wait_for_ready() times out on a page that rendered perfectly.
    PAGE_HEADER = (By.XPATH, "//h1[contains(normalize-space(),'Helpdesk')]")

    # The admin queue's box reads "Search by Ticket ID..."; the agent grids say
    # "Search by ticket ID, subject, category...". XPath contains() is
    # case-sensitive, so the inherited locator matches neither tier and every
    # search timed out on a search box that was sitting right there. Folded to
    # lower case so one locator serves all three surfaces.
    SEARCH_INPUT = (
        By.XPATH,
        "//input[contains(translate(@placeholder,"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
        "'search by ticket')]",
    )

    VIEW_COMMENT_BOX = (By.XPATH, "//textarea[@placeholder='Enter your comment']")
    RESOLVE_CLOSE_BTN = (
        By.XPATH,
        "//button[normalize-space()='Resolve & Close Ticket']",
    )
    VIEW_CLOSE_BTN = (By.XPATH, "//button[normalize-space()='Close']")
    # The row-menu Resolve path's own submit, which the form disables until a
    # comment has been entered.
    RESOLVE_SUBMIT_BTN = (By.XPATH, "//button[normalize-space()='Resolve Ticket']")
    ACTION_RESOLVE = (By.XPATH, "//*[@role='menuitem'][normalize-space()='Resolve']")

    def __init__(self, driver, tier):
        super().__init__(driver)
        tier = str(tier).strip().lower()
        if tier not in ("l1", "l2"):
            raise ValueError(f"Unknown helpdesk tier {tier!r}; expected 'l1' or 'l2'.")
        self.tier = tier

    @property
    def path(self):
        return f"/{self.tier}/helpdesk"

    def open(self, base_url):
        self.driver.get(base_url.rstrip("/") + self.path)
        self.wait_for_ready()

    def is_on_page(self):
        """The agent grid rendering is the signal, not the admin page header.

        The tiers share the 'Helpdesk' heading with the admin queue but not its
        subtext, so requiring the admin furniture here would fail on a page
        that is perfectly healthy.
        """
        return bool(self.driver.find_elements(*self.TABLE_ROWS)) or self.is_element_visible_quick(
            self.EMPTY_STATE, timeout=3
        )

    # ------------------------------------------------------------- columns

    def column_index(self, header_name):
        """1-based index of a column, by its visible header.

        Returns None when this tier does not render that column - L1 has no
        `Resolved` column at all, and a caller asking for it should get a clean
        None rather than silently reading whatever sits at a fixed offset.
        """
        for index, header in enumerate(self.get_table_headers(), start=1):
            if header.strip().casefold() == str(header_name).strip().casefold():
                return index
        return None

    def get_row_values(self, row):
        """Row cells keyed by header name, so a tier's column layout cannot
        shift what a caller thinks it is reading."""
        cells = [cell.text.strip() for cell in row.find_elements(By.XPATH, "./td")]

        def by_header(name):
            index = self.column_index(name)
            if index is None or index > len(cells):
                return ""
            return cells[index - 1]

        return {
            "ticket_id": by_header("Ticket ID"),
            "subject": by_header("Subject"),
            "raised_by": by_header("Raised By"),
            "category": by_header("Category"),
            "priority": by_header("Priority"),
            "status": by_header("Status"),
            "created": by_header("Created"),
            "resolved": by_header("Resolved"),
            "assignee": by_header("Assigned To"),
        }

    def find_ticket(self, ticket_id):
        """This tier's row for a ticket, or None when it holds no such ticket."""
        self.search_ticket(ticket_id)
        for row in self.get_rows():
            try:
                values = self.get_row_values(row)
            except WebDriverException:
                continue
            if values["ticket_id"] == ticket_id:
                return values
        return None

    def holds_ticket(self, ticket_id):
        return self.find_ticket(ticket_id) is not None

    # ---------------------------------------------------------- view panel

    VIEW_PANEL_SIGNALS = (RESOLVE_CLOSE_BTN, VIEW_COMMENT_BOX)

    def open_view(self, ticket_id, attempts=2):
        """Open a ticket's detail panel through the row menu.

        The panel is considered open once either of its own controls is on
        screen. Keying only on the Resolve button made this brittle: the panel
        paints its comment box first, and a slow render then timed out on a
        panel that had in fact opened.
        """
        last_error = None
        for attempt in range(attempts):
            try:
                self.open_row_actions(ticket_id)
                self.click_element(self.ACTION_VIEW)
                self.wait_utils.until_condition(
                    lambda driver: any(
                        self.is_element_visible_quick(locator, timeout=1)
                        for locator in self.VIEW_PANEL_SIGNALS
                    ),
                    timeout=30,
                )
                return
            except (TimeoutException, WebDriverException) as error:
                last_error = error
                if attempt < attempts - 1:
                    self.dismiss_overlays()
                    sleep(2)
        raise TimeoutException(
            f"The detail panel for {ticket_id} did not open: neither its Resolve "
            "control nor its comment box appeared."
        ) from last_error

    def is_view_open(self):
        return self.is_element_visible_quick(self.RESOLVE_CLOSE_BTN, timeout=3)

    def add_comment(self, text):
        """Type into the panel's comment box. Returns False when absent."""
        if not self.is_element_visible_quick(self.VIEW_COMMENT_BOX, timeout=5):
            return False
        box = self.wait_utils.until_visible(self.VIEW_COMMENT_BOX, timeout=10)
        box.clear()
        box.send_keys(text)
        return True

    def can_resolve(self):
        """Does this tier offer resolution on the open ticket?"""
        return self.is_element_visible_quick(self.RESOLVE_CLOSE_BTN, timeout=5)

    def resolve_and_close(self, ticket_id, comment=None):
        """Resolve the open ticket and wait for the grid to reflect it.

        Returns the status the row reads afterwards. Resolution is a one-way
        move on shared data, so the caller is expected to have created the
        ticket it is resolving.
        """
        # The tiers resolve through different controls. L1 has no Resolve entry
        # in its row menu and closes from the detail panel's "Resolve & Close
        # Ticket"; L2 carries Resolve in the row menu itself and its panel may
        # not offer that button at all. Preferring the panel keeps the comment
        # attached to the ticket, so it is tried first and the row menu is the
        # fallback rather than the other way round.
        if not self.is_view_open():
            self.open_view(ticket_id)
        if comment:
            self.add_comment(comment)

        self.pause_before_action()
        if self.is_element_visible_quick(self.RESOLVE_CLOSE_BTN, timeout=5):
            self.click_element(self.RESOLVE_CLOSE_BTN)
        else:
            self.close_view()
            actions = self.get_row_action_items(ticket_id)
            if "Resolve" not in actions:
                raise TimeoutException(
                    f"Neither the detail panel nor the row menu offers a way to "
                    f"resolve {ticket_id}; the row menu holds {actions}."
                )
            # get_row_action_items() closes the menu again on its way out, so
            # the entry it just reported is no longer on screen. Reopen before
            # clicking, or the click times out on a menu that is shut.
            self.open_row_actions(ticket_id)
            self.click_element(self.ACTION_RESOLVE)

            # Resolve does not commit anything by itself: it opens a form whose
            # "Resolve Ticket" button stays *disabled* until a comment is
            # typed. Clicking Resolve and walking away leaves the ticket
            # exactly as it was - which is how this looked like a product bug
            # ("still reads In Progress") when it was an unfinished form.
            self.wait_utils.until_visible(self.VIEW_COMMENT_BOX, timeout=20)
            self.add_comment(comment or "Resolved by automation.")
            self.wait_utils.until_condition(
                lambda driver: self.is_element_visible_quick(
                    self.RESOLVE_SUBMIT_BTN, timeout=1
                )
                and driver.find_element(*self.RESOLVE_SUBMIT_BTN).is_enabled(),
                timeout=20,
            )
            self.click_element(self.RESOLVE_SUBMIT_BTN)
        self.confirm_dialog_if_present()

        def settled(driver):
            try:
                return not self.is_element_visible_quick(self.RESOLVE_CLOSE_BTN, timeout=1)
            except WebDriverException:
                return False

        try:
            self.wait_utils.until_condition(settled, timeout=30)
        except TimeoutException:
            pass
        sleep(2)
        self.switch_tab("All")
        values = self.find_ticket(ticket_id)
        return (values or {}).get("status", "")

    CONFIRM_BUTTONS = (
        By.XPATH,
        "//*[@role='dialog' or contains(@class,'modal')]"
        "//button[normalize-space()='Confirm' or normalize-space()='Yes' "
        "or normalize-space()='Resolve' or normalize-space()='OK']",
    )

    def confirm_dialog_if_present(self):
        """Accept a confirmation dialog, if the build raises one.

        `AdminPortalPage.confirm_if_prompted` cannot be reused here: HelpdeskPage
        extends BasePage, not AdminPortalPage, so calling it raised
        AttributeError *after* the resolve click had already gone through -
        failing a test whose action had actually succeeded.
        """
        try:
            if self.is_element_visible_quick(self.CONFIRM_BUTTONS, timeout=3):
                self.click_element(self.CONFIRM_BUTTONS)
                return True
        except WebDriverException:
            pass
        return False

    def close_view(self):
        try:
            if self.is_element_visible_quick(self.VIEW_CLOSE_BTN, timeout=3):
                self.click_element(self.VIEW_CLOSE_BTN)
        except WebDriverException:
            pass
        self.dismiss_overlays()

    # -------------------------------------------------------- reassignment

    def assign_to(self, ticket_id, agent_name, priority=None):
        """Hand a ticket to another agent from this tier's grid.

        Reuses the admin queue's assign panel, which the agent grids render
        identically.
        """
        return self.reassign_ticket(ticket_id, agent_name, priority)
