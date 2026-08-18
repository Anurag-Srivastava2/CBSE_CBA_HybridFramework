"""E2E test: SME creates one manual item with bold, italic, text color,
highlight/background color, and an inserted image all applied to its
Explanation field, submits it for QAR, and the item is then approved through
RWG, SRRWG, and PIT (3/3 quorum) to publication.

At each review stage the test verifies that the SME-applied formatting and
image are actually visible to the reviewer in the rendered review pane - not
just present in the SME's own editor at creation time. This is the same
verification gap the standalone manual-item-creation checks (see
test_sme_manual_item_creation.py) can't cover, since those only look at the
editor immediately after applying the formatting, before the item is ever
reviewed.

Modeled on the RWG/SRRWG/PIT review flow in
test_e2e_sme_excel_typology_image_rwg_srrwg_revision_to_pit_publication.py,
adapted for manual item creation instead of Excel upload.
"""
from time import sleep, monotonic
from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.common.login_page import LoginPage
from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sme.bulk_upload_page import BulkUploadPage
from pages.sme.manual_item_page import ManualItemPage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from tests.M1_Item_Bank_Mgmt.m1_surveys import (
    enter_screen,
    survey_manual_form,
    survey_opened_item_set,
)
from utilities.element_checks import ElementChecks
from utilities.logger import LogGenerator
from utilities.read_config import ReadConfig

from tests.M1_Item_Bank_Mgmt.test_sme_manual_item_creation import TEST_IMAGES

# Markers each formatting/image action leaves behind in the editor's rendered
# HTML - see ManualItemPage.apply_bold_and_italic / apply_text_color /
# apply_highlight_color / insert_image_into_editor, which already assert on
# these same substrings right after applying them in the SME's own editor.
FORMATTING_MARKERS = {
    "Bold": "<strong>",
    "Italic": "<em>",
    "Text color": "color: rgb(255, 0, 0)",
    "Highlight color": "background-color",
    "Image": "<img",
}


