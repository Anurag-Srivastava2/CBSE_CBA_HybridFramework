import re
from time import sleep, time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.common.base_page import BasePage


class SupportPage(BasePage):
    """Help & Support (/support) — available to every signed-in role.

    Left column is "My Tickets", a card list (not a table) behind
    All/Open/Closed/Reopened tabs. Right column is the "Register New Issue"
    form. Opening a ticket slides in a Radix sheet carrying the issue detail,
    its attachments and the status history.
    """

    PATH = "/support"

    TICKET_ID_PATTERN = re.compile(r"CBSE-HD-\d{4}-\d+")

    CATEGORY_OPTIONS = (
        "Item Bank",
        "Item Management",
        "Item Workflow",
        "Login and Access",
        "Portal Error",
        "QAR Tool",
        "Training",
    )

    TICKET_TABS = ("All", "Open", "Closed", "Reopened")

    PAGE_HEADER = (By.XPATH, "//h1[normalize-space()='Help & Support']")
    SUBTEXT = (By.XPATH, "//*[contains(normalize-space(),'Register portal-related issues')]")

    # ------------------------------------------------------ register new issue
    FORM_HEADER = (By.XPATH, "//*[normalize-space()='Register New Issue']")
    SUBJECT_INPUT = (By.ID, "support-subject")
    DESCRIPTION_INPUT = (By.ID, "support-description")
    REG_DATE_INPUT = (By.ID, "support-reg-date")
    # The category select is a Radix combobox; anchor it to its own label so the
    # locator survives the trigger text changing from 'Select Category'.
    CATEGORY_TRIGGER = (
        By.XPATH,
        "//label[starts-with(normalize-space(),'Category')]/following::button[@role='combobox'][1]",
    )
    # The real file input is visually hidden behind the drag & drop zone.
    FILE_INPUT = (By.ID, "support-file-input")
    DROPZONE = (By.XPATH, "//*[contains(@class,'dropzone')]")
    FILE_PREVIEW_NAME = (By.XPATH, "//*[contains(@class,'filePreviewName')]")
    FILE_REMOVE_BTN = (By.XPATH, "//button[@aria-label='Remove attachment']")
    SUBMIT_BTN = (By.XPATH, "//button[normalize-space()='Submit Issue']")

    # -------------------------------------------------------------- my tickets
    MY_TICKETS_HEADER = (By.XPATH, "//h2[normalize-space()='My Tickets']")
    # The trailing underscore matters: 'ticketCard' alone also matches each
    # card's inner _ticketCardTop_ header, doubling the apparent card count.
    TICKET_CARDS = (By.XPATH, "//div[contains(@class,'_ticketCard_')]")

    # ---------------------------------------------------------- details sheet
    DETAILS_PANEL = (By.XPATH, "//*[@role='dialog'][@data-slot='sheet-content']")
    DETAILS_TICKET_NUMBER = (By.XPATH, "//*[@role='dialog']//*[contains(@class,'ticketNumber')]")
    DETAILS_TITLE = (By.XPATH, "//*[@role='dialog']//h2[contains(@class,'title')]")
    DETAILS_ATTACHMENTS_HEADING = (
        By.XPATH,
        "//*[@role='dialog']//*[normalize-space()='ATTACHMENTS']",
    )
    DETAILS_ATTACHMENT_CARDS = (
        By.XPATH,
        "//*[@role='dialog']//*[contains(@class,'attachmentCard')]",
    )
    DETAILS_CLOSE_BTN = (By.XPATH, "//*[@role='dialog']//button[normalize-space()='Close']")

    TOAST = (
        By.XPATH,
        "//*[@data-slot='toast' or @role='status' or @role='alert' or contains(@class,'toast')]",
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
        self.wait_utils.until_visible(self.SUBJECT_INPUT, timeout=timeout)

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

    # -------------------------------------------------------------- form entry

    def get_registration_date(self):
        try:
            return self.driver.find_element(*self.REG_DATE_INPUT).get_attribute("value").strip()
        except WebDriverException:
            return ""

    def is_registration_date_readonly(self):
        try:
            return bool(self.driver.find_element(*self.REG_DATE_INPUT).get_attribute("readonly"))
        except WebDriverException:
            return False

    def select_category(self, category_name):
        self.dismiss_overlays()
        self.click_resilient(self.CATEGORY_TRIGGER)
        option = (By.XPATH, f"//*[@role='option'][normalize-space()='{category_name}']")
        element = self.wait_utils.until_visible(option, timeout=15)
        self.element_utils.scroll_to_element(element)
        self.click_resilient(option)
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*self.CATEGORY_TRIGGER).get_attribute("aria-expanded")
                != "true",
                timeout=15,
            )
        except (TimeoutException, WebDriverException):
            self.dismiss_overlays()
        sleep(1)

    def get_selected_category(self):
        try:
            return self.get_text(self.CATEGORY_TRIGGER).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def get_category_options(self):
        self.click_resilient(self.CATEGORY_TRIGGER)
        sleep(1.5)
        options = [
            option.text.strip()
            for option in self.driver.find_elements(By.XPATH, "//*[@role='option']")
            if option.text.strip()
        ]
        self.dismiss_overlays()
        return options

    def fill_ticket_form(self, subject, description, category_name):
        self.enter_text(self.SUBJECT_INPUT, subject)
        self.enter_text(self.DESCRIPTION_INPUT, description)
        self.select_category(category_name)

    def attach_file(self, file_path):
        """Push an absolute path straight at the hidden <input type='file'>.

        send_keys is used rather than a click because the visible control is a
        drag & drop zone that would open an OS dialog Selenium cannot drive.
        """
        file_input = self.wait_utils.until_present(self.FILE_INPUT, timeout=20)
        file_input.send_keys(str(file_path))
        self.wait_utils.until_visible(self.FILE_PREVIEW_NAME, timeout=20)

    def get_attached_file_name(self):
        try:
            return self.get_text(self.FILE_PREVIEW_NAME).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def remove_attachment(self):
        self.click_resilient(self.FILE_REMOVE_BTN)
        sleep(1)

    def is_submit_enabled(self):
        try:
            return not self.driver.find_element(*self.SUBMIT_BTN).get_attribute("disabled")
        except WebDriverException:
            return False

    def submit_ticket(self):
        """Submit the issue. The button stays disabled until the form validates,
        so this waits for it to go live rather than clicking into a no-op."""
        self.wait_utils.until_visible(self.SUBMIT_BTN, timeout=20)
        try:
            self.wait_utils.until_condition(lambda driver: self.is_submit_enabled(), timeout=20)
        except TimeoutException:
            raise TimeoutException(
                "'Submit Issue' stayed disabled — the ticket form did not validate. "
                f"Subject={self.driver.find_element(*self.SUBJECT_INPUT).get_attribute('value')!r}, "
                f"Category={self.get_selected_category()!r}"
            )
        submit = self.driver.find_element(*self.SUBMIT_BTN)
        self.element_utils.scroll_to_element(submit)
        self.pause_before_action()
        try:
            submit.click()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", submit)

    def create_ticket(self, subject, description, category_name, attachment_path=None):
        """Raise a ticket end to end and return the generated ticket number."""
        self.fill_ticket_form(subject, description, category_name)
        if attachment_path:
            self.attach_file(attachment_path)
        self.submit_ticket()
        return self.wait_for_ticket(subject)

    # -------------------------------------------------------------- my tickets

    @staticmethod
    def _tab_locator(label):
        return (By.XPATH, f"//*[@role='tab'][starts-with(normalize-space(),'{label}')]")

    def switch_ticket_tab(self, label):
        locator = self._tab_locator(label)
        self.click_resilient(locator)
        try:
            self.wait_utils.until_condition(
                lambda driver: driver.find_element(*locator).get_attribute("aria-selected") == "true",
                timeout=15,
            )
        except TimeoutException:
            raise TimeoutException(f"My Tickets tab {label!r} did not become selected.")
        sleep(1.5)

    def get_tab_count(self, label):
        """'All 13' -> 13; -1 when the tab carries no count."""
        try:
            raw = self.get_text(self._tab_locator(label)).strip()
        except (TimeoutException, WebDriverException):
            return -1
        digits = "".join(char if char.isdigit() else " " for char in raw).split()
        return int(digits[-1]) if digits else -1

    def get_ticket_cards(self):
        return self.driver.find_elements(*self.TICKET_CARDS)

    @staticmethod
    def _card_field(card, class_fragment):
        elements = card.find_elements(By.XPATH, f".//*[contains(@class,'{class_fragment}')]")
        return elements[0].text.strip() if elements else ""

    def get_card_values(self, card):
        return {
            "ticket_id": self._card_field(card, "ticketId"),
            "subject": self._card_field(card, "ticketTitle"),
            "date": self._card_field(card, "ticketDate"),
            "status": self._card_field(card, "statusBadge"),
        }

    def get_ticket_subjects(self):
        return [self.get_card_values(card)["subject"] for card in self.get_ticket_cards()]

    def get_ticket_ids(self):
        return [self.get_card_values(card)["ticket_id"] for card in self.get_ticket_cards()]

    def find_ticket_card(self, subject):
        for card in self.get_ticket_cards():
            try:
                if self.get_card_values(card)["subject"].strip() == subject.strip():
                    return card
            except WebDriverException:
                continue
        return None

    def wait_for_ticket(self, subject, timeout=45, base_url=None):
        """Wait for a freshly raised ticket to appear in My Tickets and return
        its generated ticket number.

        The list is refetched once part-way through: submission clears the form
        immediately, but the card list has been seen to lag behind the write.
        """
        deadline = time() + timeout
        reloaded = False
        while time() < deadline:
            card = self.find_ticket_card(subject)
            if card is not None:
                try:
                    return self.get_card_values(card)["ticket_id"]
                except WebDriverException:
                    pass
            if not reloaded and time() > deadline - timeout / 2:
                reloaded = True
                self.driver.refresh()
                self.wait_for_ready()
            sleep(2)
        raise TimeoutException(
            f"Ticket {subject!r} never appeared in My Tickets within {timeout}s. "
            f"Tab counts: {[(label, self.get_tab_count(label)) for label in self.TICKET_TABS]}. "
            f"Subjects on screen: {self.get_ticket_subjects()[:8]}"
        )

    def is_ticket_listed(self, subject):
        return self.find_ticket_card(subject) is not None

    # ----------------------------------------------------------- details sheet

    def open_ticket_details(self, subject):
        card = self.find_ticket_card(subject)
        if card is None:
            raise TimeoutException(f"No ticket card in My Tickets with subject {subject!r}.")
        button = card.find_element(By.XPATH, ".//button[contains(normalize-space(),'View Details')]")
        self.element_utils.scroll_to_element(button)
        self.pause_before_action()
        try:
            button.click()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", button)
        self.wait_utils.until_visible(self.DETAILS_PANEL, timeout=20)
        sleep(1)

    def is_details_open(self):
        return self.is_element_visible_quick(self.DETAILS_PANEL, timeout=10)

    def get_details_text(self):
        try:
            return self.get_text(self.DETAILS_PANEL).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def get_details_ticket_number(self):
        try:
            return self.get_text(self.DETAILS_TICKET_NUMBER).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def get_details_field(self, label):
        """Read a labelled value out of the ISSUE DETAILS block."""
        locator = (
            By.XPATH,
            f"//*[@role='dialog']//*[contains(@class,'metaLabel')][normalize-space()='{label}']"
            f"/following-sibling::*[1]",
        )
        try:
            return self.get_text(locator).strip()
        except (TimeoutException, WebDriverException):
            return ""

    def has_attachments_section(self):
        return self.is_element_visible_quick(self.DETAILS_ATTACHMENTS_HEADING, timeout=10)

    def get_attachment_names(self):
        return [
            card.text.strip()
            for card in self.driver.find_elements(*self.DETAILS_ATTACHMENT_CARDS)
            if card.text.strip()
        ]

    def is_file_in_details(self, filename):
        return any(filename in name for name in self.get_attachment_names())

    def close_details(self):
        if self.is_element_visible_quick(self.DETAILS_CLOSE_BTN, timeout=5):
            self.click_resilient(self.DETAILS_CLOSE_BTN)
        else:
            self.dismiss_overlays()
        try:
            self.wait_utils.until_condition(
                lambda driver: not self.is_element_visible_quick(self.DETAILS_PANEL, timeout=1),
                timeout=15,
            )
        except TimeoutException:
            self.dismiss_overlays()
        sleep(1)

    def get_toast_message(self, timeout=5):
        if not self.is_element_visible_quick(self.TOAST, timeout=timeout):
            return ""
        try:
            return self.get_text(self.TOAST).strip()
        except WebDriverException:
            return ""
