from selenium.webdriver.common.by import By
from pages.common.base_page import BasePage


class DashboardPage(BasePage):
    # Update this locator after login page opens dashboard.
    # Keep one stable dashboard element here, for example: heading, user profile, logout button, or dashboard card.
    DASHBOARD_TEXT = (
        By.XPATH,
        "//*[contains(normalize-space(),'Hello, teacher') "
        "or contains(normalize-space(),'Build Assessment') "
        "or contains(normalize-space(),'Create and manage your assessments')]",
    )

    def is_dashboard_loaded(self):
        return self.is_element_visible(self.DASHBOARD_TEXT)
