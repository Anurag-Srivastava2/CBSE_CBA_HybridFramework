import re

import pytest
from selenium.webdriver.common.by import By

from pages.admin.admin_portal_page import AdminPortalPage
from utilities.read_config import ReadConfig
from utilities.smoke_support import sign_in


@pytest.mark.smoke
# Shares the single admin account with the M2 smoke checks, so both sit in one
# xdist group and run on the same worker under `--dist loadgroup`.
@pytest.mark.xdist_group("smoke-admin")
@pytest.mark.usefixtures("setup")
class TestSmokeM3ItemTesting:
    """M3 - Item Testing smoke: the psychometrics workspace is reachable.

    M3 covers IRT 3PL calibration, ICC generation, DIF analysis and the
    resulting item-bank decisions (TC-ITM-05..08). None of that is exposed in
    the current build, so this check probes for the module and reports the gap
    as KI-M3-ITM-001 rather than asserting against a screen that is not there.
    """

    # Acronyms are matched on word boundaries — a substring test for "irt" or
    # "icc" happily matches unrelated navigation copy.
    SECTION_NAME_PATTERNS = (
        r"item\s*testing",
        r"psychometric",
        r"item\s*analysis",
        r"\bIRT\b",
        r"\bICC\b",
        r"\bDIF\b",
        r"item\s*characteristic\s*curve",
        r"differential\s*item\s*functioning",
        r"piloting",
    )

    # Every interactive target, not just <nav>/<aside> descendants: the portal
    # renders its sidebar as a bare <ul><li><button> inside #root, so a
    # nav-scoped probe finds nothing and would report the module as absent
    # even on a build that ships it.
    NAVIGATION_TARGETS = (
        By.XPATH,
        "//a | //button | //*[@role='menuitem'] | //*[@role='tab'] | //*[@role='link']",
    )

    def get_navigation_labels(self):
        """Full label text for every visible interactive target.

        The sidebar clips its captions with a CSS ellipsis, and `.text`
        returns *rendered* text — so it yields 'Workfl' and a bare 'Item' that
        could equally be 'Item Bank' or 'Item Testing'. textContent is
        unaffected by the clipping and carries the real name; aria-label and
        title cover icon-only controls that have no text node at all.
        """
        labels = []
        for element in self.driver.find_elements(*self.NAVIGATION_TARGETS):
            try:
                if not element.is_displayed():
                    continue
                candidates = [
                    element.get_attribute("textContent") or "",
                    element.text,
                    element.get_attribute("aria-label") or "",
                    element.get_attribute("title") or "",
                ]
            except Exception:
                continue
            for candidate in candidates:
                label = " ".join(candidate.split())
                if label and len(label) < 60 and label not in labels:
                    labels.append(label)
        return labels

    @classmethod
    def find_item_testing_matches(cls, candidates):
        return [
            candidate
            for candidate in candidates
            if any(re.search(pattern, candidate, re.IGNORECASE) for pattern in cls.SECTION_NAME_PATTERNS)
        ]

    def test_smoke_m3_01_item_testing_workspace_is_reachable(self, record_property):
        """The portal exposes an Item Testing / psychometrics workspace."""
        username = ReadConfig.get_role_usernames("admin")[0]
        sign_in(self.driver, username)

        portal = AdminPortalPage(self.driver)
        portal.wait_for_application_ready()

        navigation_labels = self.get_navigation_labels()
        matches = self.find_item_testing_matches(navigation_labels)
        # Evidence only: the terms can appear in page copy without a way in.
        mentioned_in_page_text = bool(self.find_item_testing_matches([portal.body_text()]))
        record_property(
            "result_description",
            f"Probed the portal as {username} for an Item Testing workspace. "
            f"Navigation exposes: {navigation_labels}. Matching entries: {matches or 'none'}; "
            f"terms present in page text: {mentioned_in_page_text}.",
        )

        # Without this the check cannot tell "the module is absent" from "the
        # page never rendered", and a blank portal would quietly xfail.
        assert navigation_labels, (
            f"Signed in as {username} but the portal rendered no navigation at all, "
            "so the Item Testing probe has nothing to search."
        )

        if not matches:
            pytest.xfail(
                "KI-M3-ITM-001 [M3 Item Testing] The build exposes no Item Testing / "
                "psychometrics workspace (IRT calibration, ICC, DIF), so TC-ITM-05..08 "
                f"have no screen to smoke-test. Navigation found: {navigation_labels}."
            )

        portal.open_named_section(matches[0])
        assert self.find_item_testing_matches([portal.body_text()]), (
            f"Opening {matches[0]!r} did not render any Item Testing content. "
            f"Page text: {portal.body_text()[:1000]}"
        )
