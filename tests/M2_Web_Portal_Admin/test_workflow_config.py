"""Admin > Workflow & SLA Configuration.

M2 had no coverage of this screen at all - the framework knew the route only as
a truncated sidebar label and never opened it. These are the first tests to do
so.

WF-1..WF-4 read. WF-5 is the only one that writes, and it is deliberately
narrow: these values drive the live review workflow, and `Max Approvals
Required` on a PIT node *is* the 3/3 quorum the M1 suites depend on. So the edit
round-trip touches `Max Extension (hrs)` on an L1 or L2 row - a timer with no
bearing on the RWG/PIT quorum - and restores the original value in a `finally`,
so a mid-test failure cannot leave the environment reconfigured.
"""

import pytest

from pages.admin.workflow_config_page import WorkflowConfigPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2WorkflowConfiguration:
    """TC-WPAD-WF-*: workflow nodes, their reviewer roles and their SLA timers."""

    # The field the mutating test is allowed to touch, and where.
    SAFE_EDIT_FIELD = "maxExtensionHrs"
    SAFE_EDIT_TABS = ("L2 Workflow", "L1 Workflow")

    def open_workflow_config(self):
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
            f"Sign-in did not establish a session for {username!r}."
        )
        page = WorkflowConfigPage(self.driver)
        page.open(ReadConfig.get_base_url())
        checkpoint(f"Admin {username} opened Workflow & SLA Configuration")
        return page

    def survey(self, page, record_property, scope):
        """Soft-check the page furniture and its columns."""
        checks = ElementChecks(
            page, record_property, page_name=f"Workflow Config — {scope}"
        )
        checks.check_condition("Page header", page.is_on_page)
        checks.check("Node table", page.TABLE)
        checks.check("Search by Node Code", page.SEARCH_INPUT)
        checks.check_condition("Role filter", page.has_role_filter)
        for tab in WorkflowConfigPage.TABS:
            checks.check_condition(f"Tab — {tab}", lambda t=tab: page.is_tab_present(t))
        return checks

    # ------------------------------------------------------------------ WF-1

    def test_tc_wpad_wf_01_page_loads_with_all_workflows(
        self, record_property, page_evidence
    ):
        """Page furniture, the four workflow tabs and the node columns."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open Workflow & SLA Configuration as an admin.\n"
            "Record the page furniture, the four workflow tabs and every column the "
            "node grid is meant to carry, all as soft checks.\n"
            "The grid rendering at all stays a hard gate, because nothing below can "
            "mean anything without it.",
        )
        page = self.open_workflow_config()
        checks = self.survey(page, record_property, "Load")

        missing = checks.safe_call(page.missing_columns, [])
        for column in WorkflowConfigPage.EXPECTED_COLUMNS:
            checks.check_condition(f"Column — {column}", column not in missing)

        header = page.get_header_text()
        rows = page.get_row_count()
        page_evidence.checkpoint(
            f"{header!r} rendered with {rows} row(s) on the first tab; "
            f"missing columns: {missing or 'none'}"
        )
        record_property(
            "result_description",
            f"{checks.publish()}. Header {header!r}, {rows} row(s) on the first tab.",
        )
        assert rows > 0, (
            "Workflow & SLA Configuration rendered no node rows at all, so no "
            "workflow is configured or the grid failed to load."
        )

    # ------------------------------------------------------------------ WF-2

    def test_tc_wpad_wf_02_each_tab_scopes_to_its_own_nodes(
        self, record_property, page_evidence
    ):
        """Every workflow tab renders its own node set."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Click each of the four workflow tabs in turn and read the nodes it "
            "lists.\n"
            "Every tab must render rows of its own, and the Teacher and SME "
            "workflows must not show the same node codes - a tab that never "
            "changed the grid would otherwise look like it worked.",
        )
        page = self.open_workflow_config()
        self.survey(page, record_property, "Tabs").publish()

        # Only the tabs this environment actually renders. Which workflows a
        # portal carries is an environment fact, not this test's subject: UAT
        # ships the Teacher and SME workflows but no L1/L2 ones, and walking
        # into an absent tab cost a 20s `until_visible` timeout that read as a
        # scoping failure. WF-1 already records tab presence as soft checks, so
        # a tab going missing is still reported - here it is skipped over and
        # named, and the scoping assertions below run on what is there.
        present = [t for t in WorkflowConfigPage.TABS if page.is_tab_present(t)]
        absent = [t for t in WorkflowConfigPage.TABS if t not in present]
        if absent:
            page_evidence.checkpoint(
                f"Tabs not rendered by this environment, so not exercised: {absent}"
            )

        per_tab = {}
        for tab in present:
            page.switch_tab(tab)
            rows = page.get_rows()
            codes = [r.get("Node Code", "") for r in rows if r.get("Node Code")]
            per_tab[tab] = {"rows": len(rows), "codes": codes}
            page_evidence.checkpoint(
                f"{tab}: {len(rows)} row(s), node codes {codes or 'none (timers only)'}"
            )
            assert rows, f"The {tab} tab rendered no rows."

        record_property(
            "result_description",
            "; ".join(
                f"{tab}: {data['rows']} row(s) {data['codes'] or '(timers only)'}"
                for tab, data in per_tab.items()
            )
            + (f"; absent here: {', '.join(absent)}" if absent else ""),
        )

        # Both node-bearing workflows must exist, whatever else this portal
        # carries - without them there is no scoping left to check.
        missing_node_tabs = [
            t for t in WorkflowConfigPage.NODE_TABS if t not in per_tab
        ]
        assert not missing_node_tabs, (
            f"The {missing_node_tabs} tab(s) are missing, so the node-bearing "
            "workflows cannot be compared against each other."
        )

        # The two node-bearing workflows must be genuinely different grids.
        teacher = set(per_tab["Teacher Workflow"]["codes"])
        sme = set(per_tab["SME Workflow"]["codes"])
        assert teacher and sme, (
            "Teacher and SME workflows should both list node codes, but got "
            f"{teacher or 'none'} and {sme or 'none'}."
        )
        assert teacher != sme, (
            f"The Teacher and SME tabs list the same nodes ({sorted(teacher)}), so "
            "switching tabs is not scoping the grid."
        )

    # ------------------------------------------------------------------ WF-3

    def test_tc_wpad_wf_03_search_filters_by_node_code(
        self, record_property, page_evidence
    ):
        """Search narrows the grid to matching nodes, and empties on no match."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Search the node grid for a node code this environment actually has, "
            "taken from the grid rather than hardcoded.\n"
            "Every row that comes back must match the term, a code that exists "
            "nowhere must empty the grid, and clearing the box must restore it.",
        )
        page = self.open_workflow_config()
        checks = self.survey(page, record_property, "Search")
        page.switch_tab("Teacher Workflow")
        checks.publish()

        baseline = page.get_rows()
        codes = [r.get("Node Code") for r in baseline if r.get("Node Code")]
        assert codes, "The Teacher workflow lists no node codes to search for."
        target = codes[0]

        found = page.search_and_settle(target)
        page_evidence.checkpoint(
            f"Search for {target!r} returned {len(found)} of {len(baseline)} row(s): "
            f"{[r.get('Node Code') for r in found]}"
        )
        assert found, f"Searching for node {target!r} returned nothing."

        missing = page.search_and_settle("N000000")
        page_evidence.checkpoint(
            f"Search for a node that does not exist left {len(missing)} row(s) — must be 0"
        )

        # The decisive check: a term that matches nothing must empty the grid.
        # It does not, and the cause is server side rather than in the page.
        # Confirmed against QA 2026-09-08 by calling the endpoint the SPA uses:
        #
        #   GET /admin/workflows/19/nodes            -> 2 nodes [N196, N197]
        #   GET /admin/workflows/19/nodes?q=N196     -> 2 nodes [N196, N197]
        #   GET /admin/workflows/19/nodes?q=ZZZZZZ   -> 2 nodes [N196, N197]
        #
        # `search=` and `nodeCode=` behave the same way. The front end is
        # correct - it issues the query on every keystroke and renders what
        # comes back - so there is nothing this suite can drive differently to
        # make the filter work.
        #
        # Written as a guard rather than a bare xfail so the moment the API
        # honours the parameter, this test carries straight on and asserts the
        # real contract below instead of quietly staying yellow.
        if len(missing) == len(baseline) and len(found) == len(baseline):
            pytest.xfail(
                "KI-M2-WF-001 [M2 Workflow Config] Node Code search does not filter. "
                "GET /admin/workflows/{id}/nodes accepts q= but ignores it: a term "
                f"matching nothing still returns all {len(baseline)} node(s). "
                "Verified directly against the API, so this is a server-side gap, "
                "not a UI or automation one."
            )

        assert all(
            target.casefold() in " ".join(r.get("_cells", [])).casefold() for r in found
        ), f"Search for {target!r} returned rows that do not contain it."
        assert not missing, (
            f"Searching for a node code that does not exist left {len(missing)} row(s)."
        )

        restored = page.search_and_settle("")
        page_evidence.checkpoint(
            f"Clearing the search restored {len(restored)} row(s) (started at {len(baseline)})"
        )
        record_property(
            "result_description",
            f"Search by node code narrowed {len(baseline)} -> {len(found)} -> 0 and "
            f"restored to {len(restored)}.",
        )
        assert len(restored) == len(baseline), (
            "Clearing the search did not restore the full node list."
        )

    # ------------------------------------------------------------------ WF-4

    def test_tc_wpad_wf_04_node_quorum_and_sla_values_are_coherent(
        self, record_property, page_evidence
    ):
        """Every node's reviewer counts and timers make sense together."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Read every node on the Teacher and SME workflows and check its numbers "
            "hang together.\n"
            "A node cannot need more approvals than it has reviewers, retries cannot "
            "be negative, and a review stage must be given some time to happen in.\n"
            "Nothing is changed: this only reads what is configured.",
        )
        page = self.open_workflow_config()
        self.survey(page, record_property, "Values").publish()

        problems = []
        seen = []
        for tab in WorkflowConfigPage.NODE_TABS:
            page.switch_tab(tab)
            for row in page.get_rows():
                code = row.get("Node Code") or "?"
                role = row.get("Reviewer Role") or "?"
                reviewers = page.as_number(row.get("Max Reviewers"))
                approvals = page.as_number(row.get("Max Approvals Required"))
                retries = page.as_number(row.get("Max Retries"))
                sla = page.as_number(row.get("SLA hrs"))
                seen.append(f"{tab.split()[0]}/{code} {role}: "
                            f"reviewers={reviewers} approvals={approvals} "
                            f"retries={retries} sla={sla}")

                if reviewers is not None and approvals is not None and approvals > reviewers:
                    problems.append(
                        f"{code} ({role}) needs {approvals} approvals but allows only "
                        f"{reviewers} reviewer(s)"
                    )
                if retries is not None and retries < 0:
                    problems.append(f"{code} ({role}) has negative retries ({retries})")
                if sla is not None and sla <= 0:
                    problems.append(f"{code} ({role}) has a non-positive SLA ({sla}h)")

        page_evidence.checkpoint(
            "Node configuration read — " + "; ".join(seen)
            + f"; problems: {problems or 'none'}"
        )
        record_property(
            "result_description",
            f"Checked {len(seen)} node(s) across "
            f"{len(WorkflowConfigPage.NODE_TABS)} workflows; "
            f"{len(problems)} incoherent value(s).",
        )
        assert not problems, (
            "Workflow nodes carry values that contradict each other: "
            + "; ".join(problems)
        )

    # ------------------------------------------------------------------ WF-5

    @pytest.mark.serial
    def test_tc_wpad_wf_05_sla_edit_saves_and_can_be_restored(
        self, record_property, page_evidence
    ):
        """An SLA timer edit persists, and the original value is put back.

        Deliberately scoped to `Max Extension (hrs)` on an L1/L2 row. The other
        columns on this screen steer the live review workflow - `Max Approvals
        Required` on a PIT node is the 3/3 quorum the M1 suites rely on - so a
        round-trip against those would risk breaking other modules for everyone
        on this environment.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open a second-line workflow row for editing and change its Max "
            "Extension timer.\n"
            "Save, reload the page, and check the new value actually stuck.\n"
            "Then put the original value back, whatever happens, so the shared "
            "environment is left exactly as it was found.\n"
            "Only that one timer is touched: the reviewer and approval counts on "
            "this screen drive the real review workflow.",
        )
        page = self.open_workflow_config()
        self.survey(page, record_property, "SLA edit").publish()

        tab_used = None
        original = None
        for tab in self.SAFE_EDIT_TABS:
            if not page.is_tab_present(tab):
                continue
            page.switch_tab(tab)
            if not page.get_row_count():
                continue
            page.open_row_editor(index=0)
            fields = page.get_editable_fields()
            page_evidence.checkpoint(f"{tab} row editor exposes {fields}")
            if self.SAFE_EDIT_FIELD in fields:
                tab_used = tab
                original = fields[self.SAFE_EDIT_FIELD]
                break
            page.cancel_editor()

        if tab_used is None:
            pytest.skip(
                "No L1/L2 workflow row exposes a Max Extension timer to edit, so "
                "the SLA round-trip has nothing safe to exercise here."
            )

        current = page.as_number(original) or 0
        new_value = current + 1
        restored_ok = False
        try:
            typed = page.set_field(self.SAFE_EDIT_FIELD, new_value)
            assert page.as_number(typed) == new_value, (
                f"The editor holds {typed!r} after typing {new_value}."
            )
            page.save_editor()

            # Reload rather than trusting the grid it just repainted.
            page.open(ReadConfig.get_base_url())
            page.switch_tab(tab_used)
            page.open_row_editor(index=0)
            after = page.get_editable_fields().get(self.SAFE_EDIT_FIELD)
            page_evidence.checkpoint(
                f"{tab_used} Max Extension was {original!r}, saved as {new_value}, "
                f"reads {after!r} after a reload"
            )
            assert page.as_number(after) == new_value, (
                f"Max Extension was saved as {new_value} but reads {after!r} after a "
                "reload, so the edit did not persist."
            )
        finally:
            # Put it back whatever happened above, so a failure here cannot
            # leave the shared workflow reconfigured.
            try:
                if not page.is_editor_open():
                    page.open(ReadConfig.get_base_url())
                    page.switch_tab(tab_used)
                    page.open_row_editor(index=0)
                page.set_field(self.SAFE_EDIT_FIELD, page.as_number(original) or 0)
                page.save_editor()
                page.open(ReadConfig.get_base_url())
                page.switch_tab(tab_used)
                page.open_row_editor(index=0)
                back = page.get_editable_fields().get(self.SAFE_EDIT_FIELD)
                restored_ok = page.as_number(back) == page.as_number(original)
                page.cancel_editor()
                checkpoint(
                    f"Restored {tab_used} Max Extension to {original!r} "
                    f"(reads {back!r})"
                )
            except Exception as error:  # noqa: BLE001 - cleanup must not mask the result
                checkpoint(
                    f"WARNING: could not restore {tab_used} Max Extension to "
                    f"{original!r}: {type(error).__name__}: {error}"
                )

        record_property(
            "result_description",
            f"{tab_used} Max Extension round-tripped {original!r} -> {new_value} -> "
            f"{original!r}; restored: {restored_ok}.",
        )
        assert restored_ok, (
            f"The edit persisted, but {tab_used} Max Extension was not restored to "
            f"{original!r}. Put it back before running anything else against this "
            "environment."
        )
