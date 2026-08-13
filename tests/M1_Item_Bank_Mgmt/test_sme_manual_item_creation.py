"""Full SME manual-item typology coverage.

Coverage source:
- FR-IBMM-06 controlled dropdown: MCQ, Fill in the Blank, Match the
  Following, True/False, VSA, Short Answer, and Long Answer.
- Current dev manual form additionally exposes: Case Based Question,
  Source Based Question (a distinct typology, not an alias of Case Based
  Question - it has its own source/passage plus dynamic sub-questions),
  Assertion and Reasoning, FA Activity, and Free Response.

The inventory assertion reads the live dropdown, so a newly introduced app
typology fails this suite until test data and a form handler are added here.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.common.login_page import LoginPage
from pages.sme.manual_item_page import ManualItemPage
from utilities.logger import LogGenerator
from utilities.read_config import ReadConfig

TEST_IMAGES_DIR = Path(__file__).resolve().parents[2] / "test_images"
TEST_IMAGES = sorted(TEST_IMAGES_DIR.glob("*.png"))


def apply_rich_content_checks(page, image_path, editor_index=-1):
    """Best-effort bold/italic/text-color/highlight/image checks on one of an
    item's rich text editors. Failures here are recorded, not raised, per the
    directive to keep going until a real item-creation blocker is hit.

    editor_index defaults to the item's primary content editor, but callers
    can point it elsewhere — e.g. Fill in the Blank's question editor holds a
    "____" marker the app parses to build the Blank Answers list, and
    mutating that editor's structure (an inserted <img>, in particular)
    desyncs that parser and silently blocks Add Item. Explanation is a plain
    editor with no such parsing tied to it, so it's a safe target instead.
    """
    soft_failures = []

    editors = page.get_visible_rich_text_editors()
    if not editors[editor_index].text.strip():
        return [
            "Skipped: target editor has no content to format "
            "(this typology doesn't fill that field)."
        ]

    try:
        html_after = page.apply_bold_and_italic(editor_index=editor_index)
        if "<strong>" not in html_after or "<em>" not in html_after:
            soft_failures.append(
                f"Bold/Italic: expected <strong>/<em> markup, got: {html_after[:300]}"
            )
    except Exception as error:
        soft_failures.append(f"Bold/Italic: {error}")

    try:
        html_after = page.apply_text_color(editor_index=editor_index, hex_color="#ff0000")
        if "rgb(255, 0, 0)" not in html_after:
            soft_failures.append(
                f"Text color: expected red text color, got: {html_after[:300]}"
            )
    except Exception as error:
        soft_failures.append(f"Text color: {error}")

    try:
        html_after = page.apply_highlight_color(editor_index=editor_index, hex_color="#ffff00")
        if "background-color" not in html_after:
            soft_failures.append(
                f"Highlight color: expected a background-color style, got: {html_after[:300]}"
            )
    except Exception as error:
        soft_failures.append(f"Highlight color: {error}")

    try:
        html_after = page.insert_image_into_editor(editor_index=editor_index, image_path=str(image_path))
        if "<img" not in html_after:
            soft_failures.append(
                f"Image insert: no <img> found after upload, got: {html_after[:300]}"
            )
    except Exception as error:
        soft_failures.append(f"Image insert: {error}")

    return soft_failures


# Rich-content checks default to the LAST rich text editor (typically
# Explanation), not the question/content editor. Two independent reasons:
# 1. Some typologies parse the question editor's literal text for app-side
#    behavior (e.g. Fill in the Blank's "____" marker) — mutating it via
#    toolbar formatting desyncs that parser and silently blocks Add Item.
# 2. More generally, this framework fills rich text editors by injecting
#    innerHTML directly rather than through Tiptap's own command API. That
#    leaves Tiptap's internal document model out of sync with the DOM. A
#    subsequent toolbar click (Bold, Text color, ...) executes a real Tiptap
#    command, which reconciles the DOM back to Tiptap's actual (unsynced)
#    state — silently discarding the injected text. Since Explanation is
#    filled last and its content isn't relied on by app-side parsing, it's
#    the one field where losing this race doesn't break the item.
# Override per-typology only if a typology's last editor turns out to have
# its own special parsing.
RICH_CONTENT_EDITOR_INDEX_OVERRIDES = {}


def build_manual_typology_items(run_id):
    """Return valid, unique Grade 1 data for every supported manual typology."""
    return [
        {
            "typology": "Multiple Choice Question",
            "question": f"What comes immediately after 24? MCQ run {run_id}",
            "options": ["25", "23", "14", "55"],
            "explanation": "25 comes immediately after 24.",
            "marks": "1",
        },
        {
            "typology": "Fill in the Blank",
            "question": f"The number after 6 is ____. Fill blank run {run_id}",
            "answer": "7",
            "explanation": "Counting forward once from 6 gives 7.",
            "marks": "1",
        },
        {
            "typology": "Match the Following",
            "question": f"Match each number with its number name. Match run {run_id}",
            "pairs": [("14", "Fourteen"), ("18", "Eighteen"), ("25", "Twenty five")],
            "explanation": "Each numeral is paired with its correct number name.",
            "marks": "1",
        },
        {
            "typology": "True or False",
            "question": f"Is 18 greater than 12? True false run {run_id}",
            "answer": "True",
            "explanation": "18 is greater than 12.",
            "marks": "1",
        },
        {
            "typology": "Very Short Answer Question",
            "question": f"Which day comes after Monday? VSA run {run_id}",
            "answer": "Tuesday",
            "explanation": "Tuesday comes immediately after Monday.",
            "marks": "1",
        },
        {
            "typology": "Short Answer Question",
            "question": f"Write the number name of 18. Short answer run {run_id}",
            "answer": "Eighteen",
            "explanation": "The number name of 18 is eighteen.",
            "marks": "1",
        },
        {
            "typology": "Long Answer Question",
            "question": (
                "Explain how to arrange 12, 15, and 18 in increasing order. "
                f"Long answer run {run_id}"
            ),
            "answer": (
                "Compare the numbers from smallest to greatest. "
                "The increasing order is 12, 15, 18."
            ),
            "explanation": (
                "Increasing order starts with the smallest number and ends "
                "with the greatest number."
            ),
            "marks": "1",
        },
        {
            "typology": "Case Based Question",
            "source": (
                "Riya had 12 pencils. Her teacher gave her 6 more pencils. "
                f"She then counted all her pencils. Case run {run_id}"
            ),
            "question": f"How many pencils does Riya have now? Case based run {run_id}",
            "options": ["18", "16", "12", "6"],
            "explanation": "12 plus 6 equals 18, so Riya has 18 pencils.",
            "marks": "1",
        },
        {
            "typology": "Source Based Question",
            "source": (
                "Amit collected 14 stamps on Monday and 18 stamps on Tuesday. "
                f"He wants to know his total. Source run {run_id}"
            ),
            "question": f"How many stamps did Amit collect in total? Source based run {run_id}",
            "options": ["32", "30", "14", "18"],
            "explanation": "14 plus 18 equals 32, so Amit collected 32 stamps.",
            "marks": "1",
        },
        {
            "typology": "Assertion and Reasoning",
            "assertion": f"Assertion (A): 25 is greater than 14. A&R run {run_id}",
            "reasoning": "Reasoning (R): 25 comes after 14 when counting upward.",
            "answer": "A",
            "marks": "1",
        },
        {
            "typology": "FA Activity",
            "instructions": (
                "Arrange number cards 12, 15, and 18 in increasing order on your "
                f"desk and read them aloud. FA Activity run {run_id}"
            ),
            "rubric": "Full marks for correct increasing order: 12, 15, 18.",
            "marks": "1",
        },
        {
            "typology": "Free Response",
            "question": f"Describe one way to count from 1 to 20. Free response run {run_id}",
            "answer": "Count forward one number at a time starting from 1 up to 20.",
            "marking_scheme": "Award full marks for any correct, clearly described counting method.",
            "marks": "1",
        },
    ]


@pytest.fixture
def manual_typology_items():
    return build_manual_typology_items(uuid4().hex[:10])


def identifying_text(item_data):
    """Not every typology's test data has a "question" key — Assertion and
    Reasoning uses "assertion", FA Activity uses "instructions". Return
    whichever field actually identifies this item's added-item card."""
    for key in ("question", "assertion", "instructions"):
        if key in item_data:
            return item_data[key]
    raise KeyError(f"No identifying text field found in item data: {item_data}")


