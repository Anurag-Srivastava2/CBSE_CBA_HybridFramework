import pytest

from pages.admin.helpdesk_page import HelpdeskPage
from utilities.element_checks import ElementChecks
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2HelpdeskManagement:
    """TC-WPAD-HELPDESK-01..04: Helpdesk queue UI and KPI cards, quick-tab
    filtering, search by ticket ID / subject / category, and the metadata
    contract every newly ingested ticket must satisfy. Driven with the admin
    account.

    Ticket creation itself is covered end to end by
    tests/M2_Web_Portal_Admin/test_support_ticketing.py. Phases 1-4 are
    read-only; phase 5 reassigns one ticket.
    """

    # Reassignment always moves work off this first-line queue, so a run can
    # never disturb a ticket an L2 agent is already working.
    SOURCE_ASSIGNEE = "help Desk 1"

    def open_helpdesk(self):
        username = ReadConfig.get_admin_username()
        login = LoginPage(self.driver)
        self.driver.get(ReadConfig.get_base_url())
        login.wait_for_login_form_or_authenticated_page()
        # The shared helper treats a part-painted login screen as an
        # authenticated page and silently skips sign-in; wait for the form.
        login.wait_utils.is_visible(LoginPage.USERNAME_TEXTBOX, timeout=30)
        login.login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        assert not login.is_login_form_displayed(), (
            f"Sign-in did not establish a session for {username!r}; "
            "the application is still showing the login form."
        )
        page = HelpdeskPage(self.driver)
        page.open(ReadConfig.get_base_url())
        return page

    def survey(self, helpdesk, record_property, scope):
        """Soft-check the Helpdesk furniture, KPI cards, columns and filters."""
        checks = ElementChecks(helpdesk, record_property, page_name=f"Helpdesk — {scope}")
        checks.check_condition("Page header and subtext", helpdesk.is_on_page)
        checks.check("Search input", helpdesk.SEARCH_INPUT)
        checks.check("Create Ticket button", helpdesk.CREATE_TICKET_BTN)
        checks.check("Ticket table", helpdesk.TABLE)

        missing_kpis = checks.safe_call(helpdesk.missing_kpis)
        for label in helpdesk.KPI_LABELS:
            checks.check_condition(f"KPI card — {label}", label not in missing_kpis)
        missing_columns = checks.safe_call(helpdesk.missing_columns)
        for column in helpdesk.EXPECTED_COLUMNS:
            checks.check_condition(f"Column — {column}", column not in missing_columns)
        missing_filters = checks.safe_call(helpdesk.missing_filters)
        for label in helpdesk.FILTER_LABELS:
            checks.check_condition(f"Filter — {label}", label not in missing_filters)
        return checks

    def test_tc_wpad_helpdesk_01_verify_page_load_and_kpis(self, record_property):
        """Phase 1: furniture, KPI cards and ticket data, all recorded softly."""
        helpdesk = self.open_helpdesk()
        checks = self.survey(helpdesk, record_property, "Page Load")

        kpis = checks.safe_call(helpdesk.get_all_kpi_text, {}) or {}
        for label in helpdesk.COUNT_KPI_LABELS:
            checks.check_condition(
                f"KPI value — {label} is a whole number",
                lambda name=label: helpdesk.get_kpi_value(name) >= 0,
                detail=f"read {kpis.get(label)!r}",
            )
        # Avg Resolution Time is a duration rather than a count, so it is only
        # required to carry a value.
        checks.check_condition(
            "KPI value — Avg Resolution Time carries a value",
            kpis.get("Avg Resolution Time"),
            detail=f"read {kpis.get('Avg Resolution Time')!r}",
        )

        row_count = checks.safe_call(helpdesk.get_row_count, 0)
        checks.check_condition(
            "Queue loaded tickets", row_count > 0, detail=f"{row_count} tickets"
        )
        record_property(
            "result_description",
            f"{checks.publish()}. KPIs {kpis}, {row_count} tickets.",
        )

    def test_tc_wpad_helpdesk_02_verify_tab_filters(self, record_property):
        """Phase 2: each quick tab scopes the queue to exactly its badge count,
        and status tabs return only tickets carrying that status."""
        helpdesk = self.open_helpdesk()
        checks = self.survey(helpdesk, record_property, "Tab Filters")
        for label in helpdesk.QUEUE_TABS:
            checks.check_interaction(
                f"Tab responds — {label}",
                lambda tab=label: helpdesk.switch_tab(tab),
                lambda tab=label: helpdesk.get_tab_count(tab) >= 0,
            )
        helpdesk.switch_tab("All")
        checks.publish()

        observed = {}
        for label in helpdesk.QUEUE_TABS:
            helpdesk.switch_tab(label)
            count = helpdesk.get_tab_count(label)
            rows = helpdesk.get_row_count()
            statuses = sorted(set(helpdesk.get_statuses_in_view()))
            observed[label] = {"count": count, "rows": rows, "statuses": statuses}

            assert count >= 0, f"Tab {label!r} carried no count."
            assert rows == count, (
                f"Tab {label!r} badge says {count} tickets but the grid rendered {rows}."
            )
            if count == 0:
                assert helpdesk.is_empty_state(), (
                    f"Tab {label!r} holds no tickets but shows no empty-state placeholder."
                )
            if label in helpdesk.STATUS_TABS and rows:
                assert statuses == [label], (
                    f"Tab {label!r} should only list {label!r} tickets but showed {statuses}."
                )

        record_property("result_description", f"Helpdesk tab filtering: {observed}")

        # 'All' is the whole queue, so no single status tab may exceed it.
        all_count = observed["All"]["count"]
        assert all_count > 0, "The All tab reported an empty helpdesk queue."
        for label in helpdesk.STATUS_TABS:
            assert observed[label]["count"] <= all_count, (
                f"Tab {label!r} reports {observed[label]['count']} tickets, "
                f"more than the {all_count} in All."
            )

        helpdesk.switch_tab("All")

    def test_tc_wpad_helpdesk_03_search_functionality(self, record_property):
        """Phase 3: search narrows the queue by ticket ID, subject and category,
        and yields the empty state for a term that matches nothing."""
        helpdesk = self.open_helpdesk()
        checks = self.survey(helpdesk, record_property, "Search")
        baseline = checks.safe_call(helpdesk.get_row_count, 0)
        checks.check_interaction(
            "Search narrows the queue",
            lambda: helpdesk.search_ticket("INVALID-TKT-999"),
            lambda: helpdesk.get_row_count() < baseline,
        )
        checks.check_interaction(
            "Clearing search restores the queue",
            lambda: helpdesk.search_ticket(""),
            lambda: helpdesk.get_row_count() == baseline,
        )
        checks.publish()

        # Seed the search terms from a ticket that is actually in the queue,
        # rather than hard-coding an ID that later runs would not find.
        seed = helpdesk.get_newest_ticket()
        assert seed, "No well-formed ticket in the queue to drive the search checks."

        helpdesk.search_ticket(seed["ticket_id"])
        by_id = helpdesk.get_ticket_ids_in_view()
        assert by_id == [seed["ticket_id"]], (
            f"Searching for ticket ID {seed['ticket_id']} should isolate that one row, "
            f"but returned {by_id}."
        )

        helpdesk.search_ticket(seed["subject"])
        by_subject = helpdesk.get_subjects_in_view()
        assert by_subject, f"Searching for subject {seed['subject']!r} returned no rows."
        assert all(seed["subject"] in subject for subject in by_subject), (
            f"Subject search for {seed['subject']!r} returned unrelated rows: {by_subject}"
        )

        helpdesk.search_ticket(seed["category"])
        by_category = helpdesk.get_row_count()
        assert by_category > 0, f"Searching for category {seed['category']!r} returned no rows."

        helpdesk.search_ticket("INVALID-TKT-999")
        no_match = helpdesk.get_row_count()
        record_property(
            "result_description",
            f"Search on {seed['ticket_id']} matched {len(by_id)} row(s), subject matched "
            f"{len(by_subject)}, category {seed['category']!r} matched {by_category}, "
            f"gibberish matched {no_match}.",
        )
        assert no_match == 0, (
            f"The queue should be empty for a non-existent search but showed {no_match} rows."
        )
        assert helpdesk.is_empty_state(), (
            "A search with no matches did not render the 'No Data to display' placeholder."
        )

        helpdesk.search_ticket("")
        assert helpdesk.get_row_count() > 0, "Clearing the search did not restore the queue."

    def test_tc_wpad_helpdesk_04_verify_new_ticket_ingestion(self, record_property):
        """Phase 4: the most recently raised ticket carries a complete, valid
        metadata record in the queue.

        Fields are checked against the allowed value sets rather than fixed
        expectations, because the portal auto-triages a ticket shortly after
        submission — priority moves off the submitted value and status moves
        from Open to In Progress once it is assigned.
        """
        helpdesk = self.open_helpdesk()
        self.survey(helpdesk, record_property, "Ingestion").publish()
        helpdesk.switch_tab("All")

        newest = helpdesk.get_newest_ticket()
        assert newest, "No well-formed ticket found in the helpdesk queue."

        # Prove the row survives a round trip through search, the way an agent
        # would actually pull it up.
        helpdesk.search_ticket(newest["ticket_id"])
        found = helpdesk.find_ticket(newest["ticket_id"])

        record_property(
            "result_description",
            f"Newest helpdesk ticket {newest['ticket_id']} ingested as {found}.",
        )
        assert found is not None, (
            f"Ticket {newest['ticket_id']} could not be retrieved by its own ticket number."
        )

        assert helpdesk.TICKET_ID_PATTERN.fullmatch(found["ticket_id"]), (
            f"Ticket number {found['ticket_id']!r} does not follow the CBSE-HD-YYYY-NNN format."
        )
        assert found["subject"], f"Ticket {found['ticket_id']} was ingested without a subject."
        assert found["raised_by"], f"Ticket {found['ticket_id']} was ingested without a raiser."
        assert found["category"], f"Ticket {found['ticket_id']} was ingested without a category."
        assert found["created"], f"Ticket {found['ticket_id']} was ingested without a created date."
        assert found["status"] in helpdesk.KNOWN_STATUSES, (
            f"Ticket {found['ticket_id']} carries an unrecognised status {found['status']!r}; "
            f"expected one of {list(helpdesk.KNOWN_STATUSES)}."
        )
        assert found["priority"] in helpdesk.KNOWN_PRIORITIES, (
            f"Ticket {found['ticket_id']} carries an unrecognised priority {found['priority']!r}; "
            f"expected one of {list(helpdesk.KNOWN_PRIORITIES)}."
        )
        assert found["sla_breach"] in ("Yes", "No"), (
            f"Ticket {found['ticket_id']} has an unrecognised SLA Breach value "
            f"{found['sla_breach']!r}; expected 'Yes' or 'No'."
        )
        # A ticket this new cannot legitimately have breached its SLA yet.
        assert found["sla_breach"] == "No", (
            f"The newest ticket {found['ticket_id']} is already flagged as an SLA breach."
        )

        helpdesk.search_ticket("")

    @pytest.mark.e2e
    @pytest.mark.serial
    def test_tc_wpad_helpdesk_05_reassign_first_line_ticket(self, record_property):
        """Phase 5: a ticket sitting with the first-line queue can be reassigned
        to an L2 agent, and the queue reflects the new owner.

        Only tickets currently assigned to SOURCE_ASSIGNEE are eligible, so the
        test never moves work an L2 agent already owns. The agent picker offers
        L2 agents only, so this is a one-way move: the ticket cannot be handed
        back to the first-line queue through this panel.
        """
        helpdesk = self.open_helpdesk()
        # Reassignment is a one-way move of real work, so it stays a hard gate.
        self.survey(helpdesk, record_property, "Reassign").publish()
        helpdesk.switch_tab("All")

        candidates = helpdesk.find_tickets_assigned_to(self.SOURCE_ASSIGNEE)
        if not candidates:
            pytest.skip(
                f"No ticket is currently assigned to {self.SOURCE_ASSIGNEE!r}, so there is "
                "nothing to reassign without disturbing an L2 agent's workload."
            )
        ticket_id = candidates[0]

        actions = helpdesk.get_row_action_items(ticket_id)
        assert "Assign" in actions, (
            f"The row menu for {ticket_id} offers no Assign action; found {actions}."
        )

        helpdesk.open_assign_panel(ticket_id)
        title = helpdesk.get_assign_panel_title()
        assert ticket_id in title, (
            f"The assign panel is titled {title!r}, which does not name ticket {ticket_id}."
        )

        # Nothing may be committed before an agent is chosen.
        assert not helpdesk.is_assign_confirm_enabled(), (
            "'Assign Ticket' is enabled before any agent has been selected."
        )

        agents = helpdesk.get_agent_options()
        assert agents, "The assign panel offers no L2 agents to reassign to."
        target_agent = next(
            (agent for agent in agents if agent != self.SOURCE_ASSIGNEE), None
        )
        assert target_agent, (
            f"The only agent offered is {self.SOURCE_ASSIGNEE!r}, so the ticket cannot move."
        )

        helpdesk.select_agent(target_agent)
        assert helpdesk.is_assign_confirm_enabled(), (
            f"'Assign Ticket' stayed disabled after selecting agent {target_agent!r}."
        )

        assigned_to = helpdesk.reassign_ticket(ticket_id, target_agent)

        record_property(
            "result_description",
            f"Reassigned {ticket_id} from {self.SOURCE_ASSIGNEE!r} to {target_agent!r}; "
            f"queue now shows {assigned_to!r}. Agents offered: {agents}.",
        )
        assert assigned_to == target_agent, (
            f"Ticket {ticket_id} should now sit with {target_agent!r} but the queue "
            f"shows {assigned_to!r}."
        )

        # The move must survive a reload, not just re-render optimistically.
        helpdesk.open(ReadConfig.get_base_url())
        helpdesk.search_ticket(ticket_id)
        persisted = helpdesk.find_ticket(ticket_id)
        assert persisted is not None, f"Ticket {ticket_id} vanished from the queue after reassignment."
        assert persisted["assigned_to"] == target_agent, (
            f"After reload, ticket {ticket_id} is assigned to {persisted['assigned_to']!r} "
            f"rather than {target_agent!r} — the reassignment did not persist."
        )
        assert ticket_id not in helpdesk.find_tickets_assigned_to(self.SOURCE_ASSIGNEE), (
            f"Ticket {ticket_id} is still listed against {self.SOURCE_ASSIGNEE!r}."
        )

        helpdesk.search_ticket("")
