import re
import time

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from pages.common.base_page import BasePage


class LoginPage(BasePage):
    # Locators extracted from BlazeMeter recording.
    # Prefer ID/Name/CSS over absolute XPath.
    USERNAME_TEXTBOX = (By.ID, "identifier")
    PASSWORD_TEXTBOX = (By.ID, "password")
    SIGN_IN_BUTTON = (By.XPATH, "//button[@type='submit' and normalize-space()='Sign In']")
    AVATAR_MENU_TRIGGER = (By.XPATH, "//*[@aria-haspopup='menu'][contains(@class,'avatar')]")
    LOGOUT_MENU_ITEM = (
        By.XPATH,
        "//*[self::button or self::a or @role='menuitem']"
        "[contains(translate(normalize-space(),'LOGUT SIGNO','logut signo'),'logout')"
        " or contains(translate(normalize-space(),'LOGUT SIGNO','logut signo'),'sign out')]",
    )

    # ------------------------------------------------------------------
    # Branding and page chrome
    #
    # The sign-in screen is styled with CSS modules, so its class names carry
    # a build-specific hash suffix (`_hero_8s7o3_322`). These locators match on
    # the readable prefix, or on alt/aria text, so they survive a rebuild.
    # ------------------------------------------------------------------
    PAGE_BODY = (By.TAG_NAME, "body")
    TOPBAR = (By.TAG_NAME, "header")
    TOPBAR_LOGO = (By.CSS_SELECTOR, "header img[alt='CBSE']")
    TOPBAR_WORDMARK = (By.XPATH, "//header//span[normalize-space()='AAKALAN']")
    LOGIN_CARD_LOGO = (By.CSS_SELECTOR, "img[alt='CBSE Logo']")
    # The hero panel carries the login-bg artwork; the overlay above it carries
    # the brand gradient that keeps the form legible over that artwork.
    HERO = (By.TAG_NAME, "main")
    HERO_OVERLAY = (By.CSS_SELECTOR, "[class*='heroOverlay']")
    # The theme the app is painting with is published as data-theme on the page
    # wrapper, which is also the element the theme picker rewrites.
    THEME_ROOT = (By.CSS_SELECTOR, "[data-theme]")

    WELCOME_HEADING = (By.XPATH, "//*[normalize-space()='Welcome Back!']")
    SIGN_IN_SUBTITLE = (By.XPATH, "//*[normalize-space()='Sign in to access your account']")
    EMAIL_LABEL = (By.XPATH, "//label[normalize-space()='Enter your email']")
    PASSWORD_LABEL = (By.XPATH, "//label[normalize-space()='Enter your password']")
    PASSWORD_VISIBILITY_TOGGLE = (By.CSS_SELECTOR, "button[class*='eyeButton']")
    FORGOT_PASSWORD_LINK = (By.XPATH, "//a[contains(normalize-space(),'Forgot Password')]")
    CONTACT_SUPPORT_LINK = (By.XPATH, "//a[contains(normalize-space(),'Contact Support')]")

    # Accessibility / localisation toolbar
    # ------------------------------------------------------------------
    # MFA / session affordances
    #
    # None of these exist on this environment yet — that is precisely what the
    # KI-M2-MFA-* / KI-M2-SESSION-* known issues record. They are surveyed
    # rather than asserted so the report answers "has MFA shipped yet?" on
    # every run: the day these start reporting PASSED is the day those xfail
    # guards can be retired.
    # ------------------------------------------------------------------
    OTP_INPUT = (
        By.XPATH,
        "//input[@inputmode='numeric' or contains(@name,'otp') or contains(@id,'otp')"
        " or contains(@placeholder,'OTP') or contains(@placeholder,'code')"
        " or contains(@aria-label,'OTP') or contains(@aria-label,'verification')]",
    )
    OTP_VERIFY_BUTTON = (
        By.XPATH,
        "//button[contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'verify')]",
    )
    OTP_RESEND_CONTROL = (
        By.XPATH,
        "//*[self::button or self::a][contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'resend')]",
    )
    MFA_PROMPT_TEXT = (
        By.XPATH,
        "//*[not(*)][contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'one-time')"
        " or contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'two-factor')"
        " or contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'verification code')]",
    )
    SESSION_TIMEOUT_WARNING = (
        By.XPATH,
        "//*[contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'session')"
        " and contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'expire')]",
    )
    STAY_ACTIVE_BUTTON = (
        By.XPATH,
        "//button[contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'stay active')"
        " or contains(translate(normalize-space(),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'stay signed in')]",
    )

    MFA_AFFORDANCES = (
        ("OTP entry field", "OTP_INPUT"),
        ("OTP verify button", "OTP_VERIFY_BUTTON"),
        ("OTP resend control", "OTP_RESEND_CONTROL"),
        ("MFA prompt text", "MFA_PROMPT_TEXT"),
    )
    SESSION_AFFORDANCES = (
        ("Session expiry warning", "SESSION_TIMEOUT_WARNING"),
        ("Stay Active control", "STAY_ACTIVE_BUTTON"),
    )

    THEME_PICKER = (By.CSS_SELECTOR, "button[aria-label='Theme']")
    THEME_MENU_ITEMS = (By.CSS_SELECTOR, "[role='menuitem']")
    SCREEN_READER_TOGGLE = (By.CSS_SELECTOR, "button[aria-label='Toggle screen-reader hints']")
    LANG_EN = (By.XPATH, "//button[normalize-space()='EN']")
    LANG_HI = (By.XPATH, "//button[normalize-space()='हिंदी']")
    # 'A−' uses a typographic minus (U+2212), not a hyphen.
    FONT_SIZE_CONTROLS = (
        By.XPATH,
        "//button[normalize-space()='A−' or normalize-space()='A'"
        " or normalize-space()='A+' or normalize-space()='A++']",
    )

    SOCIAL_LINKS = (By.CSS_SELECTOR, "nav[aria-label='CBSE social media'] a")
    # Icons are Material Symbols glyphs. When that font fails to load the page
    # renders the ligature name ('mail_outline') as literal text instead.
    ICON_GLYPHS = (By.CSS_SELECTOR, "span.material-symbols-outlined")
    HELPLINE_LINK = (By.XPATH, "//a[contains(normalize-space(),'1800-11-8002')]")
    SUPPORT_EMAIL_LINK = (By.CSS_SELECTOR, "a[href^='mailto:']")
    CBSE_WEBSITE_LINK = (By.XPATH, "//a[contains(normalize-space(),'CBSE Official Website')]")
    PRIVACY_POLICY_LINK = (By.XPATH, "//a[normalize-space()='Privacy Policy']")
    TERMS_OF_USE_LINK = (By.XPATH, "//a[normalize-space()='Terms of Use']")

    # The palette the whole page is drawn from, declared as CSS variables on
    # :root and rewritten wholesale when the theme changes.
    PALETTE_VARIABLES = (
        "--primary",
        "--background",
        "--foreground",
        "--accent",
        "--secondary",
        "--muted",
        "--card",
        "--border",
        "--ring",
        "--destructive",
    )

    COMPUTED_STYLE_JS = """
        const style = window.getComputedStyle(arguments[0]);
        const values = {};
        for (const property of arguments[1]) {
            values[property] = style.getPropertyValue(property).trim();
        }
        return values;
    """

    CSS_VARIABLES_JS = """
        const style = window.getComputedStyle(document.documentElement);
        const values = {};
        for (const name of arguments[0]) {
            const value = style.getPropertyValue(name).trim();
            if (value) { values[name] = value; }
        }
        return values;
    """

    IMAGE_RENDERED_JS = """
        const image = arguments[0];
        return !!(image.complete && image.naturalWidth > 0
                  && (image.offsetWidth || image.offsetHeight));
    """

    # Asynchronous: the browser has to actually fetch and decode the URL before
    # it can say whether the asset is really there.
    IMAGE_URL_LOADS_JS = """
        const done = arguments[arguments.length - 1];
        const url = arguments[0];
        if (!url) { done(false); return; }
        const probe = new Image();
        probe.onload = () => done(probe.naturalWidth > 0);
        probe.onerror = () => done(false);
        probe.src = url;
    """

    def enter_username(self, username):
        self.enter_text(self.USERNAME_TEXTBOX, username)

    def enter_password(self, password):
        self.enter_text(self.PASSWORD_TEXTBOX, password)

    def click_sign_in(self):
        self.click_element(self.SIGN_IN_BUTTON)

    def is_login_screen_text_visible(self):
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.casefold()
        except Exception:
            return False
        return any(
            marker in page_text
            for marker in (
                "welcome back",
                "sign in",
                "enter your email",
                "enter your password",
            )
        )

    def wait_for_login_form_or_authenticated_page(self):
        def login_form_or_authenticated_page(driver):
            if self.is_element_visible_quick(self.USERNAME_TEXTBOX):
                return True
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
            except Exception:
                return False
            if not page_text.strip() or "loading" in page_text:
                return False
            return not any(
                marker in page_text
                for marker in (
                    "welcome back",
                    "sign in",
                    "enter your email",
                    "enter your password",
                )
            )

        last_error = None
        for attempt in range(3):
            try:
                self.wait_utils.until_condition(
                    login_form_or_authenticated_page,
                    timeout=30,
                )
                return
            except TimeoutException as error:
                last_error = error
                if attempt < 2:
                    self.driver.refresh()
        raise TimeoutException(
            "The application remained on its global Loading screen and did not "
            "show either the login form or an authenticated page after refresh retries."
        ) from last_error

    def login_to_application(self, username, password):
        self.wait_for_login_form_or_authenticated_page()
        if not self.is_element_visible_quick(self.USERNAME_TEXTBOX):
            return
        for attempt in range(3):
            if attempt:
                # Retype into a form the SPA may have re-rendered underneath
                # the previous attempt: reload so the fields are the live ones.
                self.driver.refresh()
                self.wait_for_login_form_or_authenticated_page()
                if not self.is_element_visible_quick(self.USERNAME_TEXTBOX):
                    return
            self.enter_username(username)
            self.enter_password(password)
            self.click_sign_in()
            try:
                self.wait_utils.until_condition(
                    lambda driver: not self.wait_utils.is_visible(self.USERNAME_TEXTBOX, timeout=1),
                    timeout=45,
                )
                # Guard against credential-rejection errors that dismiss the
                # username field but land on an error state (not a real session).
                if self.is_login_error_displayed():
                    raise TimeoutException(
                        f"Login failed for {username!r}: the application rejected the credentials."
                    )
                self.driver._logged_in_user = username
                return
            except TimeoutException:
                if attempt == 2:
                    raise

    def logout(self, base_url=None):
        """End the session so another user can sign in.

        Prefers the avatar menu's Logout item; falls back to clearing cookies
        and web storage, which the SPA treats as a signed-out session.
        """
        try:
            self.click_element(self.AVATAR_MENU_TRIGGER)
            self.click_element(self.LOGOUT_MENU_ITEM)
            self.wait_utils.until_condition(
                lambda driver: self.is_element_visible_quick(self.USERNAME_TEXTBOX, timeout=2),
                timeout=20,
            )
        except Exception:
            self.driver.delete_all_cookies()
            try:
                self.driver.execute_script(
                    "window.localStorage.clear(); window.sessionStorage.clear();"
                )
            except Exception:
                pass
            self.driver.get(base_url or self.driver.current_url)
            self.wait_for_login_form_or_authenticated_page()
        self.driver._logged_in_user = None

    def is_login_form_displayed(self, timeout=20):
        # The default 5s probe is a snapshot of a page that is still booting:
        # with several browsers driving the app at once the login form can
        # take longer than that to paint, which reads as "no login form" even
        # though the app is fine.
        return (
            self.is_element_visible_quick(self.USERNAME_TEXTBOX, timeout)
            and self.is_element_visible_quick(self.PASSWORD_TEXTBOX, timeout)
        )

    def get_login_error_text(self):
        try:
            return self.driver.find_element(By.TAG_NAME, "body").text.casefold()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Visual readers
    #
    # A presence check says an element is in the DOM; these say what it looks
    # like — the colour it paints, the artwork behind it, whether its image
    # actually decoded. Every one of them returns an empty/False value instead
    # of raising, so a branding survey records the gap and carries on rather
    # than stopping at the first unstyled element.
    # ------------------------------------------------------------------

    def is_visible(self, locator, timeout=5):
        return self.is_element_visible_quick(locator, timeout)

    def count_visible(self, locator):
        """How many matches are actually on screen — 0 when none are."""
        count = 0
        for element in self.driver.find_elements(*locator):
            try:
                if element.is_displayed():
                    count += 1
            except WebDriverException:
                continue
        return count

    def attribute_of(self, locator, name, default=""):
        try:
            return self.driver.find_element(*locator).get_attribute(name) or default
        except WebDriverException:
            return default

    def get_computed_style(self, locator, properties, timeout=5):
        """Computed CSS values for one element, keyed by property name.

        Property names are the CSS spelling ('background-color'), not the DOM
        one. Returns {} when the element is absent, so callers read values with
        `.get()` and record what was missing.
        """
        try:
            element = self.wait_utils.until_visible(locator, timeout)
        except (TimeoutException, WebDriverException):
            return {}
        try:
            return self.driver.execute_script(
                self.COMPUTED_STYLE_JS, element, list(properties)
            )
        except WebDriverException:
            return {}

    def get_settled_computed_style(self, locator, properties, timeout=5, poll=0.2):
        """Computed values read once the element has stopped changing.

        A theme change animates: reading the Sign In button the instant the
        palette flips catches its background part-way through a CSS transition,
        which compares as a colour mismatch against the theme it is on its way
        to. Samples until two consecutive reads agree, then returns those.
        """
        deadline = time.monotonic() + timeout
        previous = self.get_computed_style(locator, properties, timeout)
        while time.monotonic() < deadline:
            time.sleep(poll)
            current = self.get_computed_style(locator, properties, timeout)
            if current == previous:
                return current
            previous = current
        return previous

    def get_theme_palette(self, names=None):
        """The active theme's CSS variables, e.g. {'--primary': '#2653D9'}."""
        try:
            return self.driver.execute_script(
                self.CSS_VARIABLES_JS, list(names or self.PALETTE_VARIABLES)
            )
        except WebDriverException:
            return {}

    def get_active_theme(self):
        """The data-theme the page is painting with ('default', 'grey', ...)."""
        return self.attribute_of(self.THEME_ROOT, "data-theme")

    def get_image_source(self, locator, default=""):
        """The URL the browser actually chose for an <img> (currentSrc)."""
        try:
            image = self.driver.find_element(*locator)
            return image.get_attribute("currentSrc") or image.get_attribute("src") or default
        except WebDriverException:
            return default

    def is_image_rendered(self, locator, timeout=5):
        """True when an <img> is on screen *and* decoded a bitmap.

        A broken image still satisfies a presence check — it keeps its box in
        the DOM and shows its alt text — so a logo check has to ask the browser
        whether pixels arrived, not just whether the tag exists.
        """
        try:
            image = self.wait_utils.until_visible(locator, timeout)
            return bool(self.driver.execute_script(self.IMAGE_RENDERED_JS, image))
        except (TimeoutException, WebDriverException):
            return False

    def get_background_image(self, locator, timeout=5):
        """The computed background-image, e.g. 'url("…/login-bg.png")' or 'none'."""
        return self.get_computed_style(locator, ("background-image",), timeout).get(
            "background-image", ""
        )

    def get_background_image_url(self, locator, timeout=5):
        """The URL inside a background-image, '' when it is a gradient or none."""
        match = re.search(r'url\(["\']?([^"\')]+)', self.get_background_image(locator, timeout))
        return match.group(1) if match else ""

    def is_image_url_loaded(self, url, timeout=15):
        """Fetch and decode a URL in the browser: True when it is a real image.

        Used for assets that are referenced rather than rendered as an <img> —
        the hero background and the favicon — where a 404 leaves no visible
        trace on the page beyond the missing artwork.
        """
        if not url:
            return False
        try:
            self.driver.set_script_timeout(timeout)
            return bool(self.driver.execute_async_script(self.IMAGE_URL_LOADS_JS, url))
        except WebDriverException:
            return False
        finally:
            try:
                self.driver.set_script_timeout(30)
            except WebDriverException:
                pass

    def get_page_title(self):
        try:
            return self.driver.title or ""
        except WebDriverException:
            return ""

    def get_favicon_href(self):
        try:
            return self.driver.execute_script(
                "const link = document.querySelector('link[rel*=\"icon\"]');"
                "return link ? link.href : '';"
            ) or ""
        except WebDriverException:
            return ""

    def is_favicon_loaded(self):
        return self.is_image_url_loaded(self.get_favicon_href())

    def get_loaded_font_families(self):
        """Font families the document has actually loaded, not merely declared."""
        try:
            return self.driver.execute_script(
                "return [...document.fonts].map(font => font.family)"
                ".filter((family, index, all) => all.indexOf(family) === index);"
            ) or []
        except WebDriverException:
            return []

    FONT_LOADED_JS = """
        const done = arguments[arguments.length - 1];
        const spec = arguments[0];
        const sample = arguments[1];
        document.fonts.ready.then(() => {
            try {
                done(sample ? document.fonts.check(spec, sample) : document.fonts.check(spec));
            } catch (error) {
                done(false);
            }
        }).catch(() => done(false));
    """

    def is_font_loaded(self, font_spec, sample_text=None, timeout=15):
        """True when the browser can render `font_spec`, e.g. '16px Inter'.

        Waits on document.fonts.ready first: web fonts are fetched lazily, so
        an immediate check races the download and reports a font that is merely
        declared as missing. `sample_text` narrows the question to the glyphs
        that matter — an icon font is only useful if it has the ligature
        characters, and the default sample is a single space.
        """
        try:
            self.driver.set_script_timeout(timeout)
            return bool(self.driver.execute_async_script(
                self.FONT_LOADED_JS, font_spec, sample_text
            ))
        except WebDriverException:
            return False
        finally:
            try:
                self.driver.set_script_timeout(30)
            except WebDriverException:
                pass

    # ------------------------------------------------------------------
    # Theme picker
    # ------------------------------------------------------------------

    def open_theme_menu(self, timeout=5, attempts=3):
        """Open the palette menu, or leave it open when it already is.

        Idempotent because the trigger toggles: clicking it a second time on an
        open menu closes it, which would strand a caller that only wanted the
        options on screen.

        The click is retried because the menu swallows pointer events for a
        moment after it closes — reopening it right after picking a theme lands
        in exactly that window and the first click is dropped.
        """
        last_error = None
        for _ in range(attempts):
            if self.count_visible(self.THEME_MENU_ITEMS):
                return
            try:
                self.click_element(self.THEME_PICKER)
                self.wait_utils.until_condition(
                    lambda driver: bool(self.count_visible(self.THEME_MENU_ITEMS)),
                    timeout=timeout,
                )
                return
            except (TimeoutException, WebDriverException) as error:
                last_error = error
        raise TimeoutException(
            f"The theme menu did not open after {attempts} attempts on the trigger."
        ) from last_error

    def get_theme_option_labels(self):
        """Theme names offered by the picker ('Default', 'Grey', 'Future').

        Each menu item renders its name, a state icon and a description on
        separate lines; only the first line is the name.
        """
        labels = []
        for item in self.driver.find_elements(*self.THEME_MENU_ITEMS):
            try:
                lines = item.text.strip().splitlines()
            except WebDriverException:
                continue
            if lines and lines[0].strip():
                labels.append(lines[0].strip())
        return labels

    def select_theme(self, label, timeout=10):
        """Pick a theme and wait for the repaint.

        Returns the data-theme the page settled on rather than the label asked
        for, so a caller records what the application actually did — including
        a picker that opens but changes nothing.
        """
        previous = self.get_active_theme()
        self.open_theme_menu()
        self.click_element((
            By.XPATH,
            f"//*[@role='menuitem'][starts-with(normalize-space(),'{label}')]",
        ))
        try:
            self.wait_utils.until_condition(
                lambda driver: self.get_active_theme() != previous,
                timeout=timeout,
            )
        except TimeoutException:
            pass
        return self.get_active_theme()

    def is_login_error_displayed(self):
        page_text = self.get_login_error_text()
        return any(
            marker in page_text
            for marker in (
                "invalid password",
                "incorrect password",
                "login failed",
                "invalid credentials",
                "username or password",
                "please check your password",
                "please check your username",
                "please enter a valid email address",
                "please enter a valid email",
                "password must include an uppercase letter",
                "password must include a lowercase letter",
                "password must include a number",
                "password must include a special character",
                "password must be at least",
                "password must be at most",
                "please enter your password",
            )
        )
