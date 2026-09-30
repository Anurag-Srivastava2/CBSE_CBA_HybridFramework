from pathlib import Path

import pytest
from openpyxl import Workbook
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pages.sme.bulk_upload_page import BulkUploadPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.item_template_columns import write_canonical_headers
from utilities.qar_recovery import (
    build_workbook_qar_correction_factory,
    recover_qar_need_improvement_items,
)


class BodyElement:
    def __init__(self, text):
        self.text = text


class QarRedirectDriver:
    def __init__(self):
        self.body = BodyElement(
            "My Item Set\nItem Set Status\nItem Set Review Stage\nUnder Review"
        )

    def find_element(self, by, value):
        assert (by, value) == (By.TAG_NAME, "body")
        return self.body

    def find_elements(self, *_locator):
        return []


class MissingSubmitWait:
    def until_present(self, _locator, timeout):
        assert timeout == 30
        raise TimeoutException()


class Cell:
    def __init__(self, text):
        self.text = text


class OriginalSubmitButton:
    text = "Submit Set for QAR"

    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class ReturnedConditionWait:
    def __init__(self, result):
        self.result = result

    def until_condition(self, _condition, timeout):
        assert timeout == 5
        return self.result


class AlwaysTimeoutWait:
    def until_condition(self, _condition, timeout):
        assert timeout == 90
        raise TimeoutException()


def build_redirected_page():
    page = UploadItemFilePage.__new__(UploadItemFilePage)
    page.driver = QarRedirectDriver()
    return page


def test_upload_file_uses_only_the_native_file_input_event(tmp_path, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Upload a workbook and watch how the file reaches the input.\n"
        "Check it is sent once through the native file input, with no duplicate "
        "trigger.",
    )
    workbook_path = tmp_path / "single-trigger.xlsx"
    workbook_path.write_bytes(b"test workbook placeholder")

    class FileInput:
        def __init__(self):
            self.sent_paths = []

        def send_keys(self, value):
            self.sent_paths.append(value)

    class PresentWait:
        def __init__(self, file_input):
            self.file_input = file_input

        def until_present(self, _locator, timeout):
            assert timeout == 20
            return self.file_input

        def until_condition(self, _condition, timeout):
            # upload_file() then waits briefly for a "Switch uploaded file?"
            # dialog; a clean account never raises one, which is a timeout.
            raise TimeoutException()

    class UploadDriver:
        def __init__(self):
            self.scripts = []

        def execute_script(self, script, *arguments):
            self.scripts.append((script, arguments))

    file_input = FileInput()
    page = UploadItemFilePage.__new__(UploadItemFilePage)
    page.driver = UploadDriver()
    page.wait_utils = PresentWait(file_input)

    assert page.upload_file(workbook_path) == workbook_path.resolve()
    assert file_input.sent_paths == [str(workbook_path.resolve())]
    assert len(page.driver.scripts) == 1
    assert "dispatchEvent" not in page.driver.scripts[0][0]


