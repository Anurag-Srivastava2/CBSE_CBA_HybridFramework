import csv

import pytest

from pages.admin.item_bank_page import ItemBankPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2ItemBankOverview:
    """TC-WPAD-ITEMBANK-01..06: Item Bank Overview metric cards, quick-filter
    tabs, advanced filters and export, pagination, bulk selection, and the
    end-to-end item retirement workflow. Driven with the admin account."""

    # Question-text markers that identify items created by earlier automation
    # runs. The retirement check only ever targets one of these, so it cannot
    # destroy seeded content. Ordered most disposable first: the QA manual_*
    # items are orphaned residue that no current suite regenerates.
    RETIRABLE_ITEM_MARKERS = (
        "QA manual_no_images",
        "QA manual_with_images",
        "Rich content PIT run",
        "Teacher MCQ",
    )

    def open_item_bank(self):
        username = ReadConfig.get_role_usernames("admin")[0]
        login = LoginPage(self.driver)
        self.driver.get(ReadConfig.get_base_url())
        login.wait_for_login_form_or_authenticated_page()
        # The shared helper skips the form when the SPA is only part-painted —
        # the hero renders before the sign-in card, which reads as an already
        # authenticated page and silently leaves the session signed out. Wait
        # for the form itself; a fresh driver always has to sign in.
        login.wait_utils.is_visible(LoginPage.USERNAME_TEXTBOX, timeout=30)
        login.login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        assert not login.is_login_form_displayed(), (
            f"Sign-in did not establish a session for {username!r}; "
            "the application is still showing the login form."
        )
        page = ItemBankPage(self.driver)
        page.open(ReadConfig.get_base_url())
        return page

    def test_tc_wpad_itembank_01_core_ui_kpis(self, record_property):
        """Phase 1: the page loads with all five metric cards and a populated grid."""
        item_bank = self.open_item_bank()

        assert item_bank.is_on_page(), "Item Bank Overview header or repository subtext is missing."

        missing_kpis = item_bank.missing_kpis()
        assert not missing_kpis, f"Metric cards missing from the overview: {missing_kpis}"

        kpis = item_bank.get_all_kpi_values()
        invalid = [label for label, value in kpis.items() if value < 0]
        assert not invalid, f"Metric cards did not render a numeric value: {invalid}. Read: {kpis}"

        missing_columns = item_bank.missing_columns()
        headers = item_bank.get_table_headers()
        assert not missing_columns, (
            f"Item Bank columns missing: {missing_columns}. Found: {headers}"
        )

        row_count = item_bank.get_table_row_count()
        record_property(
            "result_description",
            f"Item Bank Overview rendered metric cards {kpis} and {row_count} grid rows "
            f"({item_bank.get_showing_summary()}).",
        )
        assert row_count > 0, "No data loaded in the Item Bank grid."

    def test_tc_wpad_itembank_02_quick_filters(self, record_property):
        """Phase 2: All / IB1 / IB2 / Retired tabs each scope the grid to their badge count."""
        item_bank = self.open_item_bank()

        missing_tabs = item_bank.missing_tabs()
        assert not missing_tabs, f"Quick filter tabs missing: {missing_tabs}"

        badges = {label: item_bank.get_tab_badge_count(label) for label in item_bank.TAB_LABELS}
        unbadged = [label for label, count in badges.items() if count < 0]
        assert not unbadged, f"Tabs carried no badge count: {unbadged}. Read: {badges}"

        # The All badge is the sum of the bank tabs; Retired is tracked separately.
        assert badges["All"] == badges["IB1"] + badges["IB2"], (
            f"All badge ({badges['All']}) does not equal IB1 + IB2 "
            f"({badges['IB1']} + {badges['IB2']} = {badges['IB1'] + badges['IB2']})."
        )

        totals = {}
        for label in item_bank.TAB_LABELS:
            item_bank.switch_tab(label)
            assert item_bank.is_tab_active(label), f"Tab {label!r} did not become active."
            totals[label] = item_bank.get_total_item_count()
            rows = item_bank.get_table_row_count()

            assert totals[label] == badges[label], (
                f"Tab {label!r} badge says {badges[label]} items but the grid reports "
                f"{totals[label]} ({item_bank.get_showing_summary()!r})."
            )
            if badges[label] > 0:
                assert rows > 0, f"Tab {label!r} claims {badges[label]} items but rendered no rows."
            assert rows <= badges[label], (
                f"Tab {label!r} rendered {rows} rows, more than its badge count {badges[label]}."
            )

        record_property(
            "result_description",
            f"Quick filter tabs scoped the grid correctly — badges {badges}, grid totals {totals}.",
        )

        # IB1 and IB2 are disjoint slices of the bank.
        item_bank.switch_tab("IB1")
        ib1_ids = set(item_bank.get_item_ids_in_view())
        item_bank.switch_tab("IB2")
        ib2_ids = set(item_bank.get_item_ids_in_view())
        overlap = ib1_ids & ib2_ids
        assert not overlap, f"Items appear in both the IB1 and IB2 tabs: {sorted(overlap)}"

        item_bank.switch_tab("All")

    def test_tc_wpad_itembank_03_advanced_filters_export(self, record_property):
        """Phase 3: the Filters toggle reveals the metadata filters and Export downloads a CSV."""
        item_bank = self.open_item_bank()

        assert item_bank.is_element_visible_quick(item_bank.FILTERS_BTN), "Filters button is missing."
        assert item_bank.is_element_visible_quick(item_bank.EXPORT_BTN), "Export button is missing."

        item_bank.toggle_filters_panel()
        missing_filters = item_bank.missing_filter_controls()
        assert not missing_filters, (
            f"Filters panel did not expose the metadata filters {missing_filters}. "
            f"Visible: {item_bank.visible_filter_controls()}"
        )
        item_bank.toggle_filters_panel()

        rows_on_screen = item_bank.get_table_row_count()
        row_ids_on_screen = item_bank.get_row_ids_in_view()
        total_in_bank = item_bank.get_total_item_count()

        exported = item_bank.export_file_and_wait()

        assert exported.exists(), f"Export file {exported} does not exist."
        size = exported.stat().st_size
        assert size > 0, f"Export file {exported.name} is empty."
        assert exported.suffix.casefold() == ".csv", f"Expected a CSV export, got {exported.name!r}."

        with exported.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            data_rows = [row for row in reader if any(cell.strip() for cell in row)]

        record_property(
            "result_description",
            f"Filters revealed {list(item_bank.FILTER_LABELS)}; exported {exported.name} "
            f"({size} bytes) with header {header} and {len(data_rows)} data rows, "
            f"against {rows_on_screen} rows on screen and {total_in_bank} items in the bank.",
        )

        missing_export_columns = [
            column for column in item_bank.EXPORT_COLUMNS if column not in header
        ]
        assert not missing_export_columns, (
            f"Export CSV is missing columns {missing_export_columns}. Header: {header}"
        )
        assert data_rows, f"Export CSV {exported.name} has no data rows beyond its header."

        # The CSV's Item ID column carries the internal numeric row id, which is
        # also what each row's expand control is labelled with.
        exported_ids = {row[0].strip() for row in data_rows if row}
        assert set(row_ids_on_screen) <= exported_ids, (
            f"Export CSV omits items that are on screen: "
            f"{sorted(set(row_ids_on_screen) - exported_ids)}"
        )

        banks = {row[1].strip() for row in data_rows if len(row) > 1}
        assert banks <= {"IB1", "IB2"}, f"Export CSV carries unexpected Bank values: {sorted(banks)}"

    def test_tc_wpad_itembank_04_interactions_pagination(self, record_property):
        """Phase 4: pagination controls exist and actually advance the grid."""
        item_bank = self.open_item_bank()

        assert item_bank.is_element_visible_quick(item_bank.ROWS_PER_PAGE), "Rows per page control is missing."
        assert item_bank.is_element_visible_quick(item_bank.NEXT_PAGE_BTN), "Next page button is missing."
        assert item_bank.is_element_visible_quick(item_bank.PREV_PAGE_BTN), "Previous page button is missing."
        assert item_bank.is_element_visible_quick(item_bank.PAGE_INDICATOR), (
            "Page number indicator (e.g. 'Page 1 of X') is missing."
        )

        first_page = item_bank.get_page_indicator()
        first_ids = item_bank.get_item_ids_in_view()
        second_page = item_bank.go_to_next_page()
        second_ids = item_bank.get_item_ids_in_view()

        record_property(
            "result_description",
            f"Pagination moved from {first_page!r} to {second_page!r}; "
            f"page 1 held {len(first_ids)} items, page 2 held {len(second_ids)}.",
        )
        assert second_page != first_page, (
            f"Next page did not advance the indicator (still {first_page!r})."
        )
        assert second_ids, "Page 2 rendered no rows."
        assert not set(first_ids) & set(second_ids), (
            f"Page 2 repeated items from page 1: {sorted(set(first_ids) & set(second_ids))}"
        )

    def test_tc_wpad_itembank_05_bulk_actions(self, record_property):
        """Phase 5: the master checkbox selects and clears every row on the page."""
        item_bank = self.open_item_bank()
        item_bank.switch_tab("All")

        total_rows = item_bank.get_table_row_count()
        assert total_rows > 0, "No rows available to exercise bulk selection."
        assert item_bank.get_checked_rows_count() == 0, "Rows were already selected before the test acted."

        item_bank.toggle_master_checkbox()
        checked = item_bank.get_checked_rows_count()
        summary = item_bank.get_selection_summary()

        record_property(
            "result_description",
            f"Master checkbox selected {checked}/{total_rows} rows; summary read {summary!r}.",
        )
        assert checked == total_rows, (
            f"Expected all {total_rows} row checkboxes to be selected, but {checked} were."
        )
        assert summary, "Selecting all rows produced no selection summary."
        assert str(total_rows) in summary, (
            f"Selection summary {summary!r} does not reflect the {total_rows} selected rows."
        )

        item_bank.toggle_master_checkbox()
        assert item_bank.get_checked_rows_count() == 0, (
            "Toggling the master checkbox off did not clear the row selection."
        )

    @pytest.mark.e2e
    @pytest.mark.serial
    def test_tc_wpad_itembank_06_retire_item(self, record_property):
        """Phase 6: retiring an item moves it out of the active bank into Retired.

        Retirement cannot be undone from the UI, so this never touches a seeded
        item: it retires automation residue left behind by earlier runs,
        identified by the markers in RETIRABLE_ITEM_MARKERS, and skips outright
        when the bank holds no such item.
        """
        item_bank = self.open_item_bank()
        item_bank.switch_tab("All")

        # Markers are tried in order, so the most disposable residue goes first
        # regardless of where it sits in the grid.
        target_item_id = ""
        for marker in self.RETIRABLE_ITEM_MARKERS:
            matches = item_bank.find_items_matching((marker,))
            if matches:
                target_item_id = matches[0]
                break
        if not target_item_id:
            pytest.skip(
                "No automation-residue item on the first page of the Item Bank to retire "
                f"(looked for {list(self.RETIRABLE_ITEM_MARKERS)}). Refusing to retire a "
                "seeded item, because retirement cannot be reversed from the UI."
            )

        retired_before = item_bank.get_tab_badge_count("Retired")
        all_before = item_bank.get_tab_badge_count("All")

        target_row_id = item_bank.get_row_id_for_item(target_item_id)

        item_bank.expand_item_view(target_item_id)
        assert item_bank.is_item_expanded(), f"Expanding {target_item_id} revealed no detail panel."
        assert item_bank.is_retire_button_visible(), (
            f"The expanded view for {target_item_id} exposes no 'Retire Item' control."
        )

        # Retiring is destructive, so the app must guard it: a confirmation that
        # names the item, warns that it is irreversible, and demands a reason.
        item_bank.open_retire_confirmation()
        prompt = item_bank.get_retire_confirmation_prompt()
        assert "cannot be undone" in prompt.casefold(), (
            f"The retire confirmation does not warn that the action is irreversible: {prompt!r}"
        )
        assert target_row_id and f"#{target_row_id}" in prompt, (
            f"The retire confirmation names the wrong item — expected #{target_row_id}, got {prompt!r}"
        )
        assert item_bank.is_retire_reason_required(), (
            "The retire confirmation does not ask for a reason for retirement."
        )

        item_bank.confirm_retire(
            f"Automated retirement verification (TC-WPAD-ITEMBANK-06) for {target_item_id}"
        )
        toast = item_bank.get_toast_message()

        item_bank.open(ReadConfig.get_base_url())
        item_bank.switch_tab("All")
        retired_after = item_bank.get_tab_badge_count("Retired")
        all_after = item_bank.get_tab_badge_count("All")

        record_property(
            "result_description",
            f"Retired {target_item_id}: All {all_before} -> {all_after}, "
            f"Retired {retired_before} -> {retired_after}. Toast: {toast!r}",
        )

        assert not item_bank.is_item_present_in_table(target_item_id), (
            f"Item {target_item_id} is still listed on the 'All' tab after being retired."
        )
        assert retired_after == retired_before + 1, (
            f"Retired badge should have risen from {retired_before} to {retired_before + 1}, "
            f"but reads {retired_after}."
        )
        assert all_after == all_before - 1, (
            f"All badge should have fallen from {all_before} to {all_before - 1}, "
            f"but reads {all_after}."
        )

        item_bank.switch_tab("Retired")
        assert item_bank.is_item_present_in_table(target_item_id), (
            f"Item {target_item_id} did not appear on the 'Retired' tab after retirement."
        )
