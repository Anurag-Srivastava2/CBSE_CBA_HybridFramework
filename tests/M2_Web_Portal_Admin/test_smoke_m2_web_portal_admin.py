import pytest

from pages.admin.admin_dashboard_page import AdminDashboardPage
from pages.admin.item_bank_page import ItemBankPage
from pages.admin.user_management_page import UserManagementPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig
from utilities.smoke_support import sign_in


@pytest.mark.smoke
# All three checks drive the single admin account, so they share an xdist
# group and run on one worker under `--dist loadgroup`.
@pytest.mark.xdist_group("smoke-admin")
# The portal intermittently fails to complete a sign-in, leaving the login
# form on screen until login_to_application() exhausts its retries. It lands
# on a different check each run — observed on M5 twice and here once — so
# every smoke class carries one retry rather than whichever one happened to
# be hit last. The retry badge keeps each occurrence visible.
@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestSmokeM2WebPortalAdmin:
    """M2 - Web Portal Admin smoke: the admin landing screens load and hold data.

    Read-only by design — no user, role or item is created, edited or retired.
    """

    @staticmethod
    def admin_username():
        return ReadConfig.get_admin_username()

    def sign_in_as_admin(self):
        sign_in(self.driver, self.admin_username())

    def test_smoke_m2_01_admin_dashboard_kpis_render(self, record_property):
        """Admin lands on the dashboard and its KPI cards carry real numbers."""
        self.sign_in_as_admin()
        dashboard = AdminDashboardPage(self.driver)
        dashboard.wait_for_dashboard_ready()

        # Additive only: every assertion below stays exactly as hard as it
        # was, so the smoke gate still fails loudly and fast.
        checks = ElementChecks(
            dashboard, record_property, page_name="Admin Dashboard — Smoke"
        )
        checks.check("Welcome header", dashboard.PAGE_HEADER, timeout=2)
        checks.check("Header bar", dashboard.HEADER, timeout=2)
        checks.check("Sidebar nav", dashboard.SIDEBAR_NAV, timeout=2)
        checks.check("Notification bell", dashboard.NOTIFICATION_BELL, timeout=2)
        for label, locator in (
            ("All Items", dashboard.METRIC_CARD_ALL_ITEMS),
            ("All Item Sets", dashboard.METRIC_CARD_ALL_SETS),
            ("Total Users", dashboard.METRIC_CARD_TOTAL_USERS),
            ("QAR Failed", dashboard.METRIC_CARD_QAR_FAILED),
        ):
            checks.check(f"KPI card — {label}", locator, timeout=2)
        for label, locator in (
            ("Status Distribution", dashboard.SECTION_STATUS_DIST),
            ("Pipeline Stage Breakdown", dashboard.SECTION_PIPELINE),
            ("User Activity", dashboard.SECTION_ACTIVITY),
            ("Published Items by Grade & Subject", dashboard.SECTION_PUBLISHED_GRID),
        ):
            checks.check(f"Section — {label}", locator, timeout=2)
        for label in dashboard.NAV_ITEMS:
            checks.check(f"Nav — {label}", dashboard.nav_item_locator(dashboard.NAV_ITEMS[label]), timeout=2)

        welcome_message = dashboard.get_welcome_text()
        metrics = {
            "All Items": dashboard.get_metric_value(dashboard.METRIC_CARD_ALL_ITEMS),
            "All Item Sets": dashboard.get_metric_value(dashboard.METRIC_CARD_ALL_SETS),
            "Total Users": dashboard.get_metric_value(dashboard.METRIC_CARD_TOTAL_USERS),
            "QAR Failed": dashboard.get_metric_value(dashboard.METRIC_CARD_QAR_FAILED),
        }
        record_property(
            "result_description",
            f"Admin dashboard loaded for {self.admin_username()} — {metrics}. "
            f"{checks.publish()}",
        )

        assert "Hello" in welcome_message, (
            f"Expected the admin welcome greeting, got: {welcome_message}"
        )
        unreadable_cards = [name for name, value in metrics.items() if value is None]
        assert not unreadable_cards, f"Dashboard KPI cards missing or non-numeric: {unreadable_cards}"

    def test_smoke_m2_02_item_bank_overview_loads(self, record_property):
        """Item Bank Overview renders its table with the expected columns."""
        self.sign_in_as_admin()
        item_bank = ItemBankPage(self.driver)
        item_bank.open(ReadConfig.get_base_url())

        checks = ElementChecks(
            item_bank, record_property, page_name="Item Bank Overview — Smoke"
        )
        checks.check_condition("Page header and subtext", item_bank.is_on_page)
        checks.check("Filters button", item_bank.FILTERS_BTN, timeout=2)
        checks.check("Export button", item_bank.EXPORT_BTN, timeout=2)
        checks.check("Item table", item_bank.TABLE, timeout=2)
        checks.check("Showing summary", item_bank.SHOWING_SUMMARY, timeout=2)
        missing_tabs = checks.safe_call(item_bank.missing_tabs)
        for label in item_bank.TAB_LABELS:
            checks.check_condition(f"Tab — {label}", label not in missing_tabs)
        missing_kpis = checks.safe_call(item_bank.missing_kpis)
        for label in item_bank.KPI_LABELS:
            checks.check_condition(f"KPI card — {label}", label not in missing_kpis)

        missing_columns = item_bank.missing_columns()
        for column in item_bank.EXPECTED_COLUMNS:
            checks.check_condition(f"Column — {column}", column not in missing_columns)
        row_count = len(item_bank.get_rows())
        record_property(
            "result_description",
            f"Item Bank Overview loaded with {row_count} row(s) on the first page. "
            f"{checks.publish()}",
        )

        assert item_bank.is_on_page(), "Item Bank Overview header/subtext did not render"
        assert not missing_columns, f"Item Bank table is missing columns: {missing_columns}"

    def test_smoke_m2_03_user_management_lists_accounts(self, record_property):
        """User Management opens and returns the account listing."""
        self.sign_in_as_admin()
        user_management = UserManagementPage(self.driver)
        user_management.open(ReadConfig.get_base_url())

        checks = ElementChecks(
            user_management, record_property, page_name="User Management — Smoke"
        )
        checks.check("Page heading", user_management.PAGE_HEADING, timeout=2)
        checks.check("Search box", user_management.SEARCH_INPUT, timeout=2)
        checks.check("Button — Create User", user_management.CREATE_USER_BTN, timeout=2)
        checks.check("Account rows", user_management.TABLE_ROWS, timeout=2)

        listed_users = user_management.get_listed_users()
        record_property(
            "result_description",
            f"User Management listed {len(listed_users)} account(s) on the first page. "
            f"{checks.publish()}",
        )

        assert listed_users, "User Management rendered no accounts, so RBAC administration is blocked"
        assert all(user["code"] for user in listed_users), (
            f"Some listed accounts have no user code: {listed_users}"
        )
