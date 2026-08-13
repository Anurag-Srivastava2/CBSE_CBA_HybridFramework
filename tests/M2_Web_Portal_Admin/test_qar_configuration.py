"""Admin QAR Configuration screen: layers, tabs, global settings, status bar.

The QAR rule set is owned by Admin (M2) but consumed by M1/M5, so these tests
guard the configuration surface itself: every check is exposed at its declared
layer, every tab renders, edits to the global settings persist, and the footer
status bar stays in sync with what is configured.
"""

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from pages.admin.admin_portal_page import AdminPortalPage
from pages.admin.qar_config_page import QARConfigPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig


@pytest.mark.ui
@pytest.mark.usefixtures("setup")
class TestM2QARConfiguration:
    def login_as(self, username):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys("")
        page = AdminPortalPage(self.driver)
        page.wait_for_application_ready()
        return page

    def open_qar_config(self):
        self.login_as(ReadConfig.get_role_usernames("admin")[0])
        try:
            return QARConfigPage(self.driver).open()
        except (TimeoutException, WebDriverException) as error:
            pytest.xfail(
                f"KI-M2-QARCFG-001 [M2 QAR Config] QAR Configuration screen is not "
                f"reachable for Admin: {error}"
            )

    def test_m2_qar_config_01_all_seven_checks_are_listed_at_their_layer(self):
        page = self.open_qar_config()

        missing = [
            check_name
            for check_name in page.EXPECTED_CHECKS
            if not page.get_check_container_text(check_name)
        ]
        assert not missing, f"QAR checks are not rendered on the screen: {missing}"

        mismatched = {}
        for check_name, expected_layer in page.EXPECTED_CHECKS.items():
            container_text = page.get_check_container_text(check_name).casefold()
            expected_kind = (
                "informational"
                if "informational" in expected_layer.casefold()
                else "blocker"
            )
            if expected_kind not in container_text or (
                f"layer {page.LAYER_NUMBERS[check_name]}" not in container_text
            ):
                mismatched[check_name] = expected_layer
        assert not mismatched, (
            f"QAR checks are not classified as expected (check: expected layer): {mismatched}"
        )

    def test_m2_qar_config_02_every_tab_opens_and_renders_controls(self):
        page = self.open_qar_config()

        expected_tabs = [page.GLOBAL_SETTINGS_TAB, *page.EXPECTED_CHECKS]
        absent = [tab for tab in expected_tabs if not page.has_tab(tab)]
        assert not absent, f"QAR Configuration tabs are missing: {absent}"

        unrendered = []
        for tab in expected_tabs:
            page.open_tab(tab)
            if page.visible_control_count() == 0:
                unrendered.append(tab)
        assert not unrendered, (
            f"These tabs opened but rendered no configurable control: {unrendered}"
        )

    def test_m2_qar_config_03_status_bar_reports_every_check_state(self):
        page = self.open_qar_config()

        snapshot = page.get_status_bar_snapshot()
        missing_pills = [
            check_name for check_name, state in snapshot.items() if state is None
        ]
        assert not missing_pills, (
            f"Status bar has no ON/OFF pill for: {missing_pills}. "
            f"Status bar text: {page.body_text()[-500:]}"
        )
        assert all(state in {"ON", "OFF"} for state in snapshot.values()), snapshot

        # Blocker layers must never silently run disabled.
        disabled_blockers = [
            check_name
            for check_name, layer in page.EXPECTED_CHECKS.items()
            if "blocker" in layer.casefold() and snapshot[check_name] != "ON"
        ]
        assert not disabled_blockers, (
            f"Blocker-layer QAR checks are switched OFF: {disabled_blockers}"
        )

    def test_m2_qar_config_04_status_bar_pass_pill_matches_global_threshold(self):
        page = self.open_qar_config()

        configured = page.get_global_pass_threshold()
        assert configured is not None, "Global Settings does not expose a pass threshold."

        page.open_tab(page.GLOBAL_SETTINGS_TAB)
        footer_value = page.get_status_bar_pass_threshold()
        assert footer_value is not None, (
            f"Status bar has no 'Pass: N%' pill. Page text: {page.body_text()[-500:]}"
        )
        assert footer_value == configured, (
            f"Status bar shows Pass: {footer_value}% but Global Settings is configured "
            f"at {configured}%."
        )

    @pytest.mark.serial
    def test_m2_qar_config_05_global_settings_edits_persist_after_reload(self):
        page = self.open_qar_config()

        originals = page.read_global_settings()
        # Not every setting is a control in every build — Batch Run Frequency
        # currently renders its value as plain text — so assert on whatever the
        # screen actually exposes rather than failing on the read-only ones.
        editable = {key: value for key, value in originals.items() if value is not None}
        if not editable:
            pytest.xfail(
                "KI-M2-QARCFG-002 [M2 QAR Config] No Global Settings value is exposed "
                "as an editable control in this environment."
            )

        targets = {key: page.next_setting_value(key) for key in editable}
        targets = {key: value for key, value in targets.items() if value is not None}
        if not targets:
            pytest.xfail(
                "KI-M2-QARCFG-002 [M2 QAR Config] No Global Settings control exposed an "
                "alternate value that automation can safely set."
            )

        try:
            page.update_global_settings(**targets)
            assert page.is_save_enabled(), (
                "Save stayed disabled after editing Global Settings."
            )
            page.save_configuration()

            persisted = page.reload().read_global_settings()
            not_persisted = {
                key: (targets[key], persisted[key])
                for key in targets
                if str(persisted[key]).strip().casefold()
                != str(targets[key]).strip().casefold()
            }
            assert not not_persisted, (
                f"Global settings did not persist (setting: expected vs stored): "
                f"{not_persisted}"
            )

            if "pass_threshold" in targets:
                assert page.get_status_bar_pass_threshold() == float(
                    targets["pass_threshold"]
                ), "Status bar Pass pill did not follow the saved pass threshold."
        finally:
            self.restore_global_settings(page, originals, targets)

    @pytest.mark.serial
    def test_m2_qar_config_06_out_of_range_pass_threshold_is_rejected(self):
        page = self.open_qar_config()

        originals = page.read_global_settings()
        if originals["pass_threshold"] is None:
            pytest.xfail(
                "KI-M2-QARCFG-002 [M2 QAR Config] Pass Threshold control is not exposed "
                "in this environment."
            )

        try:
            page.update_global_settings(pass_threshold="150")
            if page.is_save_enabled():
                page.save_configuration()

            stored = page.reload().get_global_pass_threshold()
            assert stored is not None, "Pass threshold disappeared after an invalid edit."
            assert 0 < stored <= 100, (
                f"Out-of-range pass threshold was accepted and stored as {stored}."
            )
        finally:
            self.restore_global_settings(page, originals, {"pass_threshold": "150"})

    def test_m2_qar_config_07_non_admin_cannot_reach_qar_configuration(self):
        page = self.login_as(ReadConfig.get_role_usernames("teacher")[0])

        assert "qar configuration" not in page.normalized_body_text(), (
            "Teacher navigation exposes the Admin QAR Configuration section."
        )

        page.open_relative_url("/admin/qar-configuration")
        text = page.normalized_body_text()
        leaked = [
            check_name
            for check_name in QARConfigPage.EXPECTED_CHECKS
            if check_name.casefold() in text
        ]
        assert not leaked, (
            f"Teacher reached the QAR rule configuration by direct URL; visible checks: "
            f"{leaked}"
        )

    @staticmethod
    def restore_global_settings(page, originals, changed):
        """Put the shared QAR configuration back the way the test found it."""
        restore = {
            key: originals[key]
            for key in changed
            if originals.get(key) not in (None, "")
        }
        if not restore:
            return
        try:
            page.open()
            page.update_global_settings(**restore)
            page.save_configuration()
        except (TimeoutException, WebDriverException) as error:
            pytest.fail(
                f"Could not restore Admin global QAR settings to {restore}; the shared "
                f"environment may be left modified: {error}"
            )
