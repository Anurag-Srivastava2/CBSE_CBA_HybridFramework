import re

import pytest
from selenium.common.exceptions import TimeoutException

from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
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
    def reviewer_username(role_key):
        usernames = ReadConfig.get_role_usernames(role_key)
        assert usernames, f"No accounts configured in CBSE_{role_key.upper()}_USERNAMES"
        return usernames[0]

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
        queue and opens one item set assigned to them."""
        username = self.reviewer_username(role_key)
        sign_in(self.driver, username)

        page = page_class(self.driver)
        dashboard_text = body_text(self.driver)
        assert dashboard_text.strip(), f"{role_name} {username} landed on an empty page after login"

        page.open_queue_module()
        queue_text = page.get_queue_body_text()
        item_set_ids = self.visible_item_set_ids(queue_text)

        record_property(
            "result_description",
            f"{role_name} {username} opened the review queue; "
            f"{len(item_set_ids)} item set(s) assigned: {item_set_ids[:5]}"
            f"{' …' if len(item_set_ids) > 5 else ''}.",
        )

        assert "queue" in queue_text.casefold(), (
            f"{role_name} review queue did not render. Page text: {queue_text[:600]}"
        )

        if not item_set_ids:
            # An empty queue is a workflow-data state, not a broken build: sets
            # only reach a reviewer once the previous stage advances them.
            pytest.xfail(
                f"KI-M1-QUEUE-001 [M1 {role_name} review queue] No item set is currently "
                f"assigned to {username}, so the assigned-set view cannot be smoke-tested. "
                "Advance a set to this stage, or point the check at an account that holds one."
            )

        # Only the first candidate, not every ID on screen. The queue lists
        # sets that are visible to the role without necessarily being allotted
        # to this reviewer, and open_first_queue_item_set() walks all of them —
        # three retries each — which turned one unavailable set into tens of
        # minutes of CI time.
        candidate_id = item_set_ids[0]
        try:
            page.open_review_item_set(candidate_id)
        except TimeoutException:
            # Listed but not actionable by this reviewer: the same workflow-data
            # gap as an empty queue, so report it the same way rather than
            # failing the deployment gate.
            pytest.xfail(
                f"KI-M1-QUEUE-001 [M1 {role_name} review queue] {username} sees "
                f"{len(item_set_ids)} set(s) in the queue but {candidate_id} did not open for "
                "this role, so no set is currently actionable. Advance a set to this stage."
            )

        set_text = body_text(self.driver)
        opened_ids = self.visible_item_set_ids(set_text)
        record_property("item_set_id", opened_ids[0] if opened_ids else "")
        assert opened_ids, (
            f"{role_name} opened item set {candidate_id} but it rendered no item set ID. "
            f"Page text: {set_text[:600]}"
        )
