"""QAR plagiarism detection against published items from item-bank-export.pdf."""

import json
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.bulk_upload_page import BulkUploadPage
from tests.M1_Item_Bank_Mgmt.m1_surveys import survey_chrome
from utilities.element_checks import ElementChecks
from utilities.qar_plagiarism_fixture import (
    EXPECTED_PLAGIARISM_THRESHOLD,
    PUBLISHED_SOURCE_ITEMS,
    build_qar_plagiarism_workbook,
)
from utilities.read_config import ReadConfig


@pytest.mark.e2e
@pytest.mark.nightly
@pytest.mark.usefixtures("setup")
class TestE2EQARPlagiarismPDFThreshold:
    ITEM_COUNT = len(PUBLISHED_SOURCE_ITEMS)

    def login_as_sme(self):
        self.driver.get(ReadConfig.get_base_url())
        sme_username = ReadConfig.get_sme2_username()
        LoginPage(self.driver).login_to_application(
            sme_username,
            ReadConfig.get_password_for_username(sme_username),
        )

    def test_pdf_repository_copies_are_blocked_at_97_percent(
        self,
        request,
        tmp_path,
        record_property,
        page_evidence,
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Build a workbook whose questions are copied word for word out of the "
            "published item-bank PDF, each at least 97% similar to its source.\n"
            "Sign in as an SME, upload it, and submit the set for QAR.\n"
            "Expect QAR to catch every copy: no copied item may come back Approved or "
            "Passed.",
        )
        run_token = f"QAR_AUTO_PDF_PLAG_{uuid4().hex[:10]}"
        workbook_path, source_evidence = build_qar_plagiarism_workbook(
            ReadConfig.get_upload_item_file_path(),
            tmp_path / f"{run_token}.xlsx",
            run_token,
        )
        assert len(source_evidence) == self.ITEM_COUNT
        assert all(
            row["source_similarity"] >= EXPECTED_PLAGIARISM_THRESHOLD
            for row in source_evidence
        )

        self.login_as_sme()
        upload_page = BulkUploadPage(self.driver)
        upload_page.close_popup_if_open()
        page_evidence.checkpoint(
            f"SME signed in with {self.ITEM_COUNT} verbatim copies of published "
            f"item-bank-export.pdf items, each >= {EXPECTED_PLAGIARISM_THRESHOLD}% "
            f"similar to its source (run {run_token})"
        )

        # Chrome only: this nightly check drives the bulk-upload page object,
        # which does not expose the upload-step furniture the other suites
        # survey. The plagiarism threshold assertions all stay hard.
        checks = ElementChecks(
            upload_page, record_property, page_name="SME Bulk Upload — PDF Plagiarism"
        )
        survey_chrome(checks, upload_page)
        record_property("result_description", checks.publish())
        validation = upload_page.upload_excel_for_validation(workbook_path)
        page_evidence.checkpoint(
            f"Fixture workbook accepted by upload validation: "
            f"{validation['accepted']} — {validation['message']}"
        )
        assert validation["accepted"], (
            f"PDF plagiarism fixture was rejected before QAR: {validation['message']}"
        )
        submission = upload_page.submit_for_qar("1LPH5FTO-3")
        page_evidence.checkpoint(
            f"Submitted for QAR as set {submission['item_set_id']} with "
            f"{len(submission['item_ids'])} item(s): {submission['item_ids']}"
        )
        assert len(submission["item_ids"]) == self.ITEM_COUNT, (
            f"Expected {self.ITEM_COUNT} copied PDF items, got {submission['item_ids']}."
        )

        report = QARReportPage(self.driver)
        report.wait_until_processed(submission["item_set_id"], timeout=180)
        initial_statuses = {
            item_id: report.get_item_status(item_id)
            for item_id in submission["item_ids"]
        }
        page_evidence.checkpoint(
            f"QAR finished; per-item verdicts: {initial_statuses}"
        )
        incorrectly_approved = {
            item_id: status
            for item_id, status in initial_statuses.items()
            if status.casefold() in {"approved", "passed"}
        }
        assert not incorrectly_approved, (
            "Verbatim PDF repository copies incorrectly passed plagiarism QAR at "
            f"the 97% threshold: {incorrectly_approved}."
        )

        page_evidence.checkpoint(
            f"No verbatim PDF copy slipped through as approved/passed at the "
            f"{EXPECTED_PLAGIARISM_THRESHOLD}% threshold"
        )

        qar_evidence = []
        for item_id, source in zip(submission["item_ids"], source_evidence):
            check = report.get_open_item_check_evidence(
                item_id,
                "Plagiarism Detection",
                expand=True,
            )
            page_evidence.checkpoint(
                f"{item_id} (copied from {source['source_item_id']}, PDF page "
                f"{source['source_pdf_page']}, {source['source_similarity']}% similar) "
                f"— Plagiarism Detection scored {check['score']}, status "
                f"{initial_statuses[item_id]}"
            )
            assert check["card"], (
                f"No Plagiarism Detection card was visible after opening {item_id}."
            )
            assert check["score"] is not None, (
                f"No Plagiarism Detection score was visible for {item_id}: {check['card']}"
            )
            qar_evidence.append(
                {
                    "new_item_id": item_id,
                    "source_item_id": source["source_item_id"],
                    "source_pdf_page": source["source_pdf_page"],
                    "source_similarity": source["source_similarity"],
                    "qar_score": check["score"],
                    "qar_card": check["card"],
                    "qar_status": initial_statuses[item_id],
                }
            )

        request.node.user_properties.extend(
            [
                ("item_set_id", submission["item_set_id"]),
                ("plagiarism_source_similarity_threshold", "97.0"),
                ("plagiarism_pdf_source", "item-bank-export.pdf"),
                ("plagiarism_evidence", json.dumps(qar_evidence)),
                (
                    "result_description",
                    f"Verified {self.ITEM_COUNT} verbatim PDF repository copies against "
                    "the 97% PDF-source similarity contract and QAR results.",
                ),
            ]
        )
