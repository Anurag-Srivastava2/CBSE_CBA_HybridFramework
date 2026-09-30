from pages.sme.manual_item_page import ManualItemPage
from tests.M1_Item_Bank_Mgmt.test_sme_manual_item_creation import (
    build_manual_typology_items,
)

# A typology's prompt and its supporting text are not always under the same
# key: Assertion and Reasoning states an `assertion`, FA Activity gives
# `instructions` with a `rubric`, and Free Response carries a `marking_scheme`
# instead of an explanation. These read whichever the typology actually uses.
PROMPT_FIELDS = ("question", "assertion", "instructions")
SUPPORTING_FIELDS = ("explanation", "rubric", "marking_scheme", "answer")


def prompt_of(item):
    for field in PROMPT_FIELDS:
        if item.get(field):
            return item[field]
    raise AssertionError(
        f"{item['typology']!r} carries no prompt under any of {PROMPT_FIELDS}."
    )


def supporting_text_of(item):
    for field in SUPPORTING_FIELDS:
        if item.get(field):
            return item[field]
    return ""


def test_manual_typology_data_covers_the_complete_supported_inventory(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Build the manual typology test data.\n"
        "Check it produces one item for every typology the manual item form "
        "supports, in the same order, with none missing.",
    )
    items = build_manual_typology_items("offlinecoverage")

    # Counted off the page object rather than hard-coded: the supported
    # inventory has grown from 8 to 12, and a literal here fails the moment a
    # typology is added even though the data is still complete - which is the
    # opposite of what "covers the complete inventory" should assert.
    assert len(items) == len(ManualItemPage.SUPPORTED_MANUAL_ITEM_TYPOLOGIES)
    assert tuple(item["typology"] for item in items) == (
        ManualItemPage.SUPPORTED_MANUAL_ITEM_TYPOLOGIES
    )
    # Checked by role, not by a fixed key: the newer typologies carry their
    # prompt elsewhere - Assertion and Reasoning has no `question` at all, and
    # FA Activity carries `instructions`/`rubric` rather than an explanation.
    prompts = [prompt_of(item) for item in items]
    assert len(set(prompts)) == len(items)
    assert all(item["marks"] for item in items)
    assert all(supporting_text_of(item) for item in items)

    by_typology = {item["typology"]: item for item in items}
    assert len(by_typology["Multiple Choice Question"]["options"]) == 4
    assert by_typology["Fill in the Blank"]["answer"]
    assert len(by_typology["Match the Following"]["pairs"]) >= 3
    assert by_typology["True or False"]["answer"] in {"True", "False"}
    for typology in (
        "Very Short Answer Question",
        "Short Answer Question",
        "Long Answer Question",
    ):
        assert by_typology[typology]["answer"]
    assert by_typology["Case Based Question"]["source"]
    assert len(by_typology["Case Based Question"]["options"]) == 4


def test_every_supported_typology_alias_canonicalizes_to_its_owner(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Take every alias the form accepts for a typology, such as a short code "
        "or an alternate spelling.\n"
        "Check each one canonicalises back to the single typology that owns it.",
    )
    for typology, aliases in ManualItemPage.MANUAL_TYPOLOGY_OPTION_ALIASES.items():
        for alias in aliases:
            assert ManualItemPage.canonical_manual_typology(alias) == typology
    assert (
        ManualItemPage.canonical_manual_typology("MCQ (Structured question)")
        == "Multiple Choice Question"
    )


def test_typology_tag_matcher_accepts_each_application_tag(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Take the short tag the application shows for each typology, such as MCQ, "
        "FIB or MTF.\n"
        "Check the matcher accepts every one of them and maps it to the right "
        "typology.",
    )
    tags = {
        "Multiple Choice Question": "MCQ",
        "Fill in the Blank": "FIB",
        "Match the Following": "MTF",
        "True or False": "T/F",
        "Very Short Answer Question": "VSAQ",
        "Short Answer Question": "SAQ",
        "Long Answer Question": "LAQ",
        "Case Based Question": "CBQ",
    }
    for typology, tag in tags.items():
        assert ManualItemPage.typology_tag_is_visible(
            typology,
            f"Mathematics {tag} Sample question",
        )


def test_every_supported_typology_has_a_manual_form_dispatch_handler(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Drive the manual item form once for each supported typology.\n"
        "Check every typology reaches a handler that knows how to fill its answer "
        "controls, so none falls through unhandled.",
    )
    class DispatchPage(ManualItemPage):
        def __init__(self):
            self.calls = []

        def ensure_true_false_answer_controls(self):
            self.calls.append("true_false")

        def enter_question_text(self, value):
            return None

        def select_answer(self, value):
            return None

        def enter_explanation(self, value):
            return None

        def fill_multiple_choice_question(self, *args):
            self.calls.append("multiple_choice")

        def fill_fill_in_the_blank_question(self, *args):
            self.calls.append("fill_in_blank")

        def fill_match_the_following_question(self, *args):
            self.calls.append("match")

        def fill_very_short_answer_question(self, *args):
            self.calls.append("very_short")

        def fill_short_answer_question(self, *args):
            self.calls.append("short")

        def fill_long_answer_question(self, *args):
            self.calls.append("long")

        def fill_source_based_question(self, *args):
            self.calls.append("case_based")

        def fill_assertion_and_reasoning_question(self, *args):
            self.calls.append("assertion_reasoning")

        def fill_fa_activity_question(self, *args):
            self.calls.append("fa_activity")

        def fill_free_response_question(self, *args):
            self.calls.append("free_response")

        def click_add_item_and_wait_for_count_increase(self):
            self.calls.append("added")

    expected_dispatch = {
        "Multiple Choice Question": "multiple_choice",
        "Fill in the Blank": "fill_in_blank",
        "Match the Following": "match",
        "True or False": "true_false",
        "Very Short Answer Question": "very_short",
        "Short Answer Question": "short",
        "Long Answer Question": "long",
        "Case Based Question": "case_based",
        # Source Based shares the case-based filler; the three below arrived
        # with the inventory's growth from 8 typologies to 12 and had no
        # expectation here, so this test could not see them at all.
        "Source Based Question": "case_based",
        "Assertion and Reasoning": "assertion_reasoning",
        "FA Activity": "fa_activity",
        "Free Response": "free_response",
    }
    # Every supported typology must have an expectation, so the next one added
    # fails here loudly rather than being silently skipped.
    assert set(expected_dispatch) == set(ManualItemPage.SUPPORTED_MANUAL_ITEM_TYPOLOGIES)
    page = DispatchPage()
    for item in build_manual_typology_items("dispatch"):
        page.calls.clear()
        page.add_manual_item_for_typology(item)
        assert page.calls == [expected_dispatch[item["typology"]], "added"]
