from openpyxl import load_workbook
import pytest

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestSMEBulkUploadRBAC:
    def test_tc_ibmm_01a_p03_sme_sees_only_assigned_grade_subject_items(self):
        workbook = load_workbook(
            ReadConfig.get_upload_item_file_path(),
            read_only=True,
            data_only=True,
        )
        worksheet = workbook.active
        expected_grade = str(worksheet.cell(row=2, column=1).value).strip()
        expected_subject = str(worksheet.cell(row=2, column=2).value).strip()
        workbook.close()

        self.driver.get(ReadConfig.get_base_url())
        sme_username = ReadConfig.get_sme2_username()
        LoginPage(self.driver).login_to_application(
            sme_username,
            ReadConfig.get_password_for_username(sme_username),
        )

        sets_page = UploadItemFilePage(self.driver)
        sets_page.close_popup_if_open()
        sets_page.open_sets_module()
        scopes = sets_page.verify_visible_item_sets_within_scope(
            expected_grade,
            expected_subject,
        )

        assert all(scope["grade"] != "Grade 10" for scope in scopes)
        assert all(scope["subject"].casefold() != "english" for scope in scopes)