@pytest.mark.usefixtures("setup")
class TestSMEManualItemCreation:
    logger = LogGenerator.loggen()

    def login_as_sme(self):
        self.driver.get(ReadConfig.get_base_url())
        # The staged "Added Items" list lives server-side per SME account, so
        # under xdist take the account pinned to this worker rather than the one
        # shared primary SME. Serial runs still use CBSE_SME_USERNAME.
        username = (
            ReadConfig.get_sme2_username()
            if os.getenv("PYTEST_XDIST_WORKER", "").strip().startswith("gw")
            else ReadConfig.get_sme_username()
        )
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        page = ManualItemPage(self.driver)
        page.close_popup_if_open()
        return page

    @staticmethod
    def assert_live_typology_inventory(page, live_options):
        canonical_options = [
            page.canonical_manual_typology(option)
            for option in live_options
        ]
        unknown_options = [
            option
            for option, canonical in zip(live_options, canonical_options)
            if not canonical
        ]
        actual = {canonical for canonical in canonical_options if canonical}
        expected = set(page.SUPPORTED_MANUAL_ITEM_TYPOLOGIES)
        assert not unknown_options, (
            "The app exposes unhandled manual typologies. Add test data and a "
            f"form handler for: {unknown_options}."
        )
        missing_from_app = expected - actual
        missing_from_tests = actual - expected
        if missing_from_app == {"Multiple Choice Question"} and not missing_from_tests:
            pytest.xfail(
                "KI-M1-TYPOLOGY-001 [M1 Manual item typology] \"Multiple Choice "
                "Question\" is missing from the live Item Typology dropdown "
                f"(only {len(actual)}/{len(expected)} controlled typologies "
                f"render); live options: {live_options}."
            )
        assert actual == expected, (
            "Manual typology inventory drifted. "
            f"Missing from app: {sorted(missing_from_app)}; "
            f"missing from tests: {sorted(missing_from_tests)}; "
            f"live options: {live_options}."
        )

    def test_sme_create_each_typology_manual_item_and_submit_for_qar_individually(
        self,
        request,
        manual_typology_items,
    ):
        """Create one typology's item, submit it for QAR, then move to the next
        typology and repeat — rather than batching all typologies into one draft
        before a single QAR submit. Each typology gets its own isolated
        create-to-QAR cycle, which also avoids state leaking between items that
        a shared draft was prone to."""
        page = self.login_as_sme()
        page.open_item_creation_module()
        page.open_manual_item_tab()
        page.wait_for_saved_draft_to_hydrate()
        page.clear_added_items()

        live_options = page.get_manual_item_typology_options()
        self.assert_live_typology_inventory(page, live_options)

        assert TEST_IMAGES, f"No .png images found under {TEST_IMAGES_DIR} to attach to items."
        rich_content_failures = {}
        results = []

        for index, item_data in enumerate(manual_typology_items):
            typology = item_data["typology"]
            try:
                if index > 0:
                    page.open_item_creation_module()
                    page.open_manual_item_tab()
                    page.wait_for_saved_draft_to_hydrate()
                    page.clear_added_items()

                page.select_common_manual_item_metadata()
                page.select_typology(typology)
                page.select_marks(item_data.get("marks", "1"))

                image_path = TEST_IMAGES[index % len(TEST_IMAGES)]
                editor_index = RICH_CONTENT_EDITOR_INDEX_OVERRIDES.get(typology, -1)

                def check_rich_content(typology=typology, image_path=image_path, editor_index=editor_index):
                    failures = apply_rich_content_checks(page, image_path, editor_index=editor_index)
                    if failures:
                        rich_content_failures[typology] = failures

                page.add_manual_item_for_typology(item_data, before_submit=check_rich_content)

                assert int(page.get_added_items_count()) == 1, (
                    f"{typology}: expected exactly 1 added item before QAR submit."
                )
                display_text = identifying_text(item_data)
                card_text = page.wait_for_added_item_card_text(display_text, typology)
                assert card_text, f"Added-item card was not found for {typology}: {display_text}"
                assert page.typology_tag_is_visible(typology, card_text), (
                    f"The added card for {typology} did not show the expected typology tag: {card_text}"
                )

                # Case Based / Source Based Question show the source/passage text
                # (not the sub-question) as the Review step's "Item" preview.
                review_search_text = item_data.get("source", display_text)
                item_id = page.submit_item_set_for_qar(review_search_text)
                qar_message = page.wait_for_qar_success_popup()
                qar_screenshot = page.capture_qar_success_screenshot(f"{request.node.name}_{typology}")

                assert item_id and item_id != "ID not found before QAR submit", (
                    f"{typology}: item ID not found before QAR submit."
                )
                assert qar_message or page.is_submission_successful(), (
                    f"{typology}: QAR submission did not report success."
                )

                results.append(
                    {
                        "typology": typology,
                        "status": "passed",
                        "item_id": item_id,
                        "qar_message": qar_message,
                        "screenshot": qar_screenshot,
                    }
                )
            except Exception as error:
                failure_screenshot = page.capture_qar_success_screenshot(
                    f"{request.node.name}_{typology}_FAILED"
                )
                print(f"[{typology}] FAILED: {error}")
                results.append(
                    {
                        "typology": typology,
                        "status": "failed",
                        "item_id": "",
                        "qar_message": str(error).splitlines()[0] if str(error) else "",
                        "screenshot": failure_screenshot,
                    }
                )

        passed = [result for result in results if result["status"] == "passed"]
        failed = [result for result in results if result["status"] == "failed"]
        print(f"Per-typology create+QAR results: {len(passed)} passed, {len(failed)} failed")
        for result in results:
            print(f"  [{result['status'].upper()}] {result['typology']}")

        if rich_content_failures:
            print("Rich content (image/bold/italic/color) issues found (non-blocking):")
            for typology, failures in rich_content_failures.items():
                for failure in failures:
                    print(f"  [{typology}] {failure}")
            request.node.user_properties.append(
                (
                    "rich_content_issues",
                    "; ".join(
                        f"{typology}: {' | '.join(failures)}"
                        for typology, failures in rich_content_failures.items()
                    ),
                )
            )

        expected_count = len(page.SUPPORTED_MANUAL_ITEM_TYPOLOGIES)
        assert len(results) == expected_count
        typologies = [result["typology"] for result in results]
        item_ids = [result["item_id"] for result in results]
        request.node.user_properties.extend(
            [
                ("manual_typology_coverage", f"{len(typologies)}/{expected_count}"),
                ("manual_item_typologies", ", ".join(typologies)),
                ("manual_item_id", ", ".join(item_ids)),
                (
                    "qar_success_message",
                    "; ".join(f"{result['typology']}: {result['qar_message']}" for result in results),
                ),
                ("qar_success_screenshot", results[-1]["screenshot"] if results else None),
            ]
        )
        print(f"Manual typology coverage: {len(typologies)}/{expected_count}")
        print(f"Manual typologies: {', '.join(typologies)}")
        print(f"Manual item IDs: {', '.join(item_ids)}")

        if failed:
            failure_summary = "; ".join(f"{result['typology']}: {result['qar_message']}" for result in failed)
            pytest.fail(
                f"{len(failed)}/{expected_count} typologies failed create+QAR "
                f"(others passed and are recorded above): {failure_summary}"
            )

    @pytest.mark.parametrize(
        "typology",
        ManualItemPage.SUPPORTED_MANUAL_ITEM_TYPOLOGIES,
        ids=lambda typology: typology.lower().replace(" ", "-"),
    )
    def test_sme_required_fields_block_empty_item_for_every_typology(self, typology):
        """An empty content payload must not create an item for any typology."""
        page = self.login_as_sme()
        page.open_item_creation_module()
        page.open_manual_item_tab()
        page.wait_for_saved_draft_to_hydrate()
        page.clear_added_items()
        try:
            page.select_manual_item_metadata(typology, "1")
        except TimeoutException as error:
            if typology == "Multiple Choice Question":
                pytest.xfail(
                    "KI-M1-TYPOLOGY-001 [M1 Manual item typology] \"Multiple "
                    f"Choice Question\" is missing from the live Item Typology "
                    f"dropdown, so it cannot be selected: {error}"
                )
            raise

        # Selecting Grade/Subject/Chapter can rehydrate a chapter-scoped
        # saved draft that the earlier clear (done before any chapter was
        # picked) could not have seen. Clear again now that the real
        # metadata combination for this typology is active.
        page.clear_added_items()
        before_count = int(page.get_added_items_count())
        clicked = page.click_add_item_if_enabled()
        page.pause_before_action()
        after_count = int(page.get_added_items_count())
        required_messages = page.get_visible_required_validation_messages()
        validation_messages = page.get_visible_validation_messages()

        assert before_count == after_count == 0, (
            f"{typology} created an item despite all typology-specific required "
            "content fields being empty."
        )
        assert (
            required_messages
            or validation_messages
            or not clicked
            or page.is_continue_enabled() is False
        ), (
            f"{typology} showed no required-field signal after an empty Add Item attempt."
        )
