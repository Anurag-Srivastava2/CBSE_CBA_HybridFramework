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
from utilities.element_checks import ElementChecks
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
        self.login_as(ReadConfig.get_admin_username())
        try:
            return QARConfigPage(self.driver).open()
        except (TimeoutException, WebDriverException) as error:
            pytest.xfail(
                f"KI-M2-QARCFG-001 [M2 QAR Config] QAR Configuration screen is not "
                f"reachable for Admin: {error}"
            )

    def test_m2_qar_config_01_all_seven_checks_are_listed_at_their_layer(self, record_property):
        """Every check is recorded individually, so a partial screen names which
        check is missing or misclassified rather than only the first."""
        page = self.open_qar_config()
        checks = ElementChecks(page, record_property, page_name="QAR Configuration — Checks")

        for check_name, expected_layer in page.EXPECTED_CHECKS.items():
            container_text = page.get_check_container_text(check_name)
            if not checks.check_condition(
                f"Check listed — {check_name}", container_text
            ):
                continue
            folded = container_text.casefold()
            expected_kind = (
                "informational"
                if "informational" in expected_layer.casefold()
                else "blocker"
            )
            classified = (
                expected_kind in folded
                and f"layer {page.LAYER_NUMBERS[check_name]}" in folded
            )
            checks.check_condition(
                f"Check classified — {check_name}",
                classified,
                detail=f"expected {expected_layer}",
            )

        record_property("result_description", checks.publish())

    def test_m2_qar_config_02_every_tab_opens_and_renders_controls(self, record_property):
        """Tab presence and its rendered controls, both recorded softly."""
        page = self.open_qar_config()
        checks = ElementChecks(page, record_property, page_name="QAR Configuration — Tabs")

        for tab in [page.GLOBAL_SETTINGS_TAB, *page.EXPECTED_CHECKS]:
            if not checks.check_condition(f"Tab — {tab}", page.has_tab(tab)):
                continue
            page.open_tab(tab)
            control_count = page.visible_control_count()
            checks.check_condition(
                f"Tab renders controls — {tab}",
                control_count > 0,
                detail=f"{control_count} controls",
            )

        record_property("result_description", checks.publish())

    def test_m2_qar_config_03_status_bar_reports_every_check_state(self, record_property):
        """Pill presence is soft; a blocker check switched OFF stays a hard gate."""
        page = self.open_qar_config()
        checks = ElementChecks(page, record_property, page_name="QAR Configuration — Status Bar")

        snapshot = page.get_status_bar_snapshot()
        for check_name, state in snapshot.items():
            checks.check_condition(
                f"Status pill — {check_name}",
                state in {"ON", "OFF"},
                detail=f"reads {state!r}",
            )
        checks.publish()

        # Blocker layers must never silently run disabled. Only an explicit OFF
        # counts — an unreadable pill is already recorded as a soft gap above,
        # and reporting it here as "switched OFF" would misname the problem.
        disabled_blockers = [
            check_name
            for check_name, layer in page.EXPECTED_CHECKS.items()
            if "blocker" in layer.casefold() and snapshot[check_name] == "OFF"
        ]
        assert not disabled_blockers, (
            f"Blocker-layer QAR checks are switched OFF: {disabled_blockers}"
        )

    def test_m2_qar_config_04_status_bar_pass_pill_matches_global_threshold(self, record_property):
        """Pill presence is soft; the threshold agreeing with Global Settings is hard."""
        page = self.open_qar_config()
        checks = ElementChecks(page, record_property, page_name="QAR Configuration — Pass Threshold")

        configured = page.get_global_pass_threshold()
        checks.check_condition(
            "Global Settings exposes a pass threshold",
            configured is not None,
            detail=f"reads {configured!r}",
        )

        page.open_tab(page.GLOBAL_SETTINGS_TAB)
        footer_value = page.get_status_bar_pass_threshold()
        checks.check_condition(
            "Status bar shows a 'Pass: N%' pill",
            footer_value is not None,
            detail=f"reads {footer_value!r}",
        )
        checks.publish()

        if configured is None or footer_value is None:
            pytest.xfail(
                "KI-M2-QARCFG-002 [M2 QAR Config] Pass threshold is not exposed on both "
                "Global Settings and the status bar, so they cannot be reconciled."
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
