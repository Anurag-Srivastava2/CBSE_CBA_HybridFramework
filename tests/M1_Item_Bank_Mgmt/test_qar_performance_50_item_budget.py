"""TC-IBMM-08-P01: QAR completes a 50-item check within 120 seconds.

The point of this test is to *measure*, not to time out. The wait ceiling is
set far above the budget on purpose: a test that aborts at 120s can only ever
report "it took at least 120s", which is the same information as no test at
all. Letting the analysis finish and asserting on the elapsed time gives a
real number, and the number is recorded whether the assertion passes or fails
so the trend is visible run to run.

Context for the budget. Measured on this environment during the readiness
review, on 3-item text-only sets:

    230s, 238s, 303s

Three items already exceeded the budget the RTM allows for fifty. That may be
environment rather than product, but until something measures it, nobody can
tell - and raising a test's timeout to absorb it hides the symptom instead of
tracking it. This is that measurement.
"""
import time
from pathlib import Path
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.item_bank_workbook_builder import build_item_workbook
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.performance
@pytest.mark.usefixtures("setup")
class TestQAR50ItemPerformanceBudget:
    """Runtime cost is real: exclude with -m "not performance" on PR gates."""

    ITEM_COUNT = 50
    BUDGET_SECONDS = 120

    # Ten minutes. Not a budget - a ceiling high enough that the run produces a
    # measurement rather than a timeout, even on a badly degraded environment.
    MEASUREMENT_CEILING_SECONDS = 600

    def login_as_sme(self):
        self.driver.get(ReadConfig.get_base_url())
        username = ReadConfig.get_sme2_username()
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_password_for_username(username)
        )
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        return page

    def test_tc_ibmm_08_p01_qar_completes_50_item_set_within_budget(
        self, tmp_path, record_property, page_evidence
    ):
        page = self.login_as_sme()
        page_evidence.checkpoint(
            f"SME signed in to measure QAR against a {self.BUDGET_SECONDS}s "
            f"budget for {self.ITEM_COUNT} items"
        )

        workbook, _ = build_item_workbook(
            Path(ReadConfig.get_upload_item_file_path()),
            tmp_path / f"qar_perf_50_{uuid4().hex[:8]}.xlsx",
            count=self.ITEM_COUNT,
        )

        page.open_item_creation_module()
        page.open_upload_item_file_tab()
        page.open_upload_step()
        page.upload_file(workbook)
        page.wait_for_upload_validation_success()
        page_evidence.checkpoint(
            f"{workbook.name} ({self.ITEM_COUNT} rows) passed upload validation"
        )
        page.click_continue()
        item_ids = page.get_review_item_ids()
        page_evidence.checkpoint(
            f"Review step ingested {len(item_ids)} item(s); the timer starts at "
            "Submit for QAR, so the wizard is outside the measurement"
        )
        page.click_continue()

        # The upload and review steps are deliberately outside the timer: the
        # requirement is about how long QAR takes to check the set, not how
        # long the wizard takes to reach it.
        started = time.monotonic()
        page.click_submit_for_qar_and_wait_for_results(
            analysis_timeout=self.MEASUREMENT_CEILING_SECONDS
        )
        elapsed = time.monotonic() - started

        item_count = len(item_ids)
        per_item = elapsed / item_count if item_count else float("nan")
        page_evidence.checkpoint(
            f"QAR finished in {elapsed:.1f}s for {item_count} item(s) "
            f"({per_item:.2f}s/item) against a {self.BUDGET_SECONDS}s budget — "
            f"{'within' if elapsed <= self.BUDGET_SECONDS else 'over'} budget"
        )
        record_property("qar_item_count", str(item_count))
        record_property("qar_elapsed_seconds", f"{elapsed:.1f}")
        record_property("qar_seconds_per_item", f"{per_item:.2f}")
        record_property("qar_budget_seconds", str(self.BUDGET_SECONDS))
        record_property(
            "result_description",
            f"QAR checked {item_count} items in {elapsed:.1f}s "
            f"({per_item:.2f}s/item) against a {self.BUDGET_SECONDS}s budget.",
        )

        assert item_count == self.ITEM_COUNT, (
            f"Expected {self.ITEM_COUNT} items to be ingested for the "
            f"performance measurement, got {item_count}. The timing below is "
            "not comparable to the budget."
        )
        assert elapsed <= self.BUDGET_SECONDS, (
            f"TC-IBMM-08-P01: QAR took {elapsed:.1f}s to check "
            f"{item_count} items ({per_item:.2f}s/item), over the "
            f"{self.BUDGET_SECONDS}s budget by {elapsed - self.BUDGET_SECONDS:.1f}s."
        )
