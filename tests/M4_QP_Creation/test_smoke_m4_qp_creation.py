import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pages.teacher.dashboard_page import DashboardPage
from pages.teacher.question_paper_builder_page import QuestionPaperBuilderPage
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

    # The QP suites drive teacher2 so they do not contend with the M5 teacher
    # contribution flows, which use the primary teacher account.
    QP_TEACHER_USERNAME = "teacher2@dev.com"

    def sign_in_as_teacher(self):
        sign_in(self.driver, self.QP_TEACHER_USERNAME)
        # Login can land behind a welcome/announcement popup that swallows the
        # first navigation click.
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        assert DashboardPage(self.driver).is_dashboard_loaded(), (
            f"{self.QP_TEACHER_USERNAME} did not land on the teacher dashboard"
        )

    def test_smoke_m4_01_qp_builder_opens_with_creation_modes(self, record_property):
        """QP Builder reaches Assessment Configuration and offers its creation modes."""
        self.sign_in_as_teacher()
        builder = QuestionPaperBuilderPage(self.driver)
        builder.open()

        creation_modes = builder.get_creation_modes()
        record_property(
            "result_description",
            f"QP Builder opened for {self.QP_TEACHER_USERNAME} with creation modes: "
            f"{sorted(creation_modes) or 'none'}.",
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

        create_button_visible = builder.is_element_visible_quick(
            self.CREATE_NEW_PAPER_BUTTON, timeout=20
        )
        record_property(
            "result_description",
            f"My QP listing opened for {self.QP_TEACHER_USERNAME}; "
            f"'Create New Paper' available: {create_button_visible}.",
        )

        assert "my qp" in builder.body_text_casefold(), "My QP listing did not render"
        assert create_button_visible, (
            "'Create New Paper' is not available, so no question paper can be started"
        )
