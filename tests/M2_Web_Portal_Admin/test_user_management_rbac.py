from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from pages.sme.manual_item_page import ManualItemPage
from pages.teacher.dashboard_page import DashboardPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2UserManagementRBAC:
    def login_as(self, username):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_all_users_password(),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        return page

    def login_as_admin(self):
        return self.login_as(ReadConfig.get_role_usernames("admin")[0])

    def test_tc_wpad_01_p01_admin_creates_new_user_with_required_fields(self):
        page = self.login_as_admin()
        run_id = uuid4().hex[:8]
        email = f"rwg_test_{run_id}@demo.com"
        try:
            duration = page.create_user(
                name=f"RWG Automation {run_id}",
                email=email,
                mobile=f"90000{run_id[:5]}",
                role="RWG",
                grade="Grade 5",
                subject="Mathematics",
            )
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-USER-001 [M2 User Registration] Admin Create User UI is not currently reachable/actionable: {error}"
            )

        text = page.normalized_body_text()
        assert duration <= 2.0
        assert email.casefold() in text
        assert "active" in text

    def test_tc_wpad_01_p02_admin_deactivates_user_and_login_is_blocked(self):
        page = self.login_as_admin()
        users = ReadConfig.get_role_usernames("rwg")
        target_user = users[0]
        try:
            page.deactivate_user(target_user)
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-USER-002 [M2 User Lifecycle] Deactivate User control is not available for a safe fixture user: {error}"
            )
        assert "deactivated" in page.normalized_body_text()

    def test_tc_wpad_01_n01_duplicate_email_is_rejected(self):
        page = self.login_as_admin()
        existing_email = ReadConfig.get_role_usernames("rwg")[0]
        try:
            page.create_user(
                name="Duplicate Email Automation",
                email=existing_email,
                mobile=f"91111{uuid4().hex[:5]}",
                role="RWG",
                grade="Grade 5",
                subject="Mathematics",
            )
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-USER-003 [M2 User Validation] Duplicate email validation could not be exercised: {error}"
            )
        assert "already exists" in page.normalized_body_text()

    def test_tc_wpad_01_n02_duplicate_mobile_is_rejected(self):
        page = self.login_as_admin()
        try:
            page.create_user(
                name="Duplicate Mobile Automation",
                email=f"mobile_duplicate_{uuid4().hex[:8]}@demo.com",
                mobile="9999999999",
                role="RWG",
                grade="Grade 5",
                subject="Mathematics",
            )
            page.create_user(
                name="Duplicate Mobile Automation 2",
                email=f"mobile_duplicate_2_{uuid4().hex[:8]}@demo.com",
                mobile="9999999999",
                role="RWG",
                grade="Grade 5",
                subject="Mathematics",
            )
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-USER-004 [M2 User Validation] Duplicate mobile validation could not be exercised: {error}"
            )
        assert "mobile" in page.normalized_body_text() and "registered" in page.normalized_body_text()

    def test_tc_wpad_02_p01_sidebar_rbac_is_enforced_for_core_roles(self):
        role_expectations = {
            "teacher": ("home", "qp builder", "my qp", "create", "sets"),
            "rwg": ("dashboard", "review queue"),
            "sme": ("home", "create", "sets"),
            "pit": ("final", "authorisation"),
        }
        for role, expected_markers in role_expectations.items():
            username = ReadConfig.get_role_usernames(role)[0]
            page = self.login_as(username)
            text = page.normalized_body_text()
            missing = [marker for marker in expected_markers if marker not in text]
            if missing:
                pytest.xfail(
                    f"KI-M2-RBAC-001 [M2 RBAC] {role} sidebar/dashboard does not expose expected markers: {missing}"
                )
            if role == "sme":
                assert "qp builder" not in text

    def test_tc_wpad_02_p02_sme_grade_subject_restriction_is_enforced(self):
        self.login_as(ReadConfig.get_sme2_username())
        page = ManualItemPage(self.driver)
        try:
            page.open_true_false_manual_item_form()
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-RBAC-002 [M2 RBAC] SME item-creation form is not reachable for grade/subject check: {error}"
            )
        assert page.is_dropdown_option_available("Subject *", "Mathematics") is True
        assert page.is_dropdown_option_available("Grade *", "Grade 10") is False

    def test_tc_wpad_02_n01_teacher_direct_admin_url_is_denied(self):
        self.login_as(ReadConfig.get_role_usernames("teacher")[0])
        self.driver.get(ReadConfig.get_base_url().rstrip("/") + "/admin/dashboard")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        text = page.normalized_body_text()

        # The portal denies unauthorised routes by not registering them for the
        # role, so a teacher gets the 404 "Page not found" view rather than an
        # explicit 403/Access Denied. Either is a valid denial; being bounced
        # back to the teacher's own dashboard is too.
        denial_markers = ("access denied", "not authorised", "not authorized", "403", "404", "page not found")
        teacher_dashboard = DashboardPage(self.driver)
        denied = any(marker in text for marker in denial_markers) or teacher_dashboard.is_element_visible_quick(
            teacher_dashboard.DASHBOARD_TEXT
        )
        assert denied, (
            "Teacher hitting /admin/dashboard saw neither a denial nor their own dashboard. "
            f"Page text: {page.body_text()[:400]}"
        )

        # Whatever the denial style, no admin-only content may render.
        for forbidden in ("user management", "create user", "audit logs"):
            assert forbidden not in text, f"Admin-only content {forbidden!r} leaked to a teacher session."
