"""TC-IBMM-06 / TC-IBMM-07: the plagiarism and bias checks run and report.

Deliberately *not* marked `nightly`. That marker is for assertions about what
the model concluded; nothing here asserts a verdict. This test only checks that
the checks ran and reported — the card renders and carries a score. That is
application behaviour, not model behaviour, so it belongs in the gating suite:

    if QAR silently stopped running its bias or plagiarism analysis tomorrow,
    this test fails, while every verdict-based test would still pass on
    whatever verdict it happened to get.

Asserted at set level, because that is where the app puts it. The QAR Report
panel renders one card per check for the whole item set:

    Meta Data Alignment | Hard Validation | Image Moderation | Bias Detection
    Grammar Check       | Clarity Check   | Duplicate Check  | Plagiarism Check

There is no per-item breakdown of these checks in this build, so the "for every
item" half of TC-IBMM-07-P01 is not verifiable through the UI — see the xfail
on the category test below.

Covers:
  TC-IBMM-06-P01/N01  QAR Report shows a plagiarism score
  TC-IBMM-07-P01      Bias section present, with per-category detail (xfail)
"""
from pathlib import Path
from shutil import copy2
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.item_template_columns import (
    clear_rows_from,
    copy_item_row,
    item_data_worksheet,
    resolve_columns,
    trim_helper_columns,
    write_row_fields,
)
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.e2e
# serial: every test here uploads under the same SME account. Without this the
# three scattered across xdist workers and contended for that one session,
# which surfaced as a fixture ERROR rather than an honest assertion failure.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestQARPlagiarismAndBiasSections:
    ITEM_COUNT = 3

    # Card labels exactly as the QAR Report panel renders them. The app says
    # "Plagiarism Check" and "Duplicate Check" but "Bias Detection", so these
    # are not derivable from a single naming rule.
    PLAGIARISM_CHECK = "Plagiarism Check"
    BIAS_CHECK = "Bias Detection"

    # The collapsed panel that holds every check card on the results view.
    REPORT_PANEL = "QAR Report"

    # Near-verbatim copies of items already in the IB1 repository: the bank's
    # own sentence with a short reference tag appended.
    #
    # Byte-identical text cannot be used here. Upload validation rejects a row
    # whose question already exists in the bank, so an exact copy never reaches
    # QAR at all - proved with a four-row upload where the two verbatim rows
    # failed and the two novel rows passed ("PASSED 4 2 2"). The tag makes the
    # row ingestable while leaving it far more similar to the source than any
    # paraphrase, so QAR's duplicate and plagiarism checks have something real
    # to score.
    #
    # Source items (Grade 1 Mathematics, CH-1) from Item Bank Repository:
    #   IS1062-G1-Mathematics-Ch29-i3  "129 is greater than 190."
    #   IS1013-G1-Mathematics-Ch29-i3  "407 is greater than 356."
    COPIED_BANK_QUESTIONS = [
        ("True or False", "129 is greater than 190.", "FALSE"),
        ("True or False", "407 is greater than 356.", "TRUE"),
        ("True or False", "16 is greater than 140.", "FALSE"),
    ]

    # TC-IBMM-07-P01 requires a pass/fail per category. Several spellings are
    # accepted so a mismatch means the category is genuinely absent rather than
    # written differently.
    BIAS_CATEGORIES = {
        "Gender": ("gender",),
        "Cultural": ("cultural", "culture"),
        "Socio-economic": ("socio-economic", "socioeconomic", "socio economic"),
        "Statistical (DIF)": ("statistical", "dif", "differential item functioning"),
    }

    def login_as_sme(self):
        self.driver.get(ReadConfig.get_base_url())
        username = ReadConfig.get_sme2_username()
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        return page

    @staticmethod
    def build_copied_workbook(tmp_path):
        """A workbook whose questions are verbatim copies of existing IB1 items.

        Mirrors the column handling the duplicate-detection suite proved out:
        the template carries helper columns past the canonical item columns,
        and leaving them in place makes upload validation reject the file.
        """
        tag = uuid4().hex[:6]
        target = tmp_path / f"qar_copied_{tag}.xlsx"
        copy2(Path(ReadConfig.get_upload_item_file_path()), target)
        workbook = load_workbook(target)
        # Not workbook.active: a freshly downloaded template opens on its
        # Instructions sheet.
        worksheet = item_data_worksheet(workbook) or workbook.active

        max_data_column = trim_helper_columns(worksheet)
        columns = resolve_columns(worksheet)
        assert columns, "Upload template has no recognisable item-data sheet."

        questions = TestQARPlagiarismAndBiasSections.COPIED_BANK_QUESTIONS
        for offset, (typology, question, answer) in enumerate(questions):
            row = offset + 2
            if row != 2:
                copy_item_row(worksheet, 2, row, max_data_column)
            write_row_fields(
                worksheet,
                row,
                columns,
                {
                    "sequence": offset + 1,
                    "typology": typology,
                    # The bank's sentence plus a short reference tag, as the
                    # class comment above describes. Byte-identical copies are
                    # refused at upload validation ("All 3 row(s) failed
                    # validation", build #3, 2026-10-01), which set up an
                    # ERROR for all five tests before QAR ever ran.
                    "question": f"{question} [ref {tag}-{offset + 1}]",
                    "answer": answer,
                    "explanation": "Copied verbatim from the item bank.",
                    "marks": "1",
                },
            )

        clear_rows_from(worksheet, len(questions) + 2, max_data_column)

        workbook.save(target)
        workbook.close()
        return target

    def assert_check_is_not_clean(self, page_evidence, report, label, record_property):
        """One check must not score 100% on content copied out of the bank.

        A clean 100% means the check did not recognise content it has already
        stored — the exact regression this exists to catch. Split per check so
        a duplicate-detection failure and a plagiarism failure are separately
        attributable rather than sharing one red result.
        """
        page_evidence.checkpoint(
            f"QAR report opened for the copied item set; reading {label}"
        )

        result = self.read_check(report, label)
        record_property(f"{label.lower().replace(' ', '_')}_score", str(result["score"]))
        record_property(f"{label.lower().replace(' ', '_')}_card", (result["card"] or "")[:200])

        page_evidence.checkpoint(
            f"{label} card rendered: score={result['score']}, colour={result['color']}"
        )

        assert result["card"], (
            f"QAR Report rendered no {label!r} card, so the check either did "
            "not run or stopped reporting."
        )
        assert result["score"] is not None, (
            f"{label} rendered no numeric score, so it cannot be compared "
            f"against the 100% clean mark. Card: {result['card'][:200]!r}"
        )

        page_evidence.checkpoint(
            f"{label} scored {result['score']}% against a 100% clean mark"
        )
        assert result["score"] < 100, (
            f"{label} scored {result['score']}% on items copied verbatim from "
            "the item bank. A clean 100% means the check did not recognise "
            f"content already stored in IB1. Card: {result['card'][:200]!r}"
        )
        return result["score"]

    @pytest.fixture
    def qar_report(self, tmp_path, record_property, page_evidence):
        """Upload copied bank items, run QAR, and open the report.

        Content copied verbatim from IB1 on purpose: a clean set passes at 100%
        and the QAR report then renders no per-check detail at all, so there is
        no card to assert against. Copied content trips the plagiarism and
        duplicate checks, which is what makes the section render.
        """
        self.login_as_sme()
        workbook = self.build_copied_workbook(tmp_path)
        page = UploadItemFilePage(self.driver)
        page.open_item_creation_module()
        page.open_upload_item_file_tab()
        page.open_upload_step()
        page.upload_file(workbook)
        page.wait_for_upload_validation_success()
        page_evidence.checkpoint(
            f"{self.ITEM_COUNT} near-verbatim copies of IB1 items passed upload "
            "validation, so QAR has something real to score"
        )
        page.click_continue()
        review_ids = page.get_review_item_ids()
        page.click_continue()
        # 420s, not the 180s default: QAR on this environment regularly runs
        # past three minutes even for small text-only sets.
        page.click_submit_for_qar_and_wait_for_results(analysis_timeout=420)
        page.wait_for_ocr_success_message()

        item_ids = page.get_qar_result_item_ids() or review_ids
        item_set_id = page.get_item_set_id_from_item_ids(item_ids)
        record_property("item_set_id", item_set_id)
        record_property("qar_item_count", str(len(item_ids)))
        page_evidence.checkpoint(
            f"QAR finished; results list {len(item_ids)} item(s) under set "
            f"{item_set_id or 'UNKNOWN'}"
        )

        assert item_ids, "QAR results listed no items, so there is no report."
        report = QARReportPage(self.driver)

        # The check cards are disclosed by expanding a result ROW, not by any
        # panel-level control and not by opening the item (which navigates away
        # from the results view entirely). Asking to expand by a check label
        # can never work either: that label is exactly what is still hidden.
        expanded = report.expand_result_row(item_ids[0])
        record_property("result_row_expanded", str(expanded))
        page_evidence.checkpoint(
            f"Result row {item_ids[0]} expanded: {expanded} — this is what "
            "discloses the per-check cards"
        )
        assert expanded, (
            "Could not expand a QAR result row, so the per-check cards were "
            f"never disclosed. Item ids seen: {item_ids[:3]}."
        )
        return report, item_ids

    @staticmethod
    def read_check(report, label):
        """Card text and score for one check, read without an item filter.

        The cards belong to the set, not to a row. Passing an item id makes the
        lookup match whichever ancestor contains both the id and the label — in
        practice the whole results table — instead of the card itself.

        Assumes the QAR Report panel is already expanded (see the fixture);
        expanding per card is a no-op while the panel is closed.
        """
        card = report.get_check_card_text(label)
        return {
            "card": card,
            "score": report.get_check_score(label),
            "color": report.get_check_card_status_color(label),
        }

    def test_tc_ibmm_06_plagiarism_check_reports_a_score(
        self, qar_report, record_property, page_evidence
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a submitted item set.\n"
            "Find the Plagiarism Check card and expect it to show a score or a "
            "pass/fail colour.\n"
            "Fail if the card is missing, which would mean the check stopped running "
            "or stopped reporting.",
        )
        report, item_ids = qar_report
        assert item_ids, "QAR results listed no items, so there is no report."

        evidence = self.read_check(report, self.PLAGIARISM_CHECK)
        record_property("plagiarism_card", (evidence["card"] or "")[:300])
        record_property("plagiarism_score", str(evidence["score"]))
        page_evidence.checkpoint(
            f"{self.PLAGIARISM_CHECK} card rendered: score={evidence['score']}, "
            f"colour={evidence['color']} — TC-IBMM-06 needs a visible score"
        )

        assert evidence["card"], (
            f"QAR Report rendered no {self.PLAGIARISM_CHECK!r} card. The check "
            "either did not run or stopped reporting."
        )
        assert evidence["score"] is not None or evidence["color"] is not None, (
            f"{self.PLAGIARISM_CHECK} rendered neither a score nor a pass/fail "
            f"colour. TC-IBMM-06 requires a visible score. Card: "
            f"{evidence['card'][:200]!r}"
        )

    def test_tc_ibmm_07_p01_bias_check_reports_a_score(
        self, qar_report, record_property, page_evidence
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a submitted item set.\n"
            "Find the Bias Check card and expect it to show a score or a pass/fail "
            "colour.\n"
            "Fail if the card is missing, which would mean the bias check no longer "
            "runs on submitted items.",
        )
        report, item_ids = qar_report
        assert item_ids, "QAR results listed no items, so there is no report."

        evidence = self.read_check(report, self.BIAS_CHECK)
        record_property("bias_card", (evidence["card"] or "")[:300])
        record_property("bias_score", str(evidence["score"]))
        page_evidence.checkpoint(
            f"{self.BIAS_CHECK} card rendered: score={evidence['score']}, "
            f"colour={evidence['color']} — proves the bias check still runs"
        )

        assert evidence["card"], (
            f"QAR Report rendered no {self.BIAS_CHECK!r} card. TC-IBMM-07-P01 "
            "requires the bias check to run on every submitted item."
        )
        assert evidence["score"] is not None or evidence["color"] is not None, (
            f"{self.BIAS_CHECK} rendered neither a score nor a pass/fail colour. "
            f"Card: {evidence['card'][:200]!r}"
        )

    @pytest.mark.xfail(
        reason=(
            "TC-IBMM-07-P01 requires a pass/fail per bias category (Gender, "
            "Cultural, Socio-economic, Statistical/DIF). This build reports one "
            "aggregate 'Bias Detection' score with no category breakdown."
        ),
        strict=False,
    )
    def test_tc_ibmm_07_p01_bias_report_names_every_category(
        self, qar_report, record_property, page_evidence
    ):
        """Kept as a live expectation rather than deleted.

        The requirement is real; the build does not meet it. strict=False means
        this becomes XPASS the day the categories appear, which is the signal to
        remove the marker — deleting the test would lose the requirement.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report and read the Bias Check detail.\n"
            "Expect it to name every bias category the requirement lists.\n"
            "This is a known gap, so the test is expected to fail; it turns into an "
            "unexpected pass the day the categories appear, which is the signal to "
            "retire the marker.",
        )
        report, _ = qar_report
        card = (self.read_check(report, self.BIAS_CHECK)["card"] or "").casefold()
        record_property("bias_card_for_categories", card[:300])
        page_evidence.checkpoint(
            f"Bias card read for a per-category breakdown: {card[:120] or 'empty'}"
        )

        absent = [
            label
            for label, spellings in self.BIAS_CATEGORIES.items()
            if not any(spelling in card for spelling in spellings)
        ]
        page_evidence.checkpoint(
            f"Categories TC-IBMM-07-P01 requires that the card does not name: "
            f"{absent or 'none — every category present'}"
        )
        assert not absent, (
            "Bias section did not name every category TC-IBMM-07-P01 requires. "
            f"Missing: {absent}. Bias card text: {card[:300]!r}"
        )

    # Every check the QAR Report panel renders, as the app labels them.
    ALL_QAR_CHECKS = (
        "Meta Data Alignment",
        "Hard Validation",
        "Image Moderation",
        "Bias Detection",
        "Grammar Check",
        "Clarity Check",
        "Duplicate Check",
        "Plagiarism Check",
    )

    def test_tc_ibmm_03_n01_duplicate_check_flags_copied_items(
        self, qar_report, page_evidence, record_property
    ):
        """Duplicate Check must not score 100% on items copied out of IB1."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a set whose items were copied out of an earlier "
            "item bank set.\n"
            "Expect the Duplicate Check to notice: it must not hand those items a "
            "clean 100%.",
        )
        report, _ = qar_report
        score = self.assert_check_is_not_clean(
            page_evidence, report, "Duplicate Check", record_property
        )
        record_property(
            "result_description",
            f"Duplicate Check scored {score}% on items copied verbatim from the "
            "item bank, so the duplicate content was detected.",
        )

    def test_tc_ibmm_06_n01_plagiarism_check_flags_copied_items(
        self, qar_report, page_evidence, record_property
    ):
        """Plagiarism Check must not score 100% on items copied out of IB1."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a set whose items were copied out of an earlier "
            "item bank set.\n"
            "Expect the Plagiarism Check to notice: it must not hand those items a "
            "clean 100%.",
        )
        report, _ = qar_report
        score = self.assert_check_is_not_clean(
            page_evidence, report, "Plagiarism Check", record_property
        )
        record_property(
            "result_description",
            f"Plagiarism Check scored {score}% on items copied verbatim from the "
            "item bank, so the copied content was detected.",
        )

    def test_every_qar_check_reports_a_verdict(
        self, qar_report, record_property, page_evidence
    ):
        """All eight checks render and report something for the set."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a submitted item set.\n"
            "Walk all eight QAR checks and expect each one to render and report some "
            "verdict, rather than sitting blank.",
        )
        report, _ = qar_report
        scores = {
            label: self.read_check(report, label) for label in self.ALL_QAR_CHECKS
        }
        record_property(
            "qar_check_scores",
            ", ".join(f"{k}={v['score']}" for k, v in scores.items()),
        )
        page_evidence.checkpoint(
            f"Read all {len(self.ALL_QAR_CHECKS)} QAR checks: "
            + ", ".join(f"{k}={v['score']}" for k, v in scores.items())
        )

        missing = [label for label, data in scores.items() if not data["card"]]
        page_evidence.checkpoint(
            f"Checks that rendered no card: {missing or 'none — all eight rendered'}"
        )
        assert not missing, (
            f"QAR Report did not render these checks: {missing}. "
            f"Rendered: {[l for l in scores if scores[l]['card']]}."
        )
        silent = [
            label
            for label, data in scores.items()
            if data["score"] is None and data["color"] is None
        ]
        page_evidence.checkpoint(
            f"Checks that rendered neither a score nor a pass/fail colour: "
            f"{silent or 'none — all eight reported a verdict'}"
        )
        assert not silent, (
            f"These checks rendered no score and no pass/fail colour: {silent}."
        )
