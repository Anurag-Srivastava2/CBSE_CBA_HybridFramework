from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.admin.user_management_page import UserManagementPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2UserLifecycle:
    """TC-WPAD-USER-05: admin provisions a user, that user signs in while
    Active, the admin deactivates them, and the same credentials are then
    refused."""

    NEW_USER_PASSWORD = "Test@12345"

    def login(self, username, password):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(username, password)

    def login_as_admin(self):
        username = ReadConfig.get_role_usernames("admin")[0]
        self.login(username, ReadConfig.get_password_for_username(username))
        page = UserManagementPage(self.driver)
        page.open(ReadConfig.get_base_url())
        return page

    def logout(self):
        LoginPage(self.driver).logout(ReadConfig.get_base_url())

    def is_signed_in(self):
        """A signed-in session renders the app shell; the login form is gone."""
        return not LoginPage(self.driver).is_login_form_displayed()

    def test_tc_wpad_user_05_create_login_deactivate_and_block(self, record_property):
        run_id = uuid4().hex[:6]
        first_name = "Lifecycle"
        last_name = f"Auto{run_id}"
        full_name = f"{first_name} {last_name}"
        email = f"lifecycle_{run_id}@demo.com"
        mobile = f"7{uuid4().int % 10**9:09d}"

        record_property("result_description", f"Lifecycle user {full_name} <{email}>")

        # --- Step 1: admin creates the user -----------------------------------
        record_property("result_checkpoint", "Step 1 — admin creates user")
        admin_page = self.login_as_admin()
        try:
            admin_page.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                mobile=mobile,
                password=self.NEW_USER_PASSWORD,
                role="SME role",
            )
        except TimeoutException as error:
            pytest.fail(f"Admin could not create the lifecycle user: {error}")

        admin_page.search_user(full_name)
        assert admin_page.is_user_listed(full_name), (
            f"Newly created user {full_name!r} is not listed in User Management."
        )
        user_code = admin_page.get_user_code(full_name)
        record_property("manual_item_id", user_code)
        assert admin_page.is_user_active(full_name), (
            f"{user_code} should be Active immediately after creation, "
            f"but shows {admin_page.get_user_status(full_name)!r}."
        )
        self.logout()

        # --- Step 2: the active user can sign in ------------------------------
        record_property("result_checkpoint", "Step 2 — active user signs in")
        self.login(email, self.NEW_USER_PASSWORD)
        assert self.is_signed_in(), (
            f"Active user {email} could not sign in with the provisioned password."
        )
        self.logout()

        # --- Step 3: admin deactivates the user -------------------------------
        record_property("result_checkpoint", "Step 3 — admin deactivates user")
        admin_page = self.login_as_admin()
        admin_page.search_user(full_name)
        assert admin_page.is_user_active(full_name), (
            f"{user_code} should still be Active before deactivation."
        )
        admin_page.toggle_user_status(full_name)
        toast = admin_page.get_toast_message()
        admin_page.search_user(full_name)
        status_after = admin_page.get_user_status(full_name)
        record_property(
            "result_description",
            f"{user_code} ({full_name}) status after toggle: {status_after}. Toast: {toast or 'none'}",
        )
        assert status_after.casefold() == "inactive", (
            f"{user_code} should read Inactive after deactivation, got {status_after!r}."
        )
        self.logout()

        # --- Step 4: the deactivated user is blocked --------------------------
        record_property("result_checkpoint", "Step 4 — deactivated user is blocked")
        try:
            self.login(email, self.NEW_USER_PASSWORD)
        except TimeoutException:
            # The app refused the credentials and kept the login form up.
            pass
        assert not self.is_signed_in(), (
            f"Deactivated user {email} ({user_code}) was still able to sign in."
        )
