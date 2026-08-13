"""PIT revision -> SME correction -> PIT approval/publication E2E workflow."""

from uuid import uuid4

import pytest

from pages.pit.review_queue_page import PITReviewQueuePage
from utilities.pit_item_lifecycle import PITItemLifecycle


REVISION_STATUS_MARKERS = (
    "need improvement",
    "needs improvement",
    "needs revision",
    "revise",
)
PENDING_PIT_STATUS_MARKERS = (
    "pending",
    "under review",
    "revised",
    "awaiting approval",
    "pit review",
)


def _item_status(statuses, item_id):
    compact_expected = "".join(item_id.split()).casefold()
    for observed_id, status in statuses.items():
        if "".join(observed_id.split()).casefold() == compact_expected:
            return status
    return ""


# Drives the app-assigned RWG/SRRWG reviewer and the PIT panel. The portal keeps
# one session per account and assigns the same reviewer to every Grade 1
# Mathematics set, so two of these flows at once sign each other out.
@pytest.mark.serial
@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestPITSMERevisionApproval:
    @pytest.fixture
    def isolated_pit_lifecycle(self):
        """Track only this test's UUID-backed set and terminalise it on failure."""
        lifecycle = PITItemLifecycle(self.driver)
        created_contexts = []
        yield lifecycle, created_contexts
        for context in created_contexts:
            lifecycle.best_effort_finalize(context)

    def test_e2e_pit_revision_sme_resubmit_then_pit_approval_and_publication(
        self,
        request,
        tmp_path,
        isolated_pit_lifecycle,
    ):
        lifecycle, created_contexts = isolated_pit_lifecycle
        request.node.user_properties.append(
            ("result_checkpoint", "create a unique SME set and progress it to PIT")
        )
        context = lifecycle.create_and_progress_to_pit(
            tmp_path,
            count=3,
            context_registry=created_contexts,
        )
        request.node.user_properties.extend(
            [
                ("item_set_id", context.item_set_id),
                ("manual_item_id", ", ".join(context.item_ids)),
            ]
        )

        revision_item_id = context.item_ids[0]
        audit_token = uuid4().hex[:10]
        revision_comment = (
            f"PIT revision {audit_token} for {revision_item_id}: make the arithmetic stem "
            "unambiguous, retain grade alignment, and update the explanation before resubmission."
        )
        revised_question = (
            f"PIT-SME-{audit_token}: Riya has 7 pencils and receives 5 more. "
            "How many pencils does she have now?"
        )
        sme_revision_note = (
            f"SME correction {audit_token}: clarified the requested arithmetic stem and explanation."
        )

        request.node.user_properties.append(
            ("result_checkpoint", "PIT sends one item for revision with an audit comment")
        )
        pit_page = PITReviewQueuePage(self.driver)
        revised_ids, authorised_ids = pit_page.revise_some_and_authorise_rest_as_pit(
            context.item_set_id,
            context.item_ids,
            revision_comment,
            context.item_set_url,
            revision_count=1,
        )
        assert revised_ids == [revision_item_id]
        assert set(authorised_ids) == set(context.item_ids[1:])

        lifecycle.login_as(context.sme_username)
        lifecycle.sme_page.open_item_set_url_and_wait(
            context.item_set_url,
            context.item_set_id,
        )
        revision_status = _item_status(
            lifecycle.sme_page.get_qar_item_statuses(),
            revision_item_id,
        )
        revision_set_statuses = lifecycle.sme_page.get_visible_item_statuses()
        assert any(marker in revision_status.casefold() for marker in REVISION_STATUS_MARKERS), (
            f"{revision_item_id} should be Needs Revision after PIT send-back; "
            f"observed status={revision_status!r}."
        )
        assert not any("published" in status.casefold() for status in revision_set_statuses), (
            f"Item set progressed to Published while a PIT revision was open: {revision_set_statuses}."
        )
        assert not lifecycle.repository_contains(context, revision_item_id), (
            f"{revision_item_id} was published before the SME revision was submitted."
        )

        request.node.user_properties.append(
            ("result_checkpoint", "SME sees PIT history, edits the item, and resubmits")
        )
        lifecycle.login_as(context.sme_username)
        lifecycle.sme_page.open_item_set_url_and_wait(
            context.item_set_url,
            context.item_set_id,
        )
        opened_revision_id = lifecycle.sme_page.click_first_revision_item()
        assert opened_revision_id, f"SME could not open revision item {revision_item_id}."
        sme_audit_text = lifecycle.reveal_revision_audit_text(revision_comment)
        assert revision_comment in sme_audit_text, (
            "PIT revision comment was not preserved/visible to SME."
        )
        lifecycle.sme_page.edit_open_revision_item(
            revision_item_id,
            revised_question=revised_question,
            revision_note=sme_revision_note,
        )
        resubmit_message = lifecycle.sme_page.resubmit_revised_item_set_for_review()
        assert "resubmitted" in resubmit_message.casefold()

        lifecycle.sme_page.open_item_set_url_and_wait(
            context.item_set_url,
            context.item_set_id,
        )
        pending_status = _item_status(
            lifecycle.sme_page.get_qar_item_statuses(),
            revision_item_id,
        )
        resubmitted_set_statuses = lifecycle.sme_page.get_visible_item_statuses()
        pending_page_text = self.driver.find_element("tag name", "body").text
        assert (
            any(marker in pending_status.casefold() for marker in PENDING_PIT_STATUS_MARKERS)
            or any(marker in pending_page_text.casefold() for marker in PENDING_PIT_STATUS_MARKERS)
        ), (
            f"{revision_item_id} did not move to Pending PIT Review after SME resubmission; "
            f"status={pending_status!r}."
        )
        assert not any(
            "published" in status.casefold() for status in resubmitted_set_statuses
        ), (
            "SME resubmission incorrectly published the set before final PIT approval: "
            f"{resubmitted_set_statuses}."
        )
        assert not lifecycle.repository_contains(context, revision_item_id), (
            f"{revision_item_id} was published on SME resubmission, before PIT approval."
        )

        completed_pit_approvals = []
        final_pit_text = ""
        for vote_number, pit_username in enumerate(context.pit_usernames, start=1):
            request.node.user_properties.append(
                ("result_checkpoint", f"PIT approval vote {vote_number} of 3")
            )
            lifecycle.login_as(pit_username)
            pit_page = PITReviewQueuePage(self.driver)
            pit_page.open_review_item_set(context.item_set_id, context.item_set_url)

            if vote_number == 1:
                pit_page.click_item(revision_item_id)
                pit_audit_text = lifecycle.reveal_revision_audit_text(revision_comment)
                assert revision_comment in pit_audit_text, (
                    "Original PIT revision comment was not visible after SME resubmission."
                )
                assert revised_question in pit_audit_text or sme_revision_note in pit_audit_text, (
                    "SME correction/history was not visible to PIT after resubmission."
                )

            pit_page.approve_item_set_as_pit(
                context.item_set_id,
                context.item_set_url,
            )
            completed_pit_approvals.append(pit_username)
            final_pit_text = self.driver.find_element("tag name", "body").text

            if vote_number < 3:
                assert "published" not in final_pit_text.casefold(), (
                    f"Item set {context.item_set_id} published after only {vote_number}/3 PIT votes."
                )
                assert not lifecycle.repository_contains(context, revision_item_id), (
                    f"{revision_item_id} appeared live after only {vote_number}/3 PIT votes."
                )

        assert len(completed_pit_approvals) == 3
        assert "published" in final_pit_text.casefold(), (
            f"Item set {context.item_set_id} did not progress to Published after PIT 3/3."
        )
        assert lifecycle.repository_contains(context, revision_item_id), (
            f"Approved item {revision_item_id} was not present in the live Repository."
        )
        context.published = True

        request.node.user_properties.extend(
            [
                (
                    "pit_approval_message",
                    f"PIT revision was corrected by SME and approved by 3/3 users: "
                    f"{', '.join(completed_pit_approvals)}.",
                ),
                ("post_approval_status", "Published"),
                (
                    "result_description",
                    f"{context.item_set_id} remained unpublished through PIT revision and SME "
                    "resubmission, preserved the audit trail, and published only after PIT 3/3.",
                ),
            ]
        )
