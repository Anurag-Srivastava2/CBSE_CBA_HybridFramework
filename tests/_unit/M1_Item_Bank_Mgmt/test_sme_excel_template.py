import re
from shutil import copy2

from openpyxl import load_workbook
import pytest

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.item_template_columns import CANONICAL_HEADERS, item_data_worksheet
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig

# Not \b: in "Template_v3" the underscore is a word character, so \b misses
# it. The lookbehind still keeps "Level 2" and similar from matching.
VERSION_MARKER = re.compile(r"(?<![a-z])v(?:ersion)?[_ .-]?\d+", re.IGNORECASE)


def template_version_marker(template):
    """A version marker anywhere a template could carry one - its file name,
    any cell on any sheet, or the document properties - or None.

    Searched this widely on purpose: the 2026-09-29 QA template had none in
    any of these places, and a narrower search would not prove that.
    """
    workbook = load_workbook(template, read_only=True)
    try:
        texts = [template.name]
        properties = workbook.properties
        texts += [
            str(getattr(properties, name) or "")
            for name in ("title", "version", "keywords", "description")
        ]
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                texts += [str(value) for value in row if value is not None]
    finally:
        workbook.close()
    for text in texts:
        match = VERSION_MARKER.search(text)
        if match:
            return match.group(0)
    return None


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestSMEExcelTemplate:
    def login_and_open_upload_tab(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_password_for_username(ReadConfig.get_sme2_username()),
        )
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        page.open_item_creation_module()
        page.open_upload_item_file_tab()
        return page

    def download_template(self, tmp_path):
        page = self.login_and_open_upload_tab()
        checkpoint("SME signed in and opened the Upload Item File tab")
        template = page.download_latest_template(tmp_path)
        checkpoint(f"Latest template downloaded as {template.name}")
        return template

    def test_tc_ibmm_04_p01_template_downloads_with_headers_and_version(
        self, tmp_path, page_evidence, record_property
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Download the SME item template.\n"
            "Check it opens as a workbook carrying the expected headers and a version "
            "marker.",
        )
        template = self.download_template(tmp_path)
        workbook = load_workbook(template, read_only=True, data_only=False)
        worksheet = item_data_worksheet(workbook)
        assert worksheet is not None, (
            f"No item-data sheet in {template.name}: {workbook.sheetnames}"
        )
        headers = [cell.value for cell in worksheet[1] if cell.value]
        workbook.close()
        page_evidence.checkpoint(
            f"{template.name} carries {len(headers)} header(s) (>= 15 required): "
            f"{headers[:12]}"
        )

        assert template.suffix.casefold() == ".xlsx"
        assert len(headers) >= 15, f"Expected at least 15 required headers, received: {headers}"
        # The whole suite writes to this sheet by field name against
        # CANONICAL_HEADERS, so a template that no longer matches it is a
        # contract break to report here rather than a mystery row-level
        # rejection in every upload suite downstream.
        assert tuple(headers) == CANONICAL_HEADERS, (
            "Downloaded template's columns have moved away from the contract the "
            "suite writes against.\n"
            f"  app:   {tuple(headers)}\n"
            f"  suite: {CANONICAL_HEADERS}"
        )
        version_marker = template_version_marker(template)
        page_evidence.checkpoint(
            f"Version marker on the template: {version_marker or 'none found'}"
        )
        if not version_marker:
            # Documented gap; the header contract above stays a hard check.
            pytest.xfail(
                f"KI-M1-TEMPLATE-001: {template.name} carries no version marker "
                "in its name, cells or properties."
            )

    def test_tc_ibmm_04_p02_template_has_controlled_field_validations(
        self, tmp_path, page_evidence, record_property
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Download the template and inspect its cells.\n"
            "Check the controlled fields carry the dropdown validations that keep an "
            "author inside the allowed values.",
        )
        template = self.download_template(tmp_path)
        workbook = load_workbook(template, read_only=False, data_only=False)
        worksheet = item_data_worksheet(workbook)
        assert worksheet is not None, (
            f"No item-data sheet in {template.name}: {workbook.sheetnames}"
        )
        headers = {
            str(cell.value).strip().casefold(): cell.column_letter
            for cell in worksheet[1] if cell.value
        }
        validations = list(worksheet.data_validations.dataValidation)
        workbook.close()

        required = {
            "question_typology": ("question_typology", "typology"),
            "blooms_level": ("blooms_level", "bloom's level", "blooms level", "blooms taxonomy"),
            # No difficulty_level: the template dropped that column, and
            # CANONICAL_HEADERS - the contract every upload suite writes
            # against - dropped it too.
            # Book and Unit are controlled the same way: each is a cascading
            # dropdown scoped by the choice above it, so a template that ships
            # them as free text would let an author type a book that resolves
            # against nothing.
            "book": ("book",),
            "unit": ("unit",),
        }
        missing_headers = []
        missing_validations = []
        for name, aliases in required.items():
            column = next((headers[alias] for alias in aliases if alias in headers), None)
            if not column:
                missing_headers.append(name)
                continue
            if not any(
                validation.type == "list" and f"{column}2" in str(validation.sqref)
                for validation in validations
            ):
                missing_validations.append(name)

        page_evidence.checkpoint(
            f"Controlled fields on the template — missing headers: "
            f"{missing_headers or 'none'}; headers without a list validation: "
            f"{missing_validations or 'none'}"
        )
        assert not missing_headers, f"Controlled-field headers missing: {missing_headers}"
        assert not missing_validations, (
            f"List validation missing from controlled fields: {missing_validations}"
        )

    def test_tc_ibmm_04_n02_old_template_version_shows_upgrade_notice(
        self, tmp_path, page_evidence, record_property
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Upload a workbook built from an older version of the template.\n"
            "Check the app tells the author to upgrade, rather than quietly accepting "
            "stale columns.",
        )
        page = self.login_and_open_upload_tab()
        current_template = page.download_latest_template(tmp_path / "current")
        # Without a version on the current template there is nothing for an
        # older one to be stale against. Stopping here also avoids leaving a
        # pending upload on the SME account for the next suite to trip over.
        if not template_version_marker(current_template):
            pytest.xfail(
                "KI-M1-TEMPLATE-003: the template is not versioned, so a legacy "
                "version cannot be constructed or rejected."
            )
        old_template = tmp_path / "Item_Upload_Template_v0.xlsx"
        copy2(current_template, old_template)
        page_evidence.checkpoint(
            f"{current_template.name} re-filed as {old_template.name} so the "
            "upload sees a stale template version"
        )

        page.open_upload_step()
        page.upload_file(old_template)
        message = page.wait_for_upload_rejection(timeout=60)
        normalized = message.casefold()
        page_evidence.checkpoint(f"Stale template rejected with: {message}")

        assert "version" in normalized
        assert "latest" in normalized or "upgrade" in normalized or "mismatch" in normalized
