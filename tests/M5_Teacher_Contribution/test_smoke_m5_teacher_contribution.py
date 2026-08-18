import pytest
from selenium.webdriver.common.by import By

from pages.sme.manual_item_page import ManualItemPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.teacher.dashboard_page import DashboardPage
from tests.M5_Teacher_Contribution.m5_surveys import (
    survey_contribution_workspace,
    survey_teacher_chrome,
    survey_upload_history,
)
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig
from utilities.smoke_support import sign_in


@pytest.mark.smoke
# Drives the shared primary teacher account, as test_teacher_login.py does.
# `serial` puts both in one xdist group so neither signs the other out.
@pytest.mark.serial
# The first check here is dispatched in the run's opening wave, when every
# xdist worker hits the login endpoint at once, and the portal intermittently
# fails to complete a sign-in under that burst — observed on consecutive CI
# builds, while the same account signs in fine seconds later once the surge
# clears. One retry lands after the burst; the retry badge keeps the
# occurrence visible rather than hiding it.
@pytest.mark.flaky(reruns=1, reruns_delay=5)
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

        # Additive only: every assertion below stays exactly as hard as it was.
        checks = ElementChecks(
            page, record_property, page_name="Teacher Contribution — Workspace"
        )
        survey_teacher_chrome(checks, page)

        manual_tab_visible = page.is_element_visible_quick(self.MANUAL_TAB, timeout=20)
        upload_tab_visible = page.is_element_visible_quick(self.UPLOAD_TAB, timeout=20)
        record_property(
            "result_description",
            f"Teacher {ReadConfig.get_username()} reached the contribution workspace — "
            f"Manual tab: {manual_tab_visible}, Upload Item File tab: {upload_tab_visible}. "
            f"{checks.publish()}",
        )

        assert manual_tab_visible, "Manual item authoring tab is not available to the teacher"
        assert upload_tab_visible, "Upload Item File (bulk) tab is not available to the teacher"

    def test_smoke_m5_02_teacher_upload_history_renders(self, record_property):
        """The teacher's Previously Uploaded Files history table renders."""
        page = self.open_contribution_workspace()
        page.open_upload_item_file_tab()
        page.open_upload_step()

        checks = ElementChecks(
            page, record_property, page_name="Teacher Contribution — Upload History"
        )
        survey_teacher_chrome(checks, page)
        survey_contribution_workspace(checks, page)
        survey_upload_history(checks, page)

        history_visible = page.is_element_visible_quick(self.UPLOAD_HISTORY_TABLE, timeout=20)
        # A never-used account legitimately has no rows, so the statuses are
        # evidence in the report rather than an assertion.
        statuses = page.get_upload_history_statuses(timeout=10)
        record_property(
            "result_description",
            "Teacher upload history rendered; recent statuses: "
            f"{', '.join(statuses) if statuses else 'no upload history rows'}. "
            f"{checks.publish()}",
        )

        assert history_visible, (
            "Previously Uploaded Files history table did not render on the upload step"
        )
