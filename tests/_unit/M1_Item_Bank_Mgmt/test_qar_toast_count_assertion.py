"""Unit coverage for TestQARDuplicateDetection.assert_toast_count_matches_report.

Regression guard for a permanent-green assertion. The QAR results page renders
"Approved", "Needs Revision" and "Rejected" as status-filter labels whatever
the outcome, so the previous implementation - which searched the page text for
those words - was satisfied by the labels alone and could not fail. The checks
below feed it a page whose text contains every label while the parsed counts
say the opposite, which is exactly the state the old version waved through.
"""
import pytest

from tests.M1_Item_Bank_Mgmt.test_qar_duplicate_detection import (
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
    def test_passed_toast_fails_when_nothing_was_approved(self):
        """The case the old substring check could not catch."""
        broken = evidence(
            "QAR completed - 1/1 set(s) passed.",
            {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
        )
        with pytest.raises(AssertionError, match="no approved items"):
            Dup.assert_toast_count_matches_report(broken)

    def test_passed_toast_accepted_when_items_really_were_approved(self):
        ok = evidence(
            "QAR completed - 1/1 set(s) passed.",
            {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
        )
        Dup.assert_toast_count_matches_report(ok)


class TestFailedToastRequiresRealBlockedCount:
    def test_returned_toast_fails_when_nothing_was_blocked(self):
        broken = evidence(
            "QAR completed - 0/1 set(s) returned.",
            {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
        )
        with pytest.raises(AssertionError, match="no blocked items"):
            Dup.assert_toast_count_matches_report(broken)

    @pytest.mark.parametrize("blocking_status", ["Needs Revision", "Rejected"])
    def test_returned_toast_accepts_either_blocking_wording(self, blocking_status):
        """QAR blocks with either wording; both must satisfy the same toast."""
        summary = {"Approved": "0", "Needs Revision": "0", "Rejected": "0"}
        summary[blocking_status] = "3"
        Dup.assert_toast_count_matches_report(
            evidence("QAR completed - 0/1 set(s) returned.", summary)
        )


class TestToastNumberParsing:
    def test_item_set_id_digits_are_not_read_as_counts(self):
        """"IS1001" must not contribute 1001 to the toast's reported numbers."""
        ok = evidence(
            "QAR completed - 0/1 set(s) returned. Set IS1001",
            {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
        )
        Dup.assert_toast_count_matches_report(ok)

    def test_toast_without_any_number_is_rejected(self):
        with pytest.raises(AssertionError, match="no item counts"):
            Dup.assert_toast_count_matches_report(
                evidence("QAR completed.", {"Approved": "3"})
            )


class TestSubstringMatchingWouldHaveMissedThis:
    def test_page_text_alone_cannot_distinguish_pass_from_fail(self):
        """Documents why the assertion moved off page text.

        The same page text is present for a passing and a failing set, so any
        assertion reading it for status words yields the same verdict either
        way. Only the parsed counts separate the two.
        """
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

    def test_zero_of_one_passed_is_a_blocked_set_not_a_passing_one(self):
        blocked_set = evidence(
            "QAR completed - 0/1 set(s) passed.",
            {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
        )
        Dup.assert_toast_count_matches_report(blocked_set)

    def test_zero_of_one_passed_still_fails_when_nothing_is_blocked_either(self):
        incoherent = evidence(
            "QAR completed - 0/1 set(s) passed.",
            {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
        )
        with pytest.raises(AssertionError, match="no blocked items either"):
            Dup.assert_toast_count_matches_report(incoherent)

    def test_one_of_one_passed_requires_approved_items(self):
        with pytest.raises(AssertionError, match="no approved items"):
            Dup.assert_toast_count_matches_report(
                evidence(
                    "QAR completed - 1/1 set(s) passed.",
                    {"Approved": "0", "Needs Revision": "0", "Rejected": "3"},
                )
            )

    def test_malformed_ratio_is_rejected(self):
        with pytest.raises(AssertionError, match="malformed"):
            Dup.assert_toast_count_matches_report(
                evidence(
                    "QAR completed - 3/1 set(s) passed.",
                    {"Approved": "3", "Needs Revision": "0", "Rejected": "0"},
                )
            )
