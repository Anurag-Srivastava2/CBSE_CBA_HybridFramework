"""Unit coverage for confirming a teacher/SME revision actually saved.

The revision loop used to count an item as revised the moment its edit call
returned, so a silently dropped save went unnoticed until the resubmit control
refused minutes later. The first attempt to confirm it read per-item rows for
the item ID - but that screen's item list renders question text and badges and
no ID at all, so every item came back unconfirmed and the check was worse than
none. The header's "N items revised" counter is the signal that exists.
"""
import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pages.sme.upload_item_file_page import UploadItemFilePage


class Body:
    def __init__(self, text):
        self.text = text


class Driver:
    def __init__(self, text):
        self.body = Body(text)

    def find_element(self, by, value):
        assert (by, value) == (By.TAG_NAME, "body")
        return self.body


class ImmediateWait:
    """Evaluates the condition once, like a poll that gets one chance."""

    def __init__(self, driver):
        self.driver = driver

    def until_condition(self, condition, timeout):
        assert timeout > 0
        if not condition(self.driver):
            raise TimeoutException()
        return True


def build_page(page_text):
    page = UploadItemFilePage.__new__(UploadItemFilePage)
    page.driver = Driver(page_text)
    page.wait_utils = ImmediateWait(page.driver)
    return page


class TestReadingTheCounter:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("3 items revised Cancel Resubmit set for review", 3),
            ("1 item revised", 1),
            ("0 items revised", 0),
        ],
    )
    def test_the_counter_is_read_off_the_header(self, text, expected, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Read the 'N items revised' counter from the revision screen.\n"
            "Check the number is picked up, including the singular wording.",
        )
        assert build_page(text).get_revised_item_count() == expected

    def test_a_missing_counter_reads_as_unknown_not_zero(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Read the counter on a screen that does not show one.\n"
            "Check it reports 'cannot tell' rather than zero, so a screen "
            "without the counter is not read as nothing having been saved.",
        )
        assert build_page("Item Set Detail").get_revised_item_count() is None


class TestConfirmingASave:
    def test_a_save_that_registered_is_confirmed(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Confirm a revision on a screen whose counter has caught up.\n"
            "Check it is accepted.",
        )
        assert build_page("3 items revised").revised_count_reached(3)

    def test_a_save_that_never_registered_is_not_confirmed(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Confirm a fourth revision when the counter still reads three.\n"
            "Check it is refused, which is the dropped save this whole check "
            "exists to catch.",
        )
        assert not build_page("3 items revised").revised_count_reached(4)

    def test_an_absent_counter_does_not_fail_every_item(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Confirm a revision on a screen that renders no counter at all.\n"
            "Check it is accepted rather than refused, because this check guards "
            "a loop other suites rely on and must not fail them on a signal that "
            "was never there.",
        )
        assert build_page("Item Set Detail with no counter").revised_count_reached(4)


class TestFillInTheBlankKeepsItsBlank:
    """A FITB revision must carry exactly four underscores or Save does nothing.

    Items uploaded from Excel carry three, which the editor counts as zero
    blanks. The rewrite used to trigger only when the item's current text could
    be read back; when that read came back empty the item silently got the
    fixed comparison question, which has no blank at all - the invalid state
    the rewrite exists to prevent. Three live runs failed on the same FITB item
    that way.
    """

    def build(self, current_text, typology):
        page = UploadItemFilePage.__new__(UploadItemFilePage)
        page.driver = Driver("")
        page.get_item_detail_metadata = lambda _labels: {"Typology": typology}
        page.wait_utils = ImmediateWait(page.driver)
        page.get_visible_element_from_locators = lambda _locators: object()
        page.get_editable_element_text = lambda _element: current_text
        return page

    def test_three_underscores_are_rewritten_to_four(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Revise a Fill in the Blank item whose text has the three "
            "underscores an Excel upload produces.\n"
            "Check they become the four the editor requires.",
        )
        page = self.build("The journey lasts ___ hours.", "Fill in the Blank")

        question = page.default_revision_question("IS1482-G1-Mathematics-Ch29-i3")

        assert "____" in question
        assert "___ " not in question.replace("____", "")

    def test_an_unreadable_fitb_item_still_gets_a_blank(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Revise a Fill in the Blank item whose current text cannot be read "
            "back.\n"
            "Check it still gets a question containing a blank, rather than the "
            "comparison question this typology cannot save.",
        )
        page = self.build("", "Fill in the Blank")

        question = page.default_revision_question("IS1482-G1-Mathematics-Ch29-i3")

        assert "____" in question
        assert "98765" not in question

    def test_other_typologies_keep_the_comparison_question(self, record_property):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Revise a non-blank item whose text cannot be read back.\n"
            "Check it still gets the ordinary comparison question, so the blank "
            "handling does not leak into typologies that do not want one.",
        )
        page = self.build("", "Very Short Answer Question")

        question = page.default_revision_question("IS1482-G1-Mathematics-Ch29-i4")

        assert "98765" in question
        assert "____" not in question