def test_image_upload_stages_excel_then_zip_as_one_workflow(tmp_path, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Upload a workbook together with an images ZIP.\n"
        "Check the two are staged as a single workflow rather than as two "
        "unrelated uploads.",
    )
    workbook_path = tmp_path / "image-items.xlsx"
    images_zip_path = tmp_path / "test-images.zip"
    workbook_path.write_bytes(b"test workbook placeholder")
    images_zip_path.write_bytes(b"test images placeholder")

    events = []

    class UploadPairDriver:
        @staticmethod
        def find_elements(*_locator):
            return []

    class UploadPairWait:
        @staticmethod
        def until_visible(locator, timeout):
            if locator == BulkUploadPage.UPLOAD_IMAGES_ZIP_PANEL:
                assert timeout == 30
                events.append("zip-panel-ready")
                return object()
            if locator == BulkUploadPage.IMAGE_ZIP_UPLOAD_SUCCESS:
                assert timeout == 5
                raise TimeoutException()
            assert locator == BulkUploadPage.CONTINUE_BUTTON
            assert timeout == 20
            events.append("continue-ready")

            class ContinueButton:
                @staticmethod
                def is_enabled():
                    return True

            return ContinueButton()

        @staticmethod
        def until_condition(condition, timeout):
            assert timeout == 90
            outcome = condition(UploadPairDriver())
            assert outcome == {"accepted": True, "message": ""}
            events.append("zip-attached")
            return outcome

    page = BulkUploadPage.__new__(BulkUploadPage)
    page.driver = UploadPairDriver()
    page.wait_utils = UploadPairWait()
    page.open_item_creation_module = lambda: events.append("open-item-creation")
    page.open_upload_item_file_tab = lambda: events.append("open-upload-tab")
    page.open_upload_step = lambda: events.append("open-upload-step")
    page.discard_active_upload_if_present = lambda: events.append("discard-active")
    page.discard_staged_upload_files = lambda: events.append("discard-staged")
    page.pause_before_action = lambda: events.append("pause-for-zip-input")
    page.upload_file = lambda path: events.append(("upload", Path(path)))
    result = page.upload_excel_and_images_zip_for_validation(
        workbook_path, images_zip_path
    )

    assert result == {
        "accepted": True,
        "message": "Images ZIP accepted: the ZIP panel closed and Continue is enabled.",
    }
    assert events == [
        "open-item-creation",
        "open-upload-tab",
        "open-upload-step",
        "discard-active",
        "discard-staged",
        ("upload", workbook_path.resolve()),
        "zip-panel-ready",
        "pause-for-zip-input",
        ("upload", images_zip_path.resolve()),
        "zip-attached",
        "continue-ready",
    ]


def test_image_upload_validates_zip_before_staging_excel(tmp_path, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Upload a workbook and an images ZIP together.\n"
        "Check the ZIP is validated before the Excel is staged, so a bad archive "
        "is caught first.",
    )
    workbook_path = tmp_path / "image-items.xlsx"
    workbook_path.write_bytes(b"test workbook placeholder")
    page = BulkUploadPage.__new__(BulkUploadPage)
    page.open_item_creation_module = lambda: pytest.fail(
        "Browser navigation started before the complete upload pair was validated."
    )

    with pytest.raises(FileNotFoundError, match="images ZIP not found"):
        page.upload_excel_and_images_zip_for_validation(
            workbook_path, tmp_path / "missing-test-images.zip"
        )


def test_submit_button_race_accepts_redirect_to_item_sets_as_success(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Submit for QAR when the app redirects to the item sets listing before "
        "the button settles.\n"
        "Check the redirect is read as success rather than as a failed submit.",
    )
    page = build_redirected_page()
    page.wait_utils = MissingSubmitWait()

    assert page.click_submit_for_qar()
    assert page.has_qar_results_or_progress(page.driver)
    assert page.is_qar_analysis_complete(page.driver)
    assert "under review" in page.wait_for_ocr_success_message().casefold()


def test_qar_result_ids_ignore_item_set_rows_after_redirect(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Read QAR result IDs from a page that also lists item-set rows.\n"
        "Check only the item IDs are picked up and the set-level row is ignored.",
    )
    page = build_redirected_page()
    page.driver.find_elements = lambda *_locator: [
        Cell("IS431"),
        Cell("IS431-G1-Mathematics-Ch38-i1"),
        Cell("IS431-G1-Mathematics-Ch38-i2"),
    ]

    assert page.get_qar_result_item_ids() == [
        "IS431-G1-Mathematics-Ch38-i1",
        "IS431-G1-Mathematics-Ch38-i2",
    ]


def test_confirmation_guard_never_clicks_original_qar_submit_again(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Handle a confirmation prompt raised after submitting for QAR.\n"
        "Check the guard never clicks the original Submit button a second time.",
    )
    button = OriginalSubmitButton()
    page = build_redirected_page()
    page.wait_utils = ReturnedConditionWait(button)

    assert not page.confirm_submit_if_prompted()
    assert not button.clicked


