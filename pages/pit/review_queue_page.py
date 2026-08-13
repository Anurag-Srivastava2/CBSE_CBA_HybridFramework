import re

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By

from pages.common.review_queue_page import BaseReviewQueuePage


class PITReviewQueuePage(BaseReviewQueuePage):
    """Page object for PIT quorum voting and publication."""

    ITEM_SET_READY_SIGNALS = BaseReviewQueuePage.ITEM_SET_READY_SIGNALS + (
        "QUORUM STATUS",
        "YOUR DECISION",
    )

    SUBMIT_REVIEW_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Submit PIT Review') and not(@disabled)]"),
    ]

    def is_review_item_ready(self, driver):
        return self.is_pit_decision_panel_ready(driver) or super().is_review_item_ready(driver)

    def approve_item_set_as_pit(self, item_set_id, item_set_url=""):
        self.open_review_item_set(item_set_id, item_set_url)
        starting_quorum_count = self.get_pit_quorum_approval_count()
        all_item_ids = self.get_pit_item_ids(item_set_id)
        pending_item_ids = self.get_pending_pit_item_ids(item_set_id)
        if not pending_item_ids:
            raise TimeoutException(
                "PIT action is not available for this item set. "
                "There are no pending PIT items; use a fresh item set."
            )

        for item_id in pending_item_ids:
            self.click_item(item_id)
            if self.is_pit_item_already_approved(item_id):
                raise TimeoutException(
                    f"PIT action is not available for {item_id}. "
                    "This item set may already have been actioned by this PIT user; "
                    "use a fresh item set."
                )
            self.wait_for_pit_decision_panel(item_set_id)
            if not self.has_actionable_pit_vote():
                raise TimeoutException(
                    f"PIT vote controls are not available for {item_id}; use a fresh item set."
                )
            self.authorise_pit_item(item_id)
            self.return_to_item_set_if_needed(item_set_id)

        if all_item_ids:
            self.click_item(all_item_ids[0])
        self.submit_pit_review()
        self.wait_utils.until_condition(
            lambda driver: self.get_pit_quorum_approval_count() > starting_quorum_count
            or self.page_contains_text(driver, "Published"),
            timeout=60,
        )

    def revise_some_and_authorise_rest_as_pit(
        self,
        item_set_id,
        item_ids,
        revision_comment,
        item_set_url="",
        revision_count=1,
    ):
        """Submit one PIT review containing revision and authorise decisions.

        PIT's "Item Response Sheet" panel (the same Evaluation Criteria
        table RWG/SRRWG use to mark individual criteria No) is read-only
        here - every criterion row just shows a Version-1-vs-Version-2
        history comparison as static pills, with no interactive control at
        all (confirmed via a full HTML dump of the panel on a live PIT
        page). PIT's actual "send back" action is its own "Minor Edit"
        button: click it, add a comment, and save - one item at a time.
        Once every item in the set has been actioned (revised or
        authorised), the "Submit PIT Review" button becomes enabled.
        """
        item_ids = list(dict.fromkeys(item_ids))
        if not item_ids:
            raise ValueError("At least one PIT item is required.")
        revision_count = max(1, min(int(revision_count), len(item_ids)))
        revision_item_ids = item_ids[:revision_count]
        approval_item_ids = item_ids[revision_count:]

        self.open_review_item_set(item_set_id, item_set_url)
        for item_id in revision_item_ids:
            self.click_item(item_id)
            self.wait_for_pit_decision_panel(item_set_id)
            self.revise_pit_item(item_id, revision_comment)
            self.return_to_item_set_if_needed(item_set_id)

        for item_id in approval_item_ids:
            self.return_to_item_set_if_needed(item_set_id)
            self.click_item(item_id)
            self.wait_for_pit_decision_panel(item_set_id)
            self.authorise_pit_item(item_id)

        self.return_to_item_set_if_needed(item_set_id)
        self.click_item(item_ids[0])
        self.submit_pit_review()
        return revision_item_ids, approval_item_ids

    def authorise_pit_item(self, item_id):
        last_error = None
        for _ in range(3):
            try:
                self.select_pit_authorise_decision()
                self.click_pit_submit_vote()
                self.confirm_if_prompted()
                self.wait_until_pit_vote_saved(item_id)
                return
            except TimeoutException as error:
                last_error = error
                if self.is_pit_item_already_approved(item_id):
                    return
        raise TimeoutException(
            f"PIT Authorise vote was not saved for {item_id} after 3 attempts."
        ) from last_error

    MINOR_EDIT_LOCATORS = [
        (
            By.XPATH,
            "//*[self::button or @role='button']"
            "[contains(normalize-space(),'Minor Edit')][not(@disabled)]",
        ),
    ]
    SAVE_MINOR_EDIT_LOCATORS = [
        (
            By.XPATH,
            "//button[contains(normalize-space(),'Submit Vote') "
            "and contains(normalize-space(),'Redirect') and not(@disabled)]",
        ),
        (By.XPATH, "//button[contains(normalize-space(),'Save Minor Edit') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Save Comment') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Save Edit') and not(@disabled)]"),
        (By.XPATH, "//button[normalize-space()='Save' and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Save') and not(@disabled)]"),
    ]

    def revise_pit_item(self, item_id, revision_comment):
        """PIT's "send back for minor edit" action: click "Minor Edit", add
        a comment, and save - confirmed via a live diagnostic dump that
        this alone is a side annotation, not a vote (the item's status
        stays "Pending" and the queue's "N evaluated" counter doesn't
        move). "Minor Edit" fits a review pattern of flagging small issues
        via comment while still authorising the item to proceed - so the
        item also needs an actual vote afterward for the set to become
        submittable at all (confirmed: "Submit PIT Review" stayed disabled
        after Minor Edit alone, on a single-item set with nothing else to
        action).
        """
        last_error = None
        for _ in range(3):
            try:
                self.click_required_and_confirm(
                    self.MINOR_EDIT_LOCATORS, "Minor Edit", timeout=20
                )
                if not self.enter_revision_remark_if_available(revision_comment):
                    raise TimeoutException(
                        f"No comment field appeared after Minor Edit for {item_id}."
                    )
                self.click_required_and_confirm(
                    self.SAVE_MINOR_EDIT_LOCATORS, "Save Minor Edit", timeout=15
                )
                self.confirm_if_prompted()
                self.wait_until_pit_revise_vote_saved(item_id, revision_comment)
                break
            except TimeoutException as error:
                last_error = error
                if self.is_pit_item_already_revised(item_id):
                    break
        else:
            raise TimeoutException(
                f"PIT Minor Edit was not saved for {item_id} after 3 attempts."
            ) from last_error

        self.authorise_pit_item(item_id)

    def wait_until_pit_revise_vote_saved(self, item_id, revision_comment=None):
        # Minor Edit is a side annotation on the item, not a vote - the
        # item's own status button stays "Pending" and the page's
        # "N evaluated" counter doesn't move (confirmed via a live
        # diagnostic dump), so neither is a usable completion signal here.
        # The comment text actually appearing on the page is direct proof
        # the edit was saved.
        if revision_comment:
            comment_snippet = revision_comment[:40]
            try:
                self.wait_utils.until_condition(
                    lambda driver: comment_snippet in (
                        driver.execute_script(
                            "return document.body.innerText || "
                            "document.body.textContent || '';"
                        )
                        or ""
                    ),
                    timeout=20,
                )
                return
            except TimeoutException:
                pass
        try:
            self.wait_utils.until_condition(
                lambda driver: self.is_pit_item_already_revised(item_id),
                timeout=10,
            )
        except TimeoutException:
            self.log_pit_item_status_diagnostic(item_id)
            raise

    def log_pit_item_status_diagnostic(self, item_id):
        """One-shot diagnostic for wait_until_pit_revise_vote_saved()
        timeouts: dumps every item-status button's full text so the real
        post-Minor-Edit status label can be read directly, instead of
        guessing at more label variants.
        """
        try:
            item_number_match = re.search(r"-i(\d+)$", item_id, re.IGNORECASE)
            item_number = item_number_match.group(1) if item_number_match else None
            button_texts = self.driver.execute_script(
                """
                return Array.from(document.querySelectorAll('button'))
                    .filter(button => button.offsetParent !== null)
                    .map(button => button.innerText || '');
                """
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "wait_until_pit_revise_vote_saved diagnostic: item_number=%r, "
                "%d visible buttons total",
                item_number,
                len(button_texts),
            )
            for text in button_texts:
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                if item_number and lines and lines[0] == item_number:
                    logger.warning(
                        "  matching item-number button lines=%r", lines
                    )
            page_text = self.driver.execute_script(
                "return document.body.innerText || document.body.textContent || '';"
            )
            logger.warning(
                "wait_until_pit_revise_vote_saved diagnostic: page snippet=%r",
                page_text[:800],
            )
        except Exception as diagnostic_error:
            import logging
            logging.getLogger(__name__).warning(
                "wait_until_pit_revise_vote_saved diagnostic logging failed: %s",
                diagnostic_error,
            )

    def is_pit_item_already_approved(self, item_id):
        return self._pit_item_status_is(item_id, ("Approved",))

    def is_pit_item_already_revised(self, item_id):
        return self._pit_item_status_is(
            item_id,
            (
                "Revise", "Revised", "Sent Back", "Send Back", "Revision",
                "Minor Edit", "Redirect", "Redirected", "Redirect for Minor Edits",
            ),
        )

    def _pit_item_status_is(self, item_id, status_labels):
        item_number_match = re.search(r"-i(\d+)$", item_id, re.IGNORECASE)
        if not item_number_match:
            return False
        item_number = item_number_match.group(1)
        button_texts = self.driver.execute_script(
            """
            return Array.from(document.querySelectorAll('button'))
                .filter(button => button.offsetParent !== null)
                .map(button => button.innerText || '');
            """
        )
        for button_text in button_texts:
            lines = [line.strip() for line in button_text.splitlines() if line.strip()]
            if len(lines) >= 4 and lines[0] == item_number and lines[-1] in status_labels:
                return True
        return False

    def get_pit_item_ids(self, item_set_id):
        # Match on the stable "IS<number>" prefix, not the full item_set_id -
        # this page can render a different chapter-code segment than the ID
        # captured right after upload (see item_set_numeric_prefix()), so a
        # regex requiring the exact full ID never matches even though it's
        # the same item.
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        item_ids = []
        for row in self.driver.find_elements(By.XPATH, "//table//tbody/tr"):
            match = re.search(
                rf"({re.escape(numeric_prefix)}[\w-]*?-i\d+)",
                row.text,
                re.IGNORECASE,
            )
            if match and match.group(1) not in item_ids:
                item_ids.append(match.group(1))
        return item_ids

    def get_pending_pit_item_ids(self, item_set_id):
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        pending_item_ids = []
        rows = self.driver.find_elements(
            By.XPATH,
            "//table//tbody/tr[.//*[contains(normalize-space(),'Under Review') "
            "or normalize-space()='Pending']]",
        )
        for row in rows:
            match = re.search(
                rf"({re.escape(numeric_prefix)}[\w-]*?-i\d+)",
                row.text,
                re.IGNORECASE,
            )
            if match and match.group(1) not in pending_item_ids:
                pending_item_ids.append(match.group(1))
        return pending_item_ids

    def submit_pit_review(self):
        last_error = None
        for attempt in range(3):
            try:
                self.click_required_and_confirm(
                    self.SUBMIT_REVIEW_LOCATORS,
                    "Submit PIT Review",
                    timeout=30,
                )
                return
            except TimeoutException as error:
                last_error = error
                if attempt < 2:
                    # The "all items reviewed" count backing this button can
                    # lag a moment behind the last Minor Edit save; a
                    # refresh gives the backend time to catch up before
                    # giving up.
                    self.driver.refresh()
                    self.wait_utils.until_condition(
                        lambda driver: not self.is_pit_decision_panel_loading(driver),
                        timeout=30,
                    )
        raise last_error

    @staticmethod
    def is_pit_decision_panel_loading(driver):
        return "Loading" in driver.find_element(By.TAG_NAME, "body").text

    @staticmethod
    def page_contains_text(driver, expected_text):
        page_text = driver.find_element(By.TAG_NAME, "body").text or ""
        return expected_text in page_text

    def open_first_item_for_pit(self, item_set_id):
        if self.is_pit_decision_panel_ready(self.driver):
            return

        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        first_item = self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//*[self::a or self::button]"
                f"[contains(normalize-space(),'{numeric_prefix}')][1]",
            ),
            timeout=30,
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            first_item,
        )
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", first_item)
        self.wait_utils.until_condition(
            lambda driver: self.is_pit_decision_panel_ready(driver),
            timeout=60,
        )

    def wait_for_pit_decision_panel(self, item_set_id):
        for attempt in range(2):
            try:
                self.wait_utils.until_condition(
                    lambda driver: self.is_pit_decision_panel_ready(driver),
                    timeout=60,
                )
                return
            except TimeoutException:
                if attempt == 1:
                    raise
                self.driver.refresh()
                numeric_prefix = self.item_set_numeric_prefix(item_set_id)
                self.wait_utils.until_condition(
                    lambda driver: numeric_prefix
                    in driver.find_element(By.TAG_NAME, "body").text,
                    timeout=60,
                )

    @staticmethod
    def is_pit_decision_panel_ready(driver):
        page_text = driver.find_element(By.TAG_NAME, "body").text
        return (
            "Loading items" not in page_text
            and "QUORUM STATUS" in page_text
            and "YOUR DECISION" in page_text
            and "Authorise" in page_text
        )

    def select_pit_authorise_decision(self):
        authorise_locator = (
            By.XPATH,
            "//*[self::button or @role='button']"
            "[contains(normalize-space(),'Authorise') "
            "and not(contains(normalize-space(),'Submit Vote'))]",
        )
        for attempt in range(3):
            if self.is_pit_submit_vote_available():
                return
            try:
                authorise_option = self.wait_utils.until_clickable(
                    authorise_locator,
                    timeout=20,
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    authorise_option,
                )
                authorise_option = self.wait_utils.until_clickable(
                    authorise_locator,
                    timeout=5,
                )
                authorise_option.click()
                self.wait_utils.until_condition(
                    lambda driver: self.is_pit_submit_vote_available(),
                    timeout=5,
                )
                return
            except StaleElementReferenceException:
                if attempt == 2:
                    raise
            except TimeoutException:
                continue
        raise TimeoutException(
            "Authorise was clicked, but Submit Vote - Authorise did not appear."
        )

    def is_pit_submit_vote_available(self):
        return any(
            button.is_displayed() and button.is_enabled()
            for button in self.driver.find_elements(
                By.XPATH,
                "//button[contains(normalize-space(),'Submit Vote') "
                "and contains(normalize-space(),'Authorise') and not(@disabled)]",
            )
        )

    def has_actionable_pit_vote(self):
        if self.is_pit_submit_vote_available():
            return True
        return any(
            option.is_displayed() and option.is_enabled()
            for option in self.driver.find_elements(
                By.XPATH,
                "//*[self::button or @role='button']"
                "[contains(normalize-space(),'Authorise') "
                "and not(contains(normalize-space(),'Submit Vote'))]",
            )
        )

    def click_pit_submit_vote(self):
        submit_vote_locator = (
            By.XPATH,
            "//button[contains(normalize-space(),'Submit Vote') "
            "and contains(normalize-space(),'Authorise') and not(@disabled)]",
        )
        for attempt in range(3):
            try:
                submit_vote_button = self.wait_utils.until_clickable(
                    submit_vote_locator,
                    timeout=20,
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    submit_vote_button,
                )
                submit_vote_button = self.wait_utils.until_clickable(
                    submit_vote_locator,
                    timeout=5,
                )
                submit_vote_button.click()
                return
            except StaleElementReferenceException:
                if attempt == 2:
                    raise

    def wait_until_pit_vote_saved(self, item_id):
        self.wait_utils.until_condition(
            lambda driver: self.is_pit_item_already_approved(item_id),
            timeout=30,
        )

    def get_pit_quorum_approval_count(self):
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r"(\d+)\s*/\s*3\s+for\s+Quorum", page_text, re.IGNORECASE)
        return int(match.group(1)) if match else 0
