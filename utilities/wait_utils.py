from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class WaitUtils:
    DEFAULT_TIMEOUT = 20
    QUICK_TIMEOUT = 5

    def __init__(self, driver, timeout=DEFAULT_TIMEOUT):
        self.driver = driver
        self.timeout = timeout

    def get_wait(self, timeout=None):
        # Use `is not None` so that timeout=0 is honoured (0 is falsy and
        # `0 or self.timeout` would silently fall back to the default 20 s).
        return WebDriverWait(self.driver, timeout if timeout is not None else self.timeout)

    def until_visible(self, locator, timeout=None):
        return self.get_wait(timeout).until(EC.visibility_of_element_located(locator))

    def until_all_visible(self, locator, timeout=None):
        return self.get_wait(timeout).until(EC.visibility_of_all_elements_located(locator))

    def until_clickable(self, locator, timeout=None):
        return self.get_wait(timeout).until(EC.element_to_be_clickable(locator))

    def until_present(self, locator, timeout=None):
        return self.get_wait(timeout).until(EC.presence_of_element_located(locator))

    def until_url_contains(self, text, timeout=None):
        return self.get_wait(timeout).until(EC.url_contains(text))

    def until_text_present(self, locator, text, timeout=None):
        return self.get_wait(timeout).until(EC.text_to_be_present_in_element(locator, text))

    def until_condition(self, condition, timeout=None):
        return self.get_wait(timeout).until(condition)

    def is_visible(self, locator, timeout=QUICK_TIMEOUT):
        try:
            self.until_visible(locator, timeout)
            return True
        except TimeoutException:
            return False

    def wait_for_page_ready(self, timeout=None):
        return self.get_wait(timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
