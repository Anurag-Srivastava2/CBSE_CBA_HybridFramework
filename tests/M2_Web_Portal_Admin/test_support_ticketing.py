import base64
import re
import time

import pytest

from pages.admin.helpdesk_page import HelpdeskPage
from pages.common.login_page import LoginPage
from pages.common.support_page import SupportPage
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.rbac_api import current_user_display_name
from utilities.read_config import ReadConfig


def safe_display_name(driver):
    """The signed-in account's profile name, or "" if it cannot be read.

    Never raises: this only widens what counts as correct attribution, so a
    profile lookup that fails must leave the assertion to the address-based
    match rather than erroring the test out on a network problem.
    """
    try:
        return current_user_display_name(driver)
    except Exception:  # noqa: BLE001 - diagnostics only, never a test outcome
        return ""

# A real 1x1 PNG. The dropzone accepts PNG/JPG/WEBP/PDF up to 5 MB, so the
# attachment has to be a genuine image rather than arbitrary bytes named .png.
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2SupportAndHelpdesk:
    """TC-WPAD-SUPPORT-01: raise a Help & Support ticket with an attachment,
    confirm it in My Tickets with its attachment, and confirm the same ticket
    reaches the admin Helpdesk queue. Driven with the admin account."""

    CATEGORY = "Portal Error"

    @pytest.fixture()
    def sample_upload_file(self, tmp_path):
        """A throwaway PNG for the attachment check.

        tmp_path keeps it out of the repo and pytest removes it afterwards, so
        nothing is written to — or left behind in — the project folder.
        """
        upload = tmp_path / f"qa_support_screenshot_{int(time.time())}.png"
        upload.write_bytes(ONE_PIXEL_PNG)
        return upload

    @staticmethod
    def attributed_to(raised_by, username, display_name=""):
        """Does the Helpdesk's Raised By value identify this account?

        The queue renders a display name, not the login. That is fine for the
        primary admin, whose row carries the address, but the secondary admin
        signs in as 'admin@test.com' and shows as 'Test admin' - so comparing
        the raw email fails. It only failed under xdist, because
        get_admin_username() hands each worker a different account, which made
        this pass serially and fail on gw1.

        A display name need not resemble the address at all: UAT's
        adminuat@cba.com carries the profile name "sdvsv hjjhhj", so neither the
        address nor its local part appears in what the queue renders. The
        account's actual profile name is therefore passed in and accepted too -
        read from /auth/me, so it identifies *this* account and an attribution
        to an unrelated person is still caught.

        Matched on the address, the local part as a whole word, or the profile
        name the account really has.
        """
        haystack = (raised_by or "").casefold()
        if not haystack:
            return False
        if username.casefold() in haystack:
            return True
        if display_name and display_name.casefold() in haystack:
            return True
        local_part = username.split("@")[0].casefold()
        words = set(re.split(r"[^a-z0-9]+", haystack))
        return local_part in words

    def login_as_admin(self):
        username = ReadConfig.get_admin_username()
        login = LoginPage(self.driver)
        self.driver.get(ReadConfig.get_base_url())
        login.wait_for_login_form_or_authenticated_page()
        # The shared helper treats a part-painted login screen as an
        # authenticated page and silently skips sign-in; wait for the form.
        login.wait_utils.is_visible(LoginPage.USERNAME_TEXTBOX, timeout=30)
        login.login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        assert not login.is_login_form_displayed(), (
            f"Sign-in did not establish a session for {username!r}; "
            "the application is still showing the login form."
        )
        checkpoint(f"Admin {username} signed in")
        return username

    def test_tc_wpad_support_01_create_ticket_with_upload_and_verify(
        self, sample_upload_file, record_property, page_evidence
    ):
        """Raise a ticket with an attachment, verify its detail sheet, then
        verify the same ticket in the admin Helpdesk queue."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Raise a Help and Support ticket with a file attached.\n"
            "Open it again in My Tickets and check the detail sheet and its "
            "attachment are both there.\n"
            "Check the same ticket also reaches the admin Helpdesk queue, so the two "
            "views agree.",
        )
        username = self.login_as_admin()

        support = SupportPage(self.driver)
        support.open(ReadConfig.get_base_url())

        # Page furniture is surveyed softly; raising the ticket, its attachment
        # and the helpdesk routing below all stay hard gates.
        checks = ElementChecks(support, record_property, page_name="Help & Support")
        checks.check_condition("Page header and subtext", support.is_on_page)
        for tab in ("Open", "In Progress", "Resolved"):
            checks.check_condition(
                f"Tab — {tab}", lambda name=tab: support.get_tab_count(name) >= 0
            )
        checks.publish()

        token = str(int(time.time()))
        subject = f"QA automated support ticket {token}"
        description = (
            "Raised by automated regression TC-WPAD-SUPPORT-01 to verify ticket "
            "creation, attachment handling and helpdesk routing."
        )

        # ------------------------------------------------ raise the ticket
        open_before = support.get_tab_count("Open")

        support.fill_ticket_form(subject, description, self.CATEGORY)
        assert support.get_selected_category() == self.CATEGORY, (
            f"Category did not take: expected {self.CATEGORY!r}, "
            f"got {support.get_selected_category()!r}."
        )
        assert support.get_registration_date(), "Registration Date was not auto-set on the form."

        page_evidence.checkpoint(
            f"Ticket form filled — subject {subject!r}, category "
            f"{support.get_selected_category()!r}, registration date "
            f"{support.get_registration_date()!r} (auto-set)"
        )

        support.attach_file(sample_upload_file)
        page_evidence.checkpoint(
            f"Attachment pill reads {support.get_attached_file_name()!r} "
            f"(expected {sample_upload_file.name!r})"
        )
        assert support.get_attached_file_name() == sample_upload_file.name, (
            f"Attachment pill shows {support.get_attached_file_name()!r}, "
            f"expected {sample_upload_file.name!r}."
        )

        support.submit_ticket()
        ticket_id = support.wait_for_ticket(subject)
        page_evidence.checkpoint(f"Ticket submitted and issued number {ticket_id}")

        record_property(
            "result_description",
            f"{username} raised {ticket_id} ({subject!r}) with attachment "
            f"{sample_upload_file.name} under category {self.CATEGORY}.",
        )
        assert support.TICKET_ID_PATTERN.fullmatch(ticket_id), (
            f"Submission did not generate a well-formed ticket number: {ticket_id!r}"
        )

        open_after = support.get_tab_count("Open")
        page_evidence.checkpoint(
            f"Open tab count moved {open_before} -> {open_after} "
            f"(expected {open_before + 1})"
        )
        assert open_after == open_before + 1, (
            f"The Open tab count should have risen from {open_before} to {open_before + 1}, "
            f"but reads {open_after}."
        )

        # -------------------------------------- verify the user-side detail
        support.open_ticket_details(subject)

        assert support.get_details_ticket_number() == ticket_id, (
            f"Detail sheet shows ticket {support.get_details_ticket_number()!r}, expected {ticket_id!r}."
        )
        assert support.get_details_field("Subject") == subject, (
            f"Detail sheet subject is {support.get_details_field('Subject')!r}, expected {subject!r}."
        )
        assert support.get_details_field("Category") == self.CATEGORY, (
            f"Detail sheet category is {support.get_details_field('Category')!r}, "
            f"expected {self.CATEGORY!r}."
        )
        assert support.has_attachments_section(), (
            f"Ticket {ticket_id} detail sheet has no ATTACHMENTS section."
        )
        page_evidence.checkpoint(
            f"Detail sheet for {ticket_id} — subject "
            f"{support.get_details_field('Subject')!r}, category "
            f"{support.get_details_field('Category')!r}, attachments section "
            f"present: {support.has_attachments_section()}, files listed: "
            f"{support.get_attachment_names()}"
        )
        assert support.is_file_in_details(sample_upload_file.name), (
            f"Attached file {sample_upload_file.name!r} is missing from the ticket preview. "
            f"Attachments listed: {support.get_attachment_names()}"
        )
        support.close_details()

        # ------------------------------ verify it reached the helpdesk queue
        helpdesk = HelpdeskPage(self.driver)
        helpdesk.open(ReadConfig.get_base_url())

        page_evidence.checkpoint("Switched to the admin Helpdesk queue")
        assert helpdesk.is_on_page(), "Helpdesk header or subtext is missing."
        missing_columns = helpdesk.missing_columns()
        assert not missing_columns, (
            f"Helpdesk queue columns missing: {missing_columns}. "
            f"Found: {helpdesk.get_table_headers()}"
        )

        helpdesk.search_ticket(ticket_id)
        matched_ids = helpdesk.get_ticket_ids_in_view()
        page_evidence.checkpoint(
            f"Searching the Helpdesk for {ticket_id} returned {matched_ids} "
            "— it should isolate that one ticket"
        )
        assert matched_ids == [ticket_id], (
            f"Searching the helpdesk for {ticket_id} should isolate that one ticket, "
            f"but returned {matched_ids}."
        )

        queued = helpdesk.find_ticket(ticket_id)
        page_evidence.checkpoint(
            f"{ticket_id} reached the Helpdesk queue as {queued} — a newly "
            "raised ticket may read Open or In Progress once auto-triage runs"
        )
        record_property(
            "result_description",
            f"{ticket_id} reached the Helpdesk queue as {queued}.",
        )
        assert queued is not None, (
            f"E2E failure: ticket {ticket_id} was raised in Help & Support but never "
            "appeared in the admin Helpdesk queue."
        )
        assert queued["subject"] == subject, (
            f"Helpdesk shows subject {queued['subject']!r}, expected {subject!r}."
        )
        assert queued["category"] == self.CATEGORY, (
            f"Helpdesk shows category {queued['category']!r}, expected {self.CATEGORY!r}."
        )
        # The queue renders the account's profile name, which need not resemble
        # its address, so read the name this account actually carries.
        display_name = safe_display_name(self.driver)
        assert self.attributed_to(queued["raised_by"], username, display_name), (
            f"Helpdesk attributes the ticket to {queued['raised_by']!r}, expected "
            f"{username!r}"
            + (f" (profile name {display_name!r})" if display_name else "")
            + "."
        )
        # The portal auto-triages shortly after submission, moving a ticket from
        # Open to In Progress once an agent is assigned, so both are valid for a
        # ticket this new. Anything else means it was ingested in a wrong state.
        assert queued["status"] in ("Open", "In Progress"), (
            f"A newly raised ticket should be Open or In Progress, but the helpdesk "
            f"shows {queued['status']!r}."
        )
