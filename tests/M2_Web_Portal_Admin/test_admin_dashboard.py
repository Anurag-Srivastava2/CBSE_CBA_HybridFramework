import pytest

from pages.admin.admin_dashboard_page import AdminDashboardPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2AdminDashboard:
    """TC-WPAD-DASH-* : admin landing dashboard KPI cards, filters, activity
    feed and published-items grid."""

    def login_as_admin(self):
        username = ReadConfig.get_admin_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        dashboard = AdminDashboardPage(self.driver)
        dashboard.wait_for_dashboard_ready()
        return dashboard

    def test_tc_wpad_dash_01_verify_header_and_kpi_cards(self, record_property):
        """Header and KPI cards, each recorded as a soft check.

        Both the card and the value it holds are checked, so the report
        distinguishes "card missing" from "card present but non-numeric".
        """
        dashboard = self.login_as_admin()
        checks = ElementChecks(dashboard, record_property, page_name="Admin Dashboard — KPIs")

        checks.check("Welcome header", dashboard.PAGE_HEADER)
        welcome_message = checks.text_of(dashboard.PAGE_HEADER)
        checks.check_condition(
            "Welcome header greets the user",
            "Hello" in welcome_message,
            detail=f"header text: {welcome_message!r}" if welcome_message else "no header text",
        )

        cards = [
            ("All Items", dashboard.METRIC_CARD_ALL_ITEMS, 0),
            ("All Item Sets", dashboard.METRIC_CARD_ALL_SETS, 0),
            # The environment always has users; 0 means the card failed to load.
            ("Total Users", dashboard.METRIC_CARD_TOTAL_USERS, 1),
            ("QAR Failed", dashboard.METRIC_CARD_QAR_FAILED, 0),
        ]
        values = {}
        for label, locator, minimum in cards:
            checks.check(f"KPI card — {label}", locator)
            value = dashboard.get_metric_value(locator)
            values[label] = value
            checks.check_condition(
                f"KPI value — {label} is numeric and >= {minimum}",
                value is not None and value >= minimum,
                detail=f"read {value!r}",
            )

        record_property(
            "result_description",
            f"{checks.publish()}. KPI values: "
            + ", ".join(f"{label}={value}" for label, value in values.items()),
        )

    def test_tc_wpad_dash_03_verify_dynamic_activity_feed_format(self, record_property):
        """User Activity feed: section, audit link, entries and relative timestamps."""
        dashboard = self.login_as_admin()
        checks = ElementChecks(dashboard, record_property, page_name="Admin Dashboard — Activity Feed")

        checks.check("Section — User Activity", dashboard.SECTION_ACTIVITY)
        checks.check("Audit Trail link", dashboard.AUDIT_TRAIL_LINK)

        activity_logs = dashboard.get_user_activity_logs()
        checks.check_condition(
            "User Activity feed has entries",
            activity_logs,
            detail=f"{len(activity_logs)} entries",
        )

        timestamped = dashboard.get_relative_timestamp_entries()
        checks.check_condition(
            "Feed entries carry relative timestamps",
            timestamped,
            detail=(
                f"{len(timestamped)} of {len(activity_logs)} entries matched"
                if activity_logs
                else "no entries to match against"
            ),
        )

        record_property(
            "result_description",
            f"{checks.publish()}. Feed rendered {len(activity_logs)} entries, "
            f"{len(timestamped)} with relative timestamps.",
        )

    def test_tc_wpad_dash_04_verify_published_items_grid_structure(self, record_property):
        """Published Items matrix: section, table, and its expected column headers."""
        dashboard = self.login_as_admin()
        checks = ElementChecks(dashboard, record_property, page_name="Admin Dashboard — Published Items Grid")

        checks.check("Section — Published Items by Grade & Subject", dashboard.SECTION_PUBLISHED_GRID)
        checks.check("Published Items grid table", dashboard.PUBLISHED_GRID_TABLE)
        checks.check("Published Items grid column headers", dashboard.PUBLISHED_GRID_HEADERS)

        header_texts = dashboard.get_published_grid_headers()
        checks.check_condition(
            "Grid has a Grade column",
            any("grade" in header.casefold() for header in header_texts),
            detail=f"headers: {header_texts}",
        )
        expected_subjects = ("Mathematics", "English", "Science", "Total")
        found_subjects = [
            subject
            for subject in expected_subjects
            if subject.casefold() in (header.casefold() for header in header_texts)
        ]
        checks.check_condition(
            "Grid has subject columns",
            found_subjects,
            detail=f"matched {found_subjects} from {list(expected_subjects)}",
        )

        record_property(
            "result_description",
            f"{checks.publish()}. Grid headers: {header_texts}.",
        )

    def test_tc_wpad_dash_02_verify_filter_controls_and_sections(self, record_property):
        """Survey every element on the admin dashboard.

        Each element is a soft check: a missing one is reported as a FAILED row
        in the Element Presence Checks table rather than failing the test, so a
        single run inventories the whole page instead of stopping at the first
        gap. Only reaching the dashboard is a hard precondition.
        """
        dashboard = self.login_as_admin()
        checks = ElementChecks(dashboard, record_property, page_name="Admin Dashboard")

        checks.check("Welcome header", dashboard.PAGE_HEADER)

        checks.check("KPI card — All Items", dashboard.METRIC_CARD_ALL_ITEMS)
        checks.check("KPI card — All Item Sets", dashboard.METRIC_CARD_ALL_SETS)
        checks.check("KPI card — Total Users", dashboard.METRIC_CARD_TOTAL_USERS)
        checks.check("KPI card — QAR Failed", dashboard.METRIC_CARD_QAR_FAILED)

        checks.check("Filter — Apply Filters", dashboard.FILTER_APPLY_BTN)
        checks.check("Filter — Reset Filters", dashboard.FILTER_RESET_BTN)
        checks.check("Filter — Time Period", dashboard.TIME_PERIOD_DROPDOWN)
        checks.check("Filter — Grade", dashboard.GRADE_DROPDOWN)
        checks.check("Filter — Subject", dashboard.SUBJECT_DROPDOWN)

        checks.check("Section — Status Distribution", dashboard.SECTION_STATUS_DIST)
        checks.check("Section — Pipeline Stage Breakdown", dashboard.SECTION_PIPELINE)
        checks.check("Section — User Activity", dashboard.SECTION_ACTIVITY)
        checks.check("Section — Published Items by Grade & Subject", dashboard.SECTION_PUBLISHED_GRID)
        checks.check("Section — Average Review Time by Role", dashboard.SECTION_REVIEW_TIME)
        checks.check("Section — Platform Throughput", dashboard.SECTION_THROUGHPUT)
        checks.check("Section — Active Assignments", dashboard.SECTION_ACTIVE_ASSIGNMENTS)
        checks.check("Section — Question Papers by Grade & Subject", dashboard.SECTION_QP_GRID)

        checks.check("Tab — Platform Overview", dashboard.TAB_PLATFORM_OVERVIEW)
        checks.check("Tab — User Performances", dashboard.TAB_USER_PERFORMANCES)
        checks.check("Tab — QAR Reports", dashboard.TAB_QAR_REPORTS)

        # Branding and page chrome.
        checks.check("Logo", dashboard.LOGO)
        checks.check("Header bar", dashboard.HEADER)
        checks.check("Sidebar nav", dashboard.SIDEBAR_NAV)
        checks.check("Sidebar toggle", dashboard.SIDEBAR_TOGGLE)
        checks.check("Notification bell", dashboard.NOTIFICATION_BELL)

        # Sidebar navigation — every destination the admin can reach.
        for label, prefix in dashboard.NAV_ITEMS.items():
            checks.check(f"Nav — {label}", dashboard.nav_item_locator(prefix))

        # KPI card icons, checked separately from the cards: an icon that fails
        # to load is invisible in a card-level check.
        for card, icon_class in dashboard.KPI_ICONS.items():
            checks.check(f"KPI icon — {card}", dashboard.icon_locator(icon_class))

        # Accessibility / localisation toolbar.
        checks.check("Theme picker", dashboard.THEME_PICKER)
        checks.check("Screen-reader toggle", dashboard.SCREEN_READER_TOGGLE)
        checks.check("Language — EN", dashboard.LANG_EN)
        checks.check("Language — हिंदी", dashboard.LANG_HI)
        font_controls = dashboard.count_visible(dashboard.FONT_SIZE_CONTROLS)
        checks.check_condition(
            "Font-size controls (A / A+ / A++)",
            font_controls >= 3,
            detail=f"{font_controls} visible",
        )

        checks.check("Published Items grid table", dashboard.PUBLISHED_GRID_TABLE)
        checks.check("Question Papers grid table", dashboard.QP_GRID_TABLE)
        checks.check("Audit Trail link", dashboard.AUDIT_TRAIL_LINK)

        # Content-level expectations, recorded the same soft way.
        charts = dashboard.count_visible(dashboard.CHART_SURFACES)
        checks.check_condition(
            "Charts rendered", charts, detail=f"{charts} recharts surfaces visible"
        )
        badge = dashboard.get_notification_badge_text()
        checks.check_condition(
            "Notification badge shows a count",
            badge,
            detail=f"badge: {badge!r}" if badge else "no numeric badge found",
        )
        headers = dashboard.get_published_grid_headers()
        checks.check_condition(
            "Published Items grid has column headers",
            headers,
            detail=f"headers: {headers}" if headers else "no <th> text found",
        )
        qp_headers = dashboard.get_grid_headers(dashboard.QP_GRID_HEADERS)
        checks.check_condition(
            "Question Papers grid has column headers",
            qp_headers,
            detail=f"headers: {qp_headers}" if qp_headers else "no <th> text found",
        )
        activity_logs = dashboard.get_user_activity_logs()
        checks.check_condition(
            "User Activity feed has entries",
            activity_logs,
            detail=f"{len(activity_logs)} entries",
        )

        # Do the controls respond, or are they rendered but dead? Each is driven
        # and the page re-read; nothing here mutates server-side state.
        for label, locator in (
            ("Time Period", dashboard.TIME_PERIOD_DROPDOWN),
            ("Grade", dashboard.GRADE_DROPDOWN),
            ("Subject", dashboard.SUBJECT_DROPDOWN),
        ):
            checks.check_interaction(
                f"Filter opens — {label}",
                lambda control=locator: dashboard.click_element(control),
                lambda: dashboard.is_visible(dashboard.FILTER_APPLY_BTN),
            )
        for label, locator in (
            ("Apply Filters", dashboard.FILTER_APPLY_BTN),
            ("Reset Filters", dashboard.FILTER_RESET_BTN),
        ):
            checks.check_interaction(
                f"Button responds — {label}",
                lambda control=locator: dashboard.click_element(control),
                dashboard.wait_for_dashboard_ready,
            )
        for label, locator in (
            ("Platform Overview", dashboard.TAB_PLATFORM_OVERVIEW),
            ("User Performances", dashboard.TAB_USER_PERFORMANCES),
            ("QAR Reports", dashboard.TAB_QAR_REPORTS),
        ):
            checks.check_interaction(
                f"Tab responds — {label}",
                lambda control=locator: dashboard.click_element(control),
                dashboard.wait_for_dashboard_ready,
            )

        record_property("result_description", checks.publish())

