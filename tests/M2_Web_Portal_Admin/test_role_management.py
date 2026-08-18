import pytest

from pages.admin.role_management_page import RoleManagementPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2RoleManagement:
    """Role Management grid: load, search, Active toggles, pagination.

    Each test opens the section from a fresh login rather than inheriting the
    previous test's filter, so the cases stay independent under pytest-xdist.
    """

    def open_role_management(self):
        admin_username = ReadConfig.get_admin_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            admin_username,
            ReadConfig.get_password_for_username(admin_username),
        )
        page = RoleManagementPage(self.driver)
        page.wait_for_application_ready()
        return page.open()

    def survey(self, page, record_property, scope):
        """Soft-check the Role Management page furniture."""
        checks = ElementChecks(page, record_property, page_name=f"Role Management — {scope}")
        checks.check_condition("Page header", page.is_on_page)
        checks.check("Role table rows", page.TABLE_ROWS)
        checks.check_condition("Rows per page control", page.has_rows_per_page_control)
        checks.check_condition("Next page control", page.has_next_page_control)
        return checks

    def test_tc_wpad_role_01_page_loads_with_default_roles(self, record_property):
        """Page furniture and the default role list, all recorded softly."""
        page = self.open_role_management()
        checks = self.survey(page, record_property, "Load")

        row_count = checks.safe_call(page.get_table_row_count, 0)
        checks.check_condition(
            f"At least {RoleManagementPage.DEFAULT_ROLE_COUNT} default roles listed",
            row_count >= RoleManagementPage.DEFAULT_ROLE_COUNT,
            detail=f"{row_count} rows",
        )
        for index in range(1, RoleManagementPage.DEFAULT_ROLE_COUNT + 1):
            role_id = f"Role-{index}"
            checks.check(f"Role row — {role_id}", page.role_row_locator(role_id), timeout=2)

        record_property(
            "result_description",
            f"{checks.publish()}. Listed {row_count} roles on load.",
        )

    def test_tc_wpad_role_02_search_filters_by_name_and_id(self, record_property):
        """Search behaviour stays a hard gate; the controls are surveyed softly."""
        page = self.open_role_management()
        checks = self.survey(page, record_property, "Search")

        baseline = checks.safe_call(page.get_table_row_count, 0)
        checks.check_interaction(
            "Search narrows the grid",
            lambda: page.search_role("InvalidRole99"),
            lambda: page.get_table_row_count() < baseline,
        )
        checks.check_interaction(
            "Clearing search restores the grid",
            page.clear_search,
            lambda: page.get_table_row_count() == baseline,
        )
        checks.publish()

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

    def test_tc_wpad_role_03_all_default_roles_can_be_active(self, request, record_property):
        """Activation is a state contract, so it stays a hard gate."""
        page = self.open_role_management()
        self.survey(page, record_property, "Activation").publish()
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

    def test_tc_wpad_role_04_toggle_role_off_and_restore(self, record_property):
        """Toggle round-trip is a state contract, so it stays a hard gate."""
        page = self.open_role_management()
        checks = self.survey(page, record_property, "Toggle")
        # Record which role toggles are even editable before driving one.
        for index in range(1, RoleManagementPage.DEFAULT_ROLE_COUNT + 1):
            checks.check_condition(
                f"Toggle editable — Role-{index}",
                lambda i=index: page.is_role_toggle_editable(f"Role-{i}"),
            )
        checks.publish()
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

    def test_tc_wpad_role_05_pagination_controls_are_present(self, record_property):
        """Pure presence test — every check is soft."""
        page = self.open_role_management()
        checks = self.survey(page, record_property, "Pagination")
        record_property("result_description", checks.publish())
