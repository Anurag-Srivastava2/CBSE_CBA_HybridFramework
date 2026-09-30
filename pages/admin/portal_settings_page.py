from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from pages.admin.admin_portal_page import AdminPortalPage
from utilities.read_config import ReadConfig


class PortalSettingsPage(AdminPortalPage):
    """Admin > Portal Management (/admin/portal).

    Five tabs: Branding, Themes, Side Menu Customization, Dashboard
    Customization, Accessibility.

    Save and Cancel start out *disabled* and only go live once something on the
    tab actually changes. That is what makes a theme edit checkable without
    persisting one: change a colour, watch Save arm itself, then Cancel. The
    portal's branding is shared by every other suite running against this
    environment, so a test must never leave a colour change behind.
    """

    PATH = "/admin/portal"

    PAGE_HEADING = (
        By.XPATH,
        "//*[self::h1 or self::h2][normalize-space()='Portal Management']",
    )
    COLOUR_INPUTS = (By.XPATH, "//input[@type='color']")
    SAVE_BUTTON = (By.XPATH, "//button[normalize-space()='Save']")
    CANCEL_BUTTON = (By.XPATH, "//button[normalize-space()='Cancel']")
    RESET_BUTTON = (By.XPATH, "//button[normalize-space()='Reset to Default']")
    TABS = (By.XPATH, "//*[@role='tab']")

    def open(self, base_url=None):
        base = (base_url or ReadConfig.get_base_url()).rstrip("/")
        self.driver.get(base + self.PATH)
        self.wait_for_application_ready()
        self.wait_utils.until_visible(self.PAGE_HEADING, timeout=30)
        return self

    def tab_labels(self):
        return [tab.text.strip() for tab in self.driver.find_elements(*self.TABS) if tab.text.strip()]

    @staticmethod
    def tab_locator(label):
        return (By.XPATH, f"//*[@role='tab'][normalize-space()='{label}']")

    def open_tab(self, label):
        self.click_element(self.tab_locator(label))
        self.wait_for_application_ready()
        return self

    def colour_inputs(self):
        return self.driver.find_elements(*self.COLOUR_INPUTS)

    def is_save_enabled(self):
        button = self.wait_utils.until_visible(self.SAVE_BUTTON, timeout=10)
        return button.get_attribute("disabled") is None and button.is_enabled()

    def set_colour(self, index, value):
        """Set one colour swatch and return what it held before.

        `<input type="color">` is a React-controlled input: assigning .value
        from a plain script updates the DOM but never reaches React's state, so
        the form stays pristine and Save never arms. Going through the
        prototype's value setter and firing input/change is what React listens
        for.
        """
        inputs = self.colour_inputs()
        if index >= len(inputs):
            raise IndexError(
                f"Wanted colour input {index} but the Themes tab renders {len(inputs)}."
            )
        element = inputs[index]
        previous = element.get_attribute("value")
        self.driver.execute_script(
            """
            const input = arguments[0], value = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, value);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            element,
            value,
        )
        return previous

    def cancel_edits(self):
        """Discard pending edits, so nothing this test typed is persisted."""
        button = self.wait_utils.until_visible(self.CANCEL_BUTTON, timeout=10)
        if button.get_attribute("disabled") is None and button.is_enabled():
            self.driver.execute_script("arguments[0].click();", button)
            self.wait_for_application_ready()
            return True
        return False

    PREVIEW_WINDOW = (
        By.XPATH,
        "//*[normalize-space()='Preview']/following-sibling::*[1]",
    )
    PREVIEW_ROLE_BUTTONS = (
        By.XPATH,
        "//button[normalize-space()='Admin' or normalize-space()='SME' or "
        "normalize-space()='Teacher' or normalize-space()='RWG' or "
        "normalize-space()='Sr. RWG' or normalize-space()='PIT']",
    )

    def preview_primary_colour(self):
        """The primary colour the Preview panel is currently painting with.

        The preview window carries the pending theme as --pp-* custom
        properties, so reading one back is how a test sees an unsaved edit
        take effect without publishing it.
        """
        try:
            window = self.driver.find_element(*self.PREVIEW_WINDOW)
        except WebDriverException:
            return ""
        return (
            self.driver.execute_script(
                "return arguments[0].style.getPropertyValue('--pp-primary');", window
            )
            or ""
        ).strip()

    def preview_role_options(self):
        """Roles the Dashboard Customization tab can preview the platform as."""
        return [
            button.text.strip()
            for button in self.driver.find_elements(*self.PREVIEW_ROLE_BUTTONS)
            if button.text.strip()
        ]

    def select_preview_role(self, role):
        self.click_element((By.XPATH, f"//button[normalize-space()='{role}']"))
        self.wait_for_application_ready()

    def has_control(self, *labels):
        """True when any button with one of these exact labels is on the tab."""
        return any(
            self.is_element_visible_quick(
                (By.XPATH, f"//button[normalize-space()='{label}']"), timeout=3
            )
            for label in labels
        )
