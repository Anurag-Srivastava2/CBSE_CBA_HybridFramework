"""QAR plagiarism detection against published items from item-bank-export.pdf."""

import json
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.bulk_upload_page import BulkUploadPage
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
    ):
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
        validation = upload_page.upload_excel_for_validation(workbook_path)
        assert validation["accepted"], (
            f"PDF plagiarism fixture was rejected before QAR: {validation['message']}"
        )
        submission = upload_page.submit_for_qar("1LPH5FTO-3")
        assert len(submission["item_ids"]) == self.ITEM_COUNT, (
            f"Expected {self.ITEM_COUNT} copied PDF items, got {submission['item_ids']}."
        )

        report = QARReportPage(self.driver)
        report.wait_until_processed(submission["item_set_id"], timeout=180)
        initial_statuses = {
            item_id: report.get_item_status(item_id)
            for item_id in submission["item_ids"]
        }
        incorrectly_approved = {
            item_id: status
            for item_id, status in initial_statuses.items()
            if status.casefold() in {"approved", "passed"}
        }
        assert not incorrectly_approved, (
            "Verbatim PDF repository copies incorrectly passed plagiarism QAR at "
            f"the 97% threshold: {incorrectly_approved}."
        )

        qar_evidence = []
        for item_id, source in zip(submission["item_ids"], source_evidence):
            check = report.get_open_item_check_evidence(
                item_id,
                "Plagiarism Detection",
                expand=True,
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
