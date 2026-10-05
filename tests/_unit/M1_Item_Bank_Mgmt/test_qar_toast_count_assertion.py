"""Unit coverage for TestQARDuplicateDetection.assert_toast_count_matches_report.

Regression guard for a permanent-green assertion. The QAR results page renders
"Approved", "Needs Revision" and "Rejected" as status-filter labels whatever
the outcome, so the previous implementation - which searched the page text for
those words - was satisfied by the labels alone and could not fail. The checks
below feed it a page whose text contains every label while the parsed counts
say the opposite, which is exactly the state the old version waved through.
"""
import pytest

from tests._unit.M1_Item_Bank_Mgmt.test_qar_duplicate_detection import (
    TestQARDuplicateDetection as Dup,
)


# Every status word is present, as it is on the real page, regardless of result.
PAGE_TEXT_WITH_ALL_LABELS = (
    "QAR Results\n"
    "All 3   Approved 0   Needs Revision 0   Rejected 3   Revised 0\n"
    "IS1001-G1-Mathematics-CH-1-i1  Rejected\n"
)


def evidence(toast, summary, report_text=PAGE_TEXT_WITH_ALL_LABELS):
    return {"toast": toast, "status_summary": summary, "report_text": report_text}


class TestPassedToastRequiresRealApprovedCount:
    def test_passed_toast_fails_when_nothing_was_approved(self, record_property):
        """The case the old substring check could not catch."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed the toast assertion a 'set passed' message alongside a report "
            "showing nothing approved.\n"
            "Check it fails on that contradiction, which is the case the older "
            "substring check could not catch.",
        )
        broken = evidence(
            "QAR completed - 1/1 set(s) passed.",
            {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
        )
        with pytest.raises(AssertionError, match="no approved items"):
            Dup.assert_toast_count_matches_report(broken)

    def test_passed_toast_accepted_when_items_really_were_approved(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it a 'set passed' toast alongside a report that really does show "
            "approved items.\n"
            "Check it accepts.",
        )
        ok = evidence(
            "QAR completed - 1/1 set(s) passed.",
            {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
        )
        Dup.assert_toast_count_matches_report(ok)


class TestFailedToastRequiresRealBlockedCount:
    def test_returned_toast_fails_when_nothing_was_blocked(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it a 'set returned' toast alongside a report showing nothing "
            "blocked.\n"
            "Check it fails on the contradiction.",
        )
        broken = evidence(
            "QAR completed - 0/1 set(s) returned.",
            {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
        )
        with pytest.raises(AssertionError, match="no blocked items"):
            Dup.assert_toast_count_matches_report(broken)

    @pytest.mark.parametrize("blocking_status", ["Needs Revision", "Rejected"])
    def test_returned_toast_accepts_either_blocking_wording(self, blocking_status, record_property):
        """QAR blocks with either wording; both must satisfy the same toast."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "QAR announces a blocked set using either of two wordings.\n"
            "Check both satisfy the same toast assertion.",
        )
        summary = {"Approved": "0", "Needs Revision": "0", "Rejected": "0"}
        summary[blocking_status] = "3"
        Dup.assert_toast_count_matches_report(
            evidence("QAR completed - 0/1 set(s) returned.", summary)
        )


class TestToastNumberParsing:
    def test_item_set_id_digits_are_not_read_as_counts(self, record_property):
        """"IS1001" must not contribute 1001 to the toast's reported numbers."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it a toast containing an item-set ID such as IS1001.\n"
            "Check those digits are not mistaken for item counts.",
        )
        ok = evidence(
            "QAR completed - 0/1 set(s) returned. Set IS1001",
            {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
        )
        Dup.assert_toast_count_matches_report(ok)

    def test_toast_without_any_number_is_rejected(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it a toast carrying no numbers at all.\n"
            "Check it is rejected rather than quietly passing.",
        )
        with pytest.raises(AssertionError, match="no item counts"):
            Dup.assert_toast_count_matches_report(
                evidence("QAR completed.", {"Approved": "3"})
            )


class TestSubstringMatchingWouldHaveMissedThis:
    def test_page_text_alone_cannot_distinguish_pass_from_fail(self, record_property):
        """Documents why the assertion moved off page text.

        The same page text is present for a passing and a failing set, so any
        assertion reading it for status words yields the same verdict either
        way. Only the parsed counts separate the two.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Show that a passing set and a failing set produce the very same page "
            "text.\n"
            "Only the parsed counts tell them apart, which documents why this "
            "assertion stopped reading page text.",
        )
        text = PAGE_TEXT_WITH_ALL_LABELS.casefold()
        assert "approved" in text
        assert "rejected" in text
        assert "needs revision" in text

        passed = {"Approved": "3", "Needs Revision": "0", "Rejected": "0"}
        failed = {"Approved": "0", "Needs Revision": "0", "Rejected": "3"}
        assert Dup.get_status_count(evidence("x 1", passed), "Approved") == 3
        assert Dup.get_status_count(evidence("x 1", failed), "Approved") == 0