def test_accepted_submit_is_not_retried_when_result_transition_times_out(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Submit for QAR successfully, then have the transition to results time "
        "out.\n"
        "Check the submit is not retried, because it had already been accepted.",
    )
    page = build_redirected_page()
    page.wait_utils = AlwaysTimeoutWait()
    page.submit_calls = 0

    def accepted_submit():
        page.submit_calls += 1
        return True

    page.click_submit_for_qar = accepted_submit
    page.has_qar_results_or_progress = lambda _driver: False
    page.get_visible_qar_submit_blocker = lambda: ""

    # No item IDs were passed, so the outcome cannot be confirmed from the set
    # record and the failure has to say exactly that - not "QAR failed".
    with pytest.raises(AssertionError, match="could not be confirmed"):
        page.click_submit_for_qar_and_wait_for_results()

    assert page.submit_calls == 1


def test_stalled_wizard_reads_the_verdict_off_the_item_set_instead(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Submit for QAR, then have the upload wizard stop reporting on the run.\n"
        "Check the verdict is read off the item set's own page instead of the "
        "run being called a failure.\n"
        "Check the submit is never sent a second time.",
    )
    page = build_redirected_page()
    page.wait_utils = AlwaysTimeoutWait()
    page.submit_calls = 0

    def accepted_submit():
        page.submit_calls += 1
        return True

    page.click_submit_for_qar = accepted_submit
    page.has_qar_results_or_progress = lambda _driver: False
    page.get_visible_qar_submit_blocker = lambda: ""
    resolved = []

    def resolve(item_set_id, item_ids, timeout, uploaded_file_name=""):
        resolved.append((item_set_id, tuple(item_ids), timeout, uploaded_file_name))
        return True

    page.resolve_qar_outcome_from_item_set = resolve

    outcome = page.click_submit_for_qar_and_wait_for_results(
        item_ids=[
            "IS431-G1-Mathematics-Ch38-i1",
            "IS431-G1-Mathematics-Ch38-i2",
        ],
        uploaded_file_name="baseline_run.xlsx",
    )

    assert outcome == UploadItemFilePage.QAR_OUTCOME_ITEM_SET_DETAIL
    assert page.submit_calls == 1
    # The set ID is derived from the review-step item IDs, not re-scraped from
    # a page the wizard has already left.
    assert resolved == [
        (
            "IS431-G1-Mathematics-Ch38",
            (
                "IS431-G1-Mathematics-Ch38-i1",
                "IS431-G1-Mathematics-Ch38-i2",
            ),
            420,
            "baseline_run.xlsx",
        )
    ]


def test_item_set_without_a_qar_verdict_still_fails_the_run(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Submit for QAR, have the wizard stop reporting, and have the item set "
        "carry no verdict either.\n"
        "Check this still fails, because now nothing anywhere shows a result.",
    )
    page = build_redirected_page()
    page.wait_utils = AlwaysTimeoutWait()
    page.click_submit_for_qar = lambda: True
    page.has_qar_results_or_progress = lambda _driver: False
    page.get_visible_qar_submit_blocker = lambda: ""
    page.resolve_qar_outcome_from_item_set = lambda *_args, **_kwargs: False

    with pytest.raises(AssertionError, match="genuinely did not produce a result"):
        page.click_submit_for_qar_and_wait_for_results(
            item_ids=["IS431-G1-Mathematics-Ch38-i1"]
        )


class ConditionWait:
    """Runs each polled condition once and times out when it is not yet true."""

    def __init__(self, driver):
        self.driver = driver

    def until_condition(self, condition, timeout):
        assert timeout > 0
        if not condition(self.driver):
            raise TimeoutException()
        return True


def build_resolver_page(monkeypatch, statuses_by_attempt):
    """A page whose item set page only shows its verdict on a later attempt."""
    page = UploadItemFilePage.__new__(UploadItemFilePage)
    page.driver = QarRedirectDriver()
    page.wait_utils = ConditionWait(page.driver)
    page.navigations = 0
    page.verified = []
    remaining = list(statuses_by_attempt)

    def open_sets_module():
        page.navigations += 1

    page.open_sets_module = open_sets_module
    page.open_item_set_from_sets_list = lambda _item_set_id: None
    page.is_item_set_detail_loading = staticmethod(lambda _driver: False)
    page.get_qar_item_statuses = lambda _item_set_id: (
        remaining.pop(0) if remaining else {}
    )
    page.verify_items_in_opened_item_set = page.verified.append
    monkeypatch.setattr(
        "pages.sme.upload_item_file_page.QARReportPage",
        lambda _driver: type("Report", (), {"open_report_if_available": lambda self: False})(),
    )
    monkeypatch.setattr("pages.sme.upload_item_file_page.sleep", lambda _seconds: None)
    return page


