from collections import Counter

import pytest
from selenium.webdriver.common.keys import Keys

from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from pages.teacher.question_paper_builder_page import QuestionPaperBuilderPage
from tests.M4_QP_Creation.qp_surveys import (
    enter_screen,
    survey_builder,
    survey_choice_rules,
    survey_chrome,
    survey_my_qp,
    survey_preview,
)
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.qp_question_budget import cap_item_counts
from utilities.read_config import ReadConfig

# Both section sizes shrink to fit CBSE_QP_MAX_QUESTIONS when it is set. The
# choice rules keep their shape at any size: Section A always leaves at least
# one question unattempted, Section B always keeps at least one mandatory slot
# and one OR pair, so what this suite proves does not change with the cap.
ATTEMPT_ANY_ITEMS, OR_BASED_ITEMS = cap_item_counts([12, 6])

# Section A - 12 generated questions of 1 mark, of which the student attempts
# any 10. The builder costs "Attempt Any" at attempt x marks, not items x
# marks, so this section is worth 10 marks and not 12.
ATTEMPT_ANY_TO_ATTEMPT = max(1, min(ATTEMPT_ANY_ITEMS - 1, round(ATTEMPT_ANY_ITEMS * 10 / 12)))
ATTEMPT_ANY_MARKS_PER_ITEM = 1
SECTION_A_MARKS = ATTEMPT_ANY_TO_ATTEMPT * ATTEMPT_ANY_MARKS_PER_ITEM

