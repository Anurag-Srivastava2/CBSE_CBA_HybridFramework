import re
from time import monotonic, sleep
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.sme.manual_item_page import ManualItemPage
from pages.teacher.dashboard_page import DashboardPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig

# The dashboard survey runs ~60 checks against elements that all paint
# together, and every *absent* element costs its full timeout. At the 5s
# default a fully broken dashboard would add ~5 minutes to the run.
CHECK_TIMEOUT = 2


@pytest.mark.rtm
# Drives a teacher login whose dashboard and staged "Added Items" list live
# server-side per account: a second session on the same account changes what
# this one sees mid-test. get_teacher_username() gives each xdist worker its
# own account, and `serial` keeps this class on one worker.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestTeacherManualItemCreation:
    def login_as_teacher(self):
        username = ReadConfig.get_teacher_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        page = ManualItemPage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        return page

    def wait_for_dashboard_text(self, patterns, timeout=30):
        """Dashboard text once the given patterns are present.

        The shell renders before the stat tiles have their counts, so reading
        the page straight after login can catch "All Items" with no number in
        front of it yet. Returns whatever is on the page at the deadline so
        the caller's assertions still report the real content.
        """
        deadline = monotonic() + timeout
        while True:
            text = self.driver.execute_script(
                "return document.body.innerText || document.body.textContent || '';"
            )
            if all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
                return text
            if monotonic() >= deadline:
                return text
            sleep(0.5)

    def survey(self, record_property, scope):
        """Soft-check the teacher dashboard furniture.

        Presence only — driving the controls belongs to the tests that are
        about the controls, so the three tests that merely pass through the
        dashboard on their way elsewhere do not pay for 15 interactions each.

        Every page read goes through safe_call / a callable predicate: a reader
        that raises outside the guard aborts the run, which is the exact failure
        mode these soft checks exist to avoid.
        """
        dashboard = DashboardPage(self.driver)
        checks = ElementChecks(
            dashboard, record_property, page_name=f"Teacher Dashboard — {scope}"
        )

        checks.check("Welcome header", dashboard.PAGE_HEADER, timeout=CHECK_TIMEOUT)
        greeting = checks.text_of(dashboard.PAGE_HEADER)
        checks.check_condition(
            "Welcome header greets the user",
            "hello" in greeting.casefold(),
            detail=f"header text: {greeting!r}" if greeting else "no header text",
        )
        checks.check("Page subtitle", dashboard.PAGE_SUBTITLE, timeout=CHECK_TIMEOUT)
        checks.check(
            "Button — Create an Item Set",
            dashboard.CREATE_ITEM_SET_CTA,
            timeout=CHECK_TIMEOUT,
        )

        # --- Stat cards ---------------------------------------------------
        missing_stats = checks.safe_call(dashboard.missing_stat_cards)
        for label in dashboard.STAT_LABELS:
            checks.check_condition(f"Stat card — {label}", label not in missing_stats)

        # --- Analytics sections -------------------------------------------
        missing_charts = checks.safe_call(dashboard.missing_chart_sections)
        for title in dashboard.CHART_TITLES:
            checks.check_condition(f"Section — {title}", title not in missing_charts)
        chart_surfaces = checks.safe_call(
            lambda: dashboard.count_visible(dashboard.CHART_SURFACES), 0
        )
        checks.check_condition(
            "Charts rendered",
            chart_surfaces,
            detail=f"{chart_surfaces} recharts surfaces visible",
        )
        checks.check(
            "Status Distribution donut centre",
            dashboard.STATUS_DONUT_CENTRE,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Review-stage pending pill", dashboard.REVIEW_STAGE_PILL, timeout=CHECK_TIMEOUT
        )

        # --- My Item Sets grid ---------------------------------------------
        checks.check(
            "Section — My Item Sets", dashboard.SECTION_MY_ITEM_SETS, timeout=CHECK_TIMEOUT
        )
        checks.check("Link — View All", dashboard.VIEW_ALL_LINK, timeout=CHECK_TIMEOUT)
        checks.check("Item set grid", dashboard.TABLE, timeout=CHECK_TIMEOUT)
        checks.check("Grid tab list", dashboard.TAB_LIST, timeout=CHECK_TIMEOUT)

        missing_tabs = checks.safe_call(dashboard.missing_tabs)
        for label in dashboard.TAB_LABELS:
            checks.check_condition(f"Tab — {label}", label not in missing_tabs)

        missing_columns = checks.safe_call(dashboard.missing_columns)
        headers = checks.safe_call(dashboard.get_table_headers)
        for column in dashboard.ITEM_SET_COLUMNS:
            checks.check_condition(
                f"Column — {column}",
                column not in missing_columns,
                detail=f"found: {headers}" if column in missing_columns else "",
            )

        checks.check("Rows per page control", dashboard.ROWS_PER_PAGE, timeout=CHECK_TIMEOUT)
        checks.check("Previous page button", dashboard.PREV_PAGE_BTN, timeout=CHECK_TIMEOUT)
        checks.check("Next page button", dashboard.NEXT_PAGE_BTN, timeout=CHECK_TIMEOUT)

        # --- Application chrome --------------------------------------------
        checks.check("Header bar", dashboard.HEADER, timeout=CHECK_TIMEOUT)
        checks.check("Sidebar nav", dashboard.SIDEBAR_NAV, timeout=CHECK_TIMEOUT)
        checks.check("Sidebar toggle", dashboard.SIDEBAR_TOGGLE, timeout=CHECK_TIMEOUT)
        checks.check("Notification bell", dashboard.NOTIFICATION_BELL, timeout=CHECK_TIMEOUT)
        badge = checks.safe_call(dashboard.get_notification_badge_text, "")
        checks.check_condition(
            "Notification badge shows a count",
            badge,
            detail=f"badge: {badge!r}" if badge else "no badge text found",
        )

        missing_nav = checks.safe_call(dashboard.missing_nav_items)
        for label in dashboard.NAV_ITEMS:
            checks.check_condition(f"Nav — {label}", label not in missing_nav)

        # --- Accessibility / localisation toolbar ----------------------------
        checks.check("Theme picker", dashboard.THEME_PICKER, timeout=CHECK_TIMEOUT)
        checks.check(
            "Screen-reader toggle", dashboard.SCREEN_READER_TOGGLE, timeout=CHECK_TIMEOUT
        )
        checks.check("Language — EN", dashboard.LANG_EN, timeout=CHECK_TIMEOUT)
        checks.check("Language — हिंदी", dashboard.LANG_HI, timeout=CHECK_TIMEOUT)
        font_controls = checks.safe_call(
            lambda: dashboard.count_visible(dashboard.FONT_SIZE_CONTROLS), 0
        )
        checks.check_condition(
            "Font-size controls (A− / A / A+ / A++)",
            font_controls >= 4,
            detail=f"{font_controls} visible",
        )
        return dashboard, checks

    def survey_manual_form(self, page, record_property, scope):
        """Soft-check the manual authoring form.

        Excludes the per-item Edit/Delete/Show-answer controls: those are
        revealed by interacting with a staged item card, so recording their
        absence on arrival would report a gap the page is right not to show.
        """
        checks = ElementChecks(
            page, record_property, page_name=f"Manual Item Authoring — {scope}"
        )

        checks.check("Workspace title", page.WORKSPACE_TITLE, timeout=CHECK_TIMEOUT)
        checks.check("Section — Metadata Tags", page.METADATA_HEADING, timeout=CHECK_TIMEOUT)

        missing_metadata = checks.safe_call(page.missing_metadata_fields)
        for label in page.METADATA_FIELD_LABELS:
            checks.check_condition(f"Field — {label}", label not in missing_metadata)

        missing_content = checks.safe_call(page.missing_content_fields)
        for label in page.CONTENT_FIELD_LABELS:
            checks.check_condition(f"Field — {label}", label not in missing_content)

        dropdowns = checks.safe_call(
            lambda: page.count_visible(page.METADATA_DROPDOWNS), 0
        )
        checks.check_condition(
            "Metadata dropdowns rendered",
            dropdowns >= len(page.METADATA_FIELD_LABELS),
            detail=f"{dropdowns} comboboxes visible",
        )

        checks.check("Button — Clear Form", page.CLEAR_FORM_BUTTON, timeout=CHECK_TIMEOUT)
        checks.check("Button — Add Item", page.ADD_ITEM_BUTTON, timeout=CHECK_TIMEOUT)
        checks.check(
            "Answer key textbox", page.ANSWER_KEY_TEXTBOX, timeout=CHECK_TIMEOUT
        )
        checks.check("Added Items heading", page.ADDED_ITEMS_HEADING, timeout=CHECK_TIMEOUT)

        editors = checks.safe_call(lambda: page.count_visible(page.EDITOR_SURFACES), 0)
        checks.check_condition(
            "Rich-text editors rendered",
            editors >= 2,
            detail=f"{editors} editor surfaces visible",
        )
        toolbar = checks.safe_call(
            lambda: page.count_visible(page.EDITOR_TOOLBAR_BUTTONS), 0
        )
        checks.check_condition(
            "Editor toolbar rendered",
            toolbar >= 20,
            detail=f"{toolbar} toolbar buttons visible",
        )

        missing_steps = checks.safe_call(page.missing_manual_wizard_steps)
        for label in page.MANUAL_WIZARD_STEP_LABELS:
            checks.check_condition(f"Wizard step — {label}", label not in missing_steps)
        return checks

    def test_tc_tcib_01_p01_contribution_dashboard_and_create_cta(self, record_property):
        """Inventory the teacher contribution dashboard and drive its controls.

        This test's job is genuinely "does this page render", so its structure
        is recorded softly. The hard gate is reaching an authenticated
        dashboard at all — without it there is nothing to survey.
        """
        self.login_as_teacher()
        dashboard, checks = self.survey(record_property, "Landing")

        text = self.wait_for_dashboard_text(
            [
                r"hello,\s*teacher",
                r"create an item set|create new item",
                r"all items",
                r"under review",
                r"rejected",
                r"published",
            ]
        ).casefold()
        for marker in (
            "hello, teacher",
            "all items",
            "under review",
            "rejected",
            "published",
        ):
            checks.check_condition(f"Dashboard text — {marker}", marker in text)
        checks.check_condition(
            "Dashboard text — create an item set",
            "create an item set" in text or "create new item" in text,
        )

        # The one hard gate, asserted before any control is driven: the survey
        # above is only meaningful if this really is the authenticated
        # dashboard, and the stat cards below navigate away from it.
        assert "hello, teacher" in text, (
            "The teacher dashboard did not render its greeting, so the page "
            "surveyed above is not an authenticated contribution dashboard."
        )

        # Do the controls respond, or are they rendered but dead?
        # Tabs re-scope the grid in place, so the dashboard survives them.
        for label in dashboard.TAB_LABELS:
            checks.check_interaction(
                f"Tab responds — {label}",
                lambda tab=label: dashboard.switch_tab(tab),
                lambda tab=label: dashboard.is_tab_active(tab),
            )
        dashboard.switch_tab("All")

        # A stat card is a link, not an in-place filter: it opens the item-set
        # listing scoped to that status. Verified against the destination URL —
        # verifying against the dashboard would silently pass on any page that
        # happens to render a grid. Each one is walked back so the next check
        # starts from the dashboard again.
        for label in ("Published", "All Items", "Under Review", "Drafts"):
            checks.check_interaction(
                f"Stat card opens the filtered list — {label}",
                lambda card=label: dashboard.click_element(
                    dashboard.stat_card_locator(card)
                ),
                lambda: dashboard.wait_utils.until_url_contains("item-sets", timeout=15),
            )
            checks.safe_call(self.driver.back)
            checks.safe_call(dashboard.wait_for_dashboard_ready, False)

        record_property("result_description", checks.publish())

    def test_tc_tcib_01_p02_dashboard_stat_counters_are_numeric(self, record_property):
        """Every stat card exposes a numeric counter.

        Card presence is soft; the counters being readable numbers is the
        contract this test exists to enforce, so it stays a hard assert — as
        does the arithmetic between them, which is data integrity.
        """
        self.login_as_teacher()
        dashboard, checks = self.survey(record_property, "Stat Counters")

        statuses = ("All Items", "Under Review", "Rejected", "Published")
        text = self.wait_for_dashboard_text(
            [rf"\b\d+\s+{re.escape(status)}\b" for status in statuses]
        )

        values = checks.safe_call(dashboard.get_all_stat_values, {}) or {}
        for label in dashboard.STAT_LABELS:
            value = values.get(label)
            checks.check_condition(
                f"Stat value — {label} is numeric",
                value is not None and value >= 0,
                detail=f"read {value!r}",
            )

        # Recorded softly rather than asserted: "All Items is the sum of the
        # status buckets" holds on this environment, but it is an observed
        # arithmetic identity rather than a documented contract, so a mismatch
        # should show up in the report without failing the suite.
        buckets = [label for label in dashboard.STAT_LABELS if label != "All Items"]
        bucket_total = sum(values.get(label) or 0 for label in buckets)
        checks.check_condition(
            "All Items equals the sum of the status buckets",
            values.get("All Items") == bucket_total,
            detail=f"All Items {values.get('All Items')!r} vs sum {bucket_total}",
        )

        record_property(
            "result_description",
            f"{checks.publish()}. Stat counters: {values}.",
        )

        for status in statuses:
            assert re.search(rf"\b\d+\s+{re.escape(status)}\b", text, re.IGNORECASE), (
                f"No numeric counter was shown for {status}."
            )

        # Data integrity: no bucket can hold more items than the bank total.
        all_items = values.get("All Items")
        assert all_items is not None, (
            f"The All Items stat card exposed no numeric counter (read {values!r})."
        )
        oversized = {
            label: values[label]
            for label in buckets
            if values.get(label) is not None and values[label] > all_items
        }
        assert not oversized, (
            f"Stat buckets report more items than the All Items total ({all_items}): "
            f"{oversized}"
        )

    def test_tc_tcib_02_p01_submit_locked_until_mandatory_item_complete(
        self, record_property
    ):
        """Continue stays locked until one complete item has been added.

        The form furniture is surveyed softly; the locking behaviour and the
        item count are workflow outcomes and stay hard.
        """
        page = self.login_as_teacher()
        page.open_true_false_manual_item_form()
        # Surveys the authoring form rather than the dashboard it arrived
        # through: conftest collapses user_properties with dict(), so a second
        # publish() in one test silently replaces the first element table.
        checks = self.survey_manual_form(page, record_property, "True/False Form")

        # A control that renders but never responds passes every presence check
        # above. Clear Form is driven here because it is non-destructive to
        # anything server-side — it only resets the unsaved form.
        checks.check_interaction(
            "Button responds — Clear Form",
            lambda: page.click_element(page.CLEAR_FORM_BUTTON),
            lambda: page.count_visible(page.METADATA_DROPDOWNS),
        )
        record_property("result_description", checks.publish())

        page.open_true_false_manual_item_form()

        # "Added Items" is a server-side draft that outlives the run, so this
        # account arrives holding items left by earlier runs of this very test
        # (the assertion below found 4 of them). "Continue is locked until a
        # complete item exists" can only be tested from an empty draft, so the
        # precondition is established rather than assumed — the same isolation
        # step the M1 manual-item suites take before their own draft assertions.
        page.clear_added_items()
        assert page.is_continue_enabled() is False

        # Still asserted as an increment rather than an absolute count: the
        # draft can rehydrate asynchronously after being cleared.
        items_before = int(page.get_settled_added_items_count())
        run_id = uuid4().hex[:10]
        page.add_true_false_manual_item(
            question_text=f"Is 91 greater than 19? Teacher contribution {run_id}",
            answer="True",
            explanation="91 is greater than 19.",
        )
        assert int(page.get_settled_added_items_count()) == items_before + 1
        assert page.is_continue_enabled() is True

    def test_tc_tcib_02_n01_teacher_grade_subject_rbac_is_enforced(self, record_property):
        """A teacher may only author within their own grade and subject scope.

        This is a security contract, so every assertion below the survey stays
        hard — a teacher silently gaining Grade 10 is a defect, not a report row.
        """
        page = self.login_as_teacher()
        page.open_true_false_manual_item_form()
        record_property(
            "result_description",
            self.survey_manual_form(page, record_property, "RBAC Scope").publish(),
        )

        assert page.is_dropdown_option_available("Grade *", "Grade 1") is True
        assert page.is_dropdown_option_available("Grade *", "Grade 10") is False
        assert page.is_dropdown_option_available("Subject *", "Mathematics") is True