def test_verdict_that_appears_late_is_picked_up_by_re_reading_the_set(
    monkeypatch, record_property
):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Look up a set whose QAR verdict is not on its page yet, then appears.\n"
        "Check the set is re-fetched rather than the first view being trusted, so "
        "the verdict is found once it lands.",
    )
    page = build_resolver_page(
        monkeypatch,
        # First read: nothing yet. Second: the verdict has landed.
        [{}, {"IS431-G1-Mathematics-Ch38-i1": "Rejected"}],
    )

    assert page.resolve_qar_outcome_from_item_set(
        "IS431-G1-Mathematics-Ch38",
        ["IS431-G1-Mathematics-Ch38-i1"],
        timeout=120,
    )
    # Two navigations, not one poll of a page already on screen.
    assert page.navigations == 2
    assert page.verified == [["IS431-G1-Mathematics-Ch38-i1"]]


def test_set_that_never_shows_a_verdict_is_reported_as_unresolved(
    monkeypatch, record_property
):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Look up a set that never shows a QAR verdict at all.\n"
        "Check the lookup reports failure instead of inventing a result, and "
        "stops once its time is up.",
    )
    page = build_resolver_page(monkeypatch, [])

    assert not page.resolve_qar_outcome_from_item_set(
        "IS431-G1-Mathematics-Ch38",
        ["IS431-G1-Mathematics-Ch38-i1"],
        timeout=0.1,
    )
    assert page.verified == []


def test_resolver_does_nothing_without_an_item_set_id(monkeypatch, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Ask for a verdict without saying which set.\n"
        "Check nothing is navigated, so a caller that passed no IDs cannot land "
        "on some other set's result.",
    )
    page = build_resolver_page(monkeypatch, [{"IS431-G1-Mathematics-Ch38-i1": "Rejected"}])

    assert not page.resolve_qar_outcome_from_item_set("", [])
    assert page.navigations == 0


def test_pending_qar_is_not_mistaken_for_analysis_still_running(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Look at the wording that means QAR is still analysing a set.\n"
        "Check PENDING_QAR is not in that list, because it is the resting state "
        "of a set QAR has already blocked.",
    )
    in_flight = UploadItemFilePage.QAR_ANALYSIS_IN_FLIGHT_MARKERS

    assert "analysis in progress" in in_flight
    assert not any("pending" in marker for marker in in_flight)


