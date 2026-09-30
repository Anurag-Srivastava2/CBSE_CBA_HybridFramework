from shutil import copy2
from uuid import uuid4

from openpyxl import load_workbook
import pytest

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.page_evidence import checkpoint
from utilities.item_template_columns import resolve_columns
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestSMEBulkUploadValidation:
    def login_and_open_upload(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_password_for_username(ReadConfig.get_sme2_username()),
        )
        upload_page = UploadItemFilePage(self.driver)
        upload_page.close_popup_if_open()
        upload_page.open_item_creation_module()
        upload_page.open_upload_item_file_tab()
        upload_page.open_upload_step()
        checkpoint("SME signed in and reached the Upload Documents step")
        return upload_page

    def test_tc_ibmm_01a_n01_non_xlsx_file_is_rejected(self, tmp_path, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Push a PDF at the bulk upload step as an SME.\n"
            "Check it is rejected rather than accepted as an item workbook.",
        )
        invalid_file = tmp_path / "sample_items.pdf"
        invalid_file.write_bytes(b"%PDF-1.4\n% invalid item-upload test file\n")

        upload_page = self.login_and_open_upload()
        upload_page.upload_file(invalid_file)
        rejection_message = upload_page.wait_for_upload_rejection()
        page_evidence.checkpoint(
            f"{invalid_file.name} (a PDF, not a workbook) was rejected: "
            f"{rejection_message}"
        )

        normalized_message = rejection_message.casefold()
        assert "xlsx" in normalized_message
        assert "invalid" in normalized_message or "only" in normalized_message

    def test_tc_ibmm_01a_n02_modified_header_upload_fails(self, tmp_path, page_evidence, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Take a valid template, rename one of its column headers, and upload it.\n"
            "Check the upload fails, because the header no longer matches what the "
            "importer expects.",
        )
        modified_file = tmp_path / "modified_header_items.xlsx"
        copy2(ReadConfig.get_upload_item_file_path(), modified_file)
        workbook = load_workbook(modified_file)
        worksheet = workbook.active
        columns = resolve_columns(worksheet)
        assert columns, "Upload template has no recognisable item-data sheet."
        worksheet.cell(row=1, column=1).value = "Modified Grade Header"
        run_id = uuid4().hex[:12]
        for row_number in range(2, worksheet.max_row + 1):
            question_cell = worksheet.cell(row=row_number, column=columns["question"])
            if question_cell.value:
                question_cell.value = f"{question_cell.value} Header test {run_id}-{row_number}"
        workbook.save(modified_file)
        workbook.close()

        upload_page = self.login_and_open_upload()
        upload_page.upload_file(modified_file)
        rejection_message = upload_page.wait_for_upload_rejection(timeout=60)
        page_evidence.checkpoint(
            f"{modified_file.name} (column 1 header renamed to "
            "'Modified Grade Header') was rejected: "
            f"{rejection_message}"
        )

        normalized_message = rejection_message.casefold()
        assert "failed" in normalized_message or "error" in normalized_message
        assert "header" in normalized_message or "validation" in normalized_message

    def test_tc_ibmm_03_n01_duplicate_item_content_is_rejected(
        self, tmp_path, page_evidence, record_property
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Upload a workbook whose item content duplicates something already in the "
            "bank.\n"
            "Check it is rejected.",
        )
        duplicate_file = tmp_path / "duplicate_item_content.xlsx"
        copy2(ReadConfig.get_upload_item_file_path(), duplicate_file)
        workbook = load_workbook(duplicate_file)
        worksheet = workbook.active
        columns = resolve_columns(worksheet)
        assert columns, "Upload template has no recognisable item-data sheet."
        run_id = uuid4().hex[:12]
        for row_number in range(2, worksheet.max_row + 1):
            question_cell = worksheet.cell(row=row_number, column=columns["question"])
            if question_cell.value:
                question_cell.value = f"{question_cell.value} Duplicate test {run_id}-{row_number}"
        duplicate_values = [
            worksheet.cell(row=2, column=column).value
            for column in range(1, worksheet.max_column + 1)
        ]
        worksheet.append(duplicate_values)
        workbook.save(duplicate_file)
        workbook.close()

        upload_page = self.login_and_open_upload()
        upload_page.upload_file(duplicate_file)
        rejection_message = upload_page.wait_for_upload_rejection(timeout=60)
        normalized_message = rejection_message.casefold()
        page_evidence.checkpoint(
            f"{duplicate_file.name} (row 2 appended verbatim as an extra row) "
            f"was rejected: {rejection_message}"
        )

        assert "duplicate" in normalized_message
        assert "row" in normalized_message or "item" in normalized_message
