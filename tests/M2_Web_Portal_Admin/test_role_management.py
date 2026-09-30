from time import time

import pytest

from pages.admin.role_management_page import RoleManagementPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.rbac_api import delete_roles_with_prefix, system_role_grid_ids
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2RoleManagement:
    """Role Management grid: load, search, Active toggles, pagination.

    Each test opens the section from a fresh login rather than inheriting the
    previous test's filter, so the cases stay independent under pytest-xdist.
    """

    # A role this suite creates for itself. The prefix is what the residue
    # sweep matches on, so it must stay stable while the suffix stays unique.
    FIXTURE_ROLE_PREFIX = "ZZ Automation Toggle"
    FIXTURE_ROLE_REASON = "Throwaway role created by the M2 role-toggle test."

    # A search term no role can match, used to assert the grid empties.
    MISSING_ROLE_TERM = "InvalidRole99"

    def open_role_management(self):
        admin_username = ReadConfig.get_admin_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            admin_username,
            ReadConfig.get_password_for_username(admin_username),
        )
        page = RoleManagementPage(self.driver)
        page.wait_for_application_ready()
        opened = page.open()
        checkpoint(f"Admin {admin_username} opened Role Management")
        return opened

    def survey(self, page, record_property, scope):
        """Soft-check the Role Management page furniture."""
        checks = ElementChecks(page, record_property, page_name=f"Role Management — {scope}")
        checks.check_condition("Page header", page.is_on_page)
        checks.check("Role table rows", page.TABLE_ROWS)
        checks.check_condition("Rows per page control", page.has_rows_per_page_control)
        checks.check_condition("Next page control", page.has_next_page_control)
        return checks

    def test_tc_wpad_role_01_page_loads_with_default_roles(
        self, record_property, page_evidence
    ):
        """Page furniture and the default role list, all recorded softly."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open Role Management as an admin.\n"
            "Record the page furniture and the list of default roles, all as soft "
            "checks.",
        )
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

        page_evidence.checkpoint(
            f"Role Management listed {row_count} role(s) on load; "
            f"{RoleManagementPage.DEFAULT_ROLE_COUNT} defaults expected"
        )
        record_property(
            "result_description",
            f"{checks.publish()}. Listed {row_count} roles on load.",
        )

    def test_tc_wpad_role_02_search_filters_by_name_and_id(
        self, record_property, page_evidence
    ):
        """Search behaviour stays a hard gate; the controls are surveyed softly."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Search the Role Management grid by role name, then by role ID.\n"
            "The controls are surveyed softly, but the search actually narrowing the "
            "grid stays a hard gate.",
        )
        page = self.open_role_management()
        checks = self.survey(page, record_property, "Search")

        # Widen the page first: the grid pages at 10, so on an environment
        # carrying more than 10 roles an unfiltered "10" and a filtered "10"
        # are indistinguishable, and the filter looks broken when it worked.
        page.set_rows_per_page(100)
        baseline_roles = page.get_visible_roles()
        baseline = len(baseline_roles)
        assert baseline_roles, "Role Management listed no roles to search."

        checks.check_interaction(
            "Search narrows the grid",
            lambda: page.search_role(self.MISSING_ROLE_TERM),
            lambda: page.get_table_row_count() < baseline,
        )
        checks.check_interaction(
            "Clearing search restores the grid",
            page.clear_search,
            lambda: page.get_table_row_count() == baseline,
        )
        checks.publish()

        # Search for a role this environment actually has, rather than a
        # hardcoded "Role-1". Role ids are per-environment: QA seeds Role-1..
        # Role-8, UAT's Role-7/Role-8 are deleted throwaways and its seeded
        # roles run 1-6 plus 12-13. A fixed id asserts against another
        # environment's data, and "no such role" then fails a working search.
        target_id, target_name = baseline_roles[0]

        by_name = page.search_roles_and_settle(target_name)
        page_evidence.checkpoint(
            f"Search by name {target_name!r} returned {len(by_name)} of {baseline} "
            f"row(s): {[role_id for role_id, _ in by_name]}"
        )
        assert by_name, f"Search by role name {target_name!r} returned nothing."
        assert all(
            target_name.casefold() in name.casefold() for _, name in by_name
        ), (
            f"Search by role name {target_name!r} returned non-matching rows: "
            f"{[name for _, name in by_name]}."
        )

        by_id = page.search_roles_and_settle(target_id)
        page_evidence.checkpoint(
            f"Search by id {target_id!r} returned {len(by_id)} of {baseline} "
            f"row(s): {[role_id for role_id, _ in by_id]}"
        )
        assert by_id, f"Search by role ID {target_id!r} returned nothing."
        # Ids nest - "Role-1" legitimately matches Role-1 and Role-10..Role-19 -
        # so the contract is that every row matches the term, not that exactly
        # one comes back.
        assert all(target_id.casefold() in role_id.casefold() for role_id, _ in by_id), (
            f"Search by role ID {target_id!r} returned non-matching rows: "
            f"{[role_id for role_id, _ in by_id]}."
        )
        assert len(by_id) <= baseline, "Search by role ID widened the grid."

        missing = page.search_roles_and_settle(self.MISSING_ROLE_TERM)
        page_evidence.checkpoint(
            f"Search for a role that does not exist left {len(missing)} row(s) — must be 0"
        )
        assert not missing, (
            "Grid should be empty when searching for a role that does not exist, "
            f"but {len(missing)} row(s) remained: {[role_id for role_id, _ in missing]}."
        )

        page.clear_search()
        restored_count = page.get_table_row_count()
        page_evidence.checkpoint(
            f"Clearing the search restored the grid to {restored_count} row(s) "
            f"(started at {baseline})"
        )
        assert restored_count == baseline, (
            "Clearing the search did not restore the full role list."
        )

    def test_tc_wpad_role_03_all_default_roles_can_be_active(
        self, request, record_property, page_evidence
    ):
        """Every seeded role is live, and the product protects it from being
        switched off.

        This deliberately does not drive the Active toggle. The seeded roles
        are all system roles, and the grid renders a system role's toggle as
        `disabled: isSystemRole || isPending`, so there is nothing here to
        switch on - a version of this test that called ensure_all_roles_active()
        passed without ever clicking anything and proved nothing. What this run
        can honestly assert is that every default role reads Active and that
        the product is guarding it; the toggle round-trip itself is exercised
        in role_04, against a role that suite creates for the purpose.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Check every seeded role is live, and that the product protects it from "
            "being switched off.\n"
            "The seeded roles are read from the RBAC API rather than assumed to be "
            "Role-1 to Role-8, because which ids hold them differs per environment.\n"
            "This deliberately never drives the Active toggle: they are all system "
            "roles and the grid renders their toggles disabled, so clicking would "
            "prove nothing.",
        )
        page = self.open_role_management()
        self.survey(page, record_property, "Activation").publish()

        # Ask the environment which roles are seeded rather than assuming
        # Role-1..Role-8. The seeded ids are not the same everywhere: on QA
        # they are 1-8, but on UAT ids 7 and 8 hold soft-deleted throwaways
        # ("Testing123", "hk-test") which the grid still renders, and the two
        # Helpdesk roles sit at 12-13. Reading a fixed range there reports
        # deleted junk as a seeded role that has been switched off.
        role_ids = system_role_grid_ids(self.driver)
        assert role_ids, (
            "The RBAC API returned no system roles, so there is nothing to "
            "assert about seeded roles."
        )
        page.set_rows_per_page(100)
        inactive = [role_id for role_id in role_ids if not page.is_role_active(role_id)]
        unprotected = [role_id for role_id in role_ids if not page.is_role_system(role_id)]

        page_evidence.checkpoint(
            f"{len(role_ids) - len(inactive)}/{len(role_ids)} seeded roles read "
            f"Active; inactive: {inactive or 'none'}; not protected from "
            f"deactivation: {unprotected or 'none'}"
        )
        request.node.user_properties.append(
            (
                "result_description",
                f"Seeded roles reading Active: {len(role_ids) - len(inactive)}/"
                f"{len(role_ids)}; system-protected: "
                f"{len(role_ids) - len(unprotected)}/{len(role_ids)}",
            )
        )
        assert not inactive, f"Default roles are not Active: {inactive}."
        assert not unprotected, (
            f"Seeded roles {unprotected} are no longer protected as system roles - "
            "their Active toggle is editable, so they could be switched off."
        )

    def test_tc_wpad_role_04_toggle_role_off_and_restore(
        self, record_property, page_evidence
    ):
        """Toggle round-trip is a state contract, so it stays a hard gate.

        It runs against a role this test creates, not a seeded one. Every
        seeded role is a system role and the grid renders those toggles
        `disabled`, so the earlier version of this test - which aimed at
        Role-7 - could only ever skip. A custom role is the only route the UI
        offers to an editable Active toggle.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Create a custom role, switch its Active toggle off, then switch it back "
            "on.\n"
            "Check both states actually stick, since the round-trip is a state "
            "contract and stays a hard gate.\n"
            "It runs against a role this test creates because every seeded role is a "
            "system role whose toggle the grid renders disabled, leaving a custom "
            "role as the only editable one.",
        )
        page = self.open_role_management()
        checks = self.survey(page, record_property, "Toggle")
        # Record which seeded toggles the product is protecting, before
        # bringing in a role that is meant to be editable.
        for index in range(1, RoleManagementPage.DEFAULT_ROLE_COUNT + 1):
            checks.check_condition(
                f"Seeded role is system-protected — Role-{index}",
                lambda i=index: page.is_role_system(f"Role-{i}"),
            )
        checks.publish()

        # Clear residue from a run whose cleanup could not complete, so a
        # failed teardown never accumulates roles in the shared environment.
        swept = delete_roles_with_prefix(
            self.driver, self.FIXTURE_ROLE_PREFIX, self.FIXTURE_ROLE_REASON
        )
        if swept:
            page_evidence.checkpoint(f"Swept leftover throwaway role(s): {swept}")

        suffix = str(int(time()))[-5:]
        role_name = f"{self.FIXTURE_ROLE_PREFIX} {suffix}"
        role_id = page.create_custom_role(
            role_name,
            f"ZZT{suffix}",
            "Temporary role for the M2 Active-toggle contract. Safe to delete.",
        )
        page_evidence.checkpoint(f"Created throwaway role {role_name!r} as {role_id}")
        record_property("result_description", f"Toggle exercised on {role_id} ({role_name})")

        try:
            assert page.is_role_toggle_editable(role_id), (
                f"{role_id} was created as a custom role, so its Active toggle "
                "should be editable."
            )

            page.toggle_role_status(role_id)
            toast = page.get_toast_message()
            page_evidence.checkpoint(
                f"{role_id} toggled off — active now: "
                f"{page.is_role_active(role_id)}; toast: {toast!r}"
            )
            assert not page.is_role_active(role_id), (
                f"{role_id} should be inactive after toggling it off."
            )
            # The grid raises a toast only onError - there is no success toast
            # to wait for, so silence is the pass signal here.
            assert "failed" not in toast.casefold(), (
                f"Toggling {role_id} off raised an error toast: {toast!r}"
            )

            page.toggle_role_status(role_id)
            page_evidence.checkpoint(
                f"{role_id} toggled back on — active now: {page.is_role_active(role_id)}"
            )
            assert page.is_role_active(role_id), f"{role_id} was not restored to active."
        finally:
            # Role Management can create a role but not delete one, so the
            # throwaway goes back through the API.
            removed = delete_roles_with_prefix(
                self.driver, self.FIXTURE_ROLE_PREFIX, self.FIXTURE_ROLE_REASON
            )
            page_evidence.checkpoint(f"Removed throwaway role(s): {removed or 'none'}")

    def test_tc_wpad_role_05_pagination_controls_are_present(
        self, record_property, page_evidence
    ):
        """Pure presence test — every check is soft."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open Role Management and record that the pagination controls are "
            "present.\n"
            "A pure presence check: every assertion here is soft.",
        )
        page = self.open_role_management()
        checks = self.survey(page, record_property, "Pagination")
        page_evidence.checkpoint(
            f"Pagination furniture — rows-per-page control: "
            f"{page.has_rows_per_page_control()}, next-page control: "
            f"{page.has_next_page_control()}"
        )
        record_property("result_description", checks.publish())
