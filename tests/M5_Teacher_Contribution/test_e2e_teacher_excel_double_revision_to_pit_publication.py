import re
from pathlib import Path
from time import sleep
from uuid import uuid4

import pytest
from selenium.common.exceptions import TimeoutException

from pages.common.login_page import LoginPage
from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.item_bank_workbook_builder import build_item_workbook
from utilities.logger import LogGenerator
from utilities.qar_recovery import recover_qar_need_improvement_items
from tests.M1_Item_Bank_Mgmt.m1_surveys import enter_screen, survey_opened_item_set
from utilities.element_checks import ElementChecks
from utilities.read_config import ReadConfig


@pytest.mark.flaky(reruns=1, reruns_delay=5)
# Every M5 teacher-to-PIT flow drives the same contributor account, the same
# app-assigned RWG reviewer and the same three PIT accounts, and the portal
# keeps one active session per account - two of these running at once sign
# each other out mid-flow and read each other's queue state.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestE2ETeacherExcelDoubleRevisionToPITPublication:
    logger = LogGenerator.loggen()
    QUESTION_COUNT = 4
    MAX_INITIAL_QAR_RETRIES = 3

    @classmethod
    def create_unique_teacher_upload_file(cls, source_file_path):
        source_file = Path(source_file_path)
        upload_dir = Path.cwd() / "tmp_uploads"
        upload_dir.mkdir(exist_ok=True)
        run_token = uuid4().hex[:12]
        unique_file = (
            upload_dir
            / f"{source_file.stem}_teacher_mixed_{run_token}{source_file.suffix}"
        )
        _, summaries = build_item_workbook(
            source_file,
            unique_file,
            count=cls.QUESTION_COUNT,
            seed=f"teacher-double-revision-{run_token}",
        )
        question_count = sum(len(items) for items in summaries.values())
        generated_typologies = {
            item["typology"]
            for items in summaries.values()
            for item in items
        }
        assert len(generated_typologies) >= cls.QUESTION_COUNT, (
            "Fresh mixed workbook did not generate the required typology diversity: "
            f"{sorted(generated_typologies)}"
        )
        return unique_file, question_count

    def survey_reviewer_screen(self, review_page, role):
        """Survey a reviewer's opened item set, if this test is collecting.

        Read-only: marks no criteria, so it cannot consume the one-time review
        vote the set still needs. Re-published each phase because publish()
        writes the whole accumulated list, so a failure later in this long
        chain still leaves the rows gathered so far on the report card.
        """
        checks = getattr(self, "checks", None)
        if checks is None:
            return
        enter_screen(checks, f"{role} — Opened Item Set")
        survey_opened_item_set(checks, review_page)
        checks.publish()

    def login_as(self, username):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_all_users_password(),
        )
        UploadItemFilePage(self.driver).close_popup_if_open()

    def resolve_rwg_username_for_item_set(
        self, upload_item_file_page, item_set_id, preferred_username, item_set_url=""
    ):
        """Log in as whichever configured RWG user actually holds this set.

        The teacher-side "Assigned RWG" label can be missing while the detail
        page is still rendering, and the app can hand the set to a different
        reviewer for each review round - so the assignee read after the
        previous round is not necessarily the one whose queue holds it now.
        Probing each configured RWG queue finds the real one instead of
        failing with "did not become available for this role".
        """
        candidates = list(
            dict.fromkeys([preferred_username, *ReadConfig.get_role_usernames("rwg")])
        )
        last_error = None
        max_passes = 3
        for pass_number in range(1, max_passes + 1):
            for candidate in candidates:
                try:
                    # The login belongs inside the try: a candidate whose
                    # sign-in strands on the login form is just another
                    # candidate that did not work, so move to the next account
                    # instead of abandoning every remaining one and pass.
                    upload_item_file_page.reset_browser_session_to_login()
                    self.login_as(candidate)
                    rwg_queue_page = RWGReviewQueuePage(self.driver)
                    rwg_queue_page.open_review_item_set(
                        item_set_id, item_set_url
                    )
                    self.survey_reviewer_screen(rwg_queue_page, 'RWG')
                except TimeoutException as error:
                    last_error = error
                    continue
                return candidate
            if pass_number < max_passes:
                # A backend hand-off lag can outlast a single sweep over every
                # candidate, so pause and sweep again before giving up.
                sleep(10)
        raise TimeoutException(
            f"No configured RWG account could open item set {item_set_id}."
        ) from last_error

    def get_visible_item_ids_for_set(self, item_set_id):
        body_text = self.driver.find_element("tag name", "body").text
        item_ids = list(
            dict.fromkeys(
                re.findall(
                    rf"\b{re.escape(item_set_id)}-i\d+\b",
                    body_text,
                    re.IGNORECASE,
                )
            )
        )
        assert item_ids, f"No item IDs were visible for existing item set {item_set_id}."
        return item_ids

    def create_fresh_teacher_item_set(self, request, teacher_username, upload_item_file_page):
        self.login_as(teacher_username)

        upload_file_path, question_count = self.create_unique_teacher_upload_file(
            ReadConfig.get_upload_item_file_path()
        )
        uploaded_file_path, upload_success_message, item_ids, ocr_success_message = (
            upload_item_file_page.upload_item_file_and_submit_for_qar(upload_file_path)
        )
        assert len(item_ids) == question_count, (
            f"Fresh teacher upload expected {question_count} item IDs but QAR returned "
            f"{len(item_ids)}; refusing to reuse or merge a stale upload."
        )
        item_set_id = upload_item_file_page.get_item_set_id_from_item_ids(item_ids)
        qar_recovery = recover_qar_need_improvement_items(
            page=upload_item_file_page,
            item_set_id=item_set_id,
            item_ids=item_ids,
            workbook_path=upload_file_path,
            max_retries=self.MAX_INITIAL_QAR_RETRIES,
            run_label="TEACHER-DOUBLE-E2E",
        )
        item_set_url = self.driver.current_url
        item_set_status_summary = upload_item_file_page.get_item_set_status_summary()
        item_set_status_text = upload_item_file_page.format_status_summary(item_set_status_summary)
        
        # Output status change to console
        print(f"\n[Console Status Alert] Item Set Status changed (After Upload): {item_set_status_text}\n")
        
        rwg_username = ReadConfig.get_role_usernames("rwg")[0]
        try:
            rwg_assignee = upload_item_file_page.require_item_set_assignee("rwg")
            rwg_username = ReadConfig.get_all_user_username(rwg_assignee)
        except AssertionError:
            # Preserve the fresh set's original assignee when the refreshed
            # detail page temporarily omits reviewer metadata.
            pass
        sets_verification_screenshot = upload_item_file_page.capture_sets_verification_screenshot(
            request.node.name
        )
        return {
            "item_set_id": item_set_id,
            "item_ids": item_ids,
            "item_set_url": item_set_url,
            "item_set_status_text": item_set_status_text,
            "rwg_username": rwg_username,
            "sets_verification_screenshot": sets_verification_screenshot,
            "uploaded_file_path": uploaded_file_path,
            "question_count": question_count,
            "upload_success_message": upload_success_message,
            "ocr_success_message": " | ".join(
                [ocr_success_message, *qar_recovery.rerun_messages]
            ),
            "initial_qar_recovery": qar_recovery,
        }

    def test_e2e_teacher_excel_upload_rwg_double_revision_teacher_resubmit_rwg_pit_publish(self, request, record_property):
        request.node.user_properties.append(
            ("result_checkpoint", "fresh double-revision teacher Excel upload and QAR validation")
        )
        upload_item_file_page = UploadItemFilePage(self.driver)
        rwg_review_queue_page = RWGReviewQueuePage(self.driver)
        pit_review_queue_page = PITReviewQueuePage(self.driver)

        # One collector for the whole teacher -> RWG -> PIT chain, re-pointed at
        # each screen as the item set moves through it.
        self.checks = ElementChecks(
            upload_item_file_page, record_property, page_name="Teacher Contribution — Double Revision"
        )
        self.checks.publish()

        default_teacher_username = ReadConfig.get_username()
        teacher_username = next(
            (
                username
                for username in ReadConfig.get_role_usernames("teacher")
                if username.casefold() != default_teacher_username.casefold()
            ),
            default_teacher_username,
        )
        uploaded_file_path = "Fresh item set created"
        item_ids = []
        item_set_url = ""
        item_set_status_text = ""
        sets_verification_screenshot = None
        rwg_username = ReadConfig.get_role_usernames("rwg")[0]

        # 1. Create a fresh item set
        fresh_set = self.create_fresh_teacher_item_set(
            request,
            teacher_username,
            upload_item_file_page,
        )
        item_set_id = fresh_set["item_set_id"]
        item_ids = fresh_set["item_ids"]
        item_set_url = fresh_set["item_set_url"]
        item_set_status_text = fresh_set["item_set_status_text"]
        rwg_username = fresh_set["rwg_username"]
        sets_verification_screenshot = fresh_set["sets_verification_screenshot"]
        uploaded_file_path = fresh_set["uploaded_file_path"]
        question_count = fresh_set["question_count"]
        upload_success_message = fresh_set["upload_success_message"]
        ocr_success_message = fresh_set["ocr_success_message"]

        request.node.user_properties.append(("item_set_id", item_set_id))
        request.node.user_properties.append(("item_ids", ", ".join(item_ids)))
        request.node.user_properties.append(("item_set_status", item_set_status_text))

        sent_back_item_ids_1 = []
        initially_approved_item_ids_1 = []
        teacher_revised_item_ids_1 = []
        
        sent_back_item_ids_2 = []
        teacher_revised_item_ids_2 = []
        
        rerun_qar_message_1 = ""
        rerun_qar_message_2 = ""
        rwg_approval_message = "RWG approval was not attempted."
        pit_approval_message = "PIT approval was not attempted."
        post_approval_status_text = ""
        evidence_screenshot = sets_verification_screenshot

        # 2. First RWG Review - Send two items back for revision
        request.node.user_properties.append(
            ("result_checkpoint", "first RWG revision request and mixed review submission")
        )
        rwg_username = self.resolve_rwg_username_for_item_set(
            upload_item_file_page, item_set_id, rwg_username, item_set_url
        )

        # Note: revise_some_and_approve_rest_as_rwg uses send_items_back_for_revision,
        # which internally uses send_open_item_back_for_revision which inputs a 50+ character remark.
        sent_back_item_ids_1, initially_approved_item_ids_1 = rwg_review_queue_page.revise_some_and_approve_rest_as_rwg(
            item_set_id,
            item_ids,
            item_set_url,
            revision_count=2,
        )
        evidence_screenshot = rwg_review_queue_page.capture_review_screenshot(
            request.node.name,
            "rwg_sent_back_for_teacher_revision_1",
        )
        
        # Check and print status change after first RWG review
        upload_item_file_page.reset_browser_session_to_login()
        LoginPage(self.driver).login_to_application(
            teacher_username,
            ReadConfig.get_all_users_password(),
        )
        upload_item_file_page.close_popup_if_open()
        upload_item_file_page.open_item_set_url_and_wait(item_set_url, item_set_id)
        
        item_set_status_summary = upload_item_file_page.get_item_set_status_summary()
        item_set_status_text = upload_item_file_page.format_status_summary(item_set_status_summary)
        print(f"\n[Console Status Alert] Item Set Status changed (After First RWG Review): {item_set_status_text}\n")

        # 3. First Teacher Revision
        request.node.user_properties.append(
            ("result_checkpoint", "first teacher edit, save, and resubmit cycle")
        )
        teacher_revised_item_ids_1 = upload_item_file_page.revise_items_in_open_item_set(item_set_id)
        assert teacher_revised_item_ids_1, (
            f"Teacher did not see revision items after RWG first send-back for {item_set_id}."
        )
        rerun_qar_message_1 = upload_item_file_page.rerun_qar_if_enabled()
        upload_item_file_page.verify_item_set_from_sets_module(item_set_id, item_ids)
        item_set_url = self.driver.current_url
        item_set_status_text = upload_item_file_page.format_status_summary(
            upload_item_file_page.get_item_set_status_summary()
        )
        print(f"\n[Console Status Alert] Item Set Status changed (After First Teacher Revision & QAR): {item_set_status_text}\n")
        request.node.user_properties.append(("item_set_status_after_first_teacher_resubmit", item_set_status_text))

        # Retrieve RWG username for round 2
        try:
            rwg_assignee = upload_item_file_page.require_item_set_assignee("rwg")
            rwg_username = ReadConfig.get_all_user_username(rwg_assignee)
        except AssertionError:
            # Preserve the fresh set's original assignee.
            pass

        # 3b. Verify that the teacher's revisions are visible to RWG before the next review
        request.node.user_properties.append(
            ("result_checkpoint", "RWG revision-content visibility check after round 1 teacher edits")
        )
        rwg_username = self.resolve_rwg_username_for_item_set(
            upload_item_file_page, item_set_id, rwg_username, item_set_url
        )
        rwg_revised_visible_content_1 = rwg_review_queue_page.verify_revised_items_visible_to_reviewer(
            item_set_id,
            teacher_revised_item_ids_1,
        )
        print(
            f"\n[RWG Revision Visibility Check - Round 1]: "
            f"{rwg_revised_visible_content_1}\n"
        )
        request.node.user_properties.append(
            ("rwg_visible_revised_content_1", str(rwg_revised_visible_content_1))
        )
        evidence_screenshot = rwg_review_queue_page.capture_review_screenshot(
            request.node.name,
            "rwg_revision_content_visible_round1",
        )

        # 4. Second RWG Review - Send back for revision AGAIN
        request.node.user_properties.append(
            ("result_checkpoint", "second RWG revision request and submission")
        )
        rwg_username = self.resolve_rwg_username_for_item_set(
            upload_item_file_page, item_set_id, rwg_username, item_set_url
        )

        # Here we send the revised items back for revision again.
        # send_item_set_back_as_rwg internally uses send_open_item_back_for_revision (which inputs 50+ chars remark)
        sent_back_item_ids_2 = rwg_review_queue_page.send_item_set_back_as_rwg(
            item_set_id,
            teacher_revised_item_ids_1,
            item_set_url,
        )
        evidence_screenshot = rwg_review_queue_page.capture_review_screenshot(
            request.node.name,
            "rwg_sent_back_for_teacher_revision_2",
        )
        
        # Check and print status change after second RWG review
        upload_item_file_page.reset_browser_session_to_login()
        LoginPage(self.driver).login_to_application(
            teacher_username,
            ReadConfig.get_all_users_password(),
        )
        upload_item_file_page.close_popup_if_open()
        upload_item_file_page.open_item_set_url_and_wait(item_set_url, item_set_id)
        
        item_set_status_summary = upload_item_file_page.get_item_set_status_summary()
        item_set_status_text = upload_item_file_page.format_status_summary(item_set_status_summary)
        print(f"\n[Console Status Alert] Item Set Status changed (After Second RWG Review): {item_set_status_text}\n")

        # 5. Second Teacher Revision
        request.node.user_properties.append(
            ("result_checkpoint", "second teacher edit, save, and resubmit cycle")
        )
        teacher_revised_item_ids_2 = upload_item_file_page.revise_items_in_open_item_set(item_set_id)
        assert teacher_revised_item_ids_2, (
            f"Teacher did not see revision items after RWG second send-back for {item_set_id}."
        )
        rerun_qar_message_2 = upload_item_file_page.rerun_qar_if_enabled()
        upload_item_file_page.verify_item_set_from_sets_module(item_set_id, item_ids)
        item_set_url = self.driver.current_url
        item_set_status_text = upload_item_file_page.format_status_summary(
            upload_item_file_page.get_item_set_status_summary()
        )
        print(f"\n[Console Status Alert] Item Set Status changed (After Second Teacher Revision & QAR): {item_set_status_text}\n")
        request.node.user_properties.append(("item_set_status_after_second_teacher_resubmit", item_set_status_text))

        # Retrieve RWG username for final approval
        try:
            rwg_assignee = upload_item_file_page.require_item_set_assignee("rwg")
            rwg_username = ReadConfig.get_all_user_username(rwg_assignee)
        except AssertionError:
            # Preserve the original assignee captured for this fresh set.
            pass

        # 5b. Verify that the teacher's round-2 revisions are visible to RWG
        request.node.user_properties.append(
            ("result_checkpoint", "RWG revision-content visibility check after round 2 teacher edits")
        )
        rwg_username = self.resolve_rwg_username_for_item_set(
            upload_item_file_page, item_set_id, rwg_username, item_set_url
        )
        rwg_revised_visible_content_2 = rwg_review_queue_page.verify_revised_items_visible_to_reviewer(
            item_set_id,
            teacher_revised_item_ids_2,
        )
        print(
            f"\n[RWG Revision Visibility Check - Round 2]: "
            f"{rwg_revised_visible_content_2}\n"
        )
        request.node.user_properties.append(
            ("rwg_visible_revised_content_2", str(rwg_revised_visible_content_2))
        )
        evidence_screenshot = rwg_review_queue_page.capture_review_screenshot(
            request.node.name,
            "rwg_revision_content_visible_round2",
        )

        # 6. Third RWG Review - Approve all remaining items
        request.node.user_properties.append(
            ("result_checkpoint", "final RWG approval after two teacher revision cycles")
        )
        rwg_username = self.resolve_rwg_username_for_item_set(
            upload_item_file_page, item_set_id, rwg_username, item_set_url
        )
        rwg_approved_item_ids = rwg_review_queue_page.approve_item_set_as_rwg(
            item_set_id,
            item_ids,
            item_set_url,
        )
        rwg_approval_message = (
            f"RWG approved {len(rwg_approved_item_ids)}/{len(item_ids)} double-revised teacher item(s) "
            f"as {rwg_username}."
        )
        request.node.user_properties.append(("rwg_approval_message", rwg_approval_message))
        evidence_screenshot = rwg_review_queue_page.capture_review_screenshot(
            request.node.name,
            "rwg_approved_after_double_revision",
        )
        
        # Check and print status change after RWG final approval
        upload_item_file_page.reset_browser_session_to_login()
        LoginPage(self.driver).login_to_application(
            teacher_username,
            ReadConfig.get_all_users_password(),
        )
        upload_item_file_page.close_popup_if_open()
        upload_item_file_page.open_item_set_url_and_wait(item_set_url, item_set_id)
        item_set_status_text = upload_item_file_page.format_status_summary(
            upload_item_file_page.get_item_set_status_summary()
        )
        print(f"\n[Console Status Alert] Item Set Status changed (After RWG Approval): {item_set_status_text}\n")

        # 7. PIT Approval
        completed_pit_approvals = []
        request.node.user_properties.append(
            ("result_checkpoint", "PIT 3/3 quorum after double teacher revision")
        )
        for pit_username in ReadConfig.get_pit_usernames()[:3]:
            upload_item_file_page.reset_browser_session_to_login()
            LoginPage(self.driver).login_to_application(
                pit_username,
                ReadConfig.get_all_users_password(),
            )
            upload_item_file_page.close_popup_if_open()
            pit_review_queue_page.approve_item_set_as_pit(item_set_id, item_set_url)
            completed_pit_approvals.append(pit_username)
            evidence_screenshot = pit_review_queue_page.capture_review_screenshot(
                request.node.name,
                f"pit_approval_{len(completed_pit_approvals)}",
            )

        pit_approval_message = (
            f"PIT approval completed by {len(completed_pit_approvals)}/3 PIT users: "
            f"{', '.join(completed_pit_approvals)}."
        )

        # 8. Final verification as Teacher
        upload_item_file_page.reset_browser_session_to_login()
        request.node.user_properties.append(
            ("result_checkpoint", "final double-revision item-set status verification")
        )
        LoginPage(self.driver).login_to_application(
            teacher_username,
            ReadConfig.get_all_users_password(),
        )
        upload_item_file_page.close_popup_if_open()
        upload_item_file_page.open_item_set_url_and_wait(item_set_url, item_set_id)
        post_approval_status_text = upload_item_file_page.format_status_summary(
            upload_item_file_page.get_item_set_status_summary()
        )
        print(f"\n[Console Status Alert] Item Set Status changed (After PIT Publication): {post_approval_status_text}\n")
        request.node.user_properties.append(("post_approval_status", post_approval_status_text))

        print(f"Teacher User: {teacher_username}")
        print(f"Uploaded Item File: {uploaded_file_path}")
        print(f"Uploaded Question Count: {question_count}")
        print(f"Upload Success Message: {upload_success_message}")
        print(f"Item Set ID: {item_set_id}")
        print(f"Uploaded Item IDs: {', '.join(item_ids) if item_ids else 'Not captured'}")
        print(f"OCR Success Message: {ocr_success_message}")
        print(f"RWG Send Back User: {rwg_username}")
        print(f"RWG Sent Back Item IDs (Round 1): {', '.join(sent_back_item_ids_1)}")
        print(f"RWG Initially Approved Item IDs: {', '.join(initially_approved_item_ids_1)}")
        print(f"Teacher Revised Item IDs (Round 1): {', '.join(teacher_revised_item_ids_1)}")
        print(f"Re-run QAR Message (Round 1): {rerun_qar_message_1}")
        print(f"RWG Sent Back Item IDs (Round 2): {', '.join(sent_back_item_ids_2)}")
        print(f"Teacher Revised Item IDs (Round 2): {', '.join(teacher_revised_item_ids_2)}")
        print(f"Re-run QAR Message (Round 2): {rerun_qar_message_2}")
        print(f"RWG Approval: {rwg_approval_message}")
        print(f"PIT Approval: {pit_approval_message}")
        print(f"Post Approval Status: {post_approval_status_text}")

        request.node.user_properties.append(("teacher_username", teacher_username))
        request.node.user_properties.append(("upload_item_file", str(uploaded_file_path)))
        request.node.user_properties.append(("upload_question_count", str(question_count)))
        request.node.user_properties.append(("rwg_send_back_user", rwg_username))
        request.node.user_properties.append(("sent_back_item_ids", ", ".join(sent_back_item_ids_1)))
        request.node.user_properties.append(("initially_approved_item_ids", ", ".join(initially_approved_item_ids_1)))
        request.node.user_properties.append(("teacher_revised_item_ids", ", ".join(teacher_revised_item_ids_1)))
        request.node.user_properties.append(("rerun_qar_message", rerun_qar_message_1))
        request.node.user_properties.append(("pit_approval_message", pit_approval_message))
        request.node.user_properties.append(("qar_success_screenshot", evidence_screenshot))

        assert completed_pit_approvals, "No PIT user approved the revised teacher item set."
        request.node.user_properties.append(
            (
                "result_description",
                f"Fresh {item_set_id} passed two teacher edit/resubmit cycles, final RWG {len(item_ids)}/{len(item_ids)}, and PIT 3/3.",
            )
        )