def test_initial_qar_needs_revision_items_are_corrected_and_rerun(tmp_path, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Take a set whose first QAR run returned items needing revision.\n"
        "Check those items are corrected in the workbook and the set is submitted "
        "again.",
    )
    workbook_path = tmp_path / "teacher-items.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    columns = write_canonical_headers(worksheet)
    original_questions = (
        "Is the reading duration one hour?",
        "How much time passes between 8:00 and 9:00?",
        "The journey lasts ___ hour.",
        "What time is shown on the clock?",
    )
    for row, question in enumerate(original_questions, start=2):
        worksheet.cell(row=row, column=columns["question"]).value = question
    workbook.save(workbook_path)
    workbook.close()

    class RetryPage:
        QAR_RETRY_STATUS_LABELS = (
            "Need Improvement",
            "Needs Improvement",
            "Needs Revision",
            "Revise",
        )

        def __init__(self):
            self.statuses = [
                {
                    "IS500-G1-Mathematics-Ch38-i1": "Need Improvement",
                    "IS500-G1-Mathematics-Ch38-i2": "Needs Revision",
                },
                {
                    "IS500-G1-Mathematics-Ch38-i1": "Approved",
                    "IS500-G1-Mathematics-Ch38-i2": "Approved",
                },
            ]
            self.corrections = []
            self.reruns = 0
            self.verifications = 0

        def get_qar_item_statuses(self, _item_set_id=None):
            return self.statuses.pop(0)

        def revise_qar_need_improvement_items(
            self,
            _item_set_id,
            item_ids,
            correction_factory,
            retry_number,
        ):
            self.corrections = [
                correction_factory(
                    item_id,
                    retry_number,
                    {
                        "status": "Need Improvement",
                        "failure_reasons": {"Clarity": "flagged"},
                    },
                )
                for item_id in item_ids
            ]
            return item_ids

        @staticmethod
        def compact_item_id(item_id):
            return item_id.replace("-", "")

        def rerun_qar_if_enabled(self):
            self.reruns += 1
            return "QAR rerun completed"

        def verify_item_set_from_sets_module(self, _item_set_id, _item_ids):
            self.verifications += 1

    page = RetryPage()
    result = recover_qar_need_improvement_items(
        page=page,
        item_set_id="IS500-G1-Mathematics-Ch38",
        item_ids=[
            "IS500-G1-Mathematics-Ch38-i1",
            "IS500-G1-Mathematics-Ch38-i2",
        ],
        workbook_path=workbook_path,
        max_retries=3,
        run_label="UNIT",
    )

    assert result.rerun_messages == ("QAR rerun completed",)
    assert result.retry_count == 1
    assert page.reruns == 1
    assert page.verifications == 2
    assert "Clear-language practice card" in page.corrections[0]["question"]
    assert "Clear-language practice card" in page.corrections[1]["question"]
    assert page.corrections[0]["question"] != page.corrections[1]["question"]


def test_workbook_corrections_preserve_typology_answers_and_use_report_reason(
    tmp_path, monkeypatch, record_property,
):
    # No question-bank match exists for this env, so the correction factory
    # falls back to its typology-preserving templated rewrite - see
    # test_qar_recovery_question_bank_replacement.py for the bank-backed path.
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Correct a workbook when the question bank holds no matching replacement.\n"
        "Check the templated rewrite keeps the item's typology and answers "
        "intact, and uses the reason QAR actually gave.",
    )
    empty_bank_path = tmp_path / "empty_bank.json"
    empty_bank_path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("CBSE_QUESTION_BANK_PATH", str(empty_bank_path))
    monkeypatch.setenv("CBSE_ENV", "unit-test-env")

    workbook_path = tmp_path / "mixed-items.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    columns = write_canonical_headers(worksheet)
    rows = (
        ("True or False", "Original false statement?", "False"),
        ("Fill in the Blank", "The duration is ___.", "2"),
        ("Short Answer Question", "State the duration.", "2 hours"),
    )
    for row, (typology, question, answer) in enumerate(rows, start=2):
        worksheet.cell(row=row, column=columns["typology"]).value = typology
        worksheet.cell(row=row, column=columns["question"]).value = question
        worksheet.cell(row=row, column=columns["answer"]).value = answer
    workbook.save(workbook_path)
    workbook.close()

    correction = build_workbook_qar_correction_factory(
        workbook_path,
        run_label="UNIT",
    )
    feedback = {
        "status": "Need Improvement",
        "failure_reasons": {"Duplicate Detection": "95% similar"},
    }

    true_false = correction("IS600-i1", 1, feedback)
    fill_blank = correction("IS600-i2", 1, feedback)
    short_answer = correction("IS600-i3", 1, feedback)

    assert "Independent duplicate-safe practice card" in true_false["question"]
    assert "4 counters" in true_false["question"]
    assert "9 counters" in true_false["question"]
    assert "recorded answer is 2" in fill_blank["question"]
    assert "answer of 2 hours" in short_answer["question"]
    assert "Duplicate Detection" in true_false["revision_note"]


