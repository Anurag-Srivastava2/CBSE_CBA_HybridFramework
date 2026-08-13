"""Reusable setup and isolation support for PIT workflow E2E tests."""

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from pages.common.login_page import LoginPage
from pages.pit.review_queue_page import PITReviewQueuePage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from pages.sme.manual_item_page import ManualItemPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from utilities.item_bank_workbook_builder import build_item_workbook
from utilities.qar_recovery import recover_qar_need_improvement_items
from utilities.read_config import ReadConfig


@dataclass
class PITReadyItemSet:
    run_token: str
    workbook_path: Path
    item_set_id: str
    item_ids: list[str]
    item_set_url: str
    sme_username: str
    rwg_username: str
    sr_rwg_username: str
    pit_usernames: list[str]
    published: bool = False
    cleanup_messages: list[str] = field(default_factory=list)


class PITItemLifecycle:
    """Create a unique SME item set and progress it only as far as PIT."""

    def __init__(self, driver):
        self.driver = driver
        self.login_page = LoginPage(driver)
        self.sme_page = UploadItemFilePage(driver)

    @staticmethod
    def get_sme_username():
        # Worker-aware: under pytest-xdist this resolves to the account pinned to
        # this worker, so parallel workers never share one SME session/draft.
        # Serial runs still get CBSE_SME2_USERNAME.
        return ReadConfig.get_sme2_username()

    def login_as(self, username, reset=True):
        if reset:
            self.sme_page.reset_browser_session_to_login()
        else:
            self.driver.get(ReadConfig.get_base_url())
        self.login_page.login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        self.sme_page.close_popup_if_open()

    def create_unique_workbook(self, output_dir, count=3):
        run_token = uuid4().hex[:12]
        template_path = Path(ReadConfig.get_upload_item_file_path())
        workbook_path = Path(output_dir) / f"pit_sme_revision_{run_token}.xlsx"
        _, summaries = build_item_workbook(
            template_path,
            workbook_path,
            count=count,
            seed=f"pit-sme-revision-{run_token}",
        )
        assert summaries and {len(items) for items in summaries.values()} == {count}
        return run_token, workbook_path

    def create_and_progress_to_pit(self, output_dir, count=3, context_registry=None):
        run_token, workbook_path = self.create_unique_workbook(output_dir, count=count)
        sme_username = self.get_sme_username()
        self.login_as(sme_username, reset=False)

        _, _, item_ids, _ = self.sme_page.upload_item_file_and_submit_for_qar(
            workbook_path
        )
        assert len(item_ids) == count, (
            f"Unique PIT setup expected {count} items, but QAR returned {len(item_ids)}."
        )
        item_set_id = self.sme_page.get_item_set_id_from_item_ids(item_ids)
        qar_recovery = recover_qar_need_improvement_items(
            page=self.sme_page,
            item_set_id=item_set_id,
            item_ids=item_ids,
            workbook_path=workbook_path,
            max_retries=3,
            run_label="PIT-SME-E2E",
        )
        item_set_url = self.driver.current_url
        status_summary = self.sme_page.get_item_set_status_summary()
        blocked = sum(
            int(status_summary.get(label, 0))
            for label in (
                "Need Improvement",
                "Needs Improvement",
                "Needs Revision",
                "Revise",
            )
        )
        assert blocked == 0, (
            "Fresh PIT setup cannot progress while QAR has revision items: "
            f"{self.sme_page.format_status_summary(status_summary)}"
        )

        rwg_key = self.sme_page.require_item_set_assignee("rwg")
        rwg_username = ReadConfig.get_all_user_username(rwg_key)
        pit_usernames = ReadConfig.get_pit_usernames()[:3]
        assert len(pit_usernames) == 3, "PIT publication requires three configured users."
        context = PITReadyItemSet(
            run_token=run_token,
            workbook_path=workbook_path,
            item_set_id=item_set_id,
            item_ids=item_ids,
            item_set_url=item_set_url,
            sme_username=sme_username,
            rwg_username=rwg_username,
            sr_rwg_username="",
            pit_usernames=pit_usernames,
        )
        context.cleanup_messages.extend(
            f"Initial QAR rerun: {message}"
            for message in qar_recovery.rerun_messages
        )
        if context_registry is not None:
            context_registry.append(context)

        self.login_as(rwg_username)
        approved_by_rwg = RWGReviewQueuePage(self.driver).approve_item_set_as_rwg(
            item_set_id,
            item_ids,
            item_set_url,
        )
        assert set(approved_by_rwg) == set(item_ids)

        self.login_as(sme_username)
        self.sme_page.open_item_set_url_and_wait(item_set_url, item_set_id)
        try:
            sr_rwg_key = self.sme_page.require_item_set_assignee("sr_rwg")
            sr_rwg_username = ReadConfig.get_all_user_username(sr_rwg_key)
        except AssertionError:
            sr_rwg_username = ReadConfig.get_role_usernames("sr_rwg")[0]
        context.sr_rwg_username = sr_rwg_username

        self.login_as(sr_rwg_username)
        approved_by_sr_rwg = SRRWGReviewQueuePage(
            self.driver
        ).approve_item_set_as_sr_rwg(item_set_id, item_ids, item_set_url)
        assert set(approved_by_sr_rwg) == set(item_ids)

        self.login_as(pit_usernames[0])
        pit_page = PITReviewQueuePage(self.driver)
        pit_page.open_review_item_set(item_set_id, item_set_url)
        pending_ids = pit_page.get_pending_pit_item_ids(item_set_id)
        assert set(pending_ids) == set(item_ids), (
            f"Expected every fresh item at PIT; pending={pending_ids}, created={item_ids}."
        )

        return context

    def repository_contains(self, context, item_id):
        self.login_as(context.sme_username)
        return ManualItemPage(self.driver).repository_has_exact_item(item_id)

    def reveal_revision_audit_text(self, expected_text):
        body_text = self.driver.find_element("tag name", "body").text
        if expected_text in body_text:
            return body_text
        self.driver.execute_script(
            """
            const labels = /^(History|Timeline|Feedback|Revision History|View History)$/i;
            const target = Array.from(document.querySelectorAll(
                'button, a, [role="button"], summary'
            )).find(element => {
                const rect = element.getBoundingClientRect();
                const text = (element.innerText || element.textContent || '').trim();
                return rect.width > 0 && rect.height > 0 && labels.test(text);
            });
            if (target) target.click();
            """
        )
        try:
            self.sme_page.wait_utils.until_condition(
                lambda driver: expected_text
                in driver.find_element("tag name", "body").text,
                timeout=15,
            )
        except Exception:
            pass
        return self.driver.find_element("tag name", "body").text

    def best_effort_finalize(self, context):
        """Avoid leaving a unique test set in Needs Revision after a failed test."""
        if context.published:
            return
        try:
            self.login_as(context.rwg_username)
            RWGReviewQueuePage(self.driver).approve_item_set_as_rwg(
                context.item_set_id,
                context.item_ids,
                context.item_set_url,
            )
        except Exception as error:
            context.cleanup_messages.append(f"RWG cleanup: {error}")

        try:
            sr_rwg_username = context.sr_rwg_username
            if not sr_rwg_username:
                self.login_as(context.sme_username)
                self.sme_page.open_item_set_url_and_wait(
                    context.item_set_url,
                    context.item_set_id,
                )
                try:
                    sr_rwg_key = self.sme_page.require_item_set_assignee("sr_rwg")
                    sr_rwg_username = ReadConfig.get_all_user_username(sr_rwg_key)
                except AssertionError:
                    sr_rwg_username = ReadConfig.get_role_usernames("sr_rwg")[0]
            self.login_as(sr_rwg_username)
            SRRWGReviewQueuePage(self.driver).approve_item_set_as_sr_rwg(
                context.item_set_id,
                context.item_ids,
                context.item_set_url,
            )
        except Exception as error:
            context.cleanup_messages.append(f"SRRWG cleanup: {error}")

        try:
            self.login_as(context.sme_username)
            self.sme_page.open_item_set_url_and_wait(
                context.item_set_url,
                context.item_set_id,
            )
            if self.sme_page.get_revision_item_targets():
                self.sme_page.revise_items_in_open_item_set(context.item_set_id)
                self.sme_page.resubmit_revised_item_set_for_review()
        except Exception as error:
            context.cleanup_messages.append(f"SME cleanup: {error}")

        for pit_username in context.pit_usernames:
            try:
                self.login_as(pit_username)
                PITReviewQueuePage(self.driver).approve_item_set_as_pit(
                    context.item_set_id,
                    context.item_set_url,
                )
            except Exception as error:
                context.cleanup_messages.append(f"PIT cleanup {pit_username}: {error}")
