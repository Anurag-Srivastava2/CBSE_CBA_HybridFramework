import pytest

from pages.admin.role_management_page import RoleManagementPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2RoleManagement:
    """Role Management grid: load, search, Active toggles, pagination.

    Each test opens the section from a fresh login rather than inheriting the
    previous test's filter, so the cases stay independent under pytest-xdist.
    """

    def open_role_management(self):
        admin_username = ReadConfig.get_role_usernames("admin")[0]
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            admin_username,
            ReadConfig.get_password_for_username(admin_username),
        )
        page = RoleManagementPage(self.driver)
        page.wait_for_application_ready()
        return page.open()

    def test_tc_wpad_role_01_page_loads_with_default_roles(self, request):
        page = self.open_role_management()
        assert page.is_on_page(), "Role Management page header is not visible."

        row_count = page.get_table_row_count()
        request.node.user_properties.append(
            ("result_description", f"Role Management listed {row_count} roles on load.")
        )
        assert row_count >= RoleManagementPage.DEFAULT_ROLE_COUNT, (
            f"Expected at least {RoleManagementPage.DEFAULT_ROLE_COUNT} roles on load, "
            f"found {row_count}."
        )

    def test_tc_wpad_role_02_search_filters_by_name_and_id(self):
        page = self.open_role_management()
        unfiltered_count = page.get_table_row_count()

        page.search_role("Role-1")
        by_id_count = page.get_table_row_count()
        assert 0 < by_id_count < unfiltered_count or by_id_count == 1, (
            f"Search by role ID did not filter the grid: {by_id_count} rows of "
            f"{unfiltered_count}."
        )

        page.search_role("InvalidRole99")
        assert page.get_table_row_count() == 0, (
            "Grid should be empty when searching for a role that does not exist."
        )

        page.clear_search()
        assert page.get_table_row_count() == unfiltered_count, (
            "Clearing the search did not restore the full role list."
        )

    def test_tc_wpad_role_03_all_default_roles_can_be_active(self, request):
        page = self.open_role_management()
        activated = page.ensure_all_roles_active()
        request.node.user_properties.append(
            (
                "result_description",
                "All default roles active"
                + (f" (had to switch on: {', '.join(activated)})" if activated else " on arrival"),
            )
        )
        inactive = [
            f"Role-{index}"
            for index in range(1, RoleManagementPage.DEFAULT_ROLE_COUNT + 1)
            if not page.is_role_active(f"Role-{index}")
        ]
        assert not inactive, f"Roles still inactive after activation: {inactive}."

    def test_tc_wpad_role_04_toggle_role_off_and_restore(self):
        page = self.open_role_management()
        role_id = "Role-7"
        if not page.is_role_toggle_editable(role_id):
            pytest.skip(
                f"ROLE_TOGGLE_READ_ONLY: the Active control for {role_id} is rendered "
                "disabled for this admin, so the toggle contract cannot be exercised. "
                "Faking the state change would not prove the behaviour."
            )
        page.ensure_all_roles_active()

        page.toggle_role_status(role_id)
        try:
            assert not page.is_role_active(role_id), (
                f"{role_id} should be inactive after toggling it off."
            )
            toast = page.get_toast_message()
            assert "success" in toast.casefold(), (
                f"Expected a success toast after toggling {role_id}, got {toast!r}."
            )
        finally:
            # Always hand the environment back with the role switched on, even
            # if an assertion above fails.
            if not page.is_role_active(role_id):
                page.toggle_role_status(role_id)

        assert page.is_role_active(role_id), f"{role_id} was not restored to active."

    def test_tc_wpad_role_05_pagination_controls_are_present(self):
        page = self.open_role_management()
        assert page.has_rows_per_page_control(), "'Rows per page' control is missing."
        assert page.has_next_page_control(), "Next-page pagination control is missing."
