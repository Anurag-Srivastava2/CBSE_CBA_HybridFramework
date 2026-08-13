from pages.sme.manual_item_page import ManualItemPage
from tests.M1_Item_Bank_Mgmt.test_sme_manual_item_creation import (
    build_manual_typology_items,
)


def test_manual_typology_data_covers_the_complete_supported_inventory():
    items = build_manual_typology_items("offlinecoverage")

    assert len(items) == 8
    assert tuple(item["typology"] for item in items) == (
        ManualItemPage.SUPPORTED_MANUAL_ITEM_TYPOLOGIES
    )
    assert len({item["question"] for item in items}) == len(items)
    assert all(item["explanation"] and item["marks"] for item in items)

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


def test_every_supported_typology_alias_canonicalizes_to_its_owner():
    for typology, aliases in ManualItemPage.MANUAL_TYPOLOGY_OPTION_ALIASES.items():
        for alias in aliases:
            assert ManualItemPage.canonical_manual_typology(alias) == typology
    assert (
        ManualItemPage.canonical_manual_typology("MCQ (Structured question)")
        == "Multiple Choice Question"
    )


def test_typology_tag_matcher_accepts_each_application_tag():
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


def test_every_supported_typology_has_a_manual_form_dispatch_handler():
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
    }
    page = DispatchPage()
    for item in build_manual_typology_items("dispatch"):
        page.calls.clear()
        page.add_manual_item_for_typology(item)
        assert page.calls == [expected_dispatch[item["typology"]], "added"]
