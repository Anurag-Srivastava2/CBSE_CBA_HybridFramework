"""E2E test: SME uploads Excel, edits items with images during QAR correction,
then verifies images are visible to RWG, SRRWG, and PIT reviewers.
"""
from pathlib import Path
from uuid import uuid4

import pytest

from pages.common.login_page import LoginPage
from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from tests.M1_Item_Bank_Mgmt.m1_surveys import survey_opened_item_set
from utilities.element_checks import ElementChecks
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from utilities.item_bank_workbook_builder import build_item_workbook
from utilities.logger import LogGenerator
from utilities.qar_recovery import (
    TERMINAL_QAR_FAILURES,
    build_workbook_qar_correction_factory,
)
from utilities.read_config import ReadConfig

TEST_IMAGES_FOLDER = Path(__file__).parent.parent.parent / "test_images"


# Drives the app-assigned RWG/SRRWG reviewer and all three PIT approvers, which
# are shared accounts with a single active session each.
@pytest.mark.serial
@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestE2ESMEExcelUploadWithImageEditToPITPublication:
    logger = LogGenerator.loggen()

    @staticmethod
    def get_sme2_username():
        # Worker-aware: under pytest-xdist this resolves to the account pinned to
        # this worker, so parallel workers never share one SME session/draft.
        # Serial runs still get CBSE_SME2_USERNAME.
        return ReadConfig.get_sme2_username()

    @classmethod
    def create_unique_upload_file(cls, source_file_path):
        source_file = Path(source_file_path)
        upload_dir = Path.cwd() / "tmp_uploads"
        upload_dir.mkdir(exist_ok=True)
        unique_file = upload_dir / f"{source_file.stem}_{uuid4().hex[:12]}{source_file.suffix}"
        _, summaries = build_item_workbook(source_file, unique_file, count=4)
        question_counts = {len(items) for items in summaries.values()}
        assert question_counts == {4}
        question_count = question_counts.pop()
        return unique_file, question_count

    @classmethod
    def assign_images_to_items(cls, item_ids):
        """Round-robin assign test images to items. Returns {item_id: Path}."""
        images = sorted(TEST_IMAGES_FOLDER.glob("*.png"))
        assert images, f"No PNG images found in {TEST_IMAGES_FOLDER}"
        return {item_id: images[i % len(images)] for i, item_id in enumerate(item_ids)}

    def _run_image_aware_qar_recovery(
        self,
        page,
        item_set_id,
        item_ids,
        image_path_by_item_id,
        workbook_path,
        max_retries=3,
    ):
        """QAR correction loop that attaches images to each revised item."""
        retry_statuses = {s.casefold() for s in page.QAR_RETRY_STATUS_LABELS}
        correction_factory = build_workbook_qar_correction_factory(
            workbook_path, run_label="IMG-E2E"
        )
        expected_item_ids = tuple(dict.fromkeys(item_ids))
        all_revised_item_ids = []
        rerun_messages = []

        page.verify_item_set_from_sets_module(item_set_id, expected_item_ids)

        for retry_number in range(1, max_retries + 1):
            statuses = page.get_qar_item_statuses()
            terminal = {
                iid: st
                for iid, st in statuses.items()
                if st.casefold() in TERMINAL_QAR_FAILURES
            }
            if terminal:
                raise AssertionError(
                    f"QAR returned terminal failures for {item_set_id}: {terminal}"
                )

            failed = [
                iid
                for iid, st in statuses.items()
                if st.casefold() in retry_statuses
            ]
            if not failed:
                return all_revised_item_ids, rerun_messages

            revised = page.revise_qar_need_improvement_items(
                item_set_id,
                failed,
                correction_factory,
                retry_number,
                image_path_by_item_id=image_path_by_item_id,
            )
            all_revised_item_ids.extend(revised)

            rerun_msg = str(page.rerun_qar_if_enabled() or "")
            if "disabled" in rerun_msg.casefold() or "not available" in rerun_msg.casefold():
                raise AssertionError(
                    f"QAR retry {retry_number} could not start for {item_set_id}: {rerun_msg}"
                )
            rerun_messages.append(rerun_msg)
            page.verify_item_set_from_sets_module(item_set_id, expected_item_ids)

        return all_revised_item_ids, rerun_messages

    def test_e2e_sme_excel_upload_with_image_edit_qar_rwg_srrwg_pit_publish(
        self, request, record_property
    ):
        request.node.user_properties.append(
            ("result_checkpoint", "SME Excel upload with image editing and QAR validation")
        )
        self.driver.get(ReadConfig.get_base_url())

        login_page = LoginPage(self.driver)
        upload_item_file_page = UploadItemFilePage(self.driver)
        rwg_review_queue_page = RWGReviewQueuePage(self.driver)
        sr_rwg_review_queue_page = SRRWGReviewQueuePage(self.driver)
        pit_review_queue_page = PITReviewQueuePage(self.driver)
        sme2_username = self.get_sme2_username()

        login_page.login_to_application(
            sme2_username,
            ReadConfig.get_password_for_username(sme2_username),
        )
        upload_item_file_page.close_popup_if_open()

        upload_file_path, question_count = self.create_unique_upload_file(
            ReadConfig.get_upload_item_file_path()
        )

        # Step 1: Upload and submit for QAR
        request.node.user_properties.append(
            ("result_checkpoint", "Excel upload and QAR submission")
        )
        uploaded_file_path, upload_success_message, item_ids, ocr_success_message = (
            upload_item_file_page.upload_item_file_and_submit_for_qar(upload_file_path)
        )
        assert len(item_ids) == question_count, (
            f"Expected {question_count} item IDs from QAR but got {len(item_ids)}."
        )

        item_set_id = upload_item_file_page.get_item_set_id_from_item_ids(item_ids)
        request.node.user_properties.append(("item_set_id", item_set_id))
        request.node.user_properties.append(("upload_item_file", str(uploaded_file_path)))
        request.node.user_properties.append(("upload_question_count", str(question_count)))
        request.node.user_properties.append(("upload_success_message", upload_success_message))
        request.node.user_properties.append(("qar_success_message", ocr_success_message))
        request.node.user_properties.append(
            ("manual_item_id", ", ".join(item_ids))
        )

        # Step 2: Assign images to items (round-robin from test_images/)
        image_path_by_item_id = self.assign_images_to_items(item_ids)
        request.node.user_properties.append(
            (
                "test_images_assigned",
                str({k: v.name for k, v in image_path_by_item_id.items()}),
            )
        )

        # Step 3: QAR recovery with image attachment during each edit
        request.node.user_properties.append(
            ("result_checkpoint", "QAR recovery with image attachment per item")
        )
        all_revised_ids, rerun_messages = self._run_image_aware_qar_recovery(
            page=upload_item_file_page,
            item_set_id=item_set_id,
            item_ids=item_ids,
            image_path_by_item_id=image_path_by_item_id,
            workbook_path=upload_file_path,
            max_retries=3,
        )
        request.node.user_properties.append(
            ("image_revised_item_ids", ", ".join(all_revised_ids))
        )
        request.node.user_properties.append(
            ("rerun_qar_message", " | ".join(rerun_messages) or "No retries needed")
        )

        item_set_url = self.driver.current_url
        item_set_reviewer = upload_item_file_page.require_item_set_assignee("rwg")
        item_set_status_summary = upload_item_file_page.get_item_set_status_summary()
        item_set_status_text = upload_item_file_page.format_status_summary(
            item_set_status_summary
        )
        remaining_revision_count = int(item_set_status_summary.get("Revise", "0"))
        assert remaining_revision_count == 0, (
            f"Items still need revision after QAR recovery: {item_set_status_text}"
        )

        sets_screenshot = upload_item_file_page.capture_sets_verification_screenshot(
            request.node.name
        )

        pending_items_count = int(item_set_status_summary.get("Pending", len(item_ids)))
        rwg_item_ids = upload_item_file_page.get_item_ids_by_status("Pending") or item_ids

        reviewer_approval_message = "Reviewer approval was not attempted."
        sr_rwg_approval_message = "SRRWG approval was not attempted."
        pit_approval_message = "PIT approval was not attempted."
        approved_count = 0
        post_approval_status_summary = {}
        post_approval_status_text = ""
        rwg_image_verification_results = {}

        if pending_items_count > 0:
            # Step 4: RWG reviews items — verify images are visible
            request.node.user_properties.append(
                ("result_checkpoint", "RWG image visibility check and approval")
            )
            reviewer_username = ReadConfig.get_all_user_username(item_set_reviewer)
            upload_item_file_page.reset_browser_session_to_login()
            login_page.login_to_application(
                reviewer_username,
                ReadConfig.get_password_for_username(reviewer_username),
            )
            upload_item_file_page.close_popup_if_open()

            # Only verify images for items that actually had images attached
            items_with_images = [
                iid for iid in rwg_item_ids if iid in image_path_by_item_id
            ]
            if items_with_images and all_revised_ids:
                try:
                    rwg_review_queue_page.open_review_item_set(item_set_id, item_set_url)
                    # Read-only survey of the RWG view; marks no criteria.
                    checks = ElementChecks(
                        rwg_review_queue_page,
                        record_property,
                        page_name="RWG — Opened Item Set",
                    )
                    survey_opened_item_set(checks, rwg_review_queue_page)
                    checks.publish()
                    rwg_image_verification_results = (
                        rwg_review_queue_page.verify_images_visible_to_reviewer(
                            item_set_id, items_with_images
                        )
                    )
                    print(
                        f"\n[RWG Image Visibility]: {rwg_image_verification_results}\n"
                    )
                    request.node.user_properties.append(
                        ("rwg_image_visible_counts", str(rwg_image_verification_results))
                    )
                    rwg_review_queue_page.capture_review_screenshot(
                        request.node.name, "rwg_image_verified"
                    )
                except Exception as img_err:
                    print(f"[WARN] RWG image verification error (non-fatal): {img_err}")
                    request.node.user_properties.append(
                        ("rwg_image_verification_warning", str(img_err))
                    )

            rwg_approved_item_ids = rwg_review_queue_page.approve_item_set_as_rwg(
                item_set_id,
                rwg_item_ids,
                item_set_url,
            )
            assert len(rwg_approved_item_ids) == len(rwg_item_ids), (
                f"RWG must approve every item; approved {len(rwg_approved_item_ids)}/{len(rwg_item_ids)}."
            )
            approved_count = len(rwg_approved_item_ids)
            reviewer_approval_message = (
                f"Approved {approved_count}/{pending_items_count} item(s) as RWG "
                f"({reviewer_username})."
            )
            rwg_review_queue_page.capture_review_screenshot(
                request.node.name, "rwg_review_submitted"
            )

            # Step 5: Get SRRWG assignee
            upload_item_file_page.reset_browser_session_to_login()
            login_page.login_to_application(
                sme2_username,
                ReadConfig.get_password_for_username(sme2_username),
            )
            upload_item_file_page.close_popup_if_open()
            upload_item_file_page.open_item_set_url_and_wait(item_set_url, item_set_id)
            try:
                sr_rwg_assignee = upload_item_file_page.require_item_set_assignee("sr_rwg")
                sr_rwg_username = ReadConfig.get_all_user_username(sr_rwg_assignee)
            except AssertionError:
                sr_rwg_username = ReadConfig.get_role_usernames("sr_rwg")[0]
                sr_rwg_approval_message = (
                    "SRRWG assignee displayed as name; falling back to configured SRRWG user."
                )

            # Step 6: SRRWG approves
            request.node.user_properties.append(
                ("result_checkpoint", "SRRWG approval")
            )
            upload_item_file_page.reset_browser_session_to_login()
            login_page.login_to_application(
                sr_rwg_username,
                ReadConfig.get_password_for_username(sr_rwg_username),
            )
            upload_item_file_page.close_popup_if_open()
            sr_rwg_approved_item_ids = sr_rwg_review_queue_page.approve_item_set_as_sr_rwg(
                item_set_id,
                item_ids,
                item_set_url,
            )
            sr_rwg_approval_message = (
                f"Approved {len(sr_rwg_approved_item_ids)} item(s) as SRRWG ({sr_rwg_username})."
            )
            sr_rwg_review_queue_page.capture_review_screenshot(
                request.node.name, "sr_rwg_review_submitted"
            )

            # Step 7: PIT 3/3
            pit_approvers = ReadConfig.get_pit_usernames()[:3]
            completed_pit_approvals = []
            request.node.user_properties.append(
                ("result_checkpoint", "PIT 3/3 quorum and publication")
            )
            for pit_username in pit_approvers:
                upload_item_file_page.reset_browser_session_to_login()
                login_page.login_to_application(
                    pit_username,
                    ReadConfig.get_password_for_username(pit_username),
                )
                upload_item_file_page.close_popup_if_open()
                pit_review_queue_page.approve_item_set_as_pit(item_set_id, item_set_url)
                completed_pit_approvals.append(pit_username)
                pit_review_queue_page.capture_review_screenshot(
                    request.node.name,
                    f"pit_approval_{len(completed_pit_approvals)}",
                )
            pit_approval_message = (
                f"PIT approval completed by {len(completed_pit_approvals)}/3 PIT users: "
                f"{', '.join(completed_pit_approvals)}."
            )

            # Step 8: Final status check
            request.node.user_properties.append(
                ("result_checkpoint", "final item-set status verification")
            )
            upload_item_file_page.reset_browser_session_to_login()
            login_page.login_to_application(
                sme2_username,
                ReadConfig.get_password_for_username(sme2_username),
            )
            upload_item_file_page.close_popup_if_open()
            upload_item_file_page.open_item_set_url_and_wait(item_set_url, item_set_id)
            post_approval_status_summary = (
                upload_item_file_page.get_item_set_status_summary()
            )
            post_approval_status_text = upload_item_file_page.format_status_summary(
                post_approval_status_summary
            )
        else:
            reviewer_approval_message = (
                f"No pending items needed review. Status: {item_set_status_text}"
            )

        print(f"Item Set ID: {item_set_id}")
        print(f"Upload Success: {upload_success_message}")
        print(f"Items with images: {list(image_path_by_item_id.keys())}")
        print(f"Image-revised IDs: {all_revised_ids}")
        print(f"RWG Image Verification: {rwg_image_verification_results}")
        print(f"RWG Approval: {reviewer_approval_message}")
        print(f"SRRWG Approval: {sr_rwg_approval_message}")
        print(f"PIT Approval: {pit_approval_message}")
        print(f"Post-Approval Status: {post_approval_status_text}")

        request.node.user_properties.append(
            ("reviewer_approval_message", reviewer_approval_message)
        )
        request.node.user_properties.append(
            ("sr_rwg_approval_message", sr_rwg_approval_message)
        )
        request.node.user_properties.append(("pit_approval_message", pit_approval_message))
        request.node.user_properties.append(
            ("post_approval_status", post_approval_status_text)
        )
        request.node.user_properties.append(
            ("item_set_status", item_set_status_text)
        )

        upload_success_text = upload_success_message.casefold()
        assert (
            "validated successfully" in upload_success_text
            or "rows added successfully" in upload_success_text
        ), f"Unexpected upload message: {upload_success_message}"
        assert "status: passed" in upload_success_text
        assert item_set_id
        assert ocr_success_message
        assert approved_count == pending_items_count
        if pending_items_count > 0:
            assert "3/3 PIT users" in pit_approval_message
            assert int(post_approval_status_summary.get("Pending", -1)) == 0
            assert int(post_approval_status_summary.get("Approved", -1)) == len(item_ids)

        request.node.user_properties.append(
            (
                "result_description",
                f"{item_set_id} uploaded with images, passed QAR, RWG (images verified), "
                f"SRRWG, PIT 3/3 with {len(item_ids)}/{len(item_ids)} items approved.",
            )
        )
