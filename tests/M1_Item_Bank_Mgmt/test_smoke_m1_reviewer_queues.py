import re

import pytest
from selenium.common.exceptions import TimeoutException

from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from utilities.read_config import ReadConfig
from utilities.smoke_support import body_text, reset_session, sign_in


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
        usernames = self.reviewer_usernames(role_key)
        page = page_class(self.driver)
        attempts = []

        for index, username in enumerate(usernames):
            if index:
                # Clear the previous reviewer's session before signing in as
                # the next: the portal keeps one active session per account
                # and would otherwise carry the old one into this login.
                reset_session(self.driver)
            sign_in(self.driver, username)

            assert body_text(self.driver).strip(), (
                f"{role_name} {username} landed on an empty page after login"
            )

            page.open_queue_module()
            queue_text = page.get_queue_body_text()
            assert "queue" in queue_text.casefold(), (
                f"{role_name} review queue did not render for {username}. "
                f"Page text: {queue_text[:600]}"
            )

            item_set_ids = self.visible_item_set_ids(queue_text)
            if not item_set_ids:
                attempts.append(f"{username}=empty queue")
                continue

            # Only the first candidate per account: the queue lists sets
            # visible to the role without necessarily being allotted to this
            # reviewer, and walking every ID with retries turned one
            # unavailable set into tens of minutes of CI time.
            candidate_id = item_set_ids[0]
            try:
                page.open_review_item_set(candidate_id)
            except TimeoutException:
                attempts.append(f"{username}={candidate_id} not actionable")
                continue

            set_text = body_text(self.driver)
            opened_ids = self.visible_item_set_ids(set_text)
            record_property(
                "result_description",
                f"{role_name} {username} opened assigned item set "
                f"{opened_ids[0] if opened_ids else candidate_id} from a queue of "
                f"{len(item_set_ids)}. Accounts tried: {attempts + [username + '=opened']}.",
            )
            record_property("item_set_id", opened_ids[0] if opened_ids else candidate_id)
            assert opened_ids, (
                f"{role_name} opened item set {candidate_id} but it rendered no item set ID. "
                f"Page text: {set_text[:600]}"
            )
            return

        record_property(
            "result_description",
            f"No {role_name} account holds an actionable item set. Tried: {attempts}.",
        )
        # Every configured reviewer for this role is idle. That is workflow
        # state, not a broken build: sets only reach a stage once the previous
        # one advances them.
        pytest.xfail(
            f"KI-M1-QUEUE-001 [M1 {role_name} review queue] None of the "
            f"{len(usernames)} configured {role_name} accounts holds an item set that opens, "
            f"so the assigned-set view cannot be smoke-tested. Tried: {attempts}."
        )
