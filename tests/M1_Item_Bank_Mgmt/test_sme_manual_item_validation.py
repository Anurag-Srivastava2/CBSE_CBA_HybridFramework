from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.common.login_page import LoginPage
from pages.sme.manual_item_page import ManualItemPage
from utilities.logger import LogGenerator
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestSMEManualItemValidation:
    logger = LogGenerator.loggen()

    # ------------------------------------------------------------------
    # Console-output helpers
    # ------------------------------------------------------------------
    @staticmethod
    def step(n, message):
        print(f"\n[STEP {n}] {message}", flush=True)

    @staticmethod
    def check(message):
        print(f"[CHECK]  {message}", flush=True)

    @staticmethod
    def passed(message):
        print(f"[PASS]   {message}", flush=True)

    @staticmethod
    def skipped(message):
        print(f"[SKIP]   {message}", flush=True)

    # ------------------------------------------------------------------
    # Shared login helper
    # ------------------------------------------------------------------
    def login_as_sme2(self):
        self.step(1, f"Navigating to application URL")
        self.driver.get(ReadConfig.get_base_url())
        username = ReadConfig.get_sme2_username()
        self.step(2, f"Logging in as SME2: {username}")
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        page = ManualItemPage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        self.logger.info("SME2 login complete: %s", username)
        return page

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_tc_ibmm_01b_p02_continue_locked_until_mandatory_item_complete(self):
        """IBMM-01b-P02: The 'Continue' button must be disabled when no item has
        been added yet, and must become enabled once at least one complete mandatory
        item (with question, answer, and explanation) has been added.
        """
        page = self.login_as_sme2()

        self.step(3, "Opening True/False manual item creation form")
        page.open_true_false_manual_item_form()

        # The staged "Added Items" list lives server-side per SME account and
        # survives previous runs, so isolate the draft before asserting on it.
        page.wait_for_saved_draft_to_hydrate()
        page.clear_added_items()

        self.check("Continue button is DISABLED before any item is added")
        initial_state = page.is_continue_enabled()
        print(f"         Continue enabled (should be False): {initial_state}", flush=True)
        assert initial_state is False, (
            "Expected Continue button to be disabled before any item is added, "
            f"but is_continue_enabled() returned: {initial_state}"
        )
        self.passed("Continue button correctly disabled — no items added yet")

        run_id = uuid4().hex[:10]
        question = f"Is 81 greater than 18? Mandatory fields run {run_id}"
        self.step(4, f"Adding a complete T/F item: question='{question}'")
        page.add_true_false_manual_item(
            question_text=question,
            answer="True",
            explanation="81 is greater than 18.",
        )
        self.logger.info("Added T/F item with run_id=%s", run_id)

        self.check("Added items count == 1")
        items_count = int(page.get_added_items_count())
        print(f"         Items count: {items_count}", flush=True)
        assert items_count == 1, (
            f"Expected 1 item in the added-items list after adding one T/F item, "
            f"but got: {items_count}"
        )
        self.passed(f"Added items count confirmed: {items_count}")

        self.check("Continue button is NOW ENABLED after mandatory item is complete")
        enabled_state = page.is_continue_enabled()
        print(f"         Continue enabled (should be True): {enabled_state}", flush=True)
        assert enabled_state is True, (
            "Expected Continue button to be enabled after adding a complete mandatory item, "
            f"but is_continue_enabled() returned: {enabled_state}"
        )
        self.passed("Continue button enabled — mandatory item completed successfully")
        self.logger.info("IBMM-01b-P02 passed")

    def test_tc_ibmm_01b_p03_new_item_is_visible_in_draft_review(self):
        """IBMM-01b-P03: After adding a T/F item and clicking Continue, the draft
        review screen must display the new item with a real assigned item ID
        (not blank and not the sentinel value 'ID not found before QAR submit').
        """
        page = self.login_as_sme2()

        self.step(3, "Opening True/False manual item creation form")
        page.open_true_false_manual_item_form()

        # Isolate the draft so leftover staged items are not swept into the
        # item set this test advances to the review screen.
        page.wait_for_saved_draft_to_hydrate()
        page.clear_added_items()

        run_id = uuid4().hex[:10]
        question = f"Is 72 greater than 27? Draft visibility run {run_id}"
        self.step(4, f"Adding T/F item: question='{question}'")
        page.add_true_false_manual_item(
            question_text=question,
            answer="True",
            explanation="72 is greater than 27.",
        )
        self.logger.info("Added T/F item with run_id=%s", run_id)

        self.step(5, "Clicking Continue to advance to draft review screen")
        page.click_continue()

        self.step(6, f"Retrieving item ID assigned to question: '{question}'")
        item_id = page.get_review_item_id_for_question(question)
        print(f"         Assigned item ID: {item_id!r}", flush=True)
        self.logger.info("Draft review item ID: %s", item_id)

        self.check("Item ID is not empty")
        assert item_id, (
            f"Expected an item ID to be assigned in draft review for question '{question}', "
            "but got an empty value."
        )
        self.passed(f"Item ID is present: {item_id!r}")

        self.check("Item ID is not the 'not found' sentinel value")
        assert item_id != "ID not found before QAR submit", (
            f"The item ID was the fallback sentinel value 'ID not found before QAR submit'. "
            "The draft review did not assign a real ID to the item."
        )
        self.passed(f"Item ID is a real assigned value: {item_id!r}")
        self.logger.info("IBMM-01b-P03 passed — item ID: %s", item_id)

    def test_tc_ibmm_01b_n01_out_of_scope_subject_is_not_available(self):
        """IBMM-01b-N01: The Subject dropdown on the T/F form must be scoped
        to only the subjects this SME role is authorised for.
        'Mathematics' must be available; 'Physics' must not.
        """
        page = self.login_as_sme2()

        self.step(3, "Opening True/False manual item creation form")
        page.open_true_false_manual_item_form()

        self.step(4, "Checking Subject dropdown for in-scope and out-of-scope options")

        self.check("'Mathematics' IS available in Subject dropdown (in-scope)")
        maths_available = page.is_dropdown_option_available("Subject *", "Mathematics")
        print(f"         Mathematics available: {maths_available}", flush=True)
        assert maths_available is True, (
            "Expected 'Mathematics' to be available in the Subject dropdown for SME2, "
            f"but is_dropdown_option_available returned: {maths_available}"
        )
        self.passed("'Mathematics' correctly available in Subject dropdown")

        self.check("'Physics' is NOT available in Subject dropdown (out-of-scope)")
        physics_available = page.is_dropdown_option_available("Subject *", "Physics")
        print(f"         Physics available: {physics_available}", flush=True)
        assert physics_available is False, (
            "Expected 'Physics' to be absent from the Subject dropdown for SME2 "
            "(out-of-scope subject), but is_dropdown_option_available returned: "
            f"{physics_available}"
        )
        self.passed("'Physics' correctly absent from Subject dropdown (RBAC enforced)")
        self.logger.info("IBMM-01b-N01 passed")

    def test_tc_ibmm_01b_n02_empty_item_content_shows_inline_error_on_blur(self):
        """IBMM-01b-N02: Leaving the Item Content field empty and blurring away
        must either show an inline required-field error or keep Continue disabled.
        Both are acceptable UX patterns — the test accepts either outcome.
        """
        page = self.login_as_sme2()

        self.step(3, "Opening True/False manual item creation form")
        page.open_true_false_manual_item_form()

        # Continue also unlocks once any item is staged, so a draft left behind
        # by an earlier run would mask the empty-content validation under test.
        page.wait_for_saved_draft_to_hydrate()
        page.clear_added_items()

        self.step(4, "Triggering blur on empty Item Content field (focus then unfocus)")
        try:
            page.blur_empty_item_content()
            self.step(5, "Collecting visible required-field error messages")
            errors = page.get_required_field_errors()
            print(f"         Visible errors after blur: {errors}", flush=True)
            self.logger.info("Required field errors after blur: %s", errors)
        except TimeoutException:
            self.skipped(
                "No inline error element appeared after blur — "
                "checking that Continue remains disabled instead"
            )
            self.check("Continue button is still DISABLED (silent validation fallback)")
            assert page.is_continue_enabled() is False, (
                "Expected Continue to remain disabled when Item Content is empty, "
                "but it is enabled."
            )
            self.passed("Continue correctly disabled — app uses silent block instead of inline error")
            return

        self.check("At least one error mentions 'item content' and 'required'")
        assert any(
            "item content" in error.lower() and "required" in error.lower()
            for error in errors
        ), (
            f"Expected an inline 'Item Content is required' error after blur, "
            f"but no matching error was found. Visible errors: {errors}"
        )
        self.passed("Inline 'Item Content required' error correctly shown after blur")
        self.logger.info("IBMM-01b-N02 passed")
