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

    Meta Data Alignment | Hard Validation | Image Moderation    | Bias Detection
    Grammar Check       | Clarity Check   | Duplicate Detection | Plagiarism Detection

There is no per-item breakdown of these checks in this build, so the "for every
item" half of TC-IBMM-07-P01 is not verifiable through the UI — see the xfail
on the category test below.

Covers:
  TC-IBMM-06-P01/N01  QAR Report shows a plagiarism score
  TC-IBMM-07-P01      Bias section present, with per-category detail (xfail)

Moved out of the daily run into tests/_unit on 2026-10-07, at the team's
request, after its tests errored in the daily runs (the shared rewording
upload stalls in QAR, KI-M1-QAR-005, and every test here depends on it). The
cbse-M1 module job still runs tests/_unit. Move it back into
tests/M1_Item_Bank_Mgmt once the upload is reliable.
"""
from datetime import date
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
    item_data_worksheet,
    resolve_columns,
    trim_helper_columns,
    write_row_fields,
)
from utilities.read_config import ReadConfig


class QARReportSnapshot:
    """The set-level check cards, read once while the QAR report was open.

    Answers the three QARReportPage calls read_check() makes, so a test that
    runs after the browser which read the report has closed can still assert
    on it. The cards belong to the set, not to a test, so one reading serves
    every test in the class.
    """

    def __init__(self, cards):
        self._cards = cards

    def get_check_card_text(self, check_name, item_id=""):
        return self._cards.get(check_name, {}).get("card")

    def get_check_score(self, check_name, item_id=""):
        return self._cards.get(check_name, {}).get("score")

    def get_check_card_status_color(self, check_name, item_id=""):
        return self._cards.get(check_name, {}).get("color")


class QARBankCopyReport:
    """What every bank-copy QAR test shares: the bank item, its rewordings,
    the one-upload-per-run fixture and the report snapshot.

    No Test prefix, so pytest does not collect it. The suite below and
    tests/_unit/M1_Item_Bank_Mgmt/test_qar_plagiarism_flags_bank_copy.py
    both build on it.
    """

    # Card labels exactly as the QAR Report panel renders them. Renamed by
    # 2026-10-01 from "Plagiarism Check" / "Duplicate Check": the old labels
    # matched no card, so every read came back score=None.
    PLAGIARISM_CHECK = "Plagiarism Detection"
    DUPLICATE_CHECK = "Duplicate Detection"
    BIAS_CHECK = "Bias Detection"

    # The collapsed panel that holds every check card on the results view.
    REPORT_PANEL = "QAR Report"

    # An exact copy of an item already in the IB1 repository, chosen by the
    # team for the plagiarism and duplicate checks (2026-10-01):
    #   Grade 1 Mathematics, CH-1: Finding the Furry Cat! (Pre-number Concepts),
    #   Very Short Answer Question  "Convert 2 hours into minutes."
    # The template's first row already carries that grade, subject and chapter,
    # so only the typology, question and answer are written.
    #
    # The bank item the team chose for the plagiarism and duplicate checks
    # (2026-10-01): Grade 1 Mathematics, CH-1: Finding the Furry Cat!
    # (Pre-number Concepts), Very Short Answer Question. The template's first
    # row already carries that grade, subject and chapter.
    BANK_QUESTION = "Convert 2 hours into minutes."
    BANK_ANSWER = "120 minutes"
    BANK_EXPLANATION = "1 hour = 60 minutes, so 2 hours = 120 minutes."

    # The bank question itself never reaches QAR. Upload validation refuses it
    # outright - "Duplicate question - an item with identical text already
    # exists in this grade/subject" - and changing only the Answer or the
    # Explanation does not get it through (probed as sme2 and sme4,
    # 2026-10-01). So the set carries the same question reworded: the
    # paraphrase case QAR's duplicate and plagiarism checks exist for.
    #
    # Each rewording works once. After a run it is in the bank as well, and
    # validation refuses it from then on, so the fixture starts at a
    # different rewording each day and steps past refused ones. When all of
    # them are used up the test says so: add new rewordings here.
    BANK_QUESTION_REWORDINGS = (
        "How many minutes are there in 2 hours?",
        "Change 2 hours into minutes.",
        "Express 2 hours in minutes.",
        "2 hours is equal to how many minutes?",
        "Write 2 hours as minutes.",
        "How many minutes make 2 hours?",
        "Find the number of minutes in 2 hours.",
        "What is 2 hours in minutes?",
        "Turn 2 hours into minutes.",
        "Convert two hours into minutes.",
        "Two hours equal how many minutes?",
        "Convert 2 hours to minutes.",
        "Change two hours into minutes.",
        "How many minutes are in two hours?",
        "Work out how many minutes are in 2 hours.",
        "Give the time 2 hours in minutes.",
    )
    # A refused rewording costs one upload, so stop after this many.
    MAX_REWORDING_ATTEMPTS = 5

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

    @classmethod
    def build_reworded_workbook(cls, tmp_path, question):
        """A one-row workbook carrying `question` with the bank item's answer.

        Mirrors the column handling the duplicate-detection suite proved out:
        the template carries helper columns past the canonical item columns,
        and leaving them in place makes upload validation reject the file.
        """
        target = tmp_path / f"qar_reworded_{uuid4().hex[:6]}.xlsx"
        copy2(Path(ReadConfig.get_upload_item_file_path()), target)
        workbook = load_workbook(target)
        # Not workbook.active: a freshly downloaded template opens on its
        # Instructions sheet.
        worksheet = item_data_worksheet(workbook) or workbook.active

        max_data_column = trim_helper_columns(worksheet)
        columns = resolve_columns(worksheet)
        assert columns, "Upload template has no recognisable item-data sheet."

        write_row_fields(
            worksheet,
            2,
            columns,
            {
                "sequence": 1,
                "typology": "Very Short Answer Question",
                "question": question,
                "answer": cls.BANK_ANSWER,
                "explanation": cls.BANK_EXPLANATION,
                "marks": "1",
            },
        )
        clear_rows_from(worksheet, 3, max_data_column)

        workbook.save(target)
        workbook.close()
        return target

    @classmethod
    def rewordings_for_today(cls):
        """The rewordings to try this run, starting at a different one each day."""
        pool = cls.BANK_QUESTION_REWORDINGS
        start = date.today().toordinal() % len(pool)
        ordered = pool[start:] + pool[:start]
        return ordered[: cls.MAX_REWORDING_ATTEMPTS]

    def assert_check_is_not_clean(self, page_evidence, report, label, record_property):
        """One check must not report a clean score on a rewording of a bank item.

        A clean score (0% for a Detection card, 100% for the others) means the
        check did not recognise content it has already stored — the exact
        regression this exists to catch. Split per check so
        a duplicate-detection failure and a plagiarism failure are separately
        attributable rather than sharing one red result.
        """
        page_evidence.checkpoint(
            f"QAR report opened for the reworded bank item; reading {label}"
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
        # A "... Detection" card scores what it found, so 0% is its clean mark
        # (the report shows Bias/Duplicate/Plagiarism Detection 0% with a pass
        # tick, 2026-10-01). The other cards score quality, where 100% is
        # clean. Asserting "< 100" on a Detection card would pass on 0% - the
        # very miss this exists to catch.
        clean_mark = 0 if "detection" in label.casefold() else 100
        assert result["score"] is not None, (
            f"{label} rendered no numeric score, so it cannot be compared "
            f"against the {clean_mark}% clean mark. Card: {result['card'][:200]!r}"
        )

        page_evidence.checkpoint(
            f"{label} scored {result['score']}% against a {clean_mark}% clean mark"
        )
        assert result["score"] != clean_mark, (
            f"{label} scored a clean {result['score']}% on a rewording of the item "
            f"bank question {self.BANK_QUESTION!r}, so the check did not recognise content already "
            f"stored in IB1. Card: {result['card'][:200]!r}"
        )
        return result["score"]

    def upload_first_unused_rewording(self, page, tmp_path, page_evidence):
        """Upload rewordings until validation accepts one; return (question, workbook).

        A rewording refused as a duplicate was used by an earlier run and is
        already in the bank, so the next one is tried. Any other refusal is a
        real validation problem and fails straight away.
        """
        refused = []
        for question in self.rewordings_for_today():
            workbook = self.build_reworded_workbook(tmp_path, question)
            page.open_item_creation_module()
            page.open_upload_item_file_tab()
            page.open_upload_step()
            page.upload_file(workbook)
            try:
                page.wait_for_upload_validation_success()
                return question, workbook
            except AssertionError as error:
                if "rejected by validation" not in str(error):
                    raise
                row = page.get_upload_history_row_by_file_name(workbook.name)
                reason = " ".join(page.click_view_errors_and_get_message(row).split())
                if "duplicate" not in reason.casefold():
                    raise AssertionError(
                        f"Upload validation refused {question!r} for a reason other "
                        f"than duplication: {reason[:300]}"
                    ) from error
                refused.append(question)
                page_evidence.checkpoint(
                    f"{question!r} is already in the bank (refused as a duplicate); "
                    "trying the next rewording"
                )
                # A refused upload leaves the wizard on its error view.
                self.driver.get(ReadConfig.get_base_url())
                page.close_popup_if_open()
                page.discard_active_upload_if_present()
        pytest.fail(
            "Every rewording tried this run was refused as already in the bank: "
            f"{refused}. Each rewording works once - add new ones to "
            "BANK_QUESTION_REWORDINGS."
        )

    def submit_reworded_bank_question(self, tmp_path, page_evidence):
        """Upload one rewording of the bank question, run QAR, and snapshot the report."""
        page = self.login_as_sme()
        question, workbook = self.upload_first_unused_rewording(
            page, tmp_path, page_evidence
        )
        page_evidence.checkpoint(
            f"Uploaded {question!r}, a rewording of the bank item "
            f"{self.BANK_QUESTION!r}; it passed upload validation, so QAR has a "
            "paraphrase of bank content to score"
        )
        page.click_continue()
        review_ids = page.get_review_item_ids()
        page.click_continue()
        # 420s, not the 180s default: QAR on this environment regularly runs
        # past three minutes even for small text-only sets. The workbook name
        # lets a wizard that drops back to Confirm & Submit mid-run (seen on QA
        # 2026-10-01, while the run completes server-side) be resolved from
        # the Sets grid instead of failing - and a rewording, once through
        # QAR, cannot be uploaded again.
        outcome = page.click_submit_for_qar_and_wait_for_results(
            analysis_timeout=420,
            item_ids=review_ids,
            uploaded_file_name=workbook.name,
        )
        if outcome == UploadItemFilePage.QAR_OUTCOME_ITEM_SET_DETAIL:
            item_set_id = getattr(page, "recovered_item_set_id", "")
            item_ids = sorted(page.get_qar_item_statuses(item_set_id)) if item_set_id else []
            read_from = "the item set's own page (the upload wizard lost the run)"
        else:
            page.wait_for_ocr_success_message()
            item_ids = page.get_qar_result_item_ids() or review_ids
            item_set_id = page.get_item_set_id_from_item_ids(item_ids)
            read_from = "the upload wizard's results view"
        page_evidence.checkpoint(
            f"QAR finished; {len(item_ids)} item(s) under set "
            f"{item_set_id or 'UNKNOWN'}, read from {read_from}"
        )
        assert item_ids, "QAR results listed no items, so there is no report."

        report = QARReportPage(self.driver)
        # The check cards are disclosed by expanding a result ROW, not by any
        # panel-level control and not by opening the item (which navigates away
        # from the results view entirely). Asking to expand by a check label
        # can never work either: that label is exactly what is still hidden.
        expanded = report.expand_result_row(item_ids[0])
        page_evidence.checkpoint(
            f"Result row {item_ids[0]} expanded: {expanded} — this is what "
            "discloses the per-check cards"
        )
        assert expanded, (
            "Could not expand a QAR result row, so the per-check cards were "
            f"never disclosed. Item ids seen: {item_ids[:3]}."
        )
        cards = {label: self.read_check(report, label) for label in self.ALL_QAR_CHECKS}
        assert any(card["card"] for card in cards.values()), (
            f"QAR completed for {item_set_id} ({question!r}), but no check card "
            f"could be read from {read_from}. Status: "
            f"{page.get_item_set_status_summary()}. Open the set to read its "
            "Duplicate and Plagiarism cards by hand."
        )
        return {
            "question": question,
            "item_set_id": item_set_id,
            "item_ids": item_ids,
            "report": QARReportSnapshot(cards),
        }

    # One upload serves every test built on this class. They all read the same
    # set-level cards, and each rewording of the bank question can be used
    # only once, so an upload per test would use them up several times as
    # fast (and cost a QAR run each). Kept on this base class rather than the
    # subclass, so the suite and its tests/_unit companion share it when they
    # run in one process. Every subclass is `serial`, so they run on one
    # worker. A failed upload is retried by the next test, at most twice in all.
    _shared_report = None
    _shared_failures = ()

    @pytest.fixture
    def qar_report(self, tmp_path, record_property, page_evidence):
        """The QAR report for one rewording of the bank question, uploaded once per run."""
        cls = QARBankCopyReport
        if cls._shared_report is None:
            if len(cls._shared_failures) >= 2:
                pytest.fail(
                    "The rewording upload already failed twice this run; not "
                    f"trying again. Last error: {cls._shared_failures[-1]}"
                )
            try:
                cls._shared_report = self.submit_reworded_bank_question(
                    tmp_path, page_evidence
                )
            except Exception as error:
                cls._shared_failures += (" ".join(str(error).split())[:300],)
                raise
        else:
            page_evidence.checkpoint(
                f"Reusing the QAR report of {cls._shared_report['item_set_id']} "
                f"({cls._shared_report['question']!r}), uploaded earlier in this run"
            )
        shared = cls._shared_report
        record_property("uploaded_question", shared["question"])
        record_property("item_set_id", shared["item_set_id"])
        record_property("qar_item_count", str(len(shared["item_ids"])))
        return shared["report"], shared["item_ids"]

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

    # Every check the QAR Report panel renders, as the app labels them.
    ALL_QAR_CHECKS = (
        "Meta Data Alignment",
        "Hard Validation",
        "Image Moderation",
        "Bias Detection",
        "Grammar Check",
        "Clarity Check",
        "Duplicate Detection",
        "Plagiarism Detection",
    )



@pytest.mark.rtm
@pytest.mark.e2e
# serial: every test here uploads under the same SME account. Without this the
# three scattered across xdist workers and contended for that one session,
# which surfaced as a fixture ERROR rather than an honest assertion failure.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestQARPlagiarismAndBiasSections(QARBankCopyReport):
    # TC-IBMM-06-N01 (Plagiarism Detection flags the bank copy) and
    # TC-IBMM-03-N01 (Duplicate Detection flags it) live beside this file in
    # test_qar_plagiarism_flags_bank_copy.py and
    # test_qar_duplicate_flags_bank_copy.py - see those files.

    def test_tc_ibmm_06_plagiarism_check_reports_a_score(
        self, qar_report, record_property, page_evidence
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a submitted item set.\n"
            "Find the Plagiarism Detection card and expect it to show a score or a "
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
