import re

import pytest
from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from tests.M5_Teacher_Contribution.m5_surveys import (
    survey_teacher_chrome,
    survey_teacher_dashboard,
)
from utilities.element_checks import ElementChecks
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

    def test_teacher_valid_login(self, record_property):
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

        # Additive: this is part of the smoke gate, so is_dashboard_loaded()
        # stays exactly as hard as it was. The survey is evidence on the card.
        checks = ElementChecks(
            dashboard_page, record_property, page_name="Teacher Dashboard — Login"
        )
        survey_teacher_chrome(checks, dashboard_page)
        survey_teacher_dashboard(checks, dashboard_page)
        record_property("result_description", checks.publish())

        assert dashboard_page.is_dashboard_loaded() is True

        self.logger.info("Teacher login test passed")


# The branding baseline, captured from the QA environment on 2026-08-17. These
# are design expectations rather than behaviour, so a mismatch is recorded as a
# FAILED row in the report's element table and the test still passes — a
# re-skinned login screen should tell us what changed, not block the suite.
EXPECTED_PAGE_TITLE = "CBSE"
EXPECTED_LOGO_FILE = "cbse-logo-with-name.png"
EXPECTED_HERO_BACKGROUND_FILE = "login-bg"
EXPECTED_PALETTE = {
    "--primary": "#2653D9",
    "--background": "#fff",
    "--foreground": "#020618",
    "--accent": "#f0f2ff",
    "--secondary": "#f0f2ff",
    "--muted": "#f5f6fa",
    "--card": "#fff",
    "--border": "#e5e7eb",
    "--destructive": "#EF4444",
}
EXPECTED_BRAND_FONT = "Inter"
EXPECTED_ICON_FONT = "Material Symbols Outlined"
EXPECTED_THEMES = ("Default", "Grey", "Future")

# Every absent element costs its full timeout, and this survey runs ~50 checks
# against elements that all paint together.
CHECK_TIMEOUT = 2


def to_rgb(value):
    """Reduce '#2653D9', '#fff' and 'rgb(38, 83, 217)' to (38, 83, 217).

    The palette is declared as hex in the CSS variables but reported as rgb()
    by getComputedStyle, so comparing the two as strings would report identical
    colours as a mismatch. Returns None for anything unparseable, which never
    compares equal — an unreadable colour is a failed check, not a passing one.
    """
    text = str(value or "").strip().lower()
    hex_match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", text)
    if hex_match:
        digits = hex_match.group(1)
        if len(digits) == 3:
            digits = "".join(digit * 2 for digit in digits)
        return tuple(int(digits[index:index + 2], 16) for index in (0, 2, 4))
    rgb_match = re.match(r"rgba?\(([^)]*)\)", text)
    if rgb_match:
        channels = re.findall(r"[\d.]+", rgb_match.group(1))[:3]
        if len(channels) == 3:
            return tuple(int(round(float(channel))) for channel in channels)
    return None