def test_positive_recovery_rejects_terminal_non_editable_qar_failures(tmp_path, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Try to recover a set whose QAR failure is terminal and cannot be edited "
        "away.\n"
        "Check recovery refuses rather than looping on something it cannot fix.",
    )
    workbook_path = tmp_path / "terminal.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    columns = write_canonical_headers(worksheet)
    worksheet.cell(row=2, column=columns["typology"]).value = "True or False"
    worksheet.cell(row=2, column=columns["question"]).value = "Is nine greater than four?"
    worksheet.cell(row=2, column=columns["answer"]).value = "True"
    workbook.save(workbook_path)
    workbook.close()

    class TerminalPage:
        QAR_RETRY_STATUS_LABELS = UploadItemFilePage.QAR_RETRY_STATUS_LABELS

        @staticmethod
        def verify_item_set_from_sets_module(_item_set_id, _item_ids):
            return True

        @staticmethod
        def get_qar_item_statuses(_item_set_id=None):
            return {"IS700-i1": "Rejected"}

    with pytest.raises(AssertionError, match="terminal, non-editable failures"):
        recover_qar_need_improvement_items(
            page=TerminalPage(),
            item_set_id="IS700",
            item_ids=["IS700-i1"],
            workbook_path=workbook_path,
        )


def test_review_step_ids_are_recognised_as_unnumbered(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Look at an item set ID built from review-step item IDs, before the set "
        "has a number.\n"
        "Check it is recognised as unnumbered, so the set is looked up by its "
        "uploaded file instead of by an ID that names nothing.",
    )
    # What the review step actually produced on QA: no set number at all.
    assert not UploadItemFilePage.item_set_id_is_numbered("IS-G1-Mathematics-Ch29")
    assert not UploadItemFilePage.item_set_id_is_numbered("")
    assert UploadItemFilePage.item_set_id_is_numbered("IS1405-G1-Mathematics-Ch29")


def test_the_set_is_found_by_the_workbook_it_was_uploaded_from(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Search the item set grid for the set created from one uploaded workbook.\n"
        "Check the row naming that workbook is matched, and rows for other "
        "people's uploads are left alone.",
    )
    page = UploadItemFilePage.__new__(UploadItemFilePage)
    page.get_item_set_list_rows = lambda: [
        {"item_set_id": "IS1440-G1-Mathematics-CH-4", "uploaded_file": "someone_else.xlsx"},
        {"item_set_id": "IS1405-G1-Mathematics-Ch29",
         "uploaded_file": "IS10_baseline_ab12cd34ef_9f3a2b1c.xlsx"},
    ]

    assert page.find_item_set_id_by_uploaded_file(
        "IS10_baseline_ab12cd34ef_9f3a2b1c.xlsx"
    ) == "IS1405-G1-Mathematics-Ch29"
    # A full path is accepted; only the file name is compared.
    assert page.find_item_set_id_by_uploaded_file(
        r"C:\tmp\IS10_baseline_ab12cd34ef_9f3a2b1c.xlsx"
    ) == "IS1405-G1-Mathematics-Ch29"
    assert page.find_item_set_id_by_uploaded_file("not_uploaded_here.xlsx") == ""
    assert page.find_item_set_id_by_uploaded_file("") == ""


def test_an_unnumbered_row_is_not_accepted_as_a_match(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Search the grid when the matching row has no set number yet.\n"
        "Check it is not returned, because the set is only addressable once it "
        "has been numbered.",
    )
    page = UploadItemFilePage.__new__(UploadItemFilePage)
    page.get_item_set_list_rows = lambda: [
        {"item_set_id": "IS-G1-Mathematics-Ch29", "uploaded_file": "pending.xlsx"},
    ]

    assert page.find_item_set_id_by_uploaded_file("pending.xlsx") == ""


def test_recovery_needs_either_a_numbered_id_or_a_file_name(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Ask for a verdict with neither a set ID nor an uploaded file name.\n"
        "Check nothing is navigated, so the lookup cannot wander onto another "
        "set's result.",
    )
    page = UploadItemFilePage.__new__(UploadItemFilePage)
    page.open_sets_module = lambda: pytest.fail("should not navigate")

    assert not page.resolve_qar_outcome_from_item_set("", [], uploaded_file_name="")
