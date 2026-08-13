"""Validate each curated image independently at the upload-moderation boundary.

The source archive contains 22 images whose original names encode the expected
upload result: ``_bad_`` images should be rejected and ``_ok_`` images should be
accepted. Pytest expands this module into 22 separate browser tests. Every test
creates exactly one one-row Excel workbook plus one ZIP containing its matching
image. Across the suite, neutral names run from ``image_001`` to ``image_022``
(with each source image's original extension).

Using a neutral name in both files ensures each result reflects image-content
processing rather than semantic words in the original image filename.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

import allure
import pytest

from pages.common.login_page import LoginPage
from pages.sme.bulk_upload_page import BulkUploadPage
from utilities.qar_image_moderation_fixture import (
    build_image_moderation_workbook,
    build_neutral_named_images_zip,
    load_real_image_cases,
)
from utilities.read_config import ReadConfig


SOURCE_ZIP_PATH = Path(ReadConfig.get_image_moderation_test_zip_path())
SOURCE_IMAGE_CASES = tuple(
    (index, case.filename)
    for index, case in enumerate(
        load_real_image_cases(SOURCE_ZIP_PATH, "COLLECTION"),
        start=1,
    )
)


@pytest.mark.e2e
@pytest.mark.nightly
@pytest.mark.xfail(
    reason=(
        "Known issue: image-content moderation is not reliable on this environment. "
        "Unsafe images are accepted and some safe images are intermittently rejected, "
        "so neither outcome is a regression signal. Remove this marker once moderation "
        "is fixed."
    ),
    strict=False,
)
@pytest.mark.usefixtures("setup")
class TestE2EQARImageModeration:
    @staticmethod
    def sme_user_for_worker(worker_id):
        users = ReadConfig.get_role_usernames("sme")
        if worker_id == "master":
            return ReadConfig.get_sme2_username()
        worker_number = int(worker_id.removeprefix("gw"))
        if worker_number >= len(users):
            raise RuntimeError(
                f"Worker {worker_id} has no dedicated SME account; "
                f"only {len(users)} SME users are configured."
            )
        return users[worker_number]

    @pytest.mark.parametrize(
        ("case_number", "source_filename"),
        SOURCE_IMAGE_CASES,
        ids=[
            f"{case_number:03d}-{source_filename}"
            for case_number, source_filename in SOURCE_IMAGE_CASES
        ],
    )
    def test_single_image_upload_moderation(
        self,
        case_number,
        source_filename,
        request,
        worker_id,
    ):
        prefix = f"QAR_AUTO_IMG_ONE_{uuid4().hex[:10]}"
        source_case = next(
            case
            for case in load_real_image_cases(SOURCE_ZIP_PATH, prefix)
            if case.filename == source_filename
        )
        expected_accepted = source_case.expected_outcome == "ALLOW"
        run_id = os.getenv("CBSE_IMAGE_MODERATION_RUN_ID", "local").strip() or "local"
        safe_run_id = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in run_id
        )

        artifact_dir = (
            Path(ReadConfig.project_root)
            / "artifacts"
            / "image_moderation"
            / "runs"
            / safe_run_id
        )
        zip_path, (upload_case,) = build_neutral_named_images_zip(
            SOURCE_ZIP_PATH,
            (source_case,),
            artifact_dir / f"{prefix}_neutral_image.zip",
            neutral_start_index=case_number,
        )
        workbook_path, fixture_rows = build_image_moderation_workbook(
            ReadConfig.get_upload_item_file_path(),
            artifact_dir / f"{prefix}.xlsx",
            prefix,
            (upload_case,),
        )
        assert len(fixture_rows) == 1
        assert fixture_rows[0]["filename"] == upload_case.filename

        sme_username = self.sme_user_for_worker(worker_id)
        sme_password = (
            ReadConfig.get_sme2_password()
            if sme_username == ReadConfig.get_sme2_username()
            else ReadConfig.get_all_users_password()
        )
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            sme_username,
            sme_password,
        )
        upload_page = BulkUploadPage(self.driver)
        upload_page.close_popup_if_open()
        validation = upload_page.upload_excel_and_images_zip_for_validation(
            workbook_path,
            zip_path,
        )

        screenshot_dir = artifact_dir / "validation_screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        outcome_label = "accepted" if validation["accepted"] else "rejected"
        screenshot_stem = f"{prefix}_{Path(source_filename).stem}_{outcome_label}"
        focused_screenshot = screenshot_dir / f"{screenshot_stem}_focused.png"
        viewport_screenshot = screenshot_dir / f"{screenshot_stem}_viewport.png"

        evidence_element, evidence_kind = (
            upload_page.get_images_zip_validation_evidence(validation["accepted"])
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            evidence_element,
        )
        upload_page.pause_before_action()
        evidence_element.screenshot(str(focused_screenshot))
        self.driver.save_screenshot(str(viewport_screenshot))
        evidence_text = evidence_element.text.strip()

        rejection_screenshot = (
            viewport_screenshot if not validation["accepted"] else None
        )

        result = {
            "run_id": safe_run_id,
            "case_number": case_number,
            "sme_username": sme_username,
            "source_filename": source_filename,
            "uploaded_filename": upload_case.filename,
            "expected_accepted": expected_accepted,
            "evidence_kind": evidence_kind,
            "evidence_text": evidence_text,
            "focused_evidence_screenshot": str(focused_screenshot),
            "viewport_evidence_screenshot": str(viewport_screenshot),
            "validation_screenshot": str(viewport_screenshot),
            "rejection_screenshot": (
                str(rejection_screenshot) if rejection_screenshot else None
            ),
            **validation,
        }
        results_dir = artifact_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        result_path = results_dir / f"{case_number:03d}.json"
        result["result_path"] = str(result_path)
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        focused_name = f"Focused product evidence - {evidence_text or evidence_kind}"
        viewport_name = f"Validation context - {outcome_label}"
        allure.attach.file(
            str(focused_screenshot),
            name=focused_name,
            attachment_type=allure.attachment_type.PNG,
        )
        allure.attach.file(
            str(viewport_screenshot),
            name=viewport_name,
            attachment_type=allure.attachment_type.PNG,
        )
        allure.attach(
            json.dumps(result, indent=2, sort_keys=True),
            name="Image upload validation result",
            attachment_type=allure.attachment_type.JSON,
        )
        print(f"[IMAGE_UPLOAD_RESULT] {json.dumps(result, sort_keys=True)}", flush=True)
        evidence_screenshots = [
            {"name": focused_name, "path": str(focused_screenshot)},
            {"name": viewport_name, "path": str(viewport_screenshot)},
        ]
        request.node.user_properties.extend(
            [
                ("single_image_upload_validation", json.dumps(result, sort_keys=True)),
                ("evidence_screenshots", json.dumps(evidence_screenshots)),
                ("qar_success_screenshot", str(viewport_screenshot)),
                (
                    "result_description",
                    f"{source_filename} as {upload_case.filename}: "
                    f"{outcome_label.upper()} - {validation['message']}",
                ),
            ]
        )

        # Leave the worker's dedicated dev account clean before evaluating the
        # assertion, so an unexpected result cannot contaminate its next case.
        if evidence_kind == "review_file_validation_passed":
            upload_page.reset_upload_step()
            upload_page.discard_active_upload_if_present()
            upload_page.discard_staged_upload_files()
        else:
            upload_page.delete_uploaded_file_if_present()

        assert validation["accepted"] is expected_accepted, (
            f"Unexpected upload result for {source_filename} renamed to "
            f"{upload_case.filename}: {validation['message']}"
        )
        if not expected_accepted:
            assert "image rejected" in validation["message"].casefold()
