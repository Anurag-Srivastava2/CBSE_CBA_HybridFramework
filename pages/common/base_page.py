from utilities.element_utils import ElementUtils
from utilities.read_config import ReadConfig
from utilities.wait_utils import WaitUtils


class BasePage:

    def __init__(self, driver):
        self.driver = driver
        self.wait_utils = WaitUtils(driver)
        self.element_utils = ElementUtils(
            driver,
            self.wait_utils,
            ReadConfig.get_click_delay_seconds(),
        )
        self.wait = self.wait_utils.get_wait()

    def click_element(self, locator):
        self.element_utils.click(locator)

    def click_any_element(self, locators):
        self.element_utils.click_any(locators)

    def enter_text(self, locator, value):
        self.element_utils.enter_text(locator, value)

    def enter_text_any_locator(self, locators, value):
        last_error = None
        for locator in locators:
            try:
                self.element_utils.enter_text(locator, value)
                return
            except Exception as error:
                last_error = error
        raise last_error

    def set_rich_text_editor_value(self, locator, value):
        self.element_utils.set_rich_text_editor_value(locator, value)

    def get_text(self, locator):
        return self.element_utils.get_text(locator)

    def is_element_visible(self, locator):
        return self.wait_utils.until_visible(locator).is_displayed()

    def is_element_visible_quick(self, locator, timeout=5):
        return self.wait_utils.is_visible(locator, timeout)

    def get_current_url(self):
        return self.driver.current_url

    def wait_for_page_ready(self):
        self.wait_utils.wait_for_page_ready()

    def pause_before_action(self):
        self.element_utils.pause_before_action()
