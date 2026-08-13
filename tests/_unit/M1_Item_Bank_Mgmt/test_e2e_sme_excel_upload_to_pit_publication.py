from pathlib import Path
from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.common.login_page import LoginPage
from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from utilities.item_bank_workbook_builder import build_item_workbook, populate_item_workbook
from utilities.logger import LogGenerator
from utilities.qar_recovery import recover_qar_need_improvement_items
from utilities.read_config import ReadConfig


@pytest.mark.flaky(reruns=1, reruns_delay=5)
@pytest.mark.usefixtures("setup")
class TestE2ESMEExcelUploadToPITPublication:
    logger = LogGenerator.loggen()

    @staticmethod
    def get_sme2_username():
        try:
            return ReadConfig.get_all_user_username("sme2")
        except RuntimeError:
            return ReadConfig.get_sme2_username()

    @classmethod
    def update_upload_file_questions(cls, upload_file):
        summaries = populate_item_workbook(upload_file, count=4)
        question_counts = {len(items) for items in summaries.values()}
        assert question_counts == {4}
        return question_counts.pop()

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

    def test_e2e_sme_excel_upload_qar_rwg_srrwg_pit_publish(self, request):
        request.node.user_properties.append(
            ("result_checkpoint", "fresh SME Excel upload and QAR validation")
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
            ReadConfig.get_all_users_password(),
        )

        upload_item_file_page.close_popup_if_open()
        upload_file_path, question_count = self.create_unique_upload_file(
            ReadConfig.get_upload_item_file_path()
        )
        uploaded_file_path, upload_success_message, item_ids, ocr_success_message = (
            upload_item_file_page.upload_item_file_and_submit_for_qar(upload_file_path)
        )
        assert len(item_ids) == question_count, (
            f"Fresh SME upload expected {question_count} item IDs but QAR returned "
            f"{len(item_ids)}; refusing to reuse or merge a stale upload."
        )
        item_set_id = upload_item_file_page.get_item_set_id_from_item_ids(item_ids)
        qar_recovery = recover_qar_need_improvement_items(
            page=upload_item_file_page,
            item_set_id=item_set_id,
            item_ids=item_ids,
            workbook_path=upload_file_path,
            max_retries=3,
            run_label="SME-E2E",
        )
        request.node.user_properties.append(
            ("initial_qar_retries", str(qar_recovery.retry_count))
        )
        item_set_url = self.driver.current_url
        item_set_reviewer = upload_item_file_page.require_item_set_assignee("rwg")
        item_set_status_summary = upload_item_file_page.get_item_set_status_summary()
        item_set_status_text = upload_item_file_page.format_status_summary(item_set_status_summary)
        item_ids_text = ", ".join(item_ids) if item_ids else "Not captured"
        revised_item_ids = []
        rerun_qar_message = " | ".join(qar_recovery.rerun_messages)

        sets_verification_screenshot = upload_item_file_page.capture_sets_verification_screenshot(
            request.node.name
        )
        reviewer_approval_message = "Reviewer approval was not attempted."
        reviewer_approval_screenshot = sets_verification_screenshot
        sr_rwg_approval_message = "SRRWG approval was not attempted."
        pit_approval_message = "PIT approval was not attempted."
        approved_count = 0
        post_approval_status_summary = {}
        post_approval_status_text = ""

        pending_items_count = int(item_set_status_summary.get("Pending", len(item_ids)))
        rwg_item_ids = upload_item_file_page.get_item_ids_by_status("Pending") or item_ids
        remaining_revision_count = int(item_set_status_summary.get("Revise", "0"))

        assert remaining_revision_count == 0, (
            "Item set still has item(s) needing revision after QAR re-run. "
            f"Status: {item_set_status_text}"
        )

        if pending_items_count > 0:
            request.node.user_properties.append(
                ("result_checkpoint", "RWG approval of all fresh SME items")
            )
            reviewer_username = ReadConfig.get_all_user_username(item_set_reviewer)
            rwg_approved_item_ids = []
            upload_item_file_page.reset_browser_session_to_login()
            login_page.login_to_application(
                reviewer_username,
                ReadConfig.get_all_users_password(),
            )
            upload_item_file_page.close_popup_if_open()
            rwg_approved_item_ids = rwg_review_queue_page.approve_item_set_as_rwg(
                item_set_id,
                rwg_item_ids,
                item_set_url,
            )
            assert len(rwg_approved_item_ids) == len(rwg_item_ids), (
                "RWG must approve every item in this E2E flow; "
                f"approved {len(rwg_approved_item_ids)}/{len(rwg_item_ids)}."
            )
            item_set_reviewer = reviewer_username.split("@", 1)[0]
            approved_count = len(rwg_approved_item_ids)
            reviewer_approval_message = (
                f"Approved {approved_count}/{pending_items_count} pending item(s) as {item_set_reviewer} "
                f"({reviewer_username})."
            )
            reviewer_approval_screenshot = rwg_review_queue_page.capture_review_screenshot(
                request.node.name,
                "rwg_review_submitted",
            )

            upload_item_file_page.reset_browser_session_to_login()
            login_page.login_to_application(
                sme2_username,
                ReadConfig.get_all_users_password(),
            )
            upload_item_file_page.close_popup_if_open()
            upload_item_file_page.open_item_set_url_and_wait(item_set_url, item_set_id)
            try:
                sr_rwg_assignee = upload_item_file_page.require_item_set_assignee("sr_rwg")
                sr_rwg_username = ReadConfig.get_all_user_username(sr_rwg_assignee)
            except AssertionError:
                sr_rwg_username = ReadConfig.get_role_usernames("sr_rwg")[0]
                sr_rwg_assignee = sr_rwg_username.split("@", 1)[0]
                sr_rwg_approval_message = (
                    "SRRWG assignee display name was shown instead of an automation key; "
                    f"falling back to configured SRRWG user {sr_rwg_username}."
                )

            upload_item_file_page.reset_browser_session_to_login()
            request.node.user_properties.append(
                ("result_checkpoint", "SRRWG approval and set-level submission")
            )
            login_page.login_to_application(
                sr_rwg_username,
                ReadConfig.get_all_users_password(),
            )
            upload_item_file_page.close_popup_if_open()
            sr_rwg_approved_item_ids = sr_rwg_review_queue_page.approve_item_set_as_sr_rwg(
                item_set_id,
                item_ids,
                item_set_url,
            )

            sr_rwg_approval_message = (
                f"Approved {len(sr_rwg_approved_item_ids)} item(s) as SRRWG "
                f"({sr_rwg_username})."
            )
            reviewer_approval_screenshot = sr_rwg_review_queue_page.capture_review_screenshot(
                request.node.name,
                "sr_rwg_review_submitted",
            )

            # Item sets are allotted to specific PIT users out of the full PIT
            # pool (same round-robin allocation as RWG), so a fixed "first 3"
            # slice can include PIT users this item set was never routed to.
            # Try every configured PIT user and skip ones the item set was not
            # allotted to, until 3 successful quorum approvals are collected.
            pit_candidates = ReadConfig.get_pit_usernames()
            completed_pit_approvals = []
            skipped_pit_users = []
            request.node.user_properties.append(
                ("result_checkpoint", "PIT 3/3 quorum and publication")
            )
            for pit_username in pit_candidates:
                if len(completed_pit_approvals) == 3:
                    break
                upload_item_file_page.reset_browser_session_to_login()
                login_page.login_to_application(
                    pit_username,
                    ReadConfig.get_all_users_password(),
                )
                upload_item_file_page.close_popup_if_open()
                try:
                    pit_review_queue_page.approve_item_set_as_pit(item_set_id, item_set_url)
                except TimeoutException:
                    skipped_pit_users.append(pit_username)
                    continue
                completed_pit_approvals.append(pit_username)
                reviewer_approval_screenshot = pit_review_queue_page.capture_review_screenshot(
                    request.node.name,
                    f"pit_approval_{len(completed_pit_approvals)}",
                )

            assert len(completed_pit_approvals) == 3, (
                f"Only {len(completed_pit_approvals)}/3 PIT users could approve this item set. "
                f"Tried and skipped (not allotted): {', '.join(skipped_pit_users) or 'none'}."
            )
            pit_approval_message = (
                f"PIT approval completed by {len(completed_pit_approvals)}/3 PIT users: "
                f"{', '.join(completed_pit_approvals)}."
            )
            if skipped_pit_users:
                pit_approval_message += (
                    f" Skipped (item set not allotted to them): {', '.join(skipped_pit_users)}."
                )

            upload_item_file_page.reset_browser_session_to_login()
            request.node.user_properties.append(
                ("result_checkpoint", "final SME item-set status verification")
            )
            login_page.login_to_application(
                sme2_username,
                ReadConfig.get_all_users_password(),
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
                f"No pending items needed reviewer approval. Status: {item_set_status_text}"
            )

        print(f"Uploaded Item File: {uploaded_file_path}")
        print(f"Uploaded Question Count: {question_count}")
        print(f"Upload Success Message: {upload_success_message}")
        print(f"Item Set ID: {item_set_id}")
        print(f"Uploaded Item IDs: {item_ids_text}")
        print(f"OCR Success Message: {ocr_success_message}")
        print(f"Item Set Reviewer/RWG: {item_set_reviewer}")
        print(f"Item Set Status: {item_set_status_text}")
        print(f"Revised Item IDs: {', '.join(revised_item_ids) if revised_item_ids else 'None'}")
        print(f"Re-run QAR Message: {rerun_qar_message or 'Not required'}")
        print(f"Reviewer Approval: {reviewer_approval_message}")
        print(f"SRRWG Approval: {sr_rwg_approval_message}")
        print(f"PIT Approval: {pit_approval_message}")
        print(f"Post Approval Status: {post_approval_status_text}")
        request.node.user_properties.append(("upload_item_file", str(uploaded_file_path)))
        request.node.user_properties.append(("upload_question_count", str(question_count)))
        request.node.user_properties.append(("upload_success_message", upload_success_message))
        request.node.user_properties.append(("item_set_id", item_set_id))
        request.node.user_properties.append(("manual_item_id", item_ids_text))
        request.node.user_properties.append(("qar_success_message", ocr_success_message))
        request.node.user_properties.append(("item_set_reviewer", item_set_reviewer))
        request.node.user_properties.append(("item_set_status", item_set_status_text))
        request.node.user_properties.append(("revised_item_ids", ", ".join(revised_item_ids)))
        request.node.user_properties.append(("rerun_qar_message", rerun_qar_message))
        request.node.user_properties.append(("reviewer_approval_message", reviewer_approval_message))
        request.node.user_properties.append(("sr_rwg_approval_message", sr_rwg_approval_message))
        request.node.user_properties.append(("pit_approval_message", pit_approval_message))
        request.node.user_properties.append(("post_approval_status", post_approval_status_text))
        request.node.user_properties.append(("qar_success_screenshot", reviewer_approval_screenshot))

        upload_success_text = upload_success_message.casefold()
        assert (
            "validated successfully" in upload_success_text
            or "rows added successfully" in upload_success_text
        ), f"Unexpected upload success message: {upload_success_message}"
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
                f"Fresh {item_set_id} passed QAR, RWG, SRRWG, PIT 3/3, and final publication with {len(item_ids)}/{len(item_ids)} items approved.",
            )
        )
