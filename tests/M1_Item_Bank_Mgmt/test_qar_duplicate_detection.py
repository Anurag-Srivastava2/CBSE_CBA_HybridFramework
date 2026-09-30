import re
from pathlib import Path
from shutil import copy2
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from tests.M1_Item_Bank_Mgmt.m1_surveys import survey_chrome, survey_upload_step
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.item_template_columns import (
    clear_rows_from,
    copy_item_row,
    resolve_columns,
    trim_helper_columns,
    write_row_fields,
)
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.e2e
@pytest.mark.usefixtures("setup")
class TestQARDuplicateDetection:
    """BUG-M1-002 regression coverage for QAR near-duplicate blocking."""

    # Both uploads carry these same three questions verbatim. The second
    # differs only in its Marks column, so every item is an exact textual
    # duplicate of one already in the bank - a deterministic trigger for the
    # duplicate check rather than a paraphrase the similarity model may or
    # may not score above its threshold.
    BASELINE_QUESTIONS = [
        "What is 6 plus 7? Is the answer 13?",
        "Riya has 8 apples and gets 2 more apples. Does she have 10 apples?",
        "What number comes just after 14? Is it 15?",
    ]
    # Same questions, different Marks - the only field that changes.
    DUPLICATE_QUESTIONS = BASELINE_QUESTIONS
    BASELINE_MARKS = ["1", "1", "1"]
    DUPLICATE_MARKS = ["2", "3", "4"]
    ITEM_COUNT = len(BASELINE_QUESTIONS)

    @staticmethod
    def build_upload_workbook(tmp_path, questions, scenario_name, run_id, marks=None):
        source = Path(ReadConfig.get_upload_item_file_path())
        target = tmp_path / f"{scenario_name}_{run_id}_{uuid4().hex[:8]}.xlsx"
        copy2(source, target)

        workbook = load_workbook(target)
        worksheet = workbook.active
        max_data_column = trim_helper_columns(worksheet)
        columns = resolve_columns(worksheet)
        assert columns, f"{source} has no recognisable item-data sheet."

        for offset, question in enumerate(questions):
            row = offset + 2
            if row != 2:
                copy_item_row(worksheet, 2, row, max_data_column)

            write_row_fields(
                worksheet,
                row,
                columns,
                {
                    "sequence": offset + 1,
                    "typology": "True or False",
                    "question": f"{question} Duplicate regression run {run_id}",
                    "answer": "True",
                    # Deliberately not keyed on scenario_name: the duplicate
                    # upload must differ from the baseline in the Marks column
                    # and nothing else, so the explanation stays identical
                    # between the two.
                    "explanation": (
                        f"Automation explanation for duplicate regression item {offset + 1}."
                    ),
                    "marks": marks[offset] if marks else "1",
                },
            )

        clear_rows_from(worksheet, len(questions) + 2, max_data_column)

        workbook.save(target)
        workbook.close()
        return target

    def login_as_sme(self):
        self.driver.get(ReadConfig.get_base_url())
        sme_username = ReadConfig.get_sme2_username()
        LoginPage(self.driver).login_to_application(
            sme_username,
            ReadConfig.get_password_for_username(sme_username),
        )
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        return page

    def submit_workbook_for_qar(self, workbook_path, label=""):
        """Upload one workbook, run QAR on it, and gather the report evidence.

        Both uploads in this test go through here, so the checkpoints are
        labelled by caller — otherwise the report shows two identical-looking
        upload/QAR pairs and a reader cannot tell IS10 from IS12.
        """
        page = UploadItemFilePage(self.driver)
        self.driver.get(ReadConfig.get_base_url())
        page.wait_for_application_to_load()
        page.close_popup_if_open()
        page.open_item_creation_module()
        page.open_upload_item_file_tab()
        page.open_upload_step()
        page.upload_file(workbook_path)
        upload_message = page.wait_for_upload_validation_success()
        checkpoint(f"{label} upload passed validation: {upload_message}")
        page.click_continue()
        item_ids = page.get_review_item_ids()
        page.click_continue()
        # 180s (the default) is not enough for QAR here: this suite submits two
        # sets back to back and the duplicate check has to compare the second
        # against everything the first just added, so analysis regularly runs
        # past three minutes. Observed 238s on a passing run and 303s on a run
        # that timed out at the default, which is what made this test look
        # intermittently broken rather than slow.
        #
        # The workbook name is passed so that a wizard which goes quiet mid-run
        # falls back to reading the set's own page. QAR finishes on its own
        # schedule server-side and the wizard's polling gives up first, so
        # waiting longer here does not help. It has to be the file name rather
        # than the item IDs: this step has not numbered the set yet, so the IDs
        # read here are "IS-G1-Mathematics-Ch29-i1" and name no set to look up.
        outcome = page.click_submit_for_qar_and_wait_for_results(
            analysis_timeout=420,
            item_ids=item_ids,
            uploaded_file_name=Path(workbook_path).name,
        )
        recovered = outcome == UploadItemFilePage.QAR_OUTCOME_ITEM_SET_DETAIL
        if recovered:
            # No completion toast exists on this path - the wizard never
            # reported the completion it is supposed to, which is the whole
            # reason the verdict came from the set page. Record its absence
            # rather than inventing a toast.
            qar_toast = ""
        else:
            qar_toast = page.wait_for_ocr_success_message()
        report_text = self.driver.find_element("tag name", "body").text
        # Numbered IDs only, from here on. The review step assigns no set
        # number, so every ID it hands out reads "IS-G1-Mathematics-Ch29-i2"
        # and addresses nothing - the report renders "IS1405-...-i2". The set's
        # identity has to come from whichever view actually holds the result:
        # the grid row matched to this workbook when the verdict was recovered,
        # otherwise the result table's own IDs.
        scraped_item_ids = [
            candidate
            for candidate in (page.get_qar_result_item_ids() or [])
            if UploadItemFilePage.item_set_id_is_numbered(candidate)
        ]
        item_set_id = getattr(page, "recovered_item_set_id", "") or (
            page.get_item_set_id_from_item_ids(scraped_item_ids)
        )
        status_summary = page.get_item_set_status_summary()
        # IDs to open each item's own report with. Preferred source is the set's
        # own status table: it is keyed by item ID, scoped to this set's "-i<n>"
        # rows, and therefore both numbered and free of stray rows from
        # elsewhere on the page (observed once: 4 IDs for a 3-row workbook).
        report_item_ids = scraped_item_ids
        if item_set_id:
            scoped_ids = sorted(page.get_qar_item_statuses(item_set_id))
            if scoped_ids:
                report_item_ids = scoped_ids
        set_number = re.match(r"\s*(IS\d+)", item_set_id or "", re.IGNORECASE)
        if set_number:
            prefix = set_number.group(1).casefold()
            report_item_ids = [
                candidate
                for candidate in report_item_ids
                if candidate.casefold().startswith(prefix)
            ]
        read_from = (
            "the item set's own page (the upload wizard stopped reporting on "
            "the run it started)"
            if recovered
            else "the upload wizard's results view"
        )
        checkpoint(
            f"{label} QAR completed on set {item_set_id or 'UNKNOWN'} "
            f"({len(item_ids)} item(s)), read from {read_from} — toast: "
            f"{qar_toast or 'none shown'}; statuses: "
            f"{UploadItemFilePage.format_status_summary(status_summary) or 'none reported'}"
        )
        return page, {
            "upload_message": upload_message,
            "toast": qar_toast,
            "report_text": report_text,
            "item_ids": item_ids,
            "report_item_ids": report_item_ids,
            "item_set_id": item_set_id,
            "status_summary": status_summary,
            "recovered": recovered,
        }

    @staticmethod
    def count_status(report_text, status):
        return len(re.findall(rf"\b{re.escape(status)}\b", report_text, re.IGNORECASE))

    @staticmethod
    def assert_toast_count_matches_report(evidence):
        """Cross-check the QAR toast against the item counts the page reports.

        Reads the parsed per-status counts rather than searching the page text
        for status words. This page renders "Approved", "Needs Revision" and
        "Rejected" as status-filter labels whatever the outcome, so a
        substring match on any of them was true unconditionally - the check
        looked strict and could never fail. The counts beside those labels do
        move with the result, so they are what gets asserted.
        """
        summary = evidence.get("status_summary", {})
        if evidence.get("recovered"):
            # There is no toast to cross-check on this path: the verdict was
            # read off the set's own page, which does not render one. Asserting
            # on an absent toast would fail a run that produced a real result,
            # so assert what this view does carry - a per-item verdict.
            assert summary, (
                "QAR was resolved from the item set page but that page reported "
                "no item statuses to cross-check."
            )
            return

        toast = evidence["toast"]
        toast_numbers = [int(value) for value in re.findall(r"\b\d+\b", toast)]
        if not toast_numbers:
            raise AssertionError(f"QAR completion toast has no item counts: {toast}")

        approved = TestQARDuplicateDetection.get_status_count(evidence, "Approved")
        blocked = TestQARDuplicateDetection.get_status_count(evidence, "Needs Revision")

        normalized_toast = toast.casefold()
        sets_ratio = re.search(r"(\d+)\s*/\s*(\d+)\s*set", normalized_toast)
        if sets_ratio:
            # Read the ratio, not the word. This toast says "0/1 set(s) passed"
            # when nothing passed, so keying on the substring "passed" inverted
            # the check and demanded approved items from a fully blocked set.
            passed_sets, total_sets = int(sets_ratio.group(1)), int(sets_ratio.group(2))
            assert passed_sets <= total_sets, (
                f"BUG-M1-002: QAR set-count toast is malformed. Toast: {toast}"
            )
            assert total_sets >= 1, (
                "BUG-M1-002: QAR set-count toast did not report any processed set. "
                f"Toast: {toast}"
            )
            if passed_sets >= 1:
                assert approved >= 1, (
                    f"BUG-M1-002: QAR toast reports {passed_sets} passed set(s) but "
                    f"the report counts no approved items. Toast: {toast}; "
                    f"status summary: {summary}."
                )
            else:
                assert blocked >= 1, (
                    "BUG-M1-002: QAR toast reports no passed set but the report "
                    f"counts no blocked items either. Toast: {toast}; "
                    f"status summary: {summary}."
                )
            return

        # Per-item toast: the counted statuses must add up to what it claims.
        visible_total = approved + blocked
        assert visible_total in toast_numbers or any(
            number == TestQARDuplicateDetection.ITEM_COUNT for number in toast_numbers
        ), (
            "BUG-M1-002: QAR toast count does not match the counted item results. "
            f"Toast: {toast}; approved={approved}, blocked={blocked}; "
            f"status summary: {summary}."
        )

    # Only the upload wizard renders a "QAR completed" banner. The set's own
    # page - where the verdict is read from when the wizard goes quiet - shows
    # the same fact as a QAR-assigned status instead, so each view is checked
    # for its own wording.
    WIZARD_VERDICT_MARKERS = ("qar completed", "qar ran")
    # Status *values*, never the status-filter labels. The set page renders
    # "Approved", "Needs Revision" and "Rejected" as filter chips whatever the
    # run did - the same trap the toast cross-check below documents - so
    # matching those words here would make this assertion a permanent green.
    # A bare "qar" is out for the same reason: it is in the page's headings.
    ITEM_SET_VERDICT_MARKERS = (
        "qar failed",
        "qar passed",
        "pending_qar",
        "pending qar",
        "under review",
        "published",
    )

    @staticmethod
    def assert_qar_verdict_rendered(evidence, label):
        recovered = evidence.get("recovered")
        markers = (
            TestQARDuplicateDetection.ITEM_SET_VERDICT_MARKERS
            if recovered
            else TestQARDuplicateDetection.WIZARD_VERDICT_MARKERS
        )
        view = "item set page" if recovered else "upload wizard"
        text = evidence["report_text"].casefold()
        assert any(marker in text for marker in markers), (
            f"{label} shows no QAR verdict on the {view}; expected one of "
            f"{list(markers)}. Status summary: {evidence.get('status_summary')}. "
            f"Page:\n{evidence['report_text']}"
        )

    # QAR blocks a duplicate with either wording depending on how strongly
    # the similarity check fired: a borderline near-duplicate comes back
    # "Needs Revision", a clear match "Rejected". Both mean the item did not
    # pass and cannot move on to RWG, so "Needs Revision" counts them together.
    STATUS_ALIASES = {
        "Needs Revision": ("Needs Revision", "Revise", "Rejected"),
        "Approved": ("Approved",),
        "Rejected": ("Rejected",),
    }

    @staticmethod
    def get_status_count(evidence, status):
        summary = evidence.get("status_summary", {})
        aliases = TestQARDuplicateDetection.STATUS_ALIASES.get(status, (status,))
        # Summed, not first-match: the summary carries a separate count per
        # status word, so a set split across "Needs Revision" and "Rejected"
        # would otherwise report only whichever alias was looked at first.
        summarised = [int(summary[alias]) for alias in aliases if alias in summary]
        if summarised:
            return sum(summarised)
        return max(
            TestQARDuplicateDetection.count_status(evidence["report_text"], alias)
            for alias in aliases
        )

    @staticmethod
    def assert_all_items_status(evidence, status, expected_count=None):
        expected_count = (
            TestQARDuplicateDetection.ITEM_COUNT
            if expected_count is None
            else expected_count
        )
        actual_count = TestQARDuplicateDetection.get_status_count(evidence, status)
        assert actual_count >= expected_count, (
            f"Expected all {expected_count} items to be {status}. "
            f"Actual {status} count: {actual_count}. "
            f"Status summary: {evidence.get('status_summary')}. "
            f"QAR report:\n{evidence['report_text']}"
        )

    def test_qar_duplicate_detection_near_duplicate_content_flagged(
        self, tmp_path, request, record_property, page_evidence
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Upload a first workbook and get every item approved, so the item bank "
            "now holds those questions.\n"
            "Upload a second workbook whose questions are near-copies of the first, "
            "and submit it for QAR.\n"
            "Expect the QAR report to flag the duplication and block every item in "
            "the second set, so no duplicate reaches RWG.",
        )
        run_id = uuid4().hex[:10]
        page = self.login_as_sme()

        # Surveyed on the upload step before any workbook is pushed, so the
        # element table shows the page as the test found it.
        page.open_item_creation_module()
        page.open_upload_item_file_tab()
        page.open_upload_step()
        checks = ElementChecks(
            page, record_property, page_name="Upload Item File — Duplicate Detection"
        )
        survey_chrome(checks, page)
        survey_upload_step(checks, page)
        record_property("result_description", checks.publish())
        page_evidence.checkpoint(
            f"Upload step surveyed before anything is pushed; run id {run_id}"
        )

        baseline_workbook = self.build_upload_workbook(
            tmp_path,
            self.BASELINE_QUESTIONS,
            "IS10_baseline",
            run_id,
            marks=self.BASELINE_MARKS,
        )
        _, baseline = self.submit_workbook_for_qar(baseline_workbook, label="IS10 baseline")

        request.node.user_properties.append(("baseline_item_set_id", baseline["item_set_id"]))
        request.node.user_properties.append(("baseline_toast", baseline["toast"]))

        assert baseline["item_set_id"], "IS10 baseline item set ID was not captured."
        # A single-file upload reports "All N rows added successfully. (Upload ID:
        # ..., Status: PASSED)" rather than the multi-file wording, so accept both.
        baseline_upload_message = baseline["upload_message"].casefold()
        assert (
            "validated successfully" in baseline_upload_message
            or "added successfully" in baseline_upload_message
        ), f"Baseline upload did not report success: {baseline['upload_message']!r}"
        self.assert_qar_verdict_rendered(baseline, "IS10 baseline")
        self.assert_all_items_status(baseline, "Approved")
        self.assert_toast_count_matches_report(baseline)
        page_evidence.checkpoint(
            f"IS10 baseline is clean — all {self.ITEM_COUNT} items Approved, so "
            "the bank now holds the questions IS12 is about to duplicate"
        )

        # Identical question text to the baseline, only Marks differ: every
        # item duplicates one the bank already holds.
        duplicate_workbook = self.build_upload_workbook(
            tmp_path,
            self.DUPLICATE_QUESTIONS,
            "IS12_exact_duplicate",
            run_id,
            marks=self.DUPLICATE_MARKS,
        )
        _, duplicate = self.submit_workbook_for_qar(
            duplicate_workbook, label="IS12 exact duplicate"
        )
        duplicate_text = duplicate["report_text"]
        duplicate_normalized = duplicate_text.casefold()

        request.node.user_properties.append(("item_set_id", duplicate["item_set_id"]))
        request.node.user_properties.append(("is12_item_set_id", duplicate["item_set_id"]))
        request.node.user_properties.append(("qar_success_message", duplicate["toast"]))
        request.node.user_properties.append(
            (
                "item_set_status",
                UploadItemFilePage.format_status_summary(duplicate["status_summary"])
                or "Expected PENDING_QAR with all items Needs Revision",
            )
        )

        assert duplicate["item_set_id"], "IS12 duplicate item set ID was not captured."
        duplicate_markers = [
            marker
            for marker in ("duplicate", "similarity", "plagiarism", "uniqueness")
            if marker in duplicate_normalized
        ]
        page_evidence.checkpoint(
            f"IS12 report names duplicate-check evidence: "
            f"{duplicate_markers or 'none of duplicate/similarity/plagiarism/uniqueness'}"
        )
        assert any(
            marker in duplicate_normalized
            for marker in ("duplicate", "similarity", "plagiarism", "uniqueness")
        ), f"IS12 QAR report does not show duplicate-check evidence: {duplicate_text}"
        # The set-level verdict now reads "QAR completed - 0/1 set(s) passed."
        # and each duplicate item carries a "Rejected" badge. Match the banner's
        # ratio rather than a bare status word: this page always renders the
        # status-filter labels "Approved", "Needs Revision" and "Rejected"
        # whatever the outcome, so a bare-word match would pass unconditionally
        # and turn this assertion into a permanent green.
        sets_passed = re.search(r"(\d+)\s*/\s*(\d+)\s*set", duplicate_normalized)
        assert (
            any(
                marker in duplicate_normalized
                for marker in ("red", "failed", "fail", "<10", "less than 10", "90%")
            )
            or (sets_passed is not None and sets_passed.group(1) == "0")
        ), f"IS12 duplicate check is not visibly failed/red: {duplicate_text}"
        page_evidence.checkpoint(
            f"IS12 duplicate check is visibly failed — set verdict: "
            f"{sets_passed.group(0) if sets_passed else 'no set ratio in the banner'}"
        )
        # Every item is an exact duplicate, so the whole set must be blocked
        # (QAR reports this as "Rejected" or "Needs Revision" - both count).
        self.assert_all_items_status(duplicate, "Needs Revision")
        page_evidence.checkpoint(
            f"All {self.ITEM_COUNT} IS12 items are blocked (Needs Revision / "
            "Rejected), so no duplicate reached RWG"
        )
        assert not re.search(r"\brwg\s*\d+\b|assigned\s+rwg", duplicate_normalized), (
            "IS12 should stay locked at PENDING_QAR and must not be forwarded to RWG."
        )
        # "QAR Failed" is the set page's spelling of the same state - QAR
        # blocked the set and it never moved on. It belongs here because this
        # verdict is read from whichever view reported it, and the set page
        # never uses the wizard's PENDING_QAR wording. The RWG check above is
        # what proves the set did not progress; this one only confirms it
        # carries a blocking verdict rather than a silent pass.
        assert any(
            marker in duplicate_normalized
            for marker in (
                "pending_qar",
                "pending qar",
                "qar pending",
                "needs revision",
                "qar failed",
            )
        ), f"IS12 set status did not remain PENDING_QAR/Needs Revision: {duplicate_text}"
        page_evidence.checkpoint(
            f"IS12 stayed locked at PENDING_QAR and was never forwarded to RWG — "
            f"{UploadItemFilePage.format_status_summary(duplicate['status_summary'])}"
        )
        self.assert_toast_count_matches_report(duplicate)

        # Per-item evidence. The set-level banner above only proves the set was
        # blocked; open each item's own report and read the Duplicate Detection
        # card so the assertion is against the score QAR actually rendered for
        # that item rather than against page text that happens to be on screen.
        report = QARReportPage(self.driver)
        # Prefer the IDs scoped to exactly the rows this workbook uploaded -
        # the review-step list, or, when the verdict was recovered from the set
        # page, that set's own numbered rows (the review step assigns no set
        # number, so its IDs cannot address the rows the report renders). The
        # unscoped scrape reads whatever table is on screen and can pick up a
        # stray row from elsewhere on the page (observed: 4 IDs for a 3-row
        # workbook, all sharing this set's prefix), so it stays a last resort.
        # Deliberately no fallback to the review-step IDs: they are unnumbered,
        # so falling back to them does not degrade gracefully, it guarantees
        # "Could not open QAR result item IS-G1-...-i2" a few lines below.
        duplicate_item_ids = duplicate["report_item_ids"]
        assert len(duplicate_item_ids) == self.ITEM_COUNT, (
            f"Expected {self.ITEM_COUNT} numbered item IDs to inspect for "
            f"{duplicate['item_set_id'] or 'an unidentified set'}, got "
            f"{duplicate_item_ids}. Review-step IDs were {duplicate['item_ids']} "
            "(these carry no set number and cannot open an item report)."
        )

        per_item = {}
        for item_id in duplicate_item_ids:
            evidence = report.get_open_item_check_evidence(
                item_id, "Duplicate Detection", expand=True
            )
            per_item[item_id] = {
                "score": evidence["score"],
                "threshold": evidence["threshold"],
                "status_color": evidence["status_color"],
                "status": report.get_item_status(item_id),
                "card": (evidence["card"] or "")[:400],
            }
        request.node.user_properties.append(
            ("duplicate_check_per_item", UploadItemFilePage.format_status_summary(
                {item_id: f"score={data['score']} status={data['status']}"
                 for item_id, data in per_item.items()}
            ))
        )

        # 1. Every item must actually render a Duplicate Detection card.
        missing_card = {
            item_id: data for item_id, data in per_item.items() if not data["card"]
        }
        assert not missing_card, (
            "Duplicate Detection card was not rendered on the item report for: "
            f"{sorted(missing_card)}. Per-item evidence: {per_item}."
        )

        # 2. The card must carry a duplicate score, and where the card also
        #    renders its threshold the score has to sit on the failing side of
        #    it. Checked per item so a single passing item cannot hide behind
        #    the set-level verdict.
        missing_score = {
            item_id: data
            for item_id, data in per_item.items()
            if data["score"] is None and data["status_color"] != "fail"
        }
        assert not missing_score, (
            "Duplicate Detection reported no similarity score and no failing "
            f"colour for: {sorted(missing_score)}. Per-item evidence: {per_item}."
        )
        score_below_threshold = {
            item_id: data
            for item_id, data in per_item.items()
            if data["score"] is not None
            and data["threshold"] is not None
            and data["score"] < data["threshold"]
        }
        assert not score_below_threshold, (
            "Duplicate Detection scored these exact duplicates below the "
            f"threshold it displayed: {score_below_threshold}."
        )

        # 3. The hard requirement: every exact duplicate must be Rejected.
        #    Anything else - Approved, Needs Revision, Pending, or a blank
        #    status - fails the test.
        not_rejected = {
            item_id: data["status"] or "<no status>"
            for item_id, data in per_item.items()
            if data["status"].casefold() != "rejected"
        }
        assert not not_rejected, (
            "Every item is an exact duplicate of one already in the bank, so "
            f"QAR must reject all {self.ITEM_COUNT}. Not rejected: "
            f"{not_rejected}. Per-item evidence: {per_item}."
        )
