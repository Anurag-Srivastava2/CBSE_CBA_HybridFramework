"""Fresh multi-topic bias items expose a score in every per-item QAR report."""

import json
import re
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.bulk_upload_page import BulkUploadPage
from utilities.qar_bias_fixture import (
    BIAS_QUESTION_SPECS,
    TEXT_BIAS_CASES,
    assert_bias_score_contract,
    assert_text_bias_category_contract,
    build_qar_bias_workbook,
    build_qar_text_bias_workbook,
)
from utilities.read_config import ReadConfig


@pytest.mark.e2e
@pytest.mark.nightly
@pytest.mark.usefixtures("setup")
class TestE2EQARBiasDetectionScores:
    ITEM_COUNT = len(BIAS_QUESTION_SPECS)

    @staticmethod
    def make_prefix():
        return f"QAR_AUTO_BIAS_LEVELS_{uuid4().hex[:10]}"

    @staticmethod
    def item_number(item_id):
        match = re.search(r"-i(\d+)$", item_id, re.IGNORECASE)
        assert match, f"QAR returned an unexpected item ID: {item_id}"
        return int(match.group(1))

    def test_each_fresh_bias_item_exposes_a_severity_sensitive_score(
        self,
        request,
        tmp_path,
    ):
        prefix = self.make_prefix()
        workbook_path, fixture_rows = build_qar_bias_workbook(
            ReadConfig.get_upload_item_file_path(),
            tmp_path / f"{prefix}.xlsx",
            prefix,
        )
        assert len(fixture_rows) == self.ITEM_COUNT
        assert len({row["topic"] for row in fixture_rows}) == self.ITEM_COUNT

        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_all_users_password(),
        )
        upload_page = BulkUploadPage(self.driver)
        upload_page.close_popup_if_open()
        validation = upload_page.upload_excel_for_validation(workbook_path)
        assert validation["accepted"], (
            f"Fresh bias fixture was rejected before QAR: {validation['message']}"
        )
        submission = upload_page.submit_for_qar(prefix)
        assert len(submission["item_ids"]) == self.ITEM_COUNT, (
            f"Expected {self.ITEM_COUNT} fresh items, received {submission['item_ids']}."
        )

        report = QARReportPage(self.driver)
        report.wait_until_processed(submission["item_set_id"], timeout=180)
        score_evidence = []
        for item_id in sorted(submission["item_ids"], key=self.item_number):
            number = self.item_number(item_id)
            spec = fixture_rows[number - 1]
            evidence = report.get_open_item_check_evidence(item_id, "Bias Detection")
            assert evidence["card"], (
                f"Opened {item_id}, but its Bias Detection card was not visible."
            )
            assert evidence["score"] is not None, (
                f"Opened {item_id}, but its Bias Detection card had no percentage: "
                f"{evidence['card']}"
            )
            assert evidence["threshold"] is not None, (
                f"Opened {item_id}, but its Bias Detection card had no live threshold: "
                f"{evidence['card']}"
            )
            score_evidence.append(
                {
                    "item_id": item_id,
                    "topic": spec["topic"],
                    "severity": spec["severity"],
                    "severity_rank": spec["severity_rank"],
                    "score": evidence["score"],
                    "threshold": evidence["threshold"],
                    "status": report.get_item_status(item_id),
                    "card": evidence["card"],
                }
            )

        ordered_scores = assert_bias_score_contract(score_evidence)
        request.node.user_properties.extend(
            [
                ("item_set_id", submission["item_set_id"]),
                ("qar_bias_fixture_prefix", prefix),
                ("qar_bias_score_evidence", json.dumps(score_evidence)),
                ("qar_bias_ordered_scores", json.dumps(ordered_scores)),
                (
                    "result_description",
                    f"Opened all {self.ITEM_COUNT} fresh items and verified a Bias "
                    "Detection score and checked strong bias against its live threshold.",
                ),
            ]
        )

    def test_each_text_bias_case_flags_or_clears_against_live_threshold(
        self,
        request,
        tmp_path,
    ):
        prefix = self.make_prefix()
        workbook_path, fixture_rows = build_qar_text_bias_workbook(
            ReadConfig.get_upload_item_file_path(),
            tmp_path / f"{prefix}.xlsx",
            prefix,
        )
        assert len(fixture_rows) == len(TEXT_BIAS_CASES)

        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_all_users_password(),
        )
        upload_page = BulkUploadPage(self.driver)
        upload_page.close_popup_if_open()
        validation = upload_page.upload_excel_for_validation(workbook_path)
        assert validation["accepted"], (
            f"TEXT BIAS fixture was rejected before QAR: {validation['message']}"
        )
        submission = upload_page.submit_for_qar(prefix, analysis_timeout=240)
        assert len(submission["item_ids"]) == len(TEXT_BIAS_CASES), (
            f"Expected {len(TEXT_BIAS_CASES)} fresh items, received {submission['item_ids']}."
        )

        report = QARReportPage(self.driver)
        report.wait_until_processed(submission["item_set_id"], timeout=240)
        score_evidence = []
        for item_id in sorted(submission["item_ids"], key=self.item_number):
            number = self.item_number(item_id)
            spec = fixture_rows[number - 1]
            evidence = report.get_open_item_check_evidence(item_id, "Bias Detection")
            assert evidence["card"], (
                f"Opened {item_id}, but its Bias Detection card was not visible."
            )
            assert evidence["score"] is not None, (
                f"Opened {item_id}, but its Bias Detection card had no percentage: "
                f"{evidence['card']}"
            )
            assert evidence["threshold"] is not None, (
                f"Opened {item_id}, but its Bias Detection card had no live threshold: "
                f"{evidence['card']}"
            )
            score_evidence.append(
                {
                    "item_id": item_id,
                    "lang": spec["lang"],
                    "input_text": spec["input_text"],
                    "expected_category": spec["expected_category"],
                    "score": evidence["score"],
                    "threshold": evidence["threshold"],
                    "status": report.get_item_status(item_id),
                    "card": evidence["card"],
                }
            )

        ordered_scores = assert_text_bias_category_contract(score_evidence)
        request.node.user_properties.extend(
            [
                ("item_set_id", submission["item_set_id"]),
                ("qar_text_bias_fixture_prefix", prefix),
                ("qar_text_bias_score_evidence", json.dumps(score_evidence)),
                ("qar_text_bias_ordered_scores", json.dumps(ordered_scores)),
                (
                    "result_description",
                    f"Opened all {len(TEXT_BIAS_CASES)} TEXT BIAS items (EN+HI) and verified "
                    "each Bias Detection score against the live threshold for its expected "
                    "category (or 'none' for neutral statements).",
                ),
            ]
        )
