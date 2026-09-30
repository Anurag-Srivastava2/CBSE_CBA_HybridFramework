from collections import Counter

import pytest
from selenium.webdriver.common.keys import Keys

from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from pages.teacher.question_paper_builder_page import QuestionPaperBuilderPage
from tests.M4_QP_Creation.qp_surveys import (
    enter_screen,
    survey_builder,
    survey_chrome,
    survey_my_qp,
    survey_preview,
)
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.qp_question_budget import cap_item_counts
from utilities.read_config import ReadConfig

NUMBER_OF_SETS = 4
EXAM_DURATION_MINUTES = 30

# Two sections, so the jumble can also be checked to stay inside its section
# rather than moving questions across section boundaries.
# Question counts shrink to fit CBSE_QP_MAX_QUESTIONS when it is set; the
# two-section shape, and everything the test proves about it, is unchanged.
SECTION_ITEM_COUNTS = cap_item_counts([10, 5])
SECTION_CONFIGS = [
    {"number_of_items": SECTION_ITEM_COUNTS[0], "marks_per_item": 1},
    {"number_of_items": SECTION_ITEM_COUNTS[1], "marks_per_item": 2},
]
TOTAL_MARKS = sum(
    config["number_of_items"] * config["marks_per_item"] for config in SECTION_CONFIGS
)
TOTAL_QUESTIONS = sum(config["number_of_items"] for config in SECTION_CONFIGS)


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestQPAllSetsSameQuestionsJumbled:
    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        username = ReadConfig.get_qp_teacher_username()
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys(Keys.ESCAPE)
        assert DashboardPage(self.driver).is_dashboard_loaded()
        checkpoint(f"QP teacher {username} signed in and reached the dashboard")
        return username

    def test_e2e_all_sets_hold_the_same_questions_in_jumbled_order(
        self, request, record_property, page_evidence
    ):
        """"All sets contain the same questions" means same questions, different order.

        The distribution radio is the only thing standing between four sets
        that are genuinely interchangeable and four that quietly differ - and
        nothing in the builder shows which you got until the paper is
        published. So this asserts both halves of the contract: every set
        holds the same questions carrying the same marks, and the order is
        actually jumbled rather than four identical printings. The metadata
        the paper was configured with is checked to survive alongside it.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Build and publish a question paper configured so that all sets hold the "
            "same questions.\n"
            "Check every set really does hold the same questions carrying the same "
            "marks.\n"
            "Check the order is genuinely jumbled between sets, rather than four "
            "identical printings of one paper.\n"
            "Check the metadata the paper was configured with survives publication "
            "alongside it.",
        )
        self.login_as_teacher()
        page = QuestionPaperBuilderPage(self.driver)

        # -------------------------------------------------------------
        # STEP 1: Auto-generate an item-level paper of four shared sets
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
            number_of_sections=len(SECTION_CONFIGS),
            number_of_sets=NUMBER_OF_SETS,
            select_all_chapters=True,
        )
        distribution = page.select_question_distribution("same")
        request.node.user_properties.append(("distribution", distribution))
        page.configure_item_level_rows(SECTION_CONFIGS)
        page_evidence.checkpoint(
            f"Item-level generator configured for {TOTAL_MARKS} marks over "
            f"{len(SECTION_CONFIGS)} section(s) and {NUMBER_OF_SETS} sets, with "
            f"question distribution set to {distribution!r} — the one control "
            "that decides whether the sets are interchangeable"
        )

        allocation = page.get_marks_allocation()
        page_evidence.checkpoint(
            f"Marks fully allocated before generation: {allocation}"
        )
        assert allocation == [TOTAL_MARKS, TOTAL_MARKS], allocation

        generation_seconds = page.generate_auto_paper()
        request.node.user_properties.append(("generation_seconds", generation_seconds))
        paper_number = page.finalise_or_publish()
        request.node.user_properties.append(("paper_number", str(paper_number)))
        page_evidence.checkpoint(
            f"Paper generated in {generation_seconds:.1f}s and published as "
            f"{paper_number or 'no number reported'}"
        )
        assert paper_number, "Publication did not report a Question Paper number."

        page.open_my_qp()
        enter_screen(checks, "QP Builder - My QP")
        survey_my_qp(checks, page)

        # -------------------------------------------------------------
        # STEP 2: The published paper carries the metadata it was given
        # -------------------------------------------------------------
        page.open_published_qp_preview(paper_number)
        enter_screen(checks, "QP Builder - Paper Preview")
        survey_preview(checks, page)
        record_property("result_description", checks.publish())

        summary = page.get_paper_summary_metadata()
        request.node.user_properties.append(("paper_summary", str(summary)))
        page_evidence.checkpoint(
            f"Published paper carries the metadata it was configured with: "
            f"{summary}"
        )
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
        assert len(section_headings) == len(SECTION_CONFIGS), section_headings

        set_labels = page.get_set_tab_labels()
        request.node.user_properties.append(("set_labels", str(set_labels)))
        page_evidence.checkpoint(
            f"Published paper renders {len(section_headings)} section(s) "
            f"({len(SECTION_CONFIGS)} configured) and {len(set_labels)} set(s) "
            f"({NUMBER_OF_SETS} configured): {set_labels}"
        )
        assert len(set_labels) == NUMBER_OF_SETS, set_labels

        # -------------------------------------------------------------
        # STEP 3: Read every set
        # -------------------------------------------------------------
        by_set = page.collect_questions_by_set()
        assert sorted(by_set) == sorted(set_labels), (sorted(by_set), sorted(set_labels))

        orders = {}
        for label, questions in by_set.items():
            assert len(questions) == TOTAL_QUESTIONS, (label, len(questions))
            # Marks belong to a question's identity here rather than to a
            # separate assertion. A fingerprint is text plus options, and that
            # is not unique inside one paper: the bank holds distinct items
            # that read identically, so the 1-mark and 2-mark sections can
            # legitimately both draw one. Pairing the two still says "the same
            # questions carrying the same marks" without the stronger - and
            # untrue - claim that no two questions can read alike.
            orders[label] = [
                (question["fingerprint"], question["marks"]) for question in questions
            ]
        request.node.user_properties.append(
            ("questions_per_set", str({k: len(v) for k, v in orders.items()}))
        )
        page_evidence.checkpoint(
            f"Read every set — each holds {TOTAL_QUESTIONS} question(s): "
            f"{ {label: len(items) for label, items in orders.items()} }"
        )

        # Observed rather than asserted: whether the generator may draw one
        # item into two sections is a question about bank content, not about
        # the jumbling contract under test, so a paper that repeats a question
        # consistently across its sets is recorded, not failed.
        repeats = [
            fingerprint
            for fingerprint, count in Counter(
                fingerprint for fingerprint, _ in orders[set_labels[0]]
            ).items()
            if count > 1
        ]
        request.node.user_properties.append(
            ("repeated_question_texts", str([text[:60] for text in sorted(repeats)]))
        )

        # -------------------------------------------------------------
        # STEP 4: Same questions, carrying the same marks, in every set
        # -------------------------------------------------------------
        baseline_label, *other_labels = set_labels
        baseline = Counter(orders[baseline_label])
        differences = {}
        for label in other_labels:
            current = Counter(orders[label])
            differences[label] = (
                len(sorted(baseline - current)),
                len(sorted(current - baseline)),
            )
        page_evidence.checkpoint(
            f"Every set measured against {baseline_label} as (missing, extra) "
            f"question+marks pairs: {differences} — all zeroes means the sets "
            "hold the same questions carrying the same marks"
        )
        for label in other_labels:
            current = Counter(orders[label])
            missing = sorted(baseline - current)
            extra = sorted(current - baseline)
            assert not missing and not extra, (
                f"{label} does not hold the same questions as {baseline_label}. "
                f"Missing {len(missing)}: "
                f"{[(text[:60], marks) for text, marks in missing]}. "
                f"Extra {len(extra)}: "
                f"{[(text[:60], marks) for text, marks in extra]}."
            )

        total_marks_per_set = {
            label: sum(int(question["marks"]) for question in questions)
            for label, questions in by_set.items()
        }
        request.node.user_properties.append(
            ("total_marks_per_set", str(total_marks_per_set))
        )
        page_evidence.checkpoint(
            f"Total marks per set (each must be {TOTAL_MARKS}): "
            f"{total_marks_per_set}"
        )
        for label, marks in total_marks_per_set.items():
            assert marks == TOTAL_MARKS, (label, marks, total_marks_per_set)

        # -------------------------------------------------------------
        # STEP 5: ...but jumbled, not four identical printings
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

        # Numbering restarts identically in each set - only the mapping from
        # number to question changes.
        for label, questions in by_set.items():
            labels_in_order = [question["label"] for question in questions]
            assert labels_in_order == [
                question["label"] for question in by_set[baseline_label]
            ], (label, labels_in_order)
