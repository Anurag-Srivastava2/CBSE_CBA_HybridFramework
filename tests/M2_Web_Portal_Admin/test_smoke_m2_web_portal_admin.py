import pytest

from pages.admin.admin_dashboard_page import AdminDashboardPage
from pages.admin.item_bank_page import ItemBankPage
from pages.admin.user_management_page import UserManagementPage
from utilities.read_config import ReadConfig
from utilities.smoke_support import sign_in


@pytest.mark.smoke
# Shares the single admin account with the M3 smoke probe, so both sit in one
# xdist group and run on the same worker under `--dist loadgroup`.
@pytest.mark.xdist_group("smoke-admin")
@pytest.mark.usefixtures("setup")
class TestSmokeM2WebPortalAdmin:
    """M2 - Web Portal Admin smoke: the admin landing screens load and hold data.

    Read-only by design — no user, role or item is created, edited or retired.
    """

    @staticmethod
    def admin_username():
        return ReadConfig.get_role_usernames("admin")[0]

    def sign_in_as_admin(self):
        sign_in(self.driver, self.admin_username())

    def test_smoke_m2_01_admin_dashboard_kpis_render(self, record_property):
        """Admin lands on the dashboard and its KPI cards carry real numbers."""
        self.sign_in_as_admin()
        dashboard = AdminDashboardPage(self.driver)
        dashboard.wait_for_dashboard_ready()

        welcome_message = dashboard.get_welcome_text()
        metrics = {
            "All Items": dashboard.get_metric_value(dashboard.METRIC_CARD_ALL_ITEMS),
            "All Item Sets": dashboard.get_metric_value(dashboard.METRIC_CARD_ALL_SETS),
            "Total Users": dashboard.get_metric_value(dashboard.METRIC_CARD_TOTAL_USERS),
            "QAR Failed": dashboard.get_metric_value(dashboard.METRIC_CARD_QAR_FAILED),
        }
        record_property(
            "result_description",
            f"Admin dashboard loaded for {self.admin_username()} — {metrics}.",
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

        missing_columns = item_bank.missing_columns()
        row_count = len(item_bank.get_rows())
        record_property(
            "result_description",
            f"Item Bank Overview loaded with {row_count} row(s) on the first page.",
        )

        assert item_bank.is_on_page(), "Item Bank Overview header/subtext did not render"
        assert not missing_columns, f"Item Bank table is missing columns: {missing_columns}"

    def test_smoke_m2_03_user_management_lists_accounts(self, record_property):
        """User Management opens and returns the account listing."""
        self.sign_in_as_admin()
        user_management = UserManagementPage(self.driver)
        user_management.open(ReadConfig.get_base_url())

        listed_users = user_management.get_listed_users()
        record_property(
            "result_description",
            f"User Management listed {len(listed_users)} account(s) on the first page.",
        )

        assert listed_users, "User Management rendered no accounts, so RBAC administration is blocked"
        assert all(user["code"] for user in listed_users), (
            f"Some listed accounts have no user code: {listed_users}"
        )
