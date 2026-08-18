import csv

import pytest

from pages.admin.audit_trail_page import AuditTrailPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2AuditTrail:
    """TC-WPAD-AUDIT-01..04: Audit Trail structure, immutability, search and
    filtering, CSV export, and pagination. Driven with the admin account."""

    def open_audit(self):
        # Per-worker admin: the portal allows one session per account, so
        # sharing an admin with a concurrent suite fails at login.
        username = ReadConfig.get_admin_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        page = AuditTrailPage(self.driver)
        page.open(ReadConfig.get_base_url())
        return page

    def survey(self, audit, record_property, scope):
        """Soft-check every control the Audit Trail page renders."""
        checks = ElementChecks(audit, record_property, page_name=f"Audit Trail — {scope}")
        checks.check("Page header", audit.PAGE_HEADER)
        checks.check("Compliance subtext", audit.SUBTEXT)
        checks.check("Search input", audit.SEARCH_INPUT)
        checks.check("Event Type filter", audit.EVENT_TYPE_FILTER)
        checks.check("Export File button", audit.EXPORT_BTN)
        checks.check("Log table", audit.TABLE)
        checks.check("Rows per page control", audit.ROWS_PER_PAGE)
        checks.check("Next page control", audit.NEXT_PAGE_BTN)
        checks.check("Page indicator", audit.PAGE_INDICATOR)
        return checks

    def test_tc_wpad_audit_01_verify_page_ui_and_immutability(self, record_property):
        """Page structure is surveyed softly; immutability stays a hard gate."""
        audit = self.open_audit()
        checks = self.survey(audit, record_property, "Structure")

        checks.check_condition(
            "Page header and subtext identify the Audit Trail",
            audit.is_on_page,
        )

        headers = checks.safe_call(audit.get_table_headers)
        for column in audit.EXPECTED_COLUMNS:
            checks.check_condition(
                f"Column — {column}",
                column in headers,
                detail=f"found: {headers}",
            )

        row_count = checks.safe_call(audit.get_table_row_count, 0)
        checks.check_condition(
            "Log entries rendered", row_count > 0, detail=f"{row_count} entries"
        )

        # Hard gate: immutability is a compliance contract, not a rendering
        # detail. A soft row here would let tamperable audit logs ship green.
        mutating_controls = audit.get_mutating_controls()
        record_property(
            "result_description",
            f"{checks.publish()}. {row_count} entries; "
            f"{len(mutating_controls)} mutating controls in the grid.",
        )
        assert not mutating_controls, (
            "SECURITY FAILURE: the Audit Trail grid exposes controls that could alter "
            f"a log record: {mutating_controls}. Logs must be immutable."
        )
        assert not audit.are_table_cells_editable(), (
            "SECURITY FAILURE: Audit Trail cells are contenteditable; logs must be immutable."
        )

    def test_tc_wpad_audit_02_search_and_filter(self, record_property):
        """Free-text search and the Event Type filter both narrow the grid.

        Controls are surveyed softly; the filtering behaviour stays hard.
        """
        audit = self.open_audit()
        checks = self.survey(audit, record_property, "Search & Filter")

        # Does each control respond at all? Recorded softly so a dead control is
        # named in the report even when the hard assertions below also catch it.
        baseline_rows = checks.safe_call(audit.get_table_row_count, 0)
        checks.check_interaction(
            "Search narrows the grid",
            lambda: audit.search_audit_log("INVALID-USER-9999"),
            lambda: audit.get_table_row_count() < baseline_rows,
        )
        checks.check_interaction(
            "Clearing search restores the grid",
            lambda: audit.search_audit_log(""),
            lambda: audit.get_table_row_count() == baseline_rows,
        )
        checks.check_interaction(
            "Event Type filter responds",
            lambda: audit.filter_by_event_type("LOGIN_SUCCESS"),
            lambda: bool(audit.get_actions_in_view()),
        )
        checks.publish()
        audit.open(ReadConfig.get_base_url())

        # Positive: search for a user that the grid is already showing.
        seed_user = next((name for name in audit.get_users_in_view() if name and name != "System"), None)
        assert seed_user, "No non-System user available in the audit grid to search for."
        audit.search_audit_log(seed_user)
        matched = audit.get_row_text()
        assert matched, f"Search for user {seed_user!r} returned no results."
        assert all(seed_user in text for text in matched), (
            f"Search for {seed_user!r} returned unrelated rows."
        )

        # Negative: gibberish yields the empty state.
        audit.search_audit_log("INVALID-USER-9999")
        empty_count = audit.get_table_row_count()
        assert empty_count == 0, (
            f"Audit table should be empty for a non-existent search but showed {empty_count} rows."
        )
        audit.search_audit_log("")

        # Event Type filter. Options are enum codes; the Action column is
        # humanised, so compare against the humanised form.
        options = audit.get_event_type_options()
        assert "LOGIN_SUCCESS" in options, f"Expected LOGIN_SUCCESS among event types, got {options[:10]}"
        audit.filter_by_event_type("LOGIN_SUCCESS")
        actions = audit.get_actions_in_view()
        expected_action = audit.humanise_event_type("LOGIN_SUCCESS")
        record_property(
            "result_description",
            f"Search matched {len(matched)} rows for {seed_user!r}; "
            f"LOGIN_SUCCESS filter returned {len(actions)} rows.",
        )
        assert actions, "Filtering by LOGIN_SUCCESS returned no rows."
        assert set(actions) == {expected_action}, (
            f"LOGIN_SUCCESS filter leaked other actions: {sorted(set(actions))}"
        )

    def test_tc_wpad_audit_03_export_file(self, record_property):
        """Export File downloads a CSV whose header matches the audit columns.

        The export contents stay a hard gate — a missing column in the CSV is a
        compliance defect, not a rendering gap.
        """
        audit = self.open_audit()
        checks = self.survey(audit, record_property, "Export")
        checks.publish()

        exported = audit.export_file_and_wait()

        assert exported.exists(), f"Export file {exported} does not exist."
        size = exported.stat().st_size
        assert size > 0, f"Export file {exported.name} is empty."
        assert exported.suffix.casefold() == ".csv", (
            f"Expected a CSV export, got {exported.name!r}."
        )

        with exported.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            data_rows = sum(1 for _ in reader)

        record_property(
            "result_description",
            f"Exported {exported.name} ({size} bytes, {data_rows} rows) with header {header}.",
        )
        missing = [column for column in audit.EXPECTED_COLUMNS if column not in header]
        assert not missing, f"Export CSV is missing audit columns {missing}. Header: {header}"
        assert data_rows > 0, "Export CSV contains a header but no audit records."

    def test_tc_wpad_audit_04_pagination(self, record_property):
        """Pagination controls are surveyed softly; advancing the grid is hard."""
        audit = self.open_audit()
        checks = self.survey(audit, record_property, "Pagination")
        checks.publish()

        first_page = audit.get_page_indicator()
        first_rows = audit.get_row_text()
        second_page = audit.go_to_next_page()
        second_rows = audit.get_row_text()

        record_property(
            "result_description",
            f"Audit pagination moved from {first_page!r} to {second_page!r}.",
        )
        assert second_page != first_page, (
            f"Next page did not advance the indicator (still {first_page!r})."
        )
        assert second_rows != first_rows, "Next page rendered the same audit rows as page 1."