class TestSetRatioIsReadAsANumberNotAWord:
    """Regression: "0/1 set(s) passed" contains "passed" but means none did.

    Keying the check on the substring inverted it — the assertion demanded
    approved items from a set QAR had entirely blocked, and a correct run
    failed. The ratio is the signal; the trailing verb is not.
    """

    def test_zero_of_one_passed_is_a_blocked_set_not_a_passing_one(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it '0/1 set(s) passed' with every item rejected.\n"
            "Check it reads that as a blocked set rather than a passing one, despite "
            "the word 'passed'.",
        )
        blocked_set = evidence(
            "QAR completed - 0/1 set(s) passed.",
            {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
        )
        Dup.assert_toast_count_matches_report(blocked_set)

    def test_zero_of_one_passed_still_fails_when_nothing_is_blocked_either(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it '0/1 set(s) passed' with nothing blocked either.\n"
            "Check it still fails, since no set passed and no item was blocked.",
        )
        incoherent = evidence(
            "QAR completed - 0/1 set(s) passed.",
            {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
        )
        with pytest.raises(AssertionError, match="no blocked items either"):
            Dup.assert_toast_count_matches_report(incoherent)

    def test_one_of_one_passed_requires_approved_items(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it '1/1 set(s) passed' with no approved items.\n"
            "Check it fails, because a set that passed must have approved something.",
        )
        with pytest.raises(AssertionError, match="no approved items"):
            Dup.assert_toast_count_matches_report(
                evidence(
                    "QAR completed - 1/1 set(s) passed.",
                    {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
                )
            )

    def test_malformed_ratio_is_rejected(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Feed it a ratio that cannot be real, such as three of one sets passed.\n"
            "Check it is rejected as malformed.",
        )
        with pytest.raises(AssertionError, match="malformed"):
            Dup.assert_toast_count_matches_report(
                evidence(
                    "QAR completed - 3/1 set(s) passed.",
                    {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
                )
            )


class TestVerdictReadFromTheItemSetPage:
    """There is no toast at all when the upload wizard stops reporting.

    The verdict is then read off the item set's own page, which renders no
    completion toast. Cross-checking an absent toast would fail a run that
    produced a real result, so the check asserts what that view does carry.
    """

    def test_absent_toast_is_accepted_when_the_set_reported_statuses(
        self, record_property
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Give it a result read off the item set page, where no toast exists, "
            "but with item statuses present.\n"
            "Check it accepts rather than failing on the missing toast.",
        )
        recovered = evidence("", {"Approved": "0", "Rejected": "3"})
        recovered["recovered"] = True

        Dup.assert_toast_count_matches_report(recovered)

    def test_absent_toast_still_fails_when_the_set_reported_nothing(
        self, record_property
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Give it a result read off the item set page with no statuses either.\n"
            "Check it fails, because now no view anywhere reported an outcome.",
        )
        empty = evidence("", {}, report_text="Loading item set")
        empty["recovered"] = True

        with pytest.raises(AssertionError, match="no item statuses"):
            Dup.assert_toast_count_matches_report(empty)

    def test_a_wizard_result_is_still_held_to_its_toast(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Give it a wizard result whose toast is missing.\n"
            "Check the toast is still required there, so the recovery path cannot "
            "be used to excuse a wizard run that reported nothing.",
        )
        no_toast = evidence("", {"Approved": "0", "Rejected": "3"})
        no_toast["recovered"] = False

        with pytest.raises(AssertionError, match="no item counts"):
            Dup.assert_toast_count_matches_report(no_toast)


class TestOnlyNumberedIdsReachTheItemReport:
    """The per-item report can only be opened with a numbered item ID.

    The review step assigns no set number, so the IDs captured there read
    "IS-G1-Mathematics-Ch29-i2" while the report renders
    "IS1405-G1-Mathematics-Ch29-i2". A live run reached the per-item loop and
    failed with "Could not open QAR result item IS-G1-Mathematics-Ch29-i2",
    which is what these guard.
    """

    def test_review_step_ids_are_rejected_as_identities(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Check an ID from the review step is not treated as naming a set, "
            "because it has no set number yet.",
        )
        from pages.sme.upload_item_file_page import UploadItemFilePage

        assert not UploadItemFilePage.item_set_id_is_numbered(
            "IS-G1-Mathematics-Ch29-i2"
        )
        assert UploadItemFilePage.item_set_id_is_numbered(
            "IS1405-G1-Mathematics-Ch29-i2"
        )

    def test_rows_from_another_set_are_not_inspected(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Filter a mixed list of item IDs down to one set's own rows.\n"
            "Check another set's rows are dropped, so the per-item checks cannot "
            "report a stranger's item as this upload's.",
        )
        import re

        item_set_id = "IS1405-G1-Mathematics-Ch29"
        candidates = [
            "IS1405-G1-Mathematics-Ch29-i1",
            "IS1440-G1-Mathematics-CH-4-i1",
            "IS1405-G1-Mathematics-CH-29-i2",
        ]
        prefix = re.match(r"\s*(IS\d+)", item_set_id, re.IGNORECASE).group(1).casefold()

        scoped = [c for c in candidates if c.casefold().startswith(prefix)]

        # Both spellings of this set's chapter are kept; the other set is not.
        assert scoped == [
            "IS1405-G1-Mathematics-Ch29-i1",
            "IS1405-G1-Mathematics-CH-29-i2",
        ]
