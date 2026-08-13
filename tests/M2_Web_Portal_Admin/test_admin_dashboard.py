import pytest

from pages.admin.admin_dashboard_page import AdminDashboardPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2AdminDashboard:
    """TC-WPAD-DASH-* : admin landing dashboard KPI cards, filters, activity
    feed and published-items grid."""

    def login_as_admin(self):
        username = ReadConfig.get_role_usernames("admin")[0]
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        dashboard = AdminDashboardPage(self.driver)
        dashboard.wait_for_dashboard_ready()
        return dashboard

    def test_tc_wpad_dash_01_verify_header_and_kpi_cards(self, record_property):
        """Top metric cards exist and hold valid non-negative integer values."""
        dashboard = self.login_as_admin()

        welcome_message = dashboard.get_welcome_text()
        assert "Hello" in welcome_message, f"Expected welcome greeting, got: {welcome_message}"

        all_items = dashboard.get_metric_value(dashboard.METRIC_CARD_ALL_ITEMS)
        all_sets = dashboard.get_metric_value(dashboard.METRIC_CARD_ALL_SETS)
        total_users = dashboard.get_metric_value(dashboard.METRIC_CARD_TOTAL_USERS)
        qar_failed = dashboard.get_metric_value(dashboard.METRIC_CARD_QAR_FAILED)

        record_property(
            "result_description",
            f"Admin dashboard KPIs — All Items: {all_items}, All Item Sets: {all_sets}, "
            f"Total Users: {total_users}, QAR Failed: {qar_failed}.",
        )

        assert all_items is not None and all_items >= 0, "All Items metric is missing or non-numeric"
        assert all_sets is not None and all_sets >= 0, "All Item Sets metric is missing or non-numeric"
        assert total_users is not None and total_users > 0, "Total Users metric should be greater than 0"
        assert qar_failed is not None and qar_failed >= 0, "QAR Failed metric is missing or non-numeric"

    def test_tc_wpad_dash_02_verify_filter_controls_and_sections(self, record_property):
        """Dashboard filter controls and the standard analytics widgets render."""
        dashboard = self.login_as_admin()

        missing_filters = dashboard.missing_filter_controls()
        assert not missing_filters, f"Dashboard filter controls not visible: {missing_filters}"

        sections = {
            "Status Distribution": dashboard.SECTION_STATUS_DIST,
            "Pipeline Stage Breakdown": dashboard.SECTION_PIPELINE,
            "User Activity": dashboard.SECTION_ACTIVITY,
            "Published Items by Grade & Subject": dashboard.SECTION_PUBLISHED_GRID,
        }
        missing_sections = [name for name, locator in sections.items() if not dashboard.is_visible(locator)]
        record_property(
            "result_description",
            "Admin dashboard filters and all four analytics sections rendered.",
        )
        assert not missing_sections, f"Dashboard sections missing: {missing_sections}"

    def test_tc_wpad_dash_03_verify_dynamic_activity_feed_format(self, record_property):
        """Activity feed entries carry relative timestamps and the audit link is present."""
        dashboard = self.login_as_admin()

        assert dashboard.is_visible(dashboard.AUDIT_TRAIL_LINK), "Audit Trail navigation link missing"

        activity_logs = dashboard.get_user_activity_logs()
        assert activity_logs, "User Activity log feed is empty"

        timestamped = dashboard.get_relative_timestamp_entries()
        record_property(
            "result_description",
            f"User Activity feed rendered {len(activity_logs)} entries, "
            f"{len(timestamped)} with relative timestamps.",
        )
        assert timestamped, (
            "No relative timestamps ('Just now', 'x min ago') found in the activity feed. "
            f"Sample entries: {activity_logs[:5]}"
        )

    def test_tc_wpad_dash_04_verify_published_items_grid_structure(self, record_property):
        """Published Items matrix renders with a Grade column and subject columns."""
        dashboard = self.login_as_admin()

        assert dashboard.is_visible(dashboard.PUBLISHED_GRID_TABLE), "Published Items grid table is not rendered"

        header_texts = dashboard.get_published_grid_headers()
        record_property(
            "result_description",
            f"Published Items grid headers: {header_texts}.",
        )

        assert any("grade" in header.casefold() for header in header_texts), (
            f"Grid table missing a 'Grade' column header. Headers found: {header_texts}"
        )
        assert any(
            subject.casefold() in (header.casefold() for header in header_texts)
            for subject in ("Mathematics", "English", "Science", "Total")
        ), f"Grid table missing subject headers. Headers found: {header_texts}"
