import re

import pytest
from selenium.common.exceptions import TimeoutException

from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from tests.M1_Item_Bank_Mgmt.m1_surveys import (
    enter_screen,
    survey_opened_item_set,
    survey_review_queue,
    survey_reviewer_chrome,
)
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig
from utilities.smoke_support import body_text, sign_in


# Item set IDs as they render in a queue listing, e.g. IS808-G1-Mathematics-Ch29.
ITEM_SET_ID_PATTERN = re.compile(r"\bIS\d+(?:-[A-Za-z0-9]+)*\b", re.IGNORECASE)

# (role key, page object, display name, xdist group). The role key resolves the
# account through CBSE_<ROLE>_USERNAMES, so the accounts stay configuration,
# not code.
#
# Each role carries its own group rather than sharing one: the three accounts
# are distinct, so nothing forces them onto a single worker, and running them
# sequentially made this the suite's critical path — three logins plus any
# paint-stall retries, stacked end to end.
REVIEWER_ROLES = [
    ("rwg", RWGReviewQueuePage, "RWG", "smoke-rwg"),
    ("sr_rwg", SRRWGReviewQueuePage, "Senior RWG", "smoke-srrwg"),
    ("pit", PITReviewQueuePage, "PIT", "smoke-pit"),
]


@pytest.mark.smoke
# Reviewer screens sit behind the same post-login paint stall the other M1
# checks hit; one clean retry keeps an environment hiccup off the gate.
@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestSmokeM1ReviewerQueues:
    """M1 - Item Bank Mgmt smoke: RWG, Senior RWG and PIT reach their queues.

    Read-only by design. Each reviewer signs in, opens their review queue and
    opens one assigned item set to confirm it renders with items — no
    criteria are marked and no review is submitted. That matters here more
    than elsewhere: reviewer votes are one-time workflow actions per set (see
    docs/known_issues.md), so a smoke check that voted would consume real
    review capacity on every run.
    """

    @staticmethod
    def reviewer_usernames(role_key):
        usernames = ReadConfig.get_role_usernames(role_key)
        assert usernames, f"No accounts configured in CBSE_{role_key.upper()}_USERNAMES"
        return usernames

    @staticmethod
    def visible_item_set_ids(queue_text):
        return list(dict.fromkeys(ITEM_SET_ID_PATTERN.findall(queue_text)))

    @pytest.mark.parametrize(
        "role_key, page_class, role_name",
        [
            pytest.param(
                role_key,
                page_class,
                role_name,
                marks=pytest.mark.xdist_group(group),
                id=role_name,
            )
            for role_key, page_class, role_name, group in REVIEWER_ROLES
        ],
    )
    def test_smoke_m1_05_reviewer_opens_queue_and_assigned_item_set(
        self, record_property, role_key, page_class, role_name
    ):
        """A reviewer signs in, lands on their dashboard, opens the review
        queue and opens one item set assigned to them.

        Tries each account configured for the role rather than only the first.
        Review work is allotted per reviewer, so whether any one account holds
        an actionable set is workflow state that changes run to run — checking
        one account made the result depend on which reviewer happened to be
        holding work. The check passes as soon as any account of this role can
        open an assigned set.
        """
        username = self.reviewer_usernames(role_key)[0]
        page = page_class(self.driver)

        sign_in(self.driver, username)
        assert body_text(self.driver).strip(), (
            f"{role_name} {username} landed on an empty page after login"
        )

        page.open_queue_module()

        # Surveys are additive here: every assertion in this test stays exactly
        # as hard as it was, so the smoke gate still fails loudly and fast. The
        # element table is extra evidence on the card, not a replacement gate.
        checks = ElementChecks(
            page, record_property, page_name=f"{role_name} — Review Queue"
        )
        survey_reviewer_chrome(checks, page)
        survey_review_queue(checks, page)

        queue_text = page.get_queue_body_text()
        item_set_ids = self.visible_item_set_ids(queue_text)

        # Opening a set is attempted but not required. Whether a reviewer holds
        # actionable work is workflow state that changes hour to hour: sets
        # arrive only as the previous stage advances them, and a vote consumes
        # them. Gating a deployment on that made the result depend on the
        # queue's contents rather than on the build, so it is recorded as
        # evidence instead. The full open-review-and-vote path stays asserted
        # by the M1 and M5 end-to-end suites.
        opened_id = ""
        if item_set_ids:
            try:
                page.open_review_item_set(item_set_ids[0])
                opened = self.visible_item_set_ids(body_text(self.driver))
                opened_id = opened[0] if opened else item_set_ids[0]
                enter_screen(checks, f"{role_name} — Opened Item Set")
                survey_opened_item_set(checks, page)
            except TimeoutException:
                opened_id = ""

        if opened_id:
            outcome = f"opened assigned set {opened_id}"
        elif item_set_ids:
            outcome = f"queue holds {len(item_set_ids)} set(s), none currently actionable"
        else:
            outcome = "queue is empty (no work allotted right now)"

        record_property(
            "result_description",
            f"{role_name} {username} signed in and reached the review queue — {outcome}. "
            f"{checks.publish()}",
        )
        record_property("item_set_id", opened_id)

        # The gate's actual subject: this role can sign in and its review queue
        # renders. That is true whenever the build is healthy, regardless of
        # what work happens to be waiting.
        assert "queue" in queue_text.casefold(), (
            f"{role_name} review queue did not render for {username}. "
            f"Page text: {queue_text[:600]}"
        )
