import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.teacher.dashboard_page import DashboardPage
from pages.teacher.question_paper_builder_page import QuestionPaperBuilderPage
from tests.M4_QP_Creation.qp_surveys import survey_builder, survey_chrome, survey_my_qp
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig
from utilities.smoke_support import sign_in


@pytest.mark.smoke
# Drives the same teacher account across both checks, and the portal keeps one
# active session per account, so they share an xdist group.
@pytest.mark.xdist_group("smoke-m4")
# Same intermittent sign-in stall the other smoke classes carry a retry for:
# the portal leaves the login form on screen until login_to_application()
# exhausts its retries, and it lands on a different check each run.
@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestSmokeM4QPCreation:
    """M4 - QP Creation smoke: the question-paper builder opens for a teacher.

    Read-only by design — a paper is neither built nor published, so the check
    leaves no draft behind for the fuller M4 suites to trip over.
    """

    CREATE_NEW_PAPER_BUTTON = (By.XPATH, "//button[contains(normalize-space(),'Create New Paper')]")

    # The QP suites drive a non-primary teacher so they do not contend with the
    # M5 teacher contribution flows, which use the primary teacher account.
    # Resolved per xdist worker rather than hardcoded, so parallel workers do
    # not sign each other out of the one account.
    @property
    def qp_teacher_username(self):
        return ReadConfig.get_qp_teacher_username()

    def sign_in_as_teacher(self):
        username = self.qp_teacher_username
        sign_in(self.driver, username)
        # Login can land behind a welcome/announcement popup that swallows the
        # first navigation click.
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        assert DashboardPage(self.driver).is_dashboard_loaded(), (
            f"{username} did not land on the teacher dashboard"
        )

    def test_smoke_m4_01_qp_builder_opens_with_creation_modes(self, record_property):
        """QP Builder reaches Assessment Configuration and offers its creation modes."""
        self.sign_in_as_teacher()
        builder = QuestionPaperBuilderPage(self.driver)
        builder.open()

        # Additive only: every assertion below stays exactly as hard as it
        # was, so the smoke gate still fails loudly and fast.
        checks = ElementChecks(
            builder, record_property, page_name="QP Builder — Smoke"
        )
        survey_chrome(checks, builder)
        survey_builder(checks, builder, mode="Manual Build")

        creation_modes = builder.get_creation_modes()
        record_property(
            "result_description",
            f"QP Builder opened for {self.qp_teacher_username} with creation modes: "
            f"{sorted(creation_modes) or 'none'}. {checks.publish()}",
        )

        assert "assessment configuration" in builder.body_text_casefold(), (
            "QP Builder did not reach the Assessment Configuration step"
        )
        # Hybrid mode is a known product gap (KI-M4-QP-001), so smoke requires
        # only the two modes the build actually ships.
        missing_modes = {"Manual", "Automated"} - creation_modes
        assert not missing_modes, f"QP Builder is missing creation modes: {sorted(missing_modes)}"

    def test_smoke_m4_02_my_qp_listing_opens(self, record_property):
        """My QP renders the teacher's papers listing and the create entry point."""
        self.sign_in_as_teacher()
        builder = QuestionPaperBuilderPage(self.driver)
        builder.open_my_qp()

        checks = ElementChecks(
            builder, record_property, page_name="My QP — Smoke"
        )
        survey_chrome(checks, builder)
        survey_my_qp(checks, builder)

        create_button_visible = builder.is_element_visible_quick(
            self.CREATE_NEW_PAPER_BUTTON, timeout=20
        )
        record_property(
            "result_description",
            f"My QP listing opened for {self.qp_teacher_username}; "
            f"'Create New Paper' available: {create_button_visible}. {checks.publish()}",
        )

        assert "my qp" in builder.body_text_casefold(), "My QP listing did not render"
        assert create_button_visible, (
            "'Create New Paper' is not available, so no question paper can be started"
        )
