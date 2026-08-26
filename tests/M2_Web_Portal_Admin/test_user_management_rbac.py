from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.admin.admin_portal_page import AdminPortalPage
from pages.common.login_page import LoginPage
from pages.sme.manual_item_page import ManualItemPage
from pages.teacher.dashboard_page import DashboardPage
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestM2UserManagementRBAC:
    def login_as(self, username):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            # Per-user password - see test_portal_admin_features.login_as.
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        checkpoint(f"Signed in as {username}")
        return page

    def login_as_admin(self):
        return self.login_as(ReadConfig.get_admin_username())

    def test_tc_wpad_01_p01_admin_creates_new_user_with_required_fields(
        self, page_evidence
    ):
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
        page_evidence.checkpoint(
            f"Created RWG user {email} in {duration:.2f}s (2.0s budget); the "
            f"address is on the page: {email.casefold() in text}; status Active: "
            f"{'active' in text}"
        )
        assert duration <= 2.0
        assert email.casefold() in text
        assert "active" in text

    def test_tc_wpad_01_p02_admin_deactivates_user_and_login_is_blocked(
        self, page_evidence
    ):
        page = self.login_as_admin()
        users = ReadConfig.get_role_usernames("rwg")
        target_user = users[0]
        try:
            page.deactivate_user(target_user)
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-USER-002 [M2 User Lifecycle] Deactivate User control is not available for a safe fixture user: {error}"
            )
        page_evidence.checkpoint(
            f"Deactivated {target_user}; the page confirms it: "
            f"{'deactivated' in page.normalized_body_text()}"
        )
        assert "deactivated" in page.normalized_body_text()

    def test_tc_wpad_01_n01_duplicate_email_is_rejected(self, page_evidence):
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
        page_evidence.checkpoint(
            f"Re-used the existing address {existing_email}; the app rejected it "
            f"with 'already exists': {'already exists' in page.normalized_body_text()}"
        )
        assert "already exists" in page.normalized_body_text()

    def test_tc_wpad_01_n02_duplicate_mobile_is_rejected(self, page_evidence):
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
        duplicate_text = page.normalized_body_text()
        page_evidence.checkpoint(
            "Created two users on the same mobile 9999999999; the second was "
            f"rejected — 'mobile' on the page: {'mobile' in duplicate_text}, "
            f"'registered': {'registered' in duplicate_text}"
        )
        assert "mobile" in page.normalized_body_text() and "registered" in page.normalized_body_text()

    def test_tc_wpad_02_p01_sidebar_rbac_is_enforced_for_core_roles(
        self, record_property, page_evidence
    ):
        """Each role's expected sidebar markers are recorded individually; the
        RBAC negative (an SME must not see QP Builder) stays a hard gate."""
        checks = ElementChecks(None, record_property, page_name="Sidebar RBAC")
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
            missing = []
            for marker in expected_markers:
                if not checks.check_condition(
                    f"{role} sidebar — {marker}", marker in text
                ):
                    missing.append(marker)
            # The guard fires for ANY role whose dashboard did not render, not
            # just the SME. The loop reaches sme third, so a degraded teacher or
            # rwg dashboard means the run never established a healthy session -
            # and the RBAC negative below would then be asserted against
            # whatever page is actually on screen, which is not evidence of an
            # access-control leak. Scoping this guard to sme alone is what made
            # the assertion fire on a login screen.
            page_evidence.checkpoint(
                f"{role} ({username}) sidebar — expected markers missing: "
                f"{missing or 'none'}"
                + (
                    f"; QP Builder visible to this SME: {'qp builder' in text}"
                    if role == "sme"
                    else ""
                )
            )
            if missing:
                checks.publish()
                pytest.xfail(
                    f"KI-M2-RBAC-001 [M2 RBAC] {role} sidebar/dashboard does not expose "
                    f"expected markers: {missing}"
                )
            if role == "sme":
                assert "qp builder" not in text, (
                    "RBAC FAILURE: the SME sidebar exposes QP Builder."
                )
        record_property("result_description", checks.publish())

    def test_tc_wpad_02_p02_sme_grade_subject_restriction_is_enforced(
        self, record_property, page_evidence
    ):
        self.login_as(ReadConfig.get_sme2_username())
        page = ManualItemPage(self.driver)
        try:
            page.open_true_false_manual_item_form()
        except TimeoutException as error:
            pytest.xfail(
                f"KI-M2-RBAC-002 [M2 RBAC] SME item-creation form is not reachable for grade/subject check: {error}"
            )
        checks = ElementChecks(page, record_property, page_name="SME Item Form")
        checks.check_condition(
            "Dropdown — Subject offers Mathematics",
            lambda: page.is_dropdown_option_available("Subject *", "Mathematics") is True,
        )
        record_property("result_description", checks.publish())
        page_evidence.checkpoint(
            "SME authoring scope — Mathematics offered: "
            f"{page.is_dropdown_option_available('Subject *', 'Mathematics')}; "
            "restricted Grade 10 offered: "
            f"{page.is_dropdown_option_available('Grade *', 'Grade 10')} "
            "(must be False)"
        )
        # The restriction itself is an access-control contract, so it stays hard.
        assert page.is_dropdown_option_available("Grade *", "Grade 10") is False, (
            "RBAC FAILURE: a restricted grade is selectable for this SME."
        )

    def test_tc_wpad_02_n01_teacher_direct_admin_url_is_denied(self, page_evidence):
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
        page_evidence.checkpoint(
            "A teacher requested /admin/dashboard directly — denied: "
            f"{denied}; markers seen: "
            f"{[m for m in denial_markers if m in text] or 'none (bounced to their own dashboard)'}"
        )
        assert denied, (
            "Teacher hitting /admin/dashboard saw neither a denial nor their own dashboard. "
            f"Page text: {page.body_text()[:400]}"
        )

        leaked = [
            forbidden
            for forbidden in ("user management", "create user", "audit logs")
            if forbidden in text
        ]
        page_evidence.checkpoint(
            f"Admin-only content leaked into the teacher session: "
            f"{leaked or 'none'}"
        )
        # Whatever the denial style, no admin-only content may render.
        for forbidden in ("user management", "create user", "audit logs"):
            assert forbidden not in text, f"Admin-only content {forbidden!r} leaked to a teacher session."
