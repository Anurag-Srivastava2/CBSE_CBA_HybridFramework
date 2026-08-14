from pathlib import Path
from uuid import uuid4

import pytest

from pages.sme.manual_item_page import ManualItemPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.item_bank_workbook_builder import build_item_workbook
from utilities.read_config import ReadConfig
from utilities.smoke_support import sign_in


@pytest.mark.smoke
# The SME item-creation workspace is the heaviest screen in the portal — it
# lazy-loads its editor bundle — and on this environment it intermittently
# sits on the global Loading screen past the page object's 45s wait and its
# refresh retry. A signed-in session that never paints is an environment
# stall, not a defect in the check, so allow one clean retry; the Extent
# report's retry badge keeps the flakiness visible rather than hiding it.
@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestSmokeM1ItemBank:
    """M1 - Item Bank Mgmt smoke: the SME authoring routes open, and Excel
    ingestion actually produces an item set.

    Checks 01 and 03 are read-only. Check 02 authors a real item but deletes
    it again, leaving the account as it was found. Check 04 is the exception:
    it uploads a generated workbook and submits it, which mints a real item
    set that lands in the RWG review queue. That is the only way to prove the
    bulk ingestion path end-to-end, but it means each run leaves data behind —
    see the note in README.md before scheduling this suite on a shared
    environment.

    Each check signs in as a different SME account and carries its own
    xdist_group, so all four can run concurrently under `--dist loadgroup`.
    """

    # Deliberately smaller than the E2E suites' 4: this only needs to prove a
    # set is minted, and every extra row costs QAR analysis time.
    EXCEL_ITEM_COUNT = 2

    # True/False is the cheapest typology to author end-to-end — one question,
    # one answer control, one explanation — so it proves the manual path
    # without the per-typology form handling the E2E suites exercise.
    TRUE_FALSE_TYPOLOGY = "True or False"

    # The formats the upload screen advertises as accepted.
    WORKBOOK_SUFFIXES = (".xlsx", ".xls", ".csv")

    # Text-based tab locators only. The positional fallbacks the page objects
    # carry for resilient clicking would satisfy a visibility assertion
    # without proving the intended tab is the one on screen.
    UPLOAD_TAB = UploadItemFilePage.UPLOAD_ITEM_FILE_TAB_LOCATORS[0]
    MANUAL_TAB = ManualItemPage.MANUAL_ITEM_TAB_LOCATORS[1]

    @staticmethod
    def sme_username(slot):
        """The SME account pinned to this check.

        Each check takes its own account from CBSE_SME_USERNAMES so they can
        run on separate workers: the portal allows one active session per
        account, and the staged "Added Items" draft is server-side per
        account, so sharing one login would force them onto a single worker
        and make this the suite's critical path. Wraps if fewer accounts are
        configured — the checks then serialise on the shared ones, which is
        correct but slower.
        """
        accounts = ReadConfig.get_role_usernames("sme")
        assert accounts, "No accounts configured in CBSE_SME_USERNAMES"
        return accounts[slot % len(accounts)]

    def open_item_creation_workspace(self, slot, page_class=ManualItemPage):
        """Sign in as this check's SME and open item creation, as `page_class`."""
        sign_in(self.driver, self.sme_username(slot))
        page = page_class(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        page.open_item_creation_module()
        return page

    @pytest.mark.xdist_group("smoke-m1-workspace")
    def test_smoke_m1_01_sme_reaches_item_creation_workspace(self, record_property):
        """SME signs in and the item-creation workspace offers both authoring routes."""
        page = self.open_item_creation_workspace(slot=0)

        manual_tab_visible = page.is_element_visible_quick(self.MANUAL_TAB, timeout=20)
        upload_tab_visible = page.is_element_visible_quick(self.UPLOAD_TAB, timeout=20)

        record_property(
            "result_description",
            f"SME {self.sme_username(0)} reached the item-creation workspace — "
            f"Manual tab: {manual_tab_visible}, Upload Item File tab: {upload_tab_visible}.",
        )

        assert manual_tab_visible, "Manual item authoring tab is not available to the SME"
        assert upload_tab_visible, "Upload Item File (bulk) tab is not available to the SME"

    @pytest.mark.xdist_group("smoke-m1-manual")
    def test_smoke_m1_02_manual_item_creation_stages_one_item(self, record_property):
        """An SME authors one complete True/False item and it stages.

        Exercises the whole manual path — metadata dropdowns (grade, subject,
        chapter, competency, learning outcome, Bloom's, typology, marks), the
        rich-text question and explanation editors, answer selection and Add
        Item — rather than only proving the form paints.

        The staged draft is server-side per SME account, so the check clears
        the draft before authoring to get a known baseline and clears it again
        afterwards. The item is never submitted for QAR, so nothing reaches
        the review workflow and the account is left as it was found.
        """
        question_text = (
            f"{ReadConfig.get_manual_item_question()} (smoke {uuid4().hex[:8]})"
        )
        answer = ReadConfig.get_manual_item_answer()
        explanation = ReadConfig.get_manual_item_explanation()

        page = self.open_item_creation_workspace(slot=1)
        page.open_manual_item_tab()
        page.wait_for_saved_draft_to_hydrate()
        page.clear_added_items()

        page.add_true_false_manual_item(question_text, answer, explanation)

        staged_count = page.get_settled_added_items_count()
        card_text = page.wait_for_added_item_card_text(question_text, self.TRUE_FALSE_TYPOLOGY)
        record_property(
            "result_description",
            f"Authored one {self.TRUE_FALSE_TYPOLOGY} item (answer: {answer}); "
            f"Added Items count: {staged_count}. Card: {card_text[:160] or 'not found'}",
        )
        record_property("manual_item_question", question_text)

        try:
            assert str(staged_count) == "1", (
                f"Expected exactly 1 staged item after authoring, got {staged_count}"
            )
            assert card_text, (
                f"Authored item {question_text!r} did not appear as an Added Items card"
            )
            assert page.typology_tag_is_visible(self.TRUE_FALSE_TYPOLOGY, card_text), (
                f"Staged card does not carry the {self.TRUE_FALSE_TYPOLOGY} typology tag: {card_text!r}"
            )
        finally:
            # Leave the shared SME draft as we found it even when the
            # assertions above fail, so the next run still starts from zero.
            page.clear_added_items()

    @pytest.mark.xdist_group("smoke-m1-upload")
    def test_smoke_m1_03_bulk_upload_screen_accepts_a_file(self, record_property):
        """The bulk Excel upload screen reaches its Upload Documents step."""
        upload_page = self.open_item_creation_workspace(slot=2, page_class=UploadItemFilePage)
        upload_page.open_upload_item_file_tab()
        upload_page.open_upload_step()

        file_input_present = bool(self.driver.find_elements(*upload_page.FILE_INPUT))
        record_property(
            "result_description",
            "Bulk upload screen reached the Upload Documents step; "
            f"file input present: {file_input_present}.",
        )
        assert file_input_present, (
            "Upload Documents step exposes no file input, so no Excel item file can be uploaded"
        )

    @pytest.mark.xdist_group("smoke-m1-excel")
    def test_smoke_m1_04_excel_upload_creates_item_set(self, record_property, tmp_path):
        """An Excel workbook uploads, validates and mints an item set.

        Stops at the review step, where the app has already assigned item IDs
        and therefore the item set ID — that is the ingestion result worth
        gating on. It deliberately does not press Submit for QAR: that waits on
        server-side QAR analysis, which took 16 minutes of a 33-minute CI build
        and pushed a set into the RWG queue on every run. The full
        upload-through-QAR path stays covered by the M1 E2E suites.

        Consequently nothing is submitted and the staged upload is discarded at
        the end, so this check no longer leaves workflow data behind.
        """
        template_path = Path(ReadConfig.get_upload_item_file_path())
        assert template_path.exists(), (
            f"SME upload template not found at {template_path}. Set CBSE_UPLOAD_ITEM_FILE "
            "to a valid template so the Excel ingestion path can be smoke-tested."
        )

        workbook_path = tmp_path / f"smoke_item_set_{uuid4().hex[:10]}.xlsx"
        _, summaries = build_item_workbook(
            template_path, workbook_path, count=self.EXCEL_ITEM_COUNT
        )
        assert summaries, f"Generated workbook {workbook_path.name} has no item-data worksheet"

        upload_page = self.open_item_creation_workspace(slot=3, page_class=UploadItemFilePage)
        try:
            _, upload_message = upload_page.upload_item_file_and_validate(str(workbook_path))

            # Advance to the review step, where the app lists the items it
            # ingested along with their assigned IDs.
            upload_page.click_continue()
            item_ids = upload_page.get_review_item_ids()
            item_set_id = upload_page.get_item_set_id_from_item_ids(item_ids)

            record_property(
                "result_description",
                f"Excel upload of {self.EXCEL_ITEM_COUNT} item(s) validated and minted item set "
                f"{item_set_id or 'UNKNOWN'} with items {item_ids}. Upload: {upload_message}",
            )
            record_property("item_set_id", item_set_id)
            record_property("manual_item_id", ", ".join(item_ids))

            assert len(item_ids) == self.EXCEL_ITEM_COUNT, (
                f"Expected {self.EXCEL_ITEM_COUNT} item ID(s) from the upload, got {len(item_ids)}: "
                f"{item_ids}. Upload message: {upload_message}"
            )
            assert item_set_id, (
                f"No item set ID could be derived from the minted item IDs {item_ids}, "
                "so the upload did not produce a reviewable set"
            )
        finally:
            # Clear the staged upload even when the assertions fail, so the
            # next run starts from a clean upload slot on this account.
            try:
                upload_page.discard_active_upload_if_present()
                upload_page.discard_staged_upload_files()
            except Exception:
                pass

    # Shares check 01's account and group deliberately: both are read-only and
    # the portal allows one active session per account, so giving this its own
    # group would have two workers fighting over the same login.
    @pytest.mark.xdist_group("smoke-m1-workspace")
    def test_smoke_m1_06_my_item_set_lists_uploaded_source_files(self, record_property):
        """The My Item Set list renders and names each set's source workbook.

        The Uploaded File column is a property of the build, so its presence is
        asserted outright. Which sets carry a file is not: a fresh account has
        none, and manually authored sets legitimately show an em dash. So the
        names that are there are asserted to be well-formed workbooks and the
        counts recorded as evidence, rather than gating the build on whatever
        this account happens to hold — the same reasoning as check 05.
        """
        sign_in(self.driver, self.sme_username(0))
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        page.open_item_sets_list()

        column_index = page.get_uploaded_file_column_index()
        listed_sets = page.get_item_set_list_rows()
        uploads = page.get_item_set_uploaded_files()

        # Read from the title attribute, which holds the untruncated name, so a
        # suffix check is meaningful here — the visible text is elided.
        malformed = sorted(
            f"{set_id} -> {name!r}"
            for set_id, name in uploads.items()
            if not name.casefold().endswith(self.WORKBOOK_SUFFIXES)
        )
        sample = sorted(uploads.items())[:3]

        record_property(
            "result_description",
            f"My Item Set listed {len(listed_sets)} set(s) for {self.sme_username(0)}; "
            f"{len(uploads)} name a source workbook (e.g. {sample or 'none on this page'}). "
            f"Uploaded File column index: {column_index}.",
        )

        assert column_index, (
            "The My Item Set list has no 'Uploaded File' column, so an item set's "
            "source workbook is no longer traceable from the list. "
            f"Headers seen: {[h.text.strip() for h in self.driver.find_elements(*page.ITEM_SET_TABLE_HEADERS)]}"
        )
        assert not malformed, (
            "Uploaded File cells do not name a workbook "
            f"({'/'.join(self.WORKBOOK_SUFFIXES)}): {malformed}"
        )
