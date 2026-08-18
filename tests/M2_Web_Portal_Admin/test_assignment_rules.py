import pytest

from pages.admin.assignment_queue_page import AssignmentQueuePage
from pages.admin.user_management_page import UserManagementPage
from pages.common.login_page import LoginPage
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig


UNASSIGNED_MARKERS = {"unassigned", "-", "", "—", "n/a"}


@pytest.mark.rtm
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestM2AssignmentQueueAutoAssignment:
    """TC-WPAD-ASSIGN-01: taking a review role offline must strip its pending
    assignments, and restoring a reviewer must route that work back.

    The RWG population is enumerated through the grid's Roles filter, not a
    name search: several RWG holders are named after their subject
    ('SocSci SME', 'Maths SME'), so a name search silently misses them and the
    role is never actually taken offline.

    Every account this test disables is re-enabled in a finally block, so the
    shared environment is handed back unchanged. Marked `serial` because other
    RBAC tests sign in as RWG users.
    """

    ROLE_LABEL = "RWG role"
    STAGE = "RWG"

    def login_as_admin(self):
        username = ReadConfig.get_admin_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )

    def open_users(self):
        page = UserManagementPage(self.driver)
        page.open(ReadConfig.get_base_url())
        return page

    def open_queue(self):
        page = AssignmentQueuePage(self.driver)
        page.open(ReadConfig.get_base_url())
        return page

    def set_user_active(self, users_page, name, should_be_active):
        """Drive a user's status to the requested state; True if it changed."""
        users_page.search_user(name)
        if not users_page.is_user_listed(name):
            return False
        if users_page.is_user_active(name) == should_be_active:
            return False
        users_page.toggle_user_status(name)
        return True

    def overdue_stage_assignees(self):
        queue = self.open_queue()
        queue.filter_by_stage(self.STAGE)
        queue.filter_by_status("Overdue")
        return queue.get_assigned_users_in_view()

    def test_tc_wpad_assign_01_inactive_role_unassigns_and_reactivation_reassigns(
        self, record_property
    ):
        self.login_as_admin()
        users_page = self.open_users()

        # Deactivating a role holder mutates shared state, so everything below
        # the survey stays a hard gate.
        checks = ElementChecks(users_page, record_property, page_name="User Management — Roles")
        checks.check_condition(
            f"Role holders listed — {self.ROLE_LABEL}",
            lambda: users_page.find_users_by_role(self.ROLE_LABEL),
        )
        checks.publish()

        rwg_users = users_page.find_users_by_role(self.ROLE_LABEL)
        if not rwg_users:
            # Missing fixture data is not a product defect - and this is the
            # same judgement the "no active holder" branch below already makes,
            # so asserting here was inconsistent with the rest of the test.
            pytest.skip(
                f"No user holds {self.ROLE_LABEL} in this environment, so the "
                "unassign/reassign rule cannot be exercised."
            )
        active_rwg = [user for user in rwg_users if user["status"].casefold() == "active"]
        inactive_names = {
            user["name"].casefold() for user in rwg_users if user["status"].casefold() != "active"
        }
        record_property(
            "result_description",
            f"{self.ROLE_LABEL} holders: {[u['name'] for u in rwg_users]}; "
            f"active at start: {[u['name'] for u in active_rwg]}",
        )
        if not active_rwg:
            pytest.skip(f"No active {self.ROLE_LABEL} account is available to exercise the rule.")

        primary_user = active_rwg[0]["name"]
        deactivated = []

        try:
            # --- Step 1: take the whole role offline --------------------------
            record_property("result_checkpoint", "Step 1 — deactivate every active RWG holder")
            for user in active_rwg:
                if self.set_user_active(users_page, user["name"], should_be_active=False):
                    deactivated.append(user["name"])
            assert deactivated, f"Could not deactivate any {self.ROLE_LABEL} account."
            for name in deactivated:
                users_page.search_user(name)
                assert not users_page.is_user_active(name), f"{name} still reads Active."

            # --- Step 2: no offline reviewer may retain pending work ----------
            record_property("result_checkpoint", "Step 2 — offline role holds no pending work")
            offline_names = inactive_names | {name.casefold() for name in deactivated}
            assignees = self.overdue_stage_assignees()
            still_assigned = sorted(
                {
                    name
                    for name in assignees
                    if name.casefold() not in UNASSIGNED_MARKERS and name.casefold() in offline_names
                }
            )
            record_property(
                "result_description",
                f"Overdue {self.STAGE} assignees while the role is offline: {sorted(set(assignees))}",
            )
            if still_assigned:
                pytest.xfail(
                    "KI-M2-ASSIGN-001 [M2 Assignment Queue] Overdue "
                    f"{self.STAGE} work stays assigned to deactivated reviewers "
                    f"{still_assigned} instead of falling back to Unassigned."
                )

            # --- Step 3: bring the primary reviewer back ----------------------
            record_property("result_checkpoint", "Step 3 — reactivate the primary reviewer")
            users_page = self.open_users()
            self.set_user_active(users_page, primary_user, should_be_active=True)
            users_page.search_user(primary_user)
            assert users_page.is_user_active(primary_user), (
                f"{primary_user} did not return to Active after reactivation."
            )
            deactivated = [name for name in deactivated if name != primary_user]

            # --- Step 4: work routes back to the active reviewer --------------
            record_property("result_checkpoint", "Step 4 — work routes to the active reviewer")
            updated = self.overdue_stage_assignees()
            record_property(
                "result_description",
                f"Overdue {self.STAGE} assignees after reactivating {primary_user!r}: "
                f"{sorted(set(updated))}",
            )
            assert updated, f"No overdue {self.STAGE} items found to verify auto-assignment."
            misrouted = sorted(
                {
                    name
                    for name in updated
                    if name.casefold() not in UNASSIGNED_MARKERS
                    and primary_user.casefold() not in name.casefold()
                }
            )
            if misrouted:
                pytest.xfail(
                    "KI-M2-ASSIGN-002 [M2 Assignment Queue] Overdue "
                    f"{self.STAGE} work did not re-route to the only active reviewer "
                    f"{primary_user!r}; it is still held by {misrouted}."
                )

        finally:
            # Always hand the environment back the way we found it.
            if deactivated:
                restore_failures = []
                try:
                    restore_page = self.open_users()
                    for name in deactivated:
                        try:
                            self.set_user_active(restore_page, name, should_be_active=True)
                        except Exception as error:
                            restore_failures.append(f"{name}: {error}")
                except Exception as error:
                    restore_failures.append(str(error))
                if restore_failures:
                    pytest.fail(
                        "RWG accounts could not be reactivated and are still disabled in the "
                        f"environment: {restore_failures}"
                    )
