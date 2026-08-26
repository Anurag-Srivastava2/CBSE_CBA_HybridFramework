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
    def test_upload_step_and_qar_results_forms_agree(self):
        assert key("IS986-G1-Mathematics-Ch29-i1") == key("IS986-G1-Mathematics-CH-1-i1")

    @pytest.mark.parametrize("index", [1, 2, 3, 10, 12])
    def test_every_item_index_survives_the_chapter_rename(self, index):
        assert key(f"IS986-G1-Mathematics-Ch29-i{index}") == key(
            f"IS986-G1-Mathematics-CH-1-i{index}"
        )

    def test_whole_id_comparison_would_have_missed_these(self):
        """The bug this helper fixes: compact_item_id disagrees where item_identity_key agrees."""
        upload, results = "IS986-G1-Mathematics-Ch29-i1", "IS986-G1-Mathematics-CH-1-i1"
        compact = UploadItemFilePage.compact_item_id
        assert compact(upload).casefold() != compact(results).casefold()
        assert key(upload) == key(results)


class TestItemIdentityKeyKeepsDistinctItemsApart:
    def test_different_item_index_differs(self):
        assert key("IS986-G1-Mathematics-CH-1-i1") != key("IS986-G1-Mathematics-CH-1-i2")

    def test_different_item_set_differs(self):
        assert key("IS986-G1-Mathematics-CH-1-i1") != key("IS987-G1-Mathematics-CH-1-i1")

    def test_set_level_id_never_collides_with_an_item_row(self):
        """Set IDs carry no -i<n> suffix, so they must not fold onto item keys."""
        assert key("IS986-G1-Mathematics-Ch29") != key("IS986-G1-Mathematics-Ch29-i1")


class TestItemIdentityKeyFallback:
    @pytest.mark.parametrize("value", ["", None, "not-an-item-id", "IS986-G1-Mathematics-CH-1"])
    def test_values_without_both_parts_fall_back_to_compact_form(self, value):
        assert key(value) == UploadItemFilePage.compact_item_id(value).casefold()

    def test_surrounding_whitespace_is_ignored(self):
        assert key("  IS986-G1-Mathematics-Ch29-i1  ") == key("IS986-G1-Mathematics-CH-1-i1")
