import base64
import time

import pytest

from pages.admin.helpdesk_page import HelpdeskPage
from pages.common.login_page import LoginPage
from pages.common.support_page import SupportPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig

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
        return username

    def test_tc_wpad_support_01_create_ticket_with_upload_and_verify(
        self, sample_upload_file, record_property
    ):
        """Raise a ticket with an attachment, verify its detail sheet, then
        verify the same ticket in the admin Helpdesk queue."""
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

        support.attach_file(sample_upload_file)
        assert support.get_attached_file_name() == sample_upload_file.name, (
            f"Attachment pill shows {support.get_attached_file_name()!r}, "
            f"expected {sample_upload_file.name!r}."
        )

        support.submit_ticket()
        ticket_id = support.wait_for_ticket(subject)

        record_property(
            "result_description",
            f"{username} raised {ticket_id} ({subject!r}) with attachment "
            f"{sample_upload_file.name} under category {self.CATEGORY}.",
        )
        assert support.TICKET_ID_PATTERN.fullmatch(ticket_id), (
            f"Submission did not generate a well-formed ticket number: {ticket_id!r}"
        )

        open_after = support.get_tab_count("Open")
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
        assert support.is_file_in_details(sample_upload_file.name), (
            f"Attached file {sample_upload_file.name!r} is missing from the ticket preview. "
            f"Attachments listed: {support.get_attachment_names()}"
        )
        support.close_details()

        # ------------------------------ verify it reached the helpdesk queue
        helpdesk = HelpdeskPage(self.driver)
        helpdesk.open(ReadConfig.get_base_url())

        assert helpdesk.is_on_page(), "Helpdesk header or subtext is missing."
        missing_columns = helpdesk.missing_columns()
        assert not missing_columns, (
            f"Helpdesk queue columns missing: {missing_columns}. "
            f"Found: {helpdesk.get_table_headers()}"
        )

        helpdesk.search_ticket(ticket_id)
        matched_ids = helpdesk.get_ticket_ids_in_view()
        assert matched_ids == [ticket_id], (
            f"Searching the helpdesk for {ticket_id} should isolate that one ticket, "
            f"but returned {matched_ids}."
        )

        queued = helpdesk.find_ticket(ticket_id)
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
        assert username.casefold() in queued["raised_by"].casefold(), (
            f"Helpdesk attributes the ticket to {queued['raised_by']!r}, expected {username!r}."
        )
        # The portal auto-triages shortly after submission, moving a ticket from
        # Open to In Progress once an agent is assigned, so both are valid for a
        # ticket this new. Anything else means it was ingested in a wrong state.
        assert queued["status"] in ("Open", "In Progress"), (
            f"A newly raised ticket should be Open or In Progress, but the helpdesk "
            f"shows {queued['status']!r}."
        )