@pytest.mark.ui
@pytest.mark.usefixtures("setup")
class TestTeacherLoginPageBranding:
    """Visual survey of the sign-in screen: logos, palette, theme, background
    artwork, typography and page chrome.

    Every branding expectation is a soft check — a logo that stops loading or a
    primary colour that changes is recorded as a FAILED row in the Element
    Presence Checks table, so one run inventories the whole screen instead of
    stopping at the first difference. The only hard gate is that the login form
    renders at all; without it there is nothing to survey.

    No credentials are submitted, so these tests do not contend for the shared
    teacher session the way TestTeacherLogin above does.
    """

    def open_login_page(self):
        self.driver.get(ReadConfig.get_base_url())
        login_page = LoginPage(self.driver)
        login_page.wait_for_login_form_or_authenticated_page()
        assert login_page.is_login_form_displayed() is True, (
            "The sign-in form did not render, so there is no login screen to survey."
        )
        return login_page

    def test_login_page_visual_branding_survey(self, record_property):
        """Logo, colours, background artwork, fonts and chrome on the login screen."""
        login_page = self.open_login_page()
        checks = ElementChecks(login_page, record_property, page_name="Teacher Login — Branding")

        # --- Identity: tab title and favicon ---------------------------------
        page_title = login_page.get_page_title()
        checks.check_condition(
            f"Page title mentions {EXPECTED_PAGE_TITLE}",
            EXPECTED_PAGE_TITLE.casefold() in page_title.casefold(),
            detail=f"title: {page_title!r}",
        )
        favicon_href = login_page.get_favicon_href()
        checks.check_condition(
            "Favicon is declared",
            favicon_href,
            detail=f"href: {favicon_href}" if favicon_href else "no <link rel=icon>",
        )
        checks.check_condition(
            "Favicon loads",
            lambda: login_page.is_favicon_loaded(),
            detail=f"href: {favicon_href}",
        )

        # --- Logos -----------------------------------------------------------
        # Presence and rendering are checked separately: a broken image keeps
        # its box in the DOM, so only the render check catches a dead asset.
        for label, locator in (
            ("CBSE topbar mark", login_page.TOPBAR_LOGO),
            ("CBSE sign-in card mark", login_page.LOGIN_CARD_LOGO),
        ):
            checks.check(f"Logo — {label}", locator, timeout=CHECK_TIMEOUT)
            checks.check_condition(
                f"Logo renders pixels — {label}",
                lambda target=locator: login_page.is_image_rendered(target, CHECK_TIMEOUT),
                detail=f"src: {login_page.get_image_source(locator) or 'none'}",
            )
        topbar_logo_source = login_page.get_image_source(login_page.TOPBAR_LOGO)
        checks.check_condition(
            f"Topbar logo is {EXPECTED_LOGO_FILE}",
            EXPECTED_LOGO_FILE in topbar_logo_source,
            detail=f"src: {topbar_logo_source or 'none'}",
        )
        checks.check("Wordmark — AAKALAN", login_page.TOPBAR_WORDMARK, timeout=CHECK_TIMEOUT)

        # --- Background artwork ----------------------------------------------
        hero_background = login_page.get_background_image(login_page.HERO, CHECK_TIMEOUT)
        hero_background_url = login_page.get_background_image_url(login_page.HERO, CHECK_TIMEOUT)
        checks.check_condition(
            "Background image — hero panel",
            "url(" in hero_background,
            detail=f"background-image: {hero_background[:120] or 'none'}",
        )
        checks.check_condition(
            f"Background image is {EXPECTED_HERO_BACKGROUND_FILE}",
            EXPECTED_HERO_BACKGROUND_FILE in hero_background_url,
            detail=f"url: {hero_background_url or 'none'}",
        )
        checks.check_condition(
            "Background image loads",
            lambda: login_page.is_image_url_loaded(hero_background_url),
            detail=f"url: {hero_background_url or 'none'}",
        )
        checks.check("Hero brand overlay", login_page.HERO_OVERLAY, timeout=CHECK_TIMEOUT)
        overlay_background = login_page.get_background_image(
            login_page.HERO_OVERLAY, CHECK_TIMEOUT
        )
        checks.check_condition(
            "Hero overlay paints the brand gradient",
            "gradient" in overlay_background,
            detail=f"background-image: {overlay_background[:120] or 'none'}",
        )

        # --- Theme palette ----------------------------------------------------
        active_theme = login_page.get_active_theme()
        checks.check_condition(
            "Theme — page starts on the Default theme",
            active_theme == "default",
            detail=f"data-theme: {active_theme!r}",
        )
        palette = login_page.get_theme_palette()
        for variable, expected in EXPECTED_PALETTE.items():
            declared = palette.get(variable, "")
            checks.check_condition(
                f"Theme colour — {variable} is {expected}",
                to_rgb(declared) == to_rgb(expected),
                detail=f"declared {declared!r}" if declared else "variable not declared",
            )

        # Colours as painted, not merely as declared: a variable can be right
        # while the component ignores it.
        button_style = login_page.get_settled_computed_style(
            login_page.SIGN_IN_BUTTON,
            ("background-color", "color", "border-radius", "font-family"),
            CHECK_TIMEOUT,
        )
        checks.check_condition(
            "Sign In button paints the primary colour",
            to_rgb(button_style.get("background-color")) == to_rgb(palette.get("--primary")),
            detail=(
                f"button {button_style.get('background-color', 'unreadable')} "
                f"vs --primary {palette.get('--primary', 'unset')}"
            ),
        )
        checks.check_condition(
            "Sign In button label is white",
            to_rgb(button_style.get("color")) == (255, 255, 255),
            detail=f"color: {button_style.get('color', 'unreadable')}",
        )
        checks.check_condition(
            "Sign In button is rounded",
            button_style.get("border-radius", "0px") not in ("", "0px"),
            detail=f"border-radius: {button_style.get('border-radius', 'unreadable')}",
        )
        body_style = login_page.get_computed_style(
            login_page.PAGE_BODY, ("background-color", "color", "font-family"), CHECK_TIMEOUT
        )
        checks.check_condition(
            "Page background matches --background",
            to_rgb(body_style.get("background-color")) == to_rgb(palette.get("--background")),
            detail=(
                f"body {body_style.get('background-color', 'unreadable')} "
                f"vs --background {palette.get('--background', 'unset')}"
            ),
        )
        checks.check_condition(
            "Body text matches --foreground",
            to_rgb(body_style.get("color")) == to_rgb(palette.get("--foreground")),
            detail=(
                f"body {body_style.get('color', 'unreadable')} "
                f"vs --foreground {palette.get('--foreground', 'unset')}"
            ),
        )

        # --- Typography -------------------------------------------------------
        body_font = body_style.get("font-family", "")
        checks.check_condition(
            f"Brand font — page is set in {EXPECTED_BRAND_FONT}",
            EXPECTED_BRAND_FONT.casefold() in body_font.casefold(),
            detail=f"font-family: {body_font or 'unreadable'}",
        )
        loaded_fonts = login_page.get_loaded_font_families()
        checks.check_condition(
            f"Brand font — {EXPECTED_BRAND_FONT} is loaded",
            login_page.is_font_loaded(f"16px {EXPECTED_BRAND_FONT}"),
            detail=f"loaded families: {loaded_fonts}",
        )
        # Without the icon font the page renders ligature names as literal text
        # ('mail_outline' next to the email box), which no presence check sees.
        # The sample text is a ligature name for that reason: the font is only
        # doing its job if it carries the characters the icons are spelled with.
        checks.check_condition(
            f"Icon font — {EXPECTED_ICON_FONT} is loaded",
            login_page.is_font_loaded(f'24px "{EXPECTED_ICON_FONT}"', "mail_outline"),
            detail=f"loaded families: {loaded_fonts}",
        )
        icon_count = login_page.count_visible(login_page.ICON_GLYPHS)
        checks.check_condition(
            "Icon glyphs rendered",
            icon_count,
            detail=f"{icon_count} Material Symbols glyphs visible",
        )

        # --- Sign-in card content --------------------------------------------
        checks.check("Heading — Welcome Back!", login_page.WELCOME_HEADING, timeout=CHECK_TIMEOUT)
        checks.check("Subtitle — Sign in to access your account", login_page.SIGN_IN_SUBTITLE, timeout=CHECK_TIMEOUT)
        checks.check("Label — Enter your email", login_page.EMAIL_LABEL, timeout=CHECK_TIMEOUT)
        checks.check("Label — Enter your password", login_page.PASSWORD_LABEL, timeout=CHECK_TIMEOUT)
        checks.check("Field — email", login_page.USERNAME_TEXTBOX, timeout=CHECK_TIMEOUT)
        checks.check("Field — password", login_page.PASSWORD_TEXTBOX, timeout=CHECK_TIMEOUT)
        checks.check("Button — Sign In", login_page.SIGN_IN_BUTTON, timeout=CHECK_TIMEOUT)
        checks.check("Button — password visibility toggle", login_page.PASSWORD_VISIBILITY_TOGGLE, timeout=CHECK_TIMEOUT)
        checks.check("Link — Forgot Password?", login_page.FORGOT_PASSWORD_LINK, timeout=CHECK_TIMEOUT)
        checks.check("Link — Contact Support", login_page.CONTACT_SUPPORT_LINK, timeout=CHECK_TIMEOUT)

        for label, locator, expected_placeholder in (
            ("email", login_page.USERNAME_TEXTBOX, "Enter your email"),
            ("password", login_page.PASSWORD_TEXTBOX, "Enter your password"),
        ):
            placeholder = login_page.attribute_of(locator, "placeholder")
            checks.check_condition(
                f"Placeholder — {label} field",
                placeholder == expected_placeholder,
                detail=f"read {placeholder!r}, expected {expected_placeholder!r}",
            )
        email_input_type = login_page.attribute_of(login_page.USERNAME_TEXTBOX, "type")
        checks.check_condition(
            "Email field uses the email input type",
            email_input_type == "email",
            detail=f"type: {email_input_type!r}",
        )

        # --- Accessibility / localisation toolbar ------------------------------
        checks.check("Theme picker", login_page.THEME_PICKER, timeout=CHECK_TIMEOUT)
        checks.check("Screen-reader toggle", login_page.SCREEN_READER_TOGGLE, timeout=CHECK_TIMEOUT)
        checks.check("Language — EN", login_page.LANG_EN, timeout=CHECK_TIMEOUT)
        checks.check("Language — हिंदी", login_page.LANG_HI, timeout=CHECK_TIMEOUT)
        font_controls = login_page.count_visible(login_page.FONT_SIZE_CONTROLS)
        checks.check_condition(
            "Font-size controls (A− / A / A+ / A++)",
            font_controls >= 4,
            detail=f"{font_controls} visible",
        )

        # --- Support and footer chrome ------------------------------------------
        social_links = login_page.count_visible(login_page.SOCIAL_LINKS)
        checks.check_condition(
            "Social media links",
            social_links >= 4,
            detail=f"{social_links} visible",
        )
        checks.check("Link — toll-free helpline", login_page.HELPLINE_LINK, timeout=CHECK_TIMEOUT)
        checks.check("Link — support email", login_page.SUPPORT_EMAIL_LINK, timeout=CHECK_TIMEOUT)
        checks.check("Link — CBSE Official Website", login_page.CBSE_WEBSITE_LINK, timeout=CHECK_TIMEOUT)
        checks.check("Link — Privacy Policy", login_page.PRIVACY_POLICY_LINK, timeout=CHECK_TIMEOUT)
        checks.check("Link — Terms of Use", login_page.TERMS_OF_USE_LINK, timeout=CHECK_TIMEOUT)

        record_property(
            "result_description",
            f"{checks.publish()}. Theme {active_theme!r}, "
            f"--primary {palette.get('--primary', 'unset')}, "
            f"background art {hero_background_url or 'none'}.",
        )

    def test_login_page_theme_switcher(self, record_property):
        """The palette menu offers each theme and repaints the page when used."""
        login_page = self.open_login_page()
        checks = ElementChecks(login_page, record_property, page_name="Teacher Login — Theme Switcher")

        checks.check("Theme picker", login_page.THEME_PICKER, timeout=CHECK_TIMEOUT)
        theme_options = checks.safe_call(
            lambda: (login_page.open_theme_menu(), login_page.get_theme_option_labels())[1]
        )
        for expected_theme in EXPECTED_THEMES:
            checks.check_condition(
                f"Theme option — {expected_theme}",
                any(option.startswith(expected_theme) for option in theme_options),
                detail=f"menu offers: {theme_options}",
            )

        starting_theme = login_page.get_active_theme()
        starting_primary = login_page.get_theme_palette(["--primary"]).get("--primary", "")

        # Switching themes rewrites the palette the whole page draws from, so a
        # picker that opens but leaves --primary alone is a dead control even
        # though every element is still on screen.
        grey_theme = checks.safe_call(lambda: login_page.select_theme("Grey"), default="")
        checks.check_condition(
            "Selecting Grey switches the active theme",
            grey_theme and grey_theme != starting_theme,
            detail=f"data-theme {starting_theme!r} -> {grey_theme!r}",
        )
        grey_primary = login_page.get_theme_palette(["--primary"]).get("--primary", "")
        checks.check_condition(
            "Grey theme repaints the primary colour",
            grey_primary and to_rgb(grey_primary) != to_rgb(starting_primary),
            detail=f"--primary {starting_primary or 'unset'} -> {grey_primary or 'unset'}",
        )
        # Settled, not immediate: the button transitions to its new colour, so
        # an instant read lands part-way between the two themes.
        grey_button = login_page.get_settled_computed_style(
            login_page.SIGN_IN_BUTTON, ("background-color",), CHECK_TIMEOUT
        )
        checks.check_condition(
            "Sign In button follows the active theme",
            to_rgb(grey_button.get("background-color")) == to_rgb(grey_primary),
            detail=(
                f"button {grey_button.get('background-color', 'unreadable')} "
                f"vs --primary {grey_primary or 'unset'}"
            ),
        )

        restored_theme = checks.safe_call(lambda: login_page.select_theme("Default"), default="")
        restored_primary = login_page.get_theme_palette(["--primary"]).get("--primary", "")
        checks.check_condition(
            "Switching back to Default restores the palette",
            restored_theme == starting_theme and to_rgb(restored_primary) == to_rgb(starting_primary),
            detail=(
                f"data-theme {restored_theme!r}, --primary {restored_primary or 'unset'}; "
                f"started at {starting_theme!r} / {starting_primary or 'unset'}"
            ),
        )

        record_property(
            "result_description",
            f"{checks.publish()}. Themes offered: {theme_options}; "
            f"{starting_theme!r} ({starting_primary or 'unset'}) -> "
            f"{grey_theme or 'unchanged'} ({grey_primary or 'unset'}) -> "
            f"{restored_theme or 'unchanged'} ({restored_primary or 'unset'}).",
        )
