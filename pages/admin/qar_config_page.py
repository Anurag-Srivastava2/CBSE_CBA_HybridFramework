import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pages.admin.admin_portal_page import AdminPortalPage


class QARConfigPage(AdminPortalPage):
    """Read-only assertions for the Admin QAR configuration screen."""

    EXPECTED_CHECKS = {
        "Hard Validation": "L1 Blocker",
        "Metadata Alignment": "L1 Blocker",
        "Bias Detection": "L2 Informational",
        "Grammar": "L2 Informational",
        "Clarity": "L2 Informational",
        "Duplicate Detection": "L3 Blocker",
        "Plagiarism Detection": "L3 Blocker",
    }
    STATUS_LABELS = {
        "Hard Validation": "Hard Validation",
        "Metadata Alignment": "Metadata",
        "Bias Detection": "Bias",
        "Grammar": "Grammar",
        "Clarity": "Clarity",
        "Duplicate Detection": "Duplicate",
        "Plagiarism Detection": "Plagiarism",
    }
    LAYER_NUMBERS = {
        "Hard Validation": 1,
        "Metadata Alignment": 1,
        "Bias Detection": 2,
        "Grammar": 2,
        "Clarity": 2,
        "Duplicate Detection": 3,
        "Plagiarism Detection": 3,
    }
    GLOBAL_SETTINGS_TAB = "Global Settings"
    GLOBAL_SETTING_LABELS = {
        "pass_threshold": "Pass Threshold",
        "batch_frequency": "Batch Run Frequency",
        "batch_time": "Scheduled Batch Time",
    }
    CONFIG_SAVE_BUTTONS = [
        (By.XPATH, "//button[normalize-space()='Save' or normalize-space()='Save Changes']"),
        (By.XPATH, "//button[contains(normalize-space(),'Save') and not(@disabled)]"),
    ]
    RESET_RULES_BUTTONS = [
        (By.XPATH, "//button[normalize-space()='Reset Rules']"),
        (By.XPATH, "//button[contains(normalize-space(),'Reset')]"),
    ]
    SAVE_CONFIRMATION_MARKERS = ("saved", "successfully", "updated")

    VISIBLE_HELPER_SCRIPT = r"""
        const visible = element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0
                && style.display !== 'none' && style.visibility !== 'hidden';
        };
    """
    FIND_CONTROL_SCRIPT = VISIBLE_HELPER_SCRIPT + r"""
        // Resolve a settings label to its control by document order rather than by
        // shared ancestry: the screen is a Setting | Value | Description table, so a
        // label is followed by its own control. Ancestry alone is unreliable — the
        // nearest ancestor holding the label can span the whole panel.
        const wanted = arguments[0].trim().toLowerCase();
        const others = (arguments[1] || [])
            .map(label => String(label).trim().toLowerCase())
            .filter(label => label && label !== wanted);

        const leafLabel = needle => {
            const matches = Array.from(document.querySelectorAll('*')).filter(element => {
                if (!visible(element)) {
                    return false;
                }
                const text = (element.innerText || element.textContent || '')
                    .trim().toLowerCase();
                if (!text.includes(needle)) {
                    return false;
                }
                // Keep only the innermost element still carrying the label text.
                return !Array.from(element.children).some(child =>
                    (child.innerText || child.textContent || '')
                        .trim().toLowerCase().includes(needle));
            });
            return matches[0] || null;
        };

        const label = leafLabel(wanted);
        if (!label) {
            return null;
        }
        const follows = (anchor, node) => !!(
            anchor.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING
        );
        const control = Array.from(
            document.querySelectorAll('input, select, textarea')
        ).filter(visible).filter(candidate => follows(label, candidate))[0];
        if (!control) {
            return null;
        }
        // If another setting's label sits between this label and that control, the
        // control belongs to that other setting and this value is display-only.
        for (const other of others) {
            const otherLabel = leafLabel(other);
            if (otherLabel && follows(label, otherLabel) && follows(otherLabel, control)) {
                return null;
            }
        }
        return control;
    """
    SET_CONTROL_VALUE_SCRIPT = r"""
        const control = arguments[0];
        const value = String(arguments[1]);
        const tag = control.tagName.toLowerCase();
        if (tag === 'select') {
            const wanted = value.trim().toLowerCase();
            const options = Array.from(control.options);
            const option = options.find(candidate =>
                    (candidate.text || '').trim().toLowerCase() === wanted
                    || (candidate.value || '').trim().toLowerCase() === wanted)
                || options.find(candidate =>
                    (candidate.text || '').trim().toLowerCase().includes(wanted));
            if (!option) {
                return false;
            }
            Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value')
                .set.call(control, option.value);
        } else {
            const prototype = tag === 'textarea'
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;
            control.focus();
            Object.getOwnPropertyDescriptor(prototype, 'value').set.call(control, value);
        }
        control.dispatchEvent(new Event('input', {bubbles: true}));
        control.dispatchEvent(new Event('change', {bubbles: true}));
        control.dispatchEvent(new Event('blur', {bubbles: true}));
        return true;
    """
    COUNT_CONTROLS_SCRIPT = VISIBLE_HELPER_SCRIPT + r"""
        return Array.from(document.querySelectorAll(
            "input, select, textarea, [role='switch'], [role='checkbox'], [role='slider']"
        )).filter(visible).length;
    """

    def open(self):
        self.open_named_section("QAR Configuration", "QAR Config", "QAR")
        self.wait_utils.until_condition(
            lambda driver: all(
                check.casefold()
                in driver.find_element(By.TAG_NAME, "body").text.casefold()
                for check in self.EXPECTED_CHECKS
            ),
            timeout=30,
        )
        return self

    def reload(self):
        """Re-render the screen from the server to prove a saved value persisted."""
        self.driver.refresh()
        self.wait_for_application_ready()
        return self.open()

    # --- Tabs -----------------------------------------------------------------

    def tab_locators(self, tab_name):
        return [
            (
                By.XPATH,
                f"//*[self::button or self::a or @role='tab'][normalize-space()='{tab_name}']",
            ),
            (
                By.XPATH,
                f"//*[self::button or self::a or @role='tab']"
                f"[contains(normalize-space(),'{tab_name}')]",
            ),
            (
                By.XPATH,
                f"//*[normalize-space()='{tab_name}']"
                f"/ancestor::*[self::button or self::a or @role='tab'][1]",
            ),
        ]

    def has_tab(self, tab_name):
        return any(
            element.is_displayed()
            for locator in self.tab_locators(tab_name)
            for element in self.driver.find_elements(*locator)
        )

    def open_tab(self, tab_name):
        self.click_any_element(self.tab_locators(tab_name))
        self.wait_for_application_ready()
        return self

    def visible_control_count(self):
        """Number of rendered form controls, used to prove a tab actually rendered."""
        return int(self.driver.execute_script(self.COUNT_CONTROLS_SCRIPT))

    # --- Bottom status bar ----------------------------------------------------

    def get_status_pill_state(self, check_name):
        """Return 'ON'/'OFF' from the footer pill for a check, or None when absent."""
        label = self.STATUS_LABELS[check_name]
        match = re.search(
            rf"\b{re.escape(label)}\s*:\s*(ON|OFF)\b",
            self.body_text(),
            re.IGNORECASE,
        )
        return match.group(1).upper() if match else None

    def get_status_bar_snapshot(self):
        return {
            check_name: self.get_status_pill_state(check_name)
            for check_name in self.EXPECTED_CHECKS
        }

    def get_status_bar_pass_threshold(self):
        """Read the footer 'Pass: 60%' pill."""
        match = re.search(
            r"\bpass\s*:\s*(\d+(?:\.\d+)?)\s*%",
            self.body_text(),
            re.IGNORECASE,
        )
        return float(match.group(1)) if match else None

    # --- Global settings ------------------------------------------------------

    def find_setting_control(self, label):
        siblings = [
            other
            for other in self.GLOBAL_SETTING_LABELS.values()
            if other.casefold() != str(label).casefold()
        ]
        return self.driver.execute_script(self.FIND_CONTROL_SCRIPT, label, siblings)

    def get_setting_value(self, label):
        control = self.find_setting_control(label)
        if control is None:
            return None
        return (control.get_attribute("value") or "").strip()

    def set_setting_value(self, label, value):
        control = self.find_setting_control(label)
        if control is None:
            # Custom (non-native) dropdowns render as buttons with role=combobox.
            self.select_option_by_visible_text(label, str(value))
            return
        self.element_utils.scroll_to_element(control)
        self.pause_before_action()
        applied = self.driver.execute_script(
            self.SET_CONTROL_VALUE_SCRIPT, control, str(value)
        )
        if not applied:
            raise TimeoutException(
                f"{label!r} has no option matching {value!r}."
            )

    def read_global_settings(self):
        self.open_tab(self.GLOBAL_SETTINGS_TAB)
        return {
            key: self.get_setting_value(label)
            for key, label in self.GLOBAL_SETTING_LABELS.items()
        }

    def update_global_settings(self, **values):
        """Set any of pass_threshold, batch_frequency, batch_time by keyword."""
        unknown = set(values) - set(self.GLOBAL_SETTING_LABELS)
        if unknown:
            raise ValueError(f"Unknown global setting(s): {sorted(unknown)}")
        self.open_tab(self.GLOBAL_SETTINGS_TAB)
        for key, value in values.items():
            if value is None:
                continue
            self.set_setting_value(self.GLOBAL_SETTING_LABELS[key], value)
        return self

    def next_setting_value(self, key):
        """A valid value for a global setting that differs from the current one.

        Returns None when the control is absent or its value shape is unknown, so
        callers can report an environment gap instead of typing junk into the form.
        """
        label = self.GLOBAL_SETTING_LABELS[key]
        control = self.find_setting_control(label)
        if control is None:
            return None
        current = (control.get_attribute("value") or "").strip()
        if control.tag_name.lower() == "select":
            for option in control.find_elements(By.TAG_NAME, "option"):
                value = (option.get_attribute("value") or "").strip()
                if value and value != current and option.is_enabled():
                    return option.text.strip() or value
            return None
        if (control.get_attribute("type") or "text").lower() == "time":
            return "09:15" if current != "09:15" else "10:45"
        if re.fullmatch(r"\d+(?:\.\d+)?", current):
            if key == "pass_threshold":
                return "80" if current != "80" else "75"
            return str(int(float(current)) + 5)
        return None

    def is_save_enabled(self):
        return any(
            element.is_displayed() and element.is_enabled()
            for locator in self.CONFIG_SAVE_BUTTONS
            for element in self.driver.find_elements(*locator)
        )

    def save_configuration(self, timeout=20):
        """Save the screen and return the confirmation text, or '' when none shows."""
        self.click_any_element(self.CONFIG_SAVE_BUTTONS)
        self.confirm_if_prompted()
        self.wait_for_application_ready()
        try:
            self.wait_utils.until_condition(
                lambda driver: any(
                    marker in driver.find_element(By.TAG_NAME, "body").text.casefold()
                    for marker in self.SAVE_CONFIRMATION_MARKERS
                ),
                timeout=timeout,
            )
        except TimeoutException:
            return ""
        text = self.normalized_body_text()
        return next(
            (marker for marker in self.SAVE_CONFIRMATION_MARKERS if marker in text),
            "",
        )

    def reset_rules(self):
        self.click_any_element(self.RESET_RULES_BUTTONS)
        self.confirm_if_prompted()
        self.wait_for_application_ready()
        return self

    def get_check_container_text(self, check_name):
        layer_number = self.LAYER_NUMBERS[check_name]
        layer_label = self.STATUS_LABELS[check_name]
        return self.driver.execute_script(
            r"""
            const expected = arguments[0].trim().toLowerCase();
            const layerNumber = arguments[1];
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0
                    && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const labels = Array.from(document.querySelectorAll('td, th, div, section, article'))
                .filter(element => visible(element)
                    && (element.innerText || element.textContent || '')
                        .trim().toLowerCase().includes(expected));
            const containers = [];
            for (const label of labels) {
                let container = label;
                while (container && container !== document.body) {
                    const text = (container.innerText || container.textContent || '').trim();
                    const rect = container.getBoundingClientRect();
                    if (visible(container) && text.toLowerCase().includes('layer ' + layerNumber)
                        && text.toLowerCase().includes(expected)
                        && text.length < 800 && rect.width > 180 && rect.height < 350) {
                        containers.push({element: container, length: text.length});
                    }
                    container = container.parentElement;
                }
            }
            containers.sort((left, right) => left.length - right.length);
            return containers[0]
                ? (containers[0].element.innerText || containers[0].element.textContent || '').trim()
                : '';
            """,
            layer_label,
            layer_number,
        )

    def is_check_enabled(self, check_name):
        return self.get_status_pill_state(check_name) == "ON"

    def assert_all_checks_enabled(self):
        evidence = {}
        for check_name, expected_layer in self.EXPECTED_CHECKS.items():
            container_text = self.get_check_container_text(check_name)
            if not container_text:
                raise TimeoutException(f"QAR check {check_name!r} was not visible.")
            assert self.is_check_enabled(check_name), (
                f"QAR check {check_name!r} was visible but not enabled: {container_text}"
            )
            normalized = container_text.casefold()
            expected_kind = "informational" if "informational" in expected_layer.casefold() else "blocker"
            assert expected_kind in normalized, (
                f"{check_name} did not show expected layer {expected_layer}: {container_text}"
            )
            evidence[check_name] = container_text
        return evidence

    def get_similarity_threshold(self, check_name):
        self.open_tab(check_name)
        text = self.body_text()
        match = re.search(
            r"(?:similarity|match|threshold)[^\d]{0,80}(\d+(?:\.\d+)?)\s*%?",
            text,
            re.IGNORECASE,
        )
        return float(match.group(1)) if match else None

    def get_global_pass_threshold(self):
        """The configured pass threshold, read from its control before its text.

        Selenium element text never contains an <input> value, so the text regex
        alone can latch onto a nearby digit (a "1-100" range hint, a layer number)
        and silently report a threshold the screen never showed. The control is
        authoritative; the text scan stays as a fallback for read-only renderings.
        """
        text = self.get_global_settings_text()
        value = self.get_setting_value(self.GLOBAL_SETTING_LABELS["pass_threshold"])
        control_match = re.search(r"\d+(?:\.\d+)?", value or "")
        if control_match:
            return float(control_match.group())
        match = re.search(
            r"(?:global\s+)?pass\s+threshold[^\d]*(\d+(?:\.\d+)?)\s*%?",
            text,
            re.IGNORECASE,
        )
        return float(match.group(1)) if match else None

    def get_global_settings_text(self):
        self.open_tab(self.GLOBAL_SETTINGS_TAB)
        return self.body_text()

    def get_set_lock_threshold(self):
        text = self.get_global_settings_text()
        patterns = (
            r"(?:set\s+)?lock(?:ing)?\s+threshold[^\d]*(\d+(?:\.\d+)?)\s*%?",
            r"failure\s+(?:rate\s+)?threshold[^\d]*(\d+(?:\.\d+)?)\s*%?",
            r"(?:lock|reject)[^\n]{0,80}(\d+(?:\.\d+)?)\s*%",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def get_max_retry_limit(self):
        text = self.get_global_settings_text()
        patterns = (
            r"max(?:imum)?\s+(?:qar\s+)?(?:retry|retries|resubmission)[^\d]*(\d+)",
            r"(?:retry|resubmission)\s+limit[^\d]*(\d+)",
            r"allowed\s+(?:retry|retries|resubmissions)[^\d]*(\d+)",
            r"max(?:imum)?\s+(?:revision|review)\s+cycles?[^\d]*(\d+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def get_typology_threshold_overrides(self):
        """Return configured typology percentages; an empty dict means global defaults."""
        tab = None
        for label in (
            "Typology Overrides",
            "Typology Thresholds",
            "Item Type Overrides",
        ):
            candidates = self.driver.find_elements(
                By.XPATH,
                f"//*[self::button or @role='tab'][normalize-space()='{label}']",
            )
            tab = next((candidate for candidate in candidates if candidate.is_displayed()), None)
            if tab:
                break
        if not tab:
            return {}
        self.driver.execute_script("arguments[0].click();", tab)
        self.wait_for_application_ready()
        text = self.body_text()
        overrides = {}
        for line in text.splitlines():
            match = re.search(
                r"^\s*([A-Za-z][A-Za-z /&()\-]{2,80}?)\s*(?:threshold|override|:)"
                r"[^\d]{0,30}(\d+(?:\.\d+)?)\s*%",
                line,
                re.IGNORECASE,
            )
            if match and "global" not in match.group(1).casefold():
                overrides[match.group(1).strip()] = float(match.group(2))
        return overrides

    def get_threshold_snapshot(self):
        """Read and validate the live Admin configuration used by downstream E2E checks."""
        checks = self.assert_all_checks_enabled()
        similarity_thresholds = {}
        for check_name in ("Duplicate Detection", "Plagiarism Detection"):
            threshold = self.get_similarity_threshold(check_name)
            assert threshold is not None, f"{check_name} threshold is missing."
            assert 0 <= threshold <= 100, (
                f"{check_name} threshold is outside 0..100: {threshold}."
            )
            similarity_thresholds[check_name] = threshold

        global_pass_threshold = self.get_global_pass_threshold()
        set_lock_threshold = self.get_set_lock_threshold()
        max_retry_limit = self.get_max_retry_limit()
        typology_overrides = self.get_typology_threshold_overrides()

        assert global_pass_threshold is not None, "Global QAR pass threshold is missing."
        assert 0 < global_pass_threshold <= 100, (
            f"Global QAR pass threshold is invalid: {global_pass_threshold}."
        )
        assert set_lock_threshold is not None, "QAR set-lock threshold is missing."
        assert 0 < set_lock_threshold <= 100, (
            f"QAR set-lock threshold is invalid: {set_lock_threshold}."
        )
        assert max_retry_limit is not None, "QAR retry/resubmission limit is missing."
        assert max_retry_limit >= 1, f"QAR retry limit is invalid: {max_retry_limit}."
        invalid_overrides = {
            typology: threshold
            for typology, threshold in typology_overrides.items()
            if not 0 < threshold <= 100
        }
        assert not invalid_overrides, (
            f"Invalid typology-specific thresholds: {invalid_overrides}."
        )
        return {
            "global_pass_threshold": global_pass_threshold,
            "set_lock_threshold": set_lock_threshold,
            "max_retry_limit": max_retry_limit,
            "similarity_thresholds": similarity_thresholds,
            "typology_overrides": typology_overrides,
            "required_checks": checks,
        }
