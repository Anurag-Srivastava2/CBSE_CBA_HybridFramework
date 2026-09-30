"""Unit coverage for UploadItemFilePage.item_identity_key.

Regression guard for the QAR retry flow: the upload/review step hands back
item IDs whose chapter segment ("...-Ch29-i1") differs from the one the QAR
results page renders for the same item ("...-CH-1-i1"). Comparing whole
compacted IDs reported every uploaded item as missing and failed the flow
before a single retry could run.
"""
import pytest

from pages.sme.upload_item_file_page import UploadItemFilePage


key = UploadItemFilePage.item_identity_key


class TestItemIdentityKeyMatchesAcrossChapterTokens:
    def test_upload_step_and_qar_results_forms_agree(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "The upload step and the QAR results page spell the same item's chapter "
            "differently, as Ch29 and as CH-1.\n"
            "Check the identity key treats both spellings of one item as the same "
            "item.",
        )
        assert key("IS986-G1-Mathematics-Ch29-i1") == key("IS986-G1-Mathematics-CH-1-i1")

    @pytest.mark.parametrize("index", [1, 2, 3, 10, 12])
    def test_every_item_index_survives_the_chapter_rename(self, index, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Take the same item at each index in a set and spell its chapter both "
            "ways.\n"
            "Check the identity key matches for every index, not just the first one.",
        )
        assert key(f"IS986-G1-Mathematics-Ch29-i{index}") == key(
            f"IS986-G1-Mathematics-CH-1-i{index}"
        )

    def test_whole_id_comparison_would_have_missed_these(self, record_property):
        """The bug this helper fixes: compact_item_id disagrees where item_identity_key agrees."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Compare the same items using the older whole-ID form instead of the "
            "identity key.\n"
            "Check the old form disagrees exactly where the identity key agrees, "
            "which is the bug this helper exists to fix.",
        )
        upload, results = "IS986-G1-Mathematics-Ch29-i1", "IS986-G1-Mathematics-CH-1-i1"
        compact = UploadItemFilePage.compact_item_id
        assert compact(upload).casefold() != compact(results).casefold()
        assert key(upload) == key(results)


class TestItemIdentityKeyKeepsDistinctItemsApart:
    def test_different_item_index_differs(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Take two different items from the same set.\n"
            "Check the identity key keeps them apart instead of folding them "
            "together.",
        )
        assert key("IS986-G1-Mathematics-CH-1-i1") != key("IS986-G1-Mathematics-CH-1-i2")

    def test_different_item_set_differs(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Take the same item index from two different item sets.\n"
            "Check the identity key keeps them apart.",
        )
        assert key("IS986-G1-Mathematics-CH-1-i1") != key("IS987-G1-Mathematics-CH-1-i1")

    def test_set_level_id_never_collides_with_an_item_row(self, record_property):
        """Set IDs carry no -i<n> suffix, so they must not fold onto item keys."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Compare a set-level ID against an item row's ID.\n"
            "Set IDs carry no item suffix, so check they never fold onto an item's "
            "key.",
        )
        assert key("IS986-G1-Mathematics-Ch29") != key("IS986-G1-Mathematics-Ch29-i1")


class TestItemIdentityKeyFallback:
    @pytest.mark.parametrize("value", ["", None, "not-an-item-id", "IS986-G1-Mathematics-CH-1"])
    def test_values_without_both_parts_fall_back_to_compact_form(self, value, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Pass in a value that does not carry both an item-set part and an item "
            "part.\n"
            "Check the key falls back to the plain compact form rather than failing.",
        )
        assert key(value) == UploadItemFilePage.compact_item_id(value).casefold()

    def test_surrounding_whitespace_is_ignored(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Pass the same ID with and without surrounding spaces.\n"
            "Check the identity key ignores the whitespace and treats them as one "
            "item.",
        )
        assert key("  IS986-G1-Mathematics-Ch29-i1  ") == key("IS986-G1-Mathematics-CH-1-i1")