# Section B - 6 numbered slots of 2 marks. "OR Based" keeps the first 3
# mandatory and turns the remaining 3 into OR pairs, so the paper renders 3
# plain questions plus 3 pairs (9 question bodies across 6 numbered slots).
# Every slot is costed, so the section is worth items x marks.
OR_BASED_MANDATORY = max(1, OR_BASED_ITEMS // 2)
OR_BASED_MARKS_PER_ITEM = 2
OR_PAIR_COUNT = OR_BASED_ITEMS - OR_BASED_MANDATORY
SECTION_B_MARKS = OR_BASED_ITEMS * OR_BASED_MARKS_PER_ITEM

TOTAL_MARKS = SECTION_A_MARKS + SECTION_B_MARKS
EXAM_DURATION_MINUTES = 30

# Both alternatives of an OR pair are printed, so the paper renders more
# question bodies than it has numbered slots.
TOTAL_QUESTION_BODIES = (
    ATTEMPT_ANY_ITEMS + OR_BASED_MANDATORY + OR_PAIR_COUNT * 2
)

# Four sets drawn from the same questions, so the choice rules can be checked
# to survive into every one of them rather than only the set shown first.
NUMBER_OF_SETS = 4


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestQPItemLevelOrAndAttemptAny:
    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        # A QP teacher account, never the primary one - see the note in
        # test_qp_autogenerate_item_level_preview: this suite also publishes
        # into "My QP" and previews the newest paper in that list.
        username = ReadConfig.get_qp_teacher_username()
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys(Keys.ESCAPE)
        assert DashboardPage(self.driver).is_dashboard_loaded()
        checkpoint(f"QP teacher {username} signed in and reached the dashboard")
        return username

    def test_e2e_item_level_attempt_any_and_or_based_question_selection(
        self, request, record_property, page_evidence
    ):
        """Item-level QUESTION SELECTION rules survive into every published set.

        Two of the three rules change what the student is asked to do rather
        than what is generated, and neither is visible anywhere until the
        paper renders: "Attempt Any" prints an "Attempt any X out of Y"
        rubric, "OR Based" prints the choice rubric and pairs its questions
        as Q<n>a / OR / Q<n>b.

        The paper is generated as four sets sharing one pool of questions, so
        the rules are asserted in each set rather than only the one shown
        first - a rule that survived into Set 01 and was dropped from Set 03
        would otherwise go unnoticed. The sets are also checked to hold the
        same questions in a jumbled order, and to carry the metadata the
        paper was configured with. Page furniture stays a soft survey, as in
        the sibling M4 suites.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Generate a paper using the item-level question-selection rules, as four "
            "sets sharing one pool of questions.\n"
            "Check Attempt Any prints its 'Attempt any X out of Y' rubric, and OR "
            "Based prints the choice rubric pairing its questions as Q1a / OR / Q1b.\n"
            "Check the rules survive into every set, not just the one shown first, "
            "since a rule kept in Set 01 and dropped from Set 03 would otherwise go "
            "unnoticed.\n"
            "Check the sets still hold the same questions in a different order.",
        )
        self.login_as_teacher()
        page = QuestionPaperBuilderPage(self.driver)

        # -------------------------------------------------------------
        # STEP 1: Configure an item-level paper with two selection rules
        # -------------------------------------------------------------
        page.open()
        checks = ElementChecks(
            page, record_property, page_name="QP Builder - Assessment Configuration"
        )
        survey_chrome(checks, page)

        page.open_auto_generator()
        enter_screen(checks, "QP Builder - Auto Generator")
        survey_builder(checks, page, mode="Auto Generator")

        page.select_item_level()
        selections = page.configure_item_level_generator(
            total_marks=TOTAL_MARKS,
            number_of_sections=2,
            number_of_sets=NUMBER_OF_SETS,
            select_all_chapters=True,
        )
        # Without this the sets may each draw different questions, and
        # "the rules survive into every set" would be a weaker claim.
        distribution = page.select_question_distribution("same")
        request.node.user_properties.append(("distribution", distribution))

        section_configs = [
            {
                "number_of_items": ATTEMPT_ANY_ITEMS,
                "marks_per_item": ATTEMPT_ANY_MARKS_PER_ITEM,
                "question_selection": "Attempt Any",
                "question_selection_count": ATTEMPT_ANY_TO_ATTEMPT,
            },
            {
                "number_of_items": OR_BASED_ITEMS,
                "marks_per_item": OR_BASED_MARKS_PER_ITEM,
                "question_selection": "OR Based",
                "question_selection_count": OR_BASED_MANDATORY,
            },
        ]
        rules = page.configure_item_level_rows(section_configs)
        request.node.user_properties.append(("selection_rules", str(rules)))
        page_evidence.checkpoint(
            f"Item-level paper configured for {TOTAL_MARKS} marks over "
            f"{NUMBER_OF_SETS} sets sharing one pool (distribution "
            f"{distribution!r}); Section A rule "
            f"{rules[0].get('QUESTION SELECTION')!r}, Section B rule "
            f"{rules[1].get('QUESTION SELECTION')!r}"
        )

        # Both rules are offered by the dropdown, and both were taken.
        assert rules[0]["QUESTION SELECTION"] == "Attempt Any", rules
        assert rules[1]["QUESTION SELECTION"] == "OR Based", rules

        # -------------------------------------------------------------
        # STEP 2: The builder costs each rule before anything is generated
        # -------------------------------------------------------------
        chips = page.get_section_rule_chips()
        request.node.user_properties.append(("section_rule_chips", str(chips)))
        checks.check_condition(
            "Section rule chips state each rule's cost", bool(chips), detail=str(chips)
        )
        # "Attempt Any" is costed on what the student attempts; "OR Based" on
        # every numbered slot. Getting this wrong is how a paper silently
        # comes out over or under its target.
        assert any(
            "Attempt {}/{}Q = {}M".format(
                ATTEMPT_ANY_TO_ATTEMPT, ATTEMPT_ANY_ITEMS, SECTION_A_MARKS
            )
            in chip
            for chip in chips
        ), chips
        assert any(
            "OR Based {}Q = {}M".format(OR_BASED_ITEMS, SECTION_B_MARKS) in chip
            for chip in chips
        ), chips

        page_evidence.checkpoint(
            f"Builder costs each rule before generating — chips: {chips}. "
            "Attempt Any is costed on what the student attempts, OR Based on "
            "every numbered slot"
        )

        allocation = page.get_marks_allocation()
        request.node.user_properties.append(("marks_allocation", str(allocation)))
        page_evidence.checkpoint(
            f"Marks fully allocated before generation: {allocation}"
        )
        assert allocation == [TOTAL_MARKS, TOTAL_MARKS], allocation

        # -------------------------------------------------------------
        # STEP 3: Generate and publish
        # -------------------------------------------------------------
        try:
            generation_seconds = page.generate_auto_paper()
        except AssertionError as error:
            # Generation depends on the environment holding enough items to
            # satisfy the rules. Publish the survey before re-raising so the
            # report still shows what the screens rendered.
            record_property("result_description", checks.publish())
            page_evidence.checkpoint(
                f"Generation failed, most likely for want of bank items matching "
                f"the configured rules: {error}"
            )
            raise
        page_evidence.checkpoint(
            f"Paper generated in {generation_seconds:.1f}s against a 10s budget"
        )
        assert generation_seconds <= 10
        request.node.user_properties.append(("generation_seconds", generation_seconds))
        paper_number = page.finalise_or_publish()
        request.node.user_properties.append(("paper_number", str(paper_number)))
        page_evidence.checkpoint(
            f"Paper published as {paper_number or 'no number reported'}"
        )
        assert paper_number, "Publication did not report a Question Paper number."

        page.open_my_qp()
        enter_screen(checks, "QP Builder - My QP")
        survey_my_qp(checks, page)
        assert selections["Paper Title*"].casefold() in page.body_text().casefold()

        # -------------------------------------------------------------
        # STEP 4: The published paper carries the metadata it was given
        # -------------------------------------------------------------
        # By number, not by listing position: the M4 suites share an account
        # and the listing is ordered by publication date, so the top row is
        # not reliably the paper this test just published.
        page.open_published_qp_preview(paper_number)
        enter_screen(checks, "QP Builder - Paper Preview")
        survey_preview(checks, page)
        rendered = survey_choice_rules(checks, page)
        record_property("result_description", checks.publish())
        request.node.user_properties.append(("rendered_choice_rules", str(rendered)))
        page_evidence.checkpoint(
            f"Preview opened by number for paper {paper_number}; choice rules as "
            f"rendered: {rendered}"
        )

        summary = page.get_paper_summary_metadata()
        request.node.user_properties.append(("paper_summary", str(summary)))
        assert summary.get("Total Marks", "").strip() == str(TOTAL_MARKS), summary
        assert str(EXAM_DURATION_MINUTES) in summary.get("Time Allowed", ""), summary
        for field, configured in (
            ("Subject", selections["Subject*"]),
            ("Class", selections["Grade*"]),
            ("Assessment Type", selections["Assessment Type*"]),
        ):
            assert configured.casefold() in summary.get(field, "").casefold(), (
                field,
                configured,
                summary,
            )

        section_headings = page.get_section_headings()
        assert len(section_headings) == 2, section_headings

        set_labels = page.get_set_tab_labels()
        request.node.user_properties.append(("set_labels", str(set_labels)))
        page_evidence.checkpoint(
            f"Published paper carries the configured metadata ({summary}), "
            f"{len(section_headings)} section(s) and {len(set_labels)} set(s) "
            f"({NUMBER_OF_SETS} configured)"
        )
        assert len(set_labels) == NUMBER_OF_SETS, set_labels

        # -------------------------------------------------------------
        # STEP 5: Walk every set, reading its questions and its rubrics
        # -------------------------------------------------------------
        # One pass over the set tabs: switching is the slow part, so the
        # questions and the choice rules are read from each set together.
        by_set = {}
        rules_by_set = {}
        for label in set_labels:
            page.switch_to_set(label)
            page.pause_before_action()
            by_set[label] = page.get_set_questions()
            pair_numbers = page.get_or_pair_numbers()
            rules_by_set[label] = {
                "attempt": page.get_attempt_any_counts(),
                "or_rule": page.get_or_choice_instruction(),
                "pairs": pair_numbers,
                "separators": page.count_or_separators(),
                "pair_order": {
                    number: page.verify_or_choice_structure(number)
                    for number in pair_numbers
                },
            }
        request.node.user_properties.append(
            ("rules_by_set", str({k: v["pairs"] for k, v in rules_by_set.items()}))
        )
        page_evidence.checkpoint(
            "Walked every set reading its questions and rubrics — "
            "Attempt Any counts per set: "
            f"{ {label: state['attempt'] for label, state in rules_by_set.items()} }"
        )
        page_evidence.checkpoint(
            "OR pairs per set (the same numbered slots must offer the choice in "
            "every set): "
            f"{ {label: state['pairs'] for label, state in rules_by_set.items()} }"
        )

        # -------------------------------------------------------------
        # STEP 6: Both rules render in every set
        # -------------------------------------------------------------
        for label in set_labels:
            state = rules_by_set[label]

            # Section A: "Attempt any 10 out of 12 questions."
            assert state["attempt"] == (
                ATTEMPT_ANY_TO_ATTEMPT,
                ATTEMPT_ANY_ITEMS,
            ), (label, state["attempt"])

            # Section B: the choice rubric, then one pair per non-mandatory
            # slot - the mandatory ones stay unpaired.
            assert state["or_rule"], f"{label} did not print the OR-choice rubric."
            assert (
                "attempt only one from each pair" in state["or_rule"].casefold()
            ), (label, state["or_rule"])
            assert len(state["pairs"]) == OR_PAIR_COUNT, (label, state["pairs"])
            assert state["separators"] == OR_PAIR_COUNT, (label, state["separators"])

            # Each pair reads Q<n>a, then OR, then Q<n>b.
            for number, positions in state["pair_order"].items():
                assert positions["a"] < positions["or"] < positions["b"], (
                    label,
                    number,
                    positions,
                )

        # The pairs occupy the same numbered slots in every set: jumbling
        # moves which question lands where, not which slots offer a choice.
        baseline_label, *other_labels = set_labels
        for label in other_labels:
            assert rules_by_set[label]["pairs"] == rules_by_set[baseline_label]["pairs"], (
                label,
                rules_by_set[label]["pairs"],
                rules_by_set[baseline_label]["pairs"],
            )

        # -------------------------------------------------------------
        # STEP 7: Every set holds the same questions...
        # -------------------------------------------------------------
        orders = {}
        for label, questions in by_set.items():
            assert len(questions) == TOTAL_QUESTION_BODIES, (label, len(questions))
            orders[label] = [question["fingerprint"] for question in questions]

        baseline = Counter(orders[baseline_label])
        page_evidence.checkpoint(
            f"Each set prints {TOTAL_QUESTION_BODIES} question bodies "
            "(both alternatives of an OR pair are printed): "
            f"{ {label: len(items) for label, items in orders.items()} }"
        )
        page_evidence.checkpoint(
            f"Every set measured against {baseline_label} as (missing, extra) "
            "questions: "
            + str(
                {
                    label: (
                        len(sorted(baseline - Counter(orders[label]))),
                        len(sorted(Counter(orders[label]) - baseline)),
                    )
                    for label in other_labels
                }
            )
        )
        for label in other_labels:
            current = Counter(orders[label])
            missing = sorted(baseline - current)
            extra = sorted(current - baseline)
            assert not missing and not extra, (
                f"{label} does not hold the same questions as {baseline_label}. "
                f"Missing {len(missing)}: {[text[:60] for text in missing]}. "
                f"Extra {len(extra)}: {[text[:60] for text in extra]}."
            )

        # Where a question's marks are printed at all they agree across sets.
        # An OR pair states its marks once, on the a-side, so the b-side is
        # blank - and jumbling moves a question between the two, which is why
        # the blank ones are skipped rather than compared.
        marks_by_question = {}
        for label, questions in by_set.items():
            for question in questions:
                if not question["marks"]:
                    continue
                seen = marks_by_question.setdefault(
                    question["fingerprint"], (label, question["marks"])
                )
                assert seen[1] == question["marks"], (
                    f"A question is worth {seen[1]} in {seen[0]} but "
                    f"{question['marks']} in {label}: "
                    f"{question['fingerprint'][:80]}"
                )

        # Summing the printed marks overshoots the paper total here - the
        # student attempts only 10 of Section A's 12 - so the printed total is
        # checked against what each section actually prints: every Section A
        # question, and one marks badge per Section B slot.
        printed_marks = {
            label: sum(
                int(question["marks"]) for question in questions if question["marks"]
            )
            for label, questions in by_set.items()
        }
        request.node.user_properties.append(("printed_marks_per_set", str(printed_marks)))
        expected_printed = (
            ATTEMPT_ANY_ITEMS * ATTEMPT_ANY_MARKS_PER_ITEM + SECTION_B_MARKS
        )
        page_evidence.checkpoint(
            f"Printed marks per set (each must be {expected_printed}, which "
            "overshoots the paper total because the student attempts only "
            f"{ATTEMPT_ANY_TO_ATTEMPT} of Section A's {ATTEMPT_ANY_ITEMS}): "
            f"{printed_marks}"
        )
        for label, marks in printed_marks.items():
            assert marks == expected_printed, (label, marks, printed_marks)

        # -------------------------------------------------------------
        # STEP 8: ...but jumbled, not four identical printings
        # -------------------------------------------------------------
        jumbled = [
            label for label in other_labels if orders[label] != orders[baseline_label]
        ]
        request.node.user_properties.append(("sets_reordered", str(jumbled)))
        page_evidence.checkpoint(
            f"Sets printing in a different order from {baseline_label}: "
            f"{jumbled or 'none — four identical printings, not jumbled'}"
        )
        assert jumbled, (
            f"Every set printed its questions in the same order as "
            f"{baseline_label}, so the sets are not jumbled at all."
        )

        # The slot layout is identical in every set - the same numbering, and
        # the same marks against each slot. Jumbling changes which question
        # fills a slot, never the shape of the paper around it.
        baseline_layout = [
            (question["label"], question["marks"])
            for question in by_set[baseline_label]
        ]
        for label in other_labels:
            layout = [
                (question["label"], question["marks"]) for question in by_set[label]
            ]
            assert layout == baseline_layout, (label, layout, baseline_layout)

        # -------------------------------------------------------------
        # STEP 9: Back to the listing
        # -------------------------------------------------------------
        page.click_back_from_preview()
        page_evidence.checkpoint(
            f"Back from the preview returns to My QP: "
            f"{'my qp' in page.body_text().casefold()}"
        )
        assert "my qp" in page.body_text().casefold()
