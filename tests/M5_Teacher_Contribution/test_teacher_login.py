import pytest
from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from utilities.read_config import ReadConfig
from utilities.logger import LogGenerator


# Signs in as the shared teacher account; the portal keeps one active session
# per account, so another worker signing in as the same user invalidates this
# session mid-test.
@pytest.mark.serial
# The teacher dashboard intermittently fails to paint within the wait even
# after the login itself succeeds — the same post-login stall the M1 smoke
# checks hit. This test is part of the smoke gate, where a known environment
# stall reading as a product failure trains people to ignore the gate, so
# allow one clean retry; the Extent report's retry badge keeps it visible.
@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestTeacherLogin:
    logger = LogGenerator.loggen()

    def test_teacher_valid_login(self):
        self.logger.info("Starting teacher valid login test")

        self.driver.get(ReadConfig.get_base_url())
        self.logger.info("Opened application URL")

        login_page = LoginPage(self.driver)
        login_page.login_to_application(
            ReadConfig.get_username(),
            ReadConfig.get_password()
        )
        self.logger.info("Submitted login form")

        dashboard_page = DashboardPage(self.driver)
        assert dashboard_page.is_dashboard_loaded() is True

        self.logger.info("Teacher login test passed")
