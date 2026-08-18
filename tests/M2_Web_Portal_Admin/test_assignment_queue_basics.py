import pytest

from pages.admin.assignment_queue_page import AssignmentQueuePage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2AssignmentQueueBasics:
    """TC-WPAD-ITEM-02..06: Assignment Queue page load, search, filters,
    reassignment and pagination. Driven with the admin account."""

    def open_queue(self):
        username = ReadConfig.get_admin_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        page = AssignmentQueuePage(self.driver)
        page.open(ReadConfig.get_base_url())
        return page

    EXPECTED_COLUMNS = (
        "Set Code", "Stage", "Grade", "Subject", "Assigned To", "Status", "Due On", "Actions",
    )

    def survey(self, queue, record_property, scope):
        """Soft-check the Assignment Queue furniture and its filter controls."""
        checks = ElementChecks(queue, record_property, page_name=f"Assignment Queue — {scope}")
        checks.check_condition("Page header and subtext", queue.is_on_page)
        checks.check("Search input", queue.SEARCH_INPUT)
        checks.check("Queue table", queue.TABLE)
        checks.check("Rows per page control", queue.ROWS_PER_PAGE)
        checks.check("Next page control", queue.NEXT_PAGE_BTN)
        checks.check("Previous page control", queue.PREV_PAGE_BTN)
        checks.check("Page indicator", queue.PAGE_INDICATOR)

        headers = checks.safe_call(queue.get_column_headers)
        for column in self.EXPECTED_COLUMNS:
            checks.check_condition(
                f"Column — {column}", column in headers, detail=f"found: {headers}"
            )
        for label in queue.FILTER_LABELS:
            checks.check_condition(
                f"Filter — {label}", lambda name=label: queue.is_filter_visible(name)
            )
        return checks

    def test_tc_wpad_item_02_verify_page_load_and_ui(self, record_property):
        """Page furniture, columns and filters, all recorded softly."""
        queue = self.open_queue()
        checks = self.survey(queue, record_property, "Page Load")

        row_count = checks.safe_call(queue.get_row_count, 0)
        checks.check_condition(
            "Queue loaded rows", row_count > 0, detail=f"{row_count} rows"
        )
        record_property(
            "result_description",
            f"{checks.publish()}. Loaded {row_count} rows.",
        )

    def test_tc_wpad_item_03_search_functionality(self, record_property):
        """Search behaviour stays hard; the control's responsiveness is recorded."""
        queue = self.open_queue()
        checks = self.survey(queue, record_property, "Search")
        baseline = checks.safe_call(queue.get_row_count, 0)
        checks.check_interaction(
            "Search narrows the queue",
            lambda: queue.search("ZZZ-NO-SUCH-SET-9999"),
            lambda: queue.get_row_count() < baseline,
        )
        checks.check_interaction(
            "Clearing search restores the queue",
            lambda: queue.search(""),
            lambda: queue.get_row_count() == baseline,
        )
        checks.publish()

        # A set code that exists in the queue.
        seed_code = queue.get_set_codes_in_view()[0]
        queue.search(seed_code)
        code_matches = queue.get_set_codes_in_view()
        assert code_matches, f"Search by set code {seed_code!r} returned no results."
        assert all(seed_code in code for code in code_matches), (
            f"Search for {seed_code!r} returned unrelated set codes: {sorted(set(code_matches))}"
        )

        # A reviewer name taken from the unfiltered grid.
        queue.search("")
        reviewer = next((name for name in queue.get_assigned_users_in_view() if name), None)
        assert reviewer, "No assignee names available to exercise reviewer search."
        queue.search(reviewer)
        assert queue.get_row_count() >= 1, f"Search by reviewer {reviewer!r} returned no results."

        # Negative: gibberish yields the empty state.
        queue.search("INVALID-CODE-999")
        empty_count = queue.get_row_count()
        record_property(
            "result_description",
            f"Search verified — set code {seed_code!r}, reviewer {reviewer!r}, "
            f"invalid term returned {empty_count} rows.",
        )
        assert empty_count == 0, (
            f"Table should be empty for an invalid search but showed {empty_count} rows."
        )

        queue.search("")

    def test_tc_wpad_item_04_dropdown_filters(self, record_property):
        """Each dropdown is driven and recorded; the filtering contract stays hard."""
        queue = self.open_queue()
        checks = self.survey(queue, record_property, "Filters")

        # Does every dropdown open and offer options? A filter that renders but
        # never populates passes presence checks while being unusable.
        for label in queue.FILTER_LABELS:
            checks.check_interaction(
                f"Filter opens with options — {label}",
                lambda: None,
                lambda name=label: queue.get_filter_options(name),
                detail="dropdown offered no options",
            )
        queue.open(ReadConfig.get_base_url())
        checks.publish()

        queue.filter_by_stage("RWG")
        stages = queue.get_stages_in_view()
        assert stages, "Stage filter 'RWG' produced an empty table."
        assert set(stages) == {"RWG"}, f"Stage filter leaked other stages: {sorted(set(stages))}"

        # Stack a second filter on top of the first.
        queue.filter_by_status("Completed")
        statuses = queue.get_statuses_in_view()
        stages_after = queue.get_stages_in_view()
        record_property(
            "result_description",
            f"Stage=RWG + Status=Completed returned {len(statuses)} rows.",
        )
        assert statuses, "Combined Stage + Status filter produced an empty table."
        assert set(statuses) == {"Completed"}, f"Status filter leaked: {sorted(set(statuses))}"
        assert set(stages_after) == {"RWG"}, (
            f"Stacking Status dropped the Stage filter: {sorted(set(stages_after))}"
        )

    def test_tc_wpad_item_05_reassign_action(self, record_property):
        """Reassignment mutates real queue state, so it stays a hard gate."""
        queue = self.open_queue()
        self.survey(queue, record_property, "Reassign").publish()

        # Completed work exposes no action; only pending rows can be reassigned.
        queue.filter_by_status("Completed")
        completed_rows = queue.get_rows()
        assert completed_rows, "No Completed rows available to check action visibility."
        assert not any(queue.row_has_action(row) for row in completed_rows), (
            "Completed assignments must not offer a Reassign action."
        )

        # Reload rather than stacking a second Status selection on the first.
        queue.open(ReadConfig.get_base_url())
        queue.filter_by_status("Overdue")
        row, values = queue.find_actionable_row()
        if row is None:
            pytest.skip("No pending/overdue assignment is available to reassign in this environment.")

        current_assignee = values["assigned_to"]
        queue.open_reassign_panel(row)
        options = queue.get_reviewer_options()
        candidates = [
            name
            for name in options
            if name and queue.reviewer_display_name(name) != current_assignee
        ]
        assert candidates, (
            f"No alternative reviewer offered for {values['set_code']} "
            f"(currently {current_assignee!r}); options were {options}."
        )
        new_reviewer = candidates[0]
        expected_assignee = queue.reviewer_display_name(new_reviewer)

        queue.select_reviewer(new_reviewer)
        queue.confirm_reassign()
        toast = queue.get_toast_message()

        queue.search(values["set_code"])
        assignees = queue.get_assigned_users_in_view()
        record_property(
            "result_description",
            f"Reassigned {values['set_code']} ({values['stage']}) from {current_assignee!r} "
            f"to {expected_assignee!r}. Toast: {toast or 'none'}",
        )
        assert any(expected_assignee in assignee for assignee in assignees), (
            f"{values['set_code']} was not reassigned to {expected_assignee!r}; "
            f"Assigned To column now reads {assignees}."
        )

    def test_tc_wpad_item_06_pagination(self, record_property):
        """Controls surveyed softly; advancing the queue stays hard."""
        queue = self.open_queue()
        self.survey(queue, record_property, "Pagination").publish()

        first_page = queue.get_page_indicator()
        first_codes = queue.get_set_codes_in_view()
        second_page = queue.go_to_next_page()
        second_codes = queue.get_set_codes_in_view()

        record_property(
            "result_description",
            f"Pagination moved from {first_page!r} to {second_page!r}.",
        )
        assert second_page != first_page, (
            f"Next page did not advance the page indicator (still {first_page!r})."
        )
        assert second_codes != first_codes, "Next page rendered the same rows as page 1."
