from time import sleep

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException,
)


class ElementUtils:
    def __init__(self, driver, wait_utils, action_delay_seconds=0.5):
        self.driver = driver
        self.wait_utils = wait_utils
        self.action_delay_seconds = action_delay_seconds

    def pause_before_action(self):
        if self.action_delay_seconds > 0:
            sleep(self.action_delay_seconds)

    def scroll_to_element(self, element, block="center"):
        self.driver.execute_script(f"arguments[0].scrollIntoView({{block: '{block}'}});", element)

    def scroll_to_top(self):
        self.driver.execute_script("window.scrollTo(0, 0);")

    def scroll_to_bottom(self):
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def click(self, locator, timeout=None):
        last_error = None
        for attempt in range(3):
            try:
                element = self.wait_utils.until_clickable(locator, timeout)
                self.pause_before_action()
                element.click()
                return element
            except StaleElementReferenceException as error:
                last_error = error
                if attempt == 2:
                    raise
            except ElementClickInterceptedException as error:
                # The app's sticky header overlays whatever scrolls under it.
                # Controls near the top of the page - the Manual/Upload tabs
                # sit at about y=18 - are reported clickable by Selenium (they
                # are displayed and enabled) while the brand name actually
                # receives the click. Recentre the element and retry, then fall
                # back to a JS click, which is not subject to the overlay.
                last_error = error
                try:
                    self.scroll_to_element(self.wait_utils.until_present(locator, timeout))
                except WebDriverException:
                    pass
                if attempt == 2:
                    return self.js_click(locator, timeout)
        raise last_error

    def js_click(self, locator, timeout=None):
        last_error = None
        for attempt in range(3):
            try:
                element = self.wait_utils.until_clickable(locator, timeout)
                self.scroll_to_element(element)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", element)
                return element
            except StaleElementReferenceException as error:
                last_error = error
                if attempt == 2:
                    raise
        raise last_error

    def click_any(self, locators, timeout=None):
        last_error = None
        for locator in locators:
            try:
                return self.click(locator, timeout)
            except WebDriverException as error:
                last_error = error
        raise last_error

    def enter_text(self, locator, value, timeout=None):
        element = self.wait_utils.until_visible(locator, timeout)
        element.clear()
        element.send_keys(value)
        return element

    def get_text(self, locator, timeout=None):
        return self.wait_utils.until_visible(locator, timeout).text

    def set_rich_text_editor_value(self, locator, value, timeout=None):
        editor = self.wait_utils.until_visible(locator, timeout)
        self.driver.execute_script(
            """
            const editor = arguments[0];
            const value = arguments[1];
            editor.innerHTML = '<p>' + value + '</p>';
            editor.dispatchEvent(new Event('input', { bubbles: true }));
            editor.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            editor,
            value,
        )
        return editor
