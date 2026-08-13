"""Validate all curated images and their questions together, carried through QAR.

Companion to test_e2e_qar_image_moderation.py, which tests each of the 22
curated images independently (one browser test per image, 22 tests total).
This module instead bundles every case into a single Excel workbook (22 rows,
one question per image) and a single images ZIP (22 files) and uploads them
as one unit with sme2, mirroring how a real SME would submit an entire item
set in one go rather than one image at a time.

Image Moderation is no longer enforced as an all-or-nothing gate at the
ZIP-upload boundary: the upload of the full batch is expected to be accepted,
and the item set then goes through a QAR run. Image Moderation is evaluated
per item during that run, so the resulting item set is expected to contain a
mix of passing items (the "_ok_" images) and failing/flagged items (the
"_bad_" images). This test opens every item afterwards and reads its QAR
report (rendered on the right-hand side of the review UI) to check the
Image Moderation result recorded for that specific item.
"""

import json
import re
from pathlib import Path
from uuid import uuid4

import allure
import pytest

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.bulk_upload_page import BulkUploadPage
from utilities.qar_image_moderation_fixture import (
    build_image_moderation_workbook,
    build_neutral_named_images_zip,
    load_real_image_cases,
)
from utilities.read_config import ReadConfig

SOURCE_ZIP_PATH = Path(ReadConfig.get_image_moderation_test_zip_path())
IMAGE_MODERATION_CHECK_NAME = "Image Moderation"
FLAGGED_PATTERN = re.compile(
    r"\b(fail(?:ed)?|flag(?:ged)?|blocked|reject(?:ed)?|revise|"
    r"need(?:s)? improvement|revision)\b",
    re.IGNORECASE,
)


def _is_flagged(item):
    if item["image_moderation_status_color"] == "fail":
        return True
    if item["image_moderation_status_color"] == "pass":
        return False
    text = f"{item['status']} {item['image_moderation_card']}"
    return bool(FLAGGED_PATTERN.search(text))


@pytest.mark.e2e
@pytest.mark.usefixtures("setup")
class TestE2EQARImageModerationBulk:
    @staticmethod
    def item_number(item_id):
        match = re.search(r"-i(\d+)$", item_id, re.IGNORECASE)
        assert match, f"QAR returned an unexpected item ID: {item_id}"
        return int(match.group(1))

    def test_all_images_and_questions_in_one_sheet_upload_moderation(self, request):
        prefix = f"QAR_AUTO_IMG_BULK_{uuid4().hex[:10]}"
        source_cases = load_real_image_cases(SOURCE_ZIP_PATH, prefix)
        blocked_cases = [
            case for case in source_cases if case.expected_outcome == "BLOCK"
        ]
        assert blocked_cases, (
            "Fixture is expected to include at least one BLOCK-expected image."
        )

        run_id = f"bulk_{prefix}"
        artifact_dir = (
            Path(ReadConfig.project_root)
            / "artifacts"
            / "image_moderation"
            / "runs"
            / run_id
        )
        zip_path, upload_cases = build_neutral_named_images_zip(
            SOURCE_ZIP_PATH,
            source_cases,
            artifact_dir / f"{prefix}_all_images.zip",
        )
        workbook_path, fixture_rows = build_image_moderation_workbook(
            ReadConfig.get_upload_item_file_path(),
            artifact_dir / f"{prefix}.xlsx",
            prefix,
            upload_cases,
        )
        assert len(fixture_rows) == len(upload_cases) == len(source_cases)

        sme_username = ReadConfig.get_sme2_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            sme_username,
            ReadConfig.get_sme2_password(),
        )
        upload_page = BulkUploadPage(self.driver)
        upload_page.close_popup_if_open()
        validation = upload_page.upload_excel_and_images_zip_for_validation(
            workbook_path,
            zip_path,
            timeout=180,
        )
        assert validation["accepted"], (
            f"Upload of all {len(upload_cases)} images was rejected before "
            f"reaching QAR: {validation['message']}"
        )

        submission = upload_page.submit_for_qar(prefix, analysis_timeout=300)
        assert len(submission["item_ids"]) == len(upload_cases), (
            f"Expected {len(upload_cases)} fresh items, received "
            f"{submission['item_ids']}."
        )

        report = QARReportPage(self.driver)
        report.wait_until_processed(submission["item_set_id"], timeout=300)

        screenshot_dir = artifact_dir / "qar_report_screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        per_item_results = []
        for item_id in sorted(submission["item_ids"], key=self.item_number):
            number = self.item_number(item_id)
            source_case = source_cases[number - 1]
            upload_case = upload_cases[number - 1]

            evidence = report.get_open_item_check_evidence(
                item_id, IMAGE_MODERATION_CHECK_NAME
            )
            status = report.get_item_status(item_id)

            item_screenshot = (
                screenshot_dir / f"{prefix}_item_{number:03d}_qar_report.png"
            )
            self.driver.save_screenshot(str(item_screenshot))

            per_item_results.append(
                {
                    "item_id": item_id,
                    "case_number": number,
                    "uploaded_filename": upload_case.filename,
                    "source_filename": source_case.filename,
                    "category": source_case.category,
                    "expected_outcome": source_case.expected_outcome,
                    "status": status,
                    "image_moderation_card": evidence["card"],
                    "image_moderation_score": evidence["score"],
                    "image_moderation_threshold": evidence["threshold"],
                    "image_moderation_status_color": evidence["status_color"],
                    "qar_report_screenshot": str(item_screenshot),
                }
            )

        result = {
            "run_id": run_id,
            "sme_username": sme_username,
            "item_set_id": submission["item_set_id"],
            "case_count": len(upload_cases),
            "blocked_case_count": len(blocked_cases),
            "per_item_results": per_item_results,
        }
        results_dir = artifact_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        result_path = results_dir / "bulk_qar_result.json"
        result["result_path"] = str(result_path)
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )

        allure.attach(
            json.dumps(result, indent=2, sort_keys=True),
            name="Bulk image moderation QAR result",
            attachment_type=allure.attachment_type.JSON,
        )
        for item in per_item_results:
            allure.attach.file(
                item["qar_report_screenshot"],
                name=(
                    f"Item {item['case_number']:03d} QAR report - "
                    f"{item['source_filename']}"
                ),
                attachment_type=allure.attachment_type.PNG,
            )
        print(
            f"[IMAGE_MODERATION_BULK_QAR_RESULT] {json.dumps(result, sort_keys=True)}",
            flush=True,
        )
        request.node.user_properties.extend(
            [
                ("item_set_id", submission["item_set_id"]),
                (
                    "image_moderation_bulk_qar_result",
                    json.dumps(result, sort_keys=True),
                ),
                (
                    "result_description",
                    f"Uploaded all {len(upload_cases)} images/questions in one "
                    f"sheet as {sme_username}, ran QAR on item set "
                    f"{submission['item_set_id']}, and opened each item's QAR "
                    "report to check its Image Moderation result.",
                ),
            ]
        )

        mismatches = [
            item
            for item in per_item_results
            if (item["expected_outcome"] == "BLOCK") != _is_flagged(item)
        ]
        assert not mismatches, (
            f"{len(mismatches)} of {len(per_item_results)} items had an Image "
            "Moderation result inconsistent with their expected outcome: "
            f"{json.dumps(mismatches, indent=2)}"
        )
