import json

from openpyxl import load_workbook
import pytest

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
# Signs in as the shared teacher and SME accounts and reads their upload
# history, which another session on the same account adds to mid-test.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestUploadHistoryExcelDownload:
    @staticmethod
    def get_secondary_contributor_users():
        """Every non-primary SME/Teacher account, most likely candidate first.

        This test needs an account whose upload history holds both a PASSED
        and a FAILED row. The history view shows only the most recent uploads,
        so a heavily exercised account can have its older FAILED rows pushed
        out of view entirely by a run's worth of passing uploads - checking
        one alternate per role then reports a data gap that other configured
        accounts do not have.
        """
        primary_users = {
            ReadConfig.get_sme2_username().casefold(),
            ReadConfig.get_username().casefold(),
        }
        secondary_users = []
        seen = set()
        for role in ("sme", "teacher"):
            for username in ReadConfig.get_role_usernames(role):
                key = username.casefold()
                if key in primary_users or key in seen:
                    continue
                seen.add(key)
                secondary_users.append((role, username))
        return secondary_users

    def open_base_url(self, attempts=2):
        """Navigate to the app, surviving a navigation that never settles.

        A driver.get() here can sit until the remote command times out when
        the app is slow to respond. Stopping the stalled load and retrying
        recovers the session instead of failing the whole flow.
        """
        last_error = None
        for attempt in range(attempts):
            try:
                self.driver.set_page_load_timeout(60)
                self.driver.get(ReadConfig.get_base_url())
                return
            except Exception as error:
                last_error = error
                try:
                    self.driver.execute_script("window.stop();")
                except Exception:
                    pass
            finally:
                try:
                    self.driver.set_page_load_timeout(300)
                except Exception:
                    pass
        raise last_error

    def login_and_open_upload_history(self, username, reset_session=False):
        upload_page = UploadItemFilePage(self.driver)
        if reset_session:
            upload_page.reset_browser_session_to_login()
        else:
            self.open_base_url()

        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_all_users_password(),
        )
        upload_page.close_popup_if_open()
        upload_page.wait_for_application_to_load()
        upload_page.open_item_creation_module()
        upload_page.open_upload_item_file_tab()
        upload_page.open_upload_step()
        return upload_page

    @staticmethod
    def verify_excel_workbook(downloaded_file):
        assert downloaded_file.exists(), f"Downloaded file is missing: {downloaded_file}"
        assert downloaded_file.stat().st_size > 0, (
            f"Downloaded file is empty: {downloaded_file}"
        )
        assert downloaded_file.suffix.casefold() == ".xlsx", (
            f"Expected an .xlsx download, received: {downloaded_file.name}"
        )

        workbook = load_workbook(downloaded_file, read_only=True, data_only=False)
        try:
            worksheet = workbook.active
            assert worksheet.max_row >= 1
            assert worksheet.max_column >= 1
        finally:
            workbook.close()

    def test_passed_and_failed_upload_history_files_download_as_excel(
        self,
        tmp_path,
        request,
    ):
        contributors = self.get_secondary_contributor_users()
        assert contributors, "No secondary SME or Teacher user is configured."

        checked_accounts = []
        selected_account = None
        upload_page = None
        for index, (role, username) in enumerate(contributors):
            try:
                candidate_page = self.login_and_open_upload_history(
                    username,
                    reset_session=index > 0,
                )
            except Exception as error:
                # Not every configured account is necessarily usable in this
                # environment (a role list can name a login that does not
                # exist or does not share the common password). That is a
                # provisioning gap in one candidate, not a failure of the
                # download behaviour under test - record it and try the next.
                checked_accounts.append(
                    f"{role}:{username}=unavailable ({type(error).__name__})"
                )
                continue
            upload_page = candidate_page
            statuses = upload_page.get_upload_history_statuses()
            checked_accounts.append(f"{role}:{username}={','.join(statuses) or 'none'}")
            if {"PASSED", "FAILED"}.issubset(set(statuses)):
                selected_account = (role, username)
                break

        assert selected_account is not None, (
            "A secondary SME/Teacher account must have both PASSED and FAILED "
            "upload-history rows. Checked: " + "; ".join(checked_accounts)
        )

        role, username = selected_account
        request.node.user_properties.append(("download_account", f"{role}:{username}"))
        request.node.user_properties.append(("upload_history", "; ".join(checked_accounts)))

        passed_status_screenshot = upload_page.capture_upload_history_status_screenshot(
            "PASSED",
            f"{request.node.name}_passed_file_status",
            action_text="Download File",
        )
        failed_status_screenshot = upload_page.capture_upload_history_status_screenshot(
            "FAILED",
            f"{request.node.name}_failed_file_status",
            action_text="Download Annotated File",
        )
        request.node.user_properties.append(
            (
                "evidence_screenshots",
                json.dumps(
                    [
                        {
                            "name": "PASSED file status and Download File action",
                            "path": passed_status_screenshot,
                        },
                        {
                            "name": "FAILED file status and Download Annotated File action",
                            "path": failed_status_screenshot,
                        },
                    ]
                ),
            )
        )

        passed_file = upload_page.download_upload_history_file(
            "PASSED",
            tmp_path / "passed",
        )
        self.verify_excel_workbook(passed_file)

        failed_file = upload_page.download_upload_history_file(
            "FAILED",
            tmp_path / "failed",
        )
        self.verify_excel_workbook(failed_file)

        assert passed_file.resolve() != failed_file.resolve()
        request.node.user_properties.append(("passed_download", str(passed_file)))
        request.node.user_properties.append(("failed_download", str(failed_file)))
        request.node.user_properties.append(
            (
                "result_description",
                f"Downloaded and opened PASSED and FAILED Excel files as {role} {username}.",
            )
        )
