import pytest
from selenium.webdriver.common.by import By

from pages.sme.manual_item_page import ManualItemPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.teacher.dashboard_page import DashboardPage
from utilities.read_config import ReadConfig
from utilities.smoke_support import sign_in


@pytest.mark.smoke
# Drives the shared primary teacher account, as test_teacher_login.py does.
# `serial` puts both in one xdist group so neither signs the other out.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestSmokeM5TeacherContribution:
    """M5 - Teacher Contribution smoke: a teacher can reach the contribution flows.

    Read-only by design — no item is authored and no file is uploaded.
    """

    MANUAL_TAB = ManualItemPage.MANUAL_ITEM_TAB_LOCATORS[1]
    UPLOAD_TAB = UploadItemFilePage.UPLOAD_ITEM_FILE_TAB_LOCATORS[0]
    UPLOAD_HISTORY_TABLE = (
        By.XPATH,
        "//table[.//th[contains(translate(normalize-space(), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
        "'file upload status')]]",
    )

    def sign_in_as_teacher(self):
        sign_in(self.driver, ReadConfig.get_username())
        assert DashboardPage(self.driver).is_dashboard_loaded(), (
            f"{ReadConfig.get_username()} did not land on the teacher dashboard"
        )

    def open_contribution_workspace(self):
        self.sign_in_as_teacher()
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        page.open_item_creation_module()
        return page

    def test_smoke_m5_01_teacher_reaches_contribution_workspace(self, record_property):
        """Teacher signs in, lands on the dashboard and opens item creation."""
        page = self.open_contribution_workspace()

        manual_tab_visible = page.is_element_visible_quick(self.MANUAL_TAB, timeout=20)
        upload_tab_visible = page.is_element_visible_quick(self.UPLOAD_TAB, timeout=20)
        record_property(
            "result_description",
            f"Teacher {ReadConfig.get_username()} reached the contribution workspace — "
            f"Manual tab: {manual_tab_visible}, Upload Item File tab: {upload_tab_visible}.",
        )

        assert manual_tab_visible, "Manual item authoring tab is not available to the teacher"
        assert upload_tab_visible, "Upload Item File (bulk) tab is not available to the teacher"

    def test_smoke_m5_02_teacher_upload_history_renders(self, record_property):
        """The teacher's Previously Uploaded Files history table renders."""
        page = self.open_contribution_workspace()
        page.open_upload_item_file_tab()
        page.open_upload_step()

        history_visible = page.is_element_visible_quick(self.UPLOAD_HISTORY_TABLE, timeout=20)
        # A never-used account legitimately has no rows, so the statuses are
        # evidence in the report rather than an assertion.
        statuses = page.get_upload_history_statuses(timeout=10)
        record_property(
            "result_description",
            "Teacher upload history rendered; recent statuses: "
            f"{', '.join(statuses) if statuses else 'no upload history rows'}.",
        )

        assert history_visible, (
            "Previously Uploaded Files history table did not render on the upload step"
        )