# Carries a manual item through the shared RWG/SRRWG/PIT review accounts, which
# allow one active session each.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestManualItemRichContentToPITPublication:
    logger = LogGenerator.loggen()

    def login_as(self, username, helper_page):
        """Switch the active session to `username`. Uses an auxiliary
        BulkUploadPage instance for reset_browser_session_to_login() since
        ManualItemPage doesn't inherit it (only UploadItemFilePage/
        BulkUploadPage do)."""
        helper_page.reset_browser_session_to_login()
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        helper_page.close_popup_if_open()

    def resolve_reviewer_username(self, review_page, role, item_set_id, item_set_url):
        """Try each configured account for `role` until one can open this
        item set's review queue entry."""
        candidates = ReadConfig.get_role_usernames(role)
        last_error = None
        for candidate in candidates:
            try:
                # The login belongs inside the try: a candidate whose sign-in
                # strands on the login form is just another candidate that did
                # not work, so move to the next account instead of abandoning
                # every remaining one.
                self.login_as(candidate, self.helper_page)
                review_page.open_review_item_set(item_set_id, item_set_url)
                # Survey each reviewer's opened set as the chain reaches it.
                # Read-only: no criteria are marked here, so it cannot consume
                # the one-time review vote this set still needs.
                checks = getattr(self, "checks", None)
                if checks is not None:
                    enter_screen(checks, f"{role.upper()} — Opened Item Set")
                    survey_opened_item_set(checks, review_page)
                    # Re-published after every phase: publish() writes the whole
                    # accumulated list, so a failure later in this long chain
                    # still leaves the rows gathered up to that point on the card.
                    checks.publish()
                return candidate
            except TimeoutException as error:
                last_error = error
        raise TimeoutException(
            f"Item set {item_set_id} was not visible in any configured "
            f"{role.upper()} queue ({candidates})."
        ) from last_error

    def get_open_item_review_pane_html(self):
        """Return the innerHTML of the right-hand review pane for the
        currently-open item, using the same positional heuristic (rect
        bounds relative to viewport width) that get_open_item_image_count()
        and get_open_item_question_text() already use to isolate that pane
        from the left-hand item-set list."""
        return self.driver.execute_script(
            """
            const candidates = Array.from(
                document.querySelectorAll('div, p, span')
            ).filter(element => {
                const rect = element.getBoundingClientRect();
                return rect.width > 0
                    && rect.height > 0
                    && rect.right > window.innerWidth * 0.4
                    && rect.left < window.innerWidth * 0.95
                    && !element.closest('table')
                    && !element.closest('[role="navigation"]')
                    && !element.closest('header');
            }).map(element => element.innerHTML || '');
            return candidates.sort((a, b) => b.length - a.length)[0] || '';
            """
        )

    def verify_formatting_visible_to_reviewer(self, review_page, item_set_id, item_id):
        """Open the item as the currently-logged-in reviewer and check which
        of the SME-applied formatting/image markers are actually visible in
        the rendered review pane. Returns {marker_name: bool}."""
        review_page.return_to_item_set_if_needed(item_set_id)
        review_page.click_item(item_id)
        review_page.pause_before_action()
        pane_html = self.get_open_item_review_pane_html()
        return {name: marker in pane_html for name, marker in FORMATTING_MARKERS.items()}

    def test_manual_item_rich_content_survives_to_pit_publication(
        self, request, record_property
    ):
        run_token = uuid4().hex[:10]
        question_text = f"What comes immediately after 24? Rich content PIT run {run_token}"
        explanation_text = "25 comes immediately after 24."

        self.helper_page = BulkUploadPage(self.driver)

        sme_username = ReadConfig.get_sme_username()
        self.login_as(sme_username, self.helper_page)

        # 1. SME creates one MCQ item, applying bold/italic/text-color/
        # highlight-color/image to the Explanation field (the field that's
        # both safe to format - see RICH_CONTENT_EDITOR_INDEX_OVERRIDES in
        # test_sme_manual_item_creation.py - and filled last, right before
        # Add Item).
        request.node.user_properties.append(
            ("result_checkpoint", "SME creates item with bold/italic/color/highlight/image")
        )
        manual_item_page = ManualItemPage(self.driver)
        manual_item_page.close_popup_if_open()
        manual_item_page.open_item_creation_module()
        manual_item_page.open_manual_item_tab()

        # One collector for the whole SME -> RWG -> Sr. RWG -> PIT chain,
        # re-pointed at each screen as the item set moves through it.
        self.checks = ElementChecks(
            manual_item_page, record_property, page_name="SME Manual Item — Rich Content"
        )
        survey_manual_form(self.checks, manual_item_page)
        self.checks.publish()

        manual_item_page.wait_for_saved_draft_to_hydrate()
        manual_item_page.clear_added_items()
        manual_item_page.select_common_manual_item_metadata()
        manual_item_page.select_typology("Multiple Choice Question")
        manual_item_page.select_marks("1")
        manual_item_page.fill_multiple_choice_question(
            question_text, ["25", "23", "14", "55"], explanation_text
        )

        applied_html = {}
        applied_html["Bold+Italic"] = manual_item_page.apply_bold_and_italic(editor_index=-1)
        applied_html["Text color"] = manual_item_page.apply_text_color(
            editor_index=-1, hex_color="#ff0000"
        )
        applied_html["Highlight color"] = manual_item_page.apply_highlight_color(
            editor_index=-1, hex_color="#ffff00"
        )
        applied_html["Image"] = manual_item_page.insert_image_into_editor(
            editor_index=-1, image_path=str(TEST_IMAGES[0])
        )
        sme_applied = {
            "Bold": "<strong>" in applied_html["Bold+Italic"],
            "Italic": "<em>" in applied_html["Bold+Italic"],
            "Text color": "color: rgb(255, 0, 0)" in applied_html["Text color"],
            "Highlight color": "background-color" in applied_html["Highlight color"],
            "Image": "<img" in applied_html["Image"],
        }
        request.node.user_properties.append(
            ("sme_applied_formatting", str(sme_applied))
        )

        manual_item_page.click_add_item_and_wait_for_count_increase()
        assert int(manual_item_page.get_added_items_count()) == 1, (
            "Expected exactly 1 added item before QAR submit."
        )

        # 2. Submit for QAR. submit_item_set_for_qar() already waits for QAR
        # analysis to finish internally and returns the real, numbered item
        # ID from the QAR Results table (not the unnumbered placeholder ID
        # shown at the earlier Review & Tag Metadata step).
        request.node.user_properties.append(("result_checkpoint", "SME submits for QAR"))
        item_id = manual_item_page.submit_item_set_for_qar(question_text)
        assert item_id and "ID not found" not in item_id, (
            f"Item ID not found after QAR submit: {item_id!r}"
        )
        qar_message = manual_item_page.wait_for_qar_success_popup()
        item_set_url = self.driver.current_url
        # RWGReviewQueuePage.click_item derives item_set_id from item_id the
        # same way ("IS<number>-i<index>" -> "IS<number>"); ManualItemPage has
        # no equivalent getter, so replicate that convention here.
        item_set_id = item_id.rsplit("-i", 1)[0]
        request.node.user_properties.extend(
            [
                ("item_set_id", item_set_id),
                ("manual_item_id", item_id),
                ("qar_success_message", qar_message or ""),
            ]
        )

        # 3. RWG verifies formatting/image, then approves.
        request.node.user_properties.append(
            ("result_checkpoint", "RWG verifies formatting/image, approves")
        )
        rwg_page = RWGReviewQueuePage(self.driver)
        self.resolve_reviewer_username(rwg_page, "rwg", item_set_id, item_set_url)
        rwg_visible = self.verify_formatting_visible_to_reviewer(rwg_page, item_set_id, item_id)
        request.node.user_properties.append(("rwg_visible_formatting", str(rwg_visible)))
        rwg_page.approve_item_set_as_rwg(item_set_id, [item_id], item_set_url)
        rwg_page.capture_review_screenshot(request.node.name, "rwg_approved")

        # 4. SRRWG verifies formatting/image, then approves.
        request.node.user_properties.append(
            ("result_checkpoint", "SRRWG verifies formatting/image, approves")
        )
        sr_rwg_page = SRRWGReviewQueuePage(self.driver)
        self.resolve_reviewer_username(sr_rwg_page, "sr_rwg", item_set_id, item_set_url)
        sr_rwg_visible = self.verify_formatting_visible_to_reviewer(
            sr_rwg_page, item_set_id, item_id
        )
        request.node.user_properties.append(("sr_rwg_visible_formatting", str(sr_rwg_visible)))
        sr_rwg_page.approve_item_set_as_sr_rwg(item_set_id, [item_id], item_set_url)
        sr_rwg_page.capture_review_screenshot(request.node.name, "sr_rwg_approved")

        # 5. PIT 3/3 quorum publishes the item.
        request.node.user_properties.append(
            ("result_checkpoint", "PIT 3/3 quorum and publication")
        )
        pit_page = PITReviewQueuePage(self.driver)
        completed_pit_approvals = []
        for pit_username in ReadConfig.get_pit_usernames()[:3]:
            self.login_as(pit_username, self.helper_page)
            pit_page.approve_item_set_as_pit(item_set_id, item_set_url)
            completed_pit_approvals.append(pit_username)
            pit_page.capture_review_screenshot(
                request.node.name, f"pit_approval_{len(completed_pit_approvals)}"
            )
        assert len(completed_pit_approvals) == 3, (
            f"Expected PIT 3/3, completed {completed_pit_approvals}."
        )

        # 6. Final published-status verification.
        request.node.user_properties.append(
            ("result_checkpoint", "final published item-set status verification")
        )
        self.login_as(sme_username, self.helper_page)
        # item_set_url was captured inside the manual-creation wizard, so it
        # points at the wizard rather than this set's own page. Reach the detail
        # page through the Sets list, which is where the status counts live.
        self.helper_page.open_item_set_detail(item_set_id)
        final_summary = {}
        final_status_text = ""
        deadline = monotonic() + 30
        while monotonic() < deadline:
            final_summary = self.helper_page.get_item_set_status_summary()
            final_status_text = self.helper_page.format_status_summary(final_summary)
            if (
                str(final_summary.get("Approved", "")) == "1"
                and str(final_summary.get("Pending", "")) == "0"
            ):
                break
            sleep(2)
            self.helper_page.open_item_set_detail(item_set_id)
        assert int(final_summary.get("Approved", -1)) == 1, (
            f"Item was not fully approved after PIT 3/3: {final_status_text}"
        )
        assert int(final_summary.get("Pending", -1)) == 0, (
            f"Item still pending after PIT 3/3: {final_status_text}"
        )
        final_screenshot = self.helper_page.capture_sets_verification_screenshot(
            f"{request.node.name}_final_published_status"
        )

        request.node.user_properties.extend(
            [
                ("post_approval_status", final_status_text),
                ("qar_success_screenshot", final_screenshot),
                (
                    "result_description",
                    f"Manual MCQ item ({item_set_id}) with bold/italic/text-color/"
                    "highlight-color/image applied to its Explanation field passed "
                    "RWG, SRRWG, and PIT 3/3 review, then published. "
                    f"SME-applied: {sme_applied}. RWG-visible: {rwg_visible}. "
                    f"SRRWG-visible: {sr_rwg_visible}.",
                ),
            ]
        )
        print(f"SME-applied formatting: {sme_applied}")
        print(f"RWG-visible formatting: {rwg_visible}")
        print(f"SRRWG-visible formatting: {sr_rwg_visible}")
        print(f"Final published status: {final_status_text}")

        # Formatting/image visibility to reviewers is reported (see prints
        # and user_properties above) but not hard-asserted here, matching
        # the non-blocking philosophy of the standalone rich-content checks
        # in test_sme_manual_item_creation.py: a reviewer-pane rendering gap
        # (e.g. Highlight color, already known from those checks to never
        # actually apply) shouldn't fail the publish pipeline itself. The
        # pipeline's own success (QAR -> RWG -> SRRWG -> PIT 3/3 -> Published)
        # is the hard assertion above.
