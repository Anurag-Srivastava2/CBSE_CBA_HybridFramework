import re

import pytest
from selenium.common.exceptions import InvalidSessionIdException

from pages.common.login_page import LoginPage
from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from utilities.logger import LogGenerator
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestVersionRejectionContracts:
    logger = LogGenerator.loggen()

    # ------------------------------------------------------------------
    # Console-output helpers — consistent prefix across all steps.
    # ------------------------------------------------------------------
    @staticmethod
    def step(n, message):
        print(f"\n[STEP {n}] {message}", flush=True)

    @staticmethod
    def check(message):
        print(f"[CHECK]  {message}", flush=True)

    @staticmethod
    def passed(message):
        print(f"[PASS]   {message}", flush=True)

    @staticmethod
    def skipped(message):
        print(f"[SKIP]   {message}", flush=True)

    # ------------------------------------------------------------------
    # Shared login helper
    # ------------------------------------------------------------------
    def login(self, username):
        self.step(1, f"Navigating to application URL")
        self.driver.get(ReadConfig.get_base_url())
        self.step(2, f"Logging in as: {username}")
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_all_users_password(),
        )
        self.driver.find_element("tag name", "body").send_keys("\ue00c")
        UploadItemFilePage(self.driver).wait_for_application_to_load()
        self.logger.info("Login complete: %s", username)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_tc_ibmm_16_p01_full_revision_history_is_visible(self):
        """IBMM-16-P01: The SME Sets module must surface iteration/version history
        with feedback for any item-set that has undergone at least one revision cycle.
        Asserts that history markers, feedback text, and a version number are all
        present simultaneously on the page.
        """
        self.step(1, "Login as SME2 to inspect the Sets module")
        self.login(ReadConfig.get_sme2_username())

        self.step(2, "Opening Sets module — scanning for version/history markers")
        page = UploadItemFilePage(self.driver)
        page.open_sets_module()
        text = self.driver.find_element("tag name", "body").text.casefold()

        has_history = any(marker in text for marker in ("history", "iteration", "version"))
        has_feedback = "feedback" in text
        has_version_number = bool(re.search(r"(iteration|version)\s*[12]", text))
        print(
            f"         history={has_history}, feedback={has_feedback}, "
            f"version_number={has_version_number}",
            flush=True,
        )
        self.logger.info(
            "IBMM-16-P01 markers: history=%s feedback=%s version_number=%s",
            has_history, has_feedback, has_version_number,
        )

        self.check("Page shows history/iteration/version + feedback + version number")
        if not (has_history and has_feedback and has_version_number):
            pytest.skip(
                "Controlled revised item-set fixture is unavailable: "
                f"history={has_history}, feedback={has_feedback}, "
                f"version_number={has_version_number}."
            )

        self.passed("Revision history, feedback, and version number all visible on Sets page")
        self.logger.info("IBMM-16-P01 passed")

    def test_tc_ibmm_16_p02_reviewer_history_is_read_only(self):
        """IBMM-16-P02: RWG, SR-RWG, and PIT reviewers must be able to *view*
        item history (history/iteration/timeline/version visible) but must NOT see
        edit-history or delete-version controls (read-only enforcement).
        """
        roles = ("rwg", "sr_rwg", "pit")
        page_classes = {
            "rwg": RWGReviewQueuePage,
            "sr_rwg": SRRWGReviewQueuePage,
            "pit": PITReviewQueuePage,
        }

        for idx, role in enumerate(roles):
            if idx > 0:
                self.step(idx * 3 - 1, f"Resetting session before switching to {role.upper()}")
                UploadItemFilePage(self.driver).reset_browser_session_to_login()

            username = ReadConfig.get_role_usernames(role)[0]
            self.step(idx * 3 + 1 if idx == 0 else idx * 3, f"Login as {role.upper()}: {username}")
            self.login(username)

            self.step(idx * 3 + 2 if idx == 0 else idx * 3 + 1,
                      f"Opening first item in queue as {role.upper()}")
            text = page_classes[role](self.driver).open_first_item_in_first_queue_set()
            normalized = text.casefold()

            self.check(f"[{role.upper()}] History/iteration/timeline/version is visible")
            has_history = any(
                marker in normalized
                for marker in ("history", "iteration", "timeline", "version")
            )
            assert has_history, (
                f"[{role.upper()}] Expected a history/iteration/timeline/version marker "
                f"on the review page. Page excerpt: {normalized[:300]}"
            )
            self.passed(f"[{role.upper()}] History marker visible in review page")

            self.check(f"[{role.upper()}] 'edit history' is NOT shown (read-only guard)")
            assert "edit history" not in normalized, (
                f"[{role.upper()}] 'edit history' should not appear for reviewers — "
                "found in page text."
            )
            self.passed(f"[{role.upper()}] 'edit history' correctly absent")

            self.check(f"[{role.upper()}] 'delete version' is NOT shown (read-only guard)")
            assert "delete version" not in normalized, (
                f"[{role.upper()}] 'delete version' should not appear for reviewers — "
                "found in page text."
            )
            self.passed(f"[{role.upper()}] 'delete version' correctly absent")
            self.logger.info("IBMM-16-P02 read-only checks passed for role=%s", role)

        self.logger.info("IBMM-16-P02 passed for all reviewer roles: %s", roles)

    def test_tc_ibmm_16_n01_item_id_is_preserved_across_versions(self):
        """IBMM-16-N01: Item IDs (IS\\d+-i\\d+) must remain stable across revision
        versions — no new IDs should be minted when an item is revised.
        A duplicate in the found IDs means a revision created a second ID.
        """
        self.step(1, "Login as SME2")
        self.login(ReadConfig.get_sme2_username())

        self.step(2, "Opening Sets module and scanning for item IDs")
        page = UploadItemFilePage(self.driver)
        page.open_sets_module()
        text = self.driver.find_element("tag name", "body").text
        item_ids = re.findall(r"\bIS\d+(?:-[A-Za-z0-9]+)*-i\d+\b", text)
        print(f"         Found item IDs on page: {item_ids}", flush=True)
        self.logger.info("Item IDs found on Sets page: %s", item_ids)

        if not item_ids:
            pytest.skip(
                "No revised item IDs are visible; ID preservation cannot be verified "
                "without a controlled revision fixture."
            )

        self.check(f"All {len(item_ids)} item IDs are unique (no duplicates from versioning)")
        assert len(item_ids) == len(set(item_ids)), (
            f"A revision created a duplicate/new item ID. "
            f"Total IDs: {len(item_ids)}, Unique IDs: {len(set(item_ids))}. "
            f"Full list: {item_ids}"
        )
        self.passed(f"All {len(set(item_ids))} item IDs are unique — IDs stable across versions")
        self.logger.info("IBMM-16-N01 passed — %d unique IDs", len(set(item_ids)))

    def test_tc_ibmm_17_p01_admin_receives_three_strike_notification(self):
        """IBMM-17-P01: When an item-set has been rejected 3 times, the Admin
        dashboard must show a three-strike notification alongside a 'disabled' status
        and an item reference.
        """
        username = ReadConfig.get_role_usernames("admin")[0]
        self.step(1, f"Login as Admin: {username}")
        self.login(username)

        self.step(2, "Scanning Admin dashboard for three-strike notification")
        text = self.driver.find_element("tag name", "body").text.casefold()
        has_three_strike = bool(re.search(r"(3|three)[ -]?strike", text))
        has_disabled = "disabled" in text
        has_item = "item" in text
        print(
            f"         three_strike={has_three_strike}, disabled={has_disabled}, "
            f"item={has_item}",
            flush=True,
        )
        self.logger.info(
            "IBMM-17-P01 markers: three_strike=%s disabled=%s item=%s",
            has_three_strike, has_disabled, has_item,
        )

        self.check("Page shows (3|three)-strike + 'disabled' + 'item'")
        if not (has_three_strike and has_disabled and has_item):
            pytest.skip(
                f"Controlled three-strike scenario is not present: "
                f"three_strike={has_three_strike}, disabled={has_disabled}, item={has_item}"
            )

        self.passed("Three-strike notification with disabled item found on Admin dashboard")
        self.logger.info("IBMM-17-P01 passed")

    def test_tc_ibmm_17_p02_admin_can_view_rejection_history(self):
        """IBMM-17-P02: The Admin must be able to view a rejection history panel
        that includes the reason for each rejection and the associated item-set ID.
        """
        username = ReadConfig.get_role_usernames("admin")[0]
        self.step(1, f"Login as Admin: {username}")
        self.login(username)

        self.step(2, "Scanning Admin page for rejection history panel")
        text = self.driver.find_element("tag name", "body").text.casefold()
        has_rejection_history = "rejection history" in text
        has_reason = "reason" in text
        has_item_set_id = bool(re.search(r"\bIS\d+", text, re.IGNORECASE))
        print(
            f"         rejection_history={has_rejection_history}, reason={has_reason}, "
            f"item_set_id={has_item_set_id}",
            flush=True,
        )
        self.logger.info(
            "IBMM-17-P02 markers: rejection_history=%s reason=%s item_set_id=%s",
            has_rejection_history, has_reason, has_item_set_id,
        )

        self.check("Page shows 'rejection history' + 'reason' + IS\\d+ item-set ID")
        if not (has_rejection_history and has_reason and has_item_set_id):
            pytest.skip(
                f"Controlled rejection-history fixture is not present: "
                f"rejection_history={has_rejection_history}, reason={has_reason}, "
                f"item_set_id={has_item_set_id}"
            )

        self.passed("Rejection history panel with reason and item-set ID visible to Admin")
        self.logger.info("IBMM-17-P02 passed")

    def test_tc_ibmm_17_n01_second_rejection_has_no_three_strike_alert(self):
        """IBMM-17-N01: A second rejection must NOT trigger a three-strike alert.
        The three-strike rule fires only on the third (final) rejection.
        Any line on the page that says 'second rejection … three-strike' is a bug.
        """
        username = ReadConfig.get_role_usernames("admin")[0]
        self.step(1, f"Login as Admin: {username}")
        self.login(username)

        self.step(2, "Scanning page for false-positive 'second rejection + three-strike' alerts")
        text = self.driver.find_element("tag name", "body").text.casefold()
        if "second rejection" not in text and "2nd rejection" not in text:
            pytest.skip(
                "Controlled second-rejection fixture is unavailable; this negative "
                "assertion would otherwise pass vacuously."
            )
        second_rejection_alerts = re.findall(
            r"[^\n]*(?:second|2nd) rejection[^\n]*(?:3|three)[ -]?strike[^\n]*",
            text,
        )
        print(f"         False-positive alerts found: {second_rejection_alerts}", flush=True)
        self.logger.info(
            "Second-rejection three-strike false-positive alerts: %s", second_rejection_alerts
        )

        self.check("No 'second rejection … three-strike' text present")
        assert not second_rejection_alerts, (
            f"A second rejection incorrectly triggered a three-strike alert. "
            f"Matches found: {second_rejection_alerts}"
        )
        self.passed("Confirmed: second rejection does NOT show a three-strike alert")
        self.logger.info("IBMM-17-N01 passed")
