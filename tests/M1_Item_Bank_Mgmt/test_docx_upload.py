"""Word (.docx) item upload — the second ingestion format alongside Excel.

The Word template carries the same 25 canonical fields as the Excel sheet, laid
out down a two-column table (label left, value right) instead of across a header
row, one block per question. Images are not embedded: a document names them in
its image fields and ships them in a companion `images.zip`, so a Word upload of
an image-bearing item is two files, not one.

**The upload step has an "Upload format" selector that defaults to Excel**, and
it drives the file input's `accept`: Excel advertises `.xlsx,.xls,.csv`, Word
advertises `.docx`. Reading `accept` without switching it therefore "proves"
Word is unsupported when it is not — that misreading is what previously had this
whole suite red and the feature written off as undeployed. Worse, Selenium's
`send_keys` bypasses `accept`, so leaving the selector on Excel does not raise:
the document is pushed at a form in spreadsheet mode and silently never reaches
the staged-file list. `open_upload_step()` switches to Word first, and every
check here depends on that.

This suite is deliberately **one test**. The whole Word path shares one login
and one upload step, and every phase reports through a shared failure list
rather than aborting, so a single run still names each individual document that
failed instead of stopping at the first. Phase 1 needs no browser: it pins the
shape of the shipped documents — field labels, typology names, and the
document/zip image pairing — so a template drop that changes the contract is
caught in seconds rather than surfacing later as unexplained row-validation
failures. That is the same trap `ReadConfig._carries_current_columns` guards for
the Excel sheet: a stale template still opens and still looks valid.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.sme.bulk_upload_page import BulkUploadPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.docx_item_template import (
    FIELD_LABELS,
    IMAGE_FIELDS,
    assert_canonical_labels,
    read_blocks,
    read_fields,
    referenced_images,
    rename_field_label,
    uniquify_question,
    zip_member_names,
)
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig


TEMPLATES_DIR = Path(ReadConfig.get_docx_template_dir())
IMAGES_ZIP = Path(ReadConfig.get_docx_images_zip_path())

# The twelve text-only documents, paired with the typology each one declares.
# Names are quoted from the documents themselves. 11_CaseBased and 12_SourceBased
# used to ship the plural "... Questions" where the app uses the singular, and the
# importer rejected both on an exact-match; the documents were corrected on
# 2026-09-17. Phase 1 still reports any surviving plural rather than normalising
# it away, so a future template drop that reintroduces one is named, not hidden.
TEXT_TYPOLOGY_CASES = [
    ("01_MCQ.docx", "Multiple Choice Question"),
    ("02_TrueFalse.docx", "True or False"),
    ("03_FillInTheBlank.docx", "Fill in the Blank"),
    ("04_AssertionReasoning.docx", "Assertion and Reasoning"),
    ("05_VeryShortAnswer.docx", "Very Short Answer Question"),
    ("06_ShortAnswer.docx", "Short Answer Question"),
    ("07_FAActivity.docx", "FA Activity"),
    ("08_LongAnswer.docx", "Long Answer Question"),
    ("09_FreeResponse.docx", "Free Response"),
    ("10_MatchTheFollowing.docx", "Match the Following"),
    ("11_CaseBased.docx", "Case Based Question"),
    ("12_SourceBased.docx", "Source Based Question"),
]

# The eight image-bearing documents. Each needs images.zip staged beside it.
IMAGE_DOCUMENT_CASES = [
    "13_MCQ_ImageQuestion.docx",
    "14_VSAQ_ImageQuestion.docx",
    "15_SAQ_ImageQuestion.docx",
    "16_TrueFalse_ImageQuestion.docx",
    "17_VSAQ_ImageAnswer.docx",
    "18_SAQ_ImageAnswer.docx",
    "19_LongAnswer_ImageAnswer.docx",
    "20_FreeResponse_ImageAnswer.docx",
]

ALL_DOCUMENTS = [name for name, _ in TEXT_TYPOLOGY_CASES] + IMAGE_DOCUMENT_CASES

# The typologies the application itself offers, as the Excel typology suite and
# the manual-item suite spell them.
APP_TYPOLOGIES = {
    "Multiple Choice Question",
    "True or False",
    "Match the Following",
    "Fill in the Blank",
    "Assertion and Reasoning",
    "Very Short Answer Question",
    "Short Answer Question",
    "Long Answer Question",
    "FA Activity",
    "Free Response",
    "Case Based Question",
    "Source Based Question",
}




@pytest.mark.rtm
@pytest.mark.ui
@pytest.mark.e2e
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestDocxItemUpload:
    """The whole Word ingestion path, as one test.

    Phases run in order against one signed-in session. A phase records its
    failures and keeps going, so one run reports every broken document rather
    than only the first.
    """

    def login_as_sme(self):
        username = ReadConfig.get_sme2_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        return username

    def open_upload_step(self, upload_format="Word"):
        """Reach the upload step with the Upload format selector set to Word.

        The step defaults to Excel, and that selector drives the file input's
        `accept` (.xlsx/.xls/.csv for Excel, .docx for Word). Leaving it on
        Excel does not raise: send_keys bypasses `accept`, so the document is
        pushed at a form in spreadsheet mode and silently never reaches the
        staged-file list.
        """
        page = UploadItemFilePage(self.driver)
        # Back to the app root first. Phases share one signed-in session, and a
        # phase that clicked Continue is sitting on the review step where the
        # Upload Documents heading no longer exists -- navigating from wherever
        # the last phase finished is what made this time out.
        self.driver.get(ReadConfig.get_base_url())
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        page.open_item_creation_module()
        page.open_upload_item_file_tab()
        page.open_upload_step()
        if upload_format:
            page.select_upload_format(upload_format)
        return page

    @staticmethod
    def stage_document(document_name, tmp_path, run_id=None):
        """A run-unique copy of a shipped document.

        The question text is re-stamped rather than uploaded verbatim: the
        samples carry a fixed `[QA-...]` tag, so re-running would upload the
        same sentence every time and trip duplicate and plagiarism detection on
        the second run onwards.
        """
        run_id = run_id or uuid4().hex[:10]
        source = TEMPLATES_DIR / document_name
        assert source.exists(), f"Missing sample document: {source}"
        target = tmp_path / f"{source.stem}_{run_id}.docx"
        question = uniquify_question(source, target, run_id)
        # Case/Source Based documents carry sub-question blocks too; each one
        # is an item of its own and must be fresh on every run.
        for block_index in range(1, len(read_blocks(target))):
            uniquify_question(target, target, run_id, block_index=block_index)
        return target, question

    def discard_staged_upload(self, page):
        """Clear the upload slot, best effort, so the next check starts clean."""
        if page is None:
            return
        try:
            page.discard_active_upload_if_present()
            page.discard_staged_upload_files()
        except Exception:  # noqa: BLE001 - cleanup must not mask the real failure
            pass

    # A returned "rejection" carrying these is the whole page body, not an
    # error: they are permanent furniture on the upload step.
    PAGE_DUMP_MARKERS = ("Toggle Sidebar", "Accepted Formats", "Required Columns")

    @classmethod
    def looks_like_page_dump(cls, message):
        text = (message or "").strip()
        return len(text) > 400 or any(marker in text for marker in cls.PAGE_DUMP_MARKERS)

    def refusal_detail(self, page, document_name):
        """(refused, detail) for a document the importer should refuse.

        Staging is the observable worth gating on, because it is unambiguous:
        a refused document does not appear in the uploaded-file list, so
        `activate_uploaded_file` cannot find it. Any error message is kept as
        supporting evidence, but only when it is a real bounded message rather
        than a page dump; the message alone is too weak to assert on.
        """
        staged = True
        try:
            page.activate_uploaded_file(document_name)
        except Exception:  # noqa: BLE001 - not staged is exactly what we want
            staged = False

        detail = ""
        if not staged:
            try:
                message = page.wait_for_upload_rejection(timeout=10)
            except Exception:  # noqa: BLE001 - a silent refusal is still a refusal
                message = ""
            if message and not self.looks_like_page_dump(message):
                detail = f" The app explained it: {message}"
            elif message:
                detail = (
                    " The app showed no specific message, only the whole page, "
                    "which proves nothing either way."
                )
        return (not staged), detail

    def validate_document(self, page, document, images_zip=None):
        """Stage a document, plus its images .zip if it has one, and return the
        success message.

        The zip is a second step, not a companion in the same file pick: the
        app stages the document, then opens an "Upload Images ZIP" panel and
        waits for the zip there. Sending both at once (what this used to do)
        left the zip unattached and the upload waiting forever - all eight
        image documents failed that way on 2026-09-29.
        """
        page.upload_file(document)
        if images_zip is None:
            page.activate_uploaded_file(document.name)
            return page.wait_for_upload_validation_success()
        outcome = BulkUploadPage(self.driver).attach_images_zip(images_zip)
        assert outcome["accepted"], (
            f"{document.name}: the images ZIP was rejected: {outcome['message']}"
        )
        return outcome["message"]

    def test_docx_item_upload_end_to_end(self, tmp_path, record_property, page_evidence):
        """Template contract, the .docx gate, every typology, images, and negatives."""
        record_property(
            "test_summary",
            "Check the 20 shipped Word documents without a browser: field labels, "
            "typology names, and that every referenced image is in images.zip.\n"
            "Sign in as an SME, switch the Upload format selector to Word, and "
            "confirm the file input then advertises .docx.\n"
            "Upload one document per typology, and the image-bearing documents "
            "alongside images.zip, letting each validate.\n"
            "Finally push two documents the importer must refuse: one with a "
            "renamed field label, one that is not a Word file at all.\n"
            "Every phase records its own failures and keeps going, so one run "
            "names every broken document rather than stopping at the first.",
        )
        failures = []
        notes = []
        accepted = []
        item_set_id = None
        username = ""

        # ---------- Phase 1: template contract, no browser ----------
        assert TEMPLATES_DIR.is_dir(), (
            f"Word template directory not found at {TEMPLATES_DIR}. Set "
            "CBSE_DOCX_TEMPLATE_DIR to a directory holding the sample documents."
        )
        assert IMAGES_ZIP.exists(), f"Companion image zip not found at {IMAGES_ZIP}"

        for document_name in ALL_DOCUMENTS:
            document_path = TEMPLATES_DIR / document_name
            if not document_path.exists():
                failures.append(f"contract: missing sample document {document_name}")
                continue
            try:
                assert_canonical_labels(document_path)
            except AssertionError as error:
                failures.append(f"contract: {document_name} field labels - {error}")

        available = set(zip_member_names(IMAGES_ZIP))
        for document_name in IMAGE_DOCUMENT_CASES:
            absent = [
                name
                for name in referenced_images(TEMPLATES_DIR / document_name)
                if name not in available
            ]
            if absent:
                failures.append(
                    f"contract: {document_name} references {absent}, absent from "
                    f"{IMAGES_ZIP.name} which holds {sorted(available)} - a packaging "
                    "mistake, not an app defect"
                )

        plural = {}
        for document_name in ALL_DOCUMENTS:
            declared = read_fields(TEMPLATES_DIR / document_name).get("Typology", "")
            if declared in APP_TYPOLOGIES:
                continue
            singular = declared[:-1] if declared.endswith("s") else declared
            if singular in APP_TYPOLOGIES:
                # Recorded, not failed: the documents genuinely ship these plural,
                # and the upload phase below is what proves whether the importer
                # honours them.
                plural[document_name] = declared
            else:
                failures.append(
                    f"contract: {document_name} declares Typology {declared!r}, which "
                    f"matches no typology the app offers. Known: {sorted(APP_TYPOLOGIES)}"
                )
        if plural:
            notes.append(
                f"{len(plural)} document(s) name a typology in the plural where the app "
                f"uses the singular: {plural}"
            )
        page_evidence.checkpoint(
            f"Template contract checked across {len(ALL_DOCUMENTS)} documents; "
            f"{len(failures)} problem(s) so far"
        )

        try:
            # ---------- Phase 2: the .docx gate ----------
            username = self.login_as_sme()
            page = self.open_upload_step()
            accepted = page.get_accepted_upload_extensions() or []
            page_evidence.checkpoint(
                f"{username} on the upload step, format=Word, accept={accepted or 'nothing'}"
            )
            if ".docx" not in accepted:
                # Nothing below can stage a document, so stop here with the reason.
                raise AssertionError(
                    "The upload step does not offer .docx even with the Upload format "
                    f"selector set to Word. The file input advertises {accepted}. Word "
                    "mode should advertise exactly ['.docx']; seeing the spreadsheet "
                    "extensions here means the format switch silently did not take."
                )

            # ---------- Phase 3: one document ingested to the review step ----------
            try:
                document, question = self.stage_document("01_MCQ.docx", tmp_path)
                message = self.validate_document(page, document)
                page.click_continue()
                item_ids = page.get_review_item_ids()
                item_set_id = page.get_item_set_id_from_item_ids(item_ids)
                page_evidence.checkpoint(
                    f"{document.name} validated ({message}); review listed "
                    f"{len(item_ids)} item(s) {item_ids} under {item_set_id or 'UNKNOWN'}"
                )
                if not item_ids:
                    failures.append(
                        f"ingestion: {document.name} reported success ({message}) but the "
                        "review step listed no items, so nothing was created"
                    )
                elif not item_set_id:
                    failures.append(
                        f"ingestion: no item set ID derived from {item_ids}, so the upload "
                        "produced no reviewable set"
                    )
            except Exception as error:  # noqa: BLE001 - recorded, later phases still run
                failures.append(f"ingestion: 01_MCQ.docx to review step - {error}")
            finally:
                self.discard_staged_upload(page)

            # ---------- Phase 4: every text typology validates ----------
            for document_name, typology in TEXT_TYPOLOGY_CASES:
                page = None
                try:
                    page = self.open_upload_step()
                    document, _ = self.stage_document(document_name, tmp_path)
                    declared = read_fields(document).get("Typology", "")
                    if declared != typology:
                        failures.append(
                            f"typology: {document_name} declares {declared!r}, not the "
                            f"{typology!r} this suite expects - the document set changed"
                        )
                        continue
                    message = self.validate_document(page, document)
                    page_evidence.checkpoint(
                        f"{typology}: {document.name} validated: {message}"
                    )
                except Exception as error:  # noqa: BLE001
                    failures.append(f"typology {typology} ({document_name}) - {error}")
                finally:
                    self.discard_staged_upload(page)

            # ---------- Phase 5: image documents with images.zip ----------
            for document_name in IMAGE_DOCUMENT_CASES:
                page = None
                try:
                    page = self.open_upload_step()
                    document, _ = self.stage_document(document_name, tmp_path)
                    expected_images = referenced_images(document)
                    if not expected_images:
                        failures.append(
                            f"images: {document_name} is listed as image-bearing but "
                            "references no image"
                        )
                        continue
                    message = self.validate_document(
                        page, document, images_zip=IMAGES_ZIP
                    )
                    page_evidence.checkpoint(
                        f"{document.name} + {IMAGES_ZIP.name} validated "
                        f"(images {expected_images}): {message}"
                    )
                except Exception as error:  # noqa: BLE001
                    failures.append(f"images: {document_name} + images.zip - {error}")
                finally:
                    self.discard_staged_upload(page)

            # ---------- Phase 6: negatives ----------
            page = None
            try:
                page = self.open_upload_step()
                renamed = tmp_path / f"renamed_label_{uuid4().hex[:10]}.docx"
                rename_field_label(
                    TEMPLATES_DIR / "01_MCQ.docx", renamed, "Competency", "Cmptncy"
                )
                assert "Competency" not in read_fields(renamed), (
                    "The Competency label was not actually renamed, so this proves nothing."
                )
                page.upload_file(renamed)
                refused, detail = self.refusal_detail(page, renamed.name)
                page_evidence.checkpoint(
                    f"Renamed-label document: refused={refused}.{detail}"
                )
                if not refused:
                    failures.append(
                        f"negative: {renamed.name} carries a renamed field label but was "
                        "accepted into the staged-file list - the importer is taking a "
                        "document it cannot honour"
                    )
            except Exception as error:  # noqa: BLE001
                failures.append(f"negative: renamed field label - {error}")
            finally:
                self.discard_staged_upload(page)

            page = None
            try:
                page = self.open_upload_step()
                counterfeit = tmp_path / f"not_really_word_{uuid4().hex[:10]}.docx"
                counterfeit.write_bytes(
                    b"PK\x03\x04 not a Word document - .docx ingestion negative check\n"
                )
                page.upload_file(counterfeit)
                refused, detail = self.refusal_detail(page, counterfeit.name)
                page_evidence.checkpoint(f"Counterfeit .docx: refused={refused}.{detail}")
                if not refused:
                    failures.append(
                        f"negative: {counterfeit.name} is not a Word document but was "
                        "accepted into the staged-file list - the importer trusts the "
                        "extension rather than the content"
                    )
            except Exception as error:  # noqa: BLE001
                failures.append(f"negative: counterfeit .docx - {error}")
            finally:
                self.discard_staged_upload(page)
        finally:
            record_property(
                "result_description",
                f"Word ingestion exercised as {username or 'SME'}: {len(ALL_DOCUMENTS)} "
                f"shipped document(s) plus 2 negatives, accept={accepted}, item set "
                f"{item_set_id or 'none'}. {len(failures)} failure(s)."
                + (f" Notes: {'; '.join(notes)}." if notes else "")
            )

        checked = len(ALL_DOCUMENTS) + 2
        assert not failures, (
            f"{len(failures)} of the {checked} Word upload check(s) failed:\n  - "
            + "\n  - ".join(failures)
            + (f"\nNotes: {'; '.join(notes)}" if notes else "")
        )
