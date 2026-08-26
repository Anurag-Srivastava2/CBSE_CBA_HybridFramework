"""Metadata retagged on the review step must survive every step after it.

An SME can correct an item's tags at "Review & Tag Metadata" (step 3) after the
workbook has been ingested but before the set is submitted - the whole point of
that step. What matters is that the correction is what gets stored: the values
shown on "Confirm & Submit" (step 4) and on the created item set have to be the
edited ones, not the values that came out of the uploaded Excel.

This test edits four tags on one item - Marks, Bloom's Level, Competency and
Learning Outcome - and then re-reads that item's row at each later stage,
finding it by item ID because row order is not guaranteed to be stable between
stages.

Two things are deliberately not hard-coded:

- The replacement values are whatever the dropdown offers rather than fixed
  strings, because the available competencies and outcomes differ per
  grade-subject and would otherwise pin this test to one data set.
- The untouched columns (Grade, Subject, Typology) are asserted to be unchanged.
  Every metadata cell on the row is its own inline combobox, so an edit landing
  on the neighbouring cell is a real failure mode worth catching here.
"""

import json
from pathlib import Path
from uuid import uuid4

import allure
import pytest

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.bulk_upload_page import BulkUploadPage
from utilities.item_bank_workbook_builder import build_item_workbook
from utilities.read_config import ReadConfig

EDITED_COLUMNS = ("Marks", "Bloom's Level", "Competency", "Learning Outcome")
# The opened item lays its metadata out as label-above-value rather than as
# a table, and only these of the edited fields carry a label there.
DETAIL_LABELS = ("Competency", "Learning Outcome")
UNTOUCHED_COLUMNS = ("Grade", "Subject", "Typology")


@pytest.mark.e2e
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestE2EMetadataEditCarriesThroughToItemSet:
    def build_workbook(self, run_id):
        """A freshly generated workbook.

        The portal rejects a re-upload of identical content under the same
        filename, so a fixed fixture file can only be uploaded once per
        environment.
        """
        output_path = (
            Path(ReadConfig.project_root)
            / "artifacts"
            / "metadata_edit"
            / run_id
            / f"{run_id}.xlsx"
        )
        workbook_path, _ = build_item_workbook(
            ReadConfig.get_upload_item_file_path(), output_path, count=3
        )
        return workbook_path

    def login_as_sme(self):
        username = ReadConfig.get_sme2_username()
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            username, ReadConfig.get_sme2_password()
        )
        page = BulkUploadPage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        return page, username

    def shot(self, run_id, name):
        """Save a screenshot and remember it for the allure attachments."""
        path = (
            Path(ReadConfig.project_root)
            / "artifacts"
            / "metadata_edit"
            / run_id
            / "screenshots"
            / f"{name}.png"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        self.driver.save_screenshot(str(path))
        self.shots.append((name, str(path)))
        return str(path)

    @staticmethod
    def read_row_for_question(page, question):
        """The row for this question, found afresh at whatever stage we are on."""
        return page.get_review_metadata(page.review_row_index_where("Item", question))

    @staticmethod
    def read_edited_values(page, question):
        """The edited columns for this question, as this stage heads them."""
        row_index = page.review_row_index_where("Item", question)
        return page.get_review_metadata_values(row_index, EDITED_COLUMNS)

    @staticmethod
    def assert_shows(page, stage, item_id, shown, expected):
        """Every edited value is the one on screen at `stage`."""
        wrong = {
            column: {"shown": shown.get(column), "expected": value}
            for column, value in expected.items()
            if not page.metadata_cell_matches(shown.get(column), value)
        }
        assert not wrong, (
            f"{stage} did not carry the edited metadata for {item_id}: "
            f"{json.dumps(wrong, indent=2)}"
        )

    def test_review_step_metadata_edits_reach_confirm_step_and_created_item_set(
        self, request, page_evidence
    ):
        run_id = f"metadata_edit_{uuid4().hex[:10]}"
        self.shots = []
        workbook_path = self.build_workbook(run_id)
        page, username = self.login_as_sme()

        page.upload_item_file_and_validate(str(workbook_path))
        page.click_continue()
        page.wait_for_review_step()
        page_evidence.checkpoint(
            f"SME {username} uploaded {workbook_path.name} (3 items) and reached "
            "the review step, where metadata is still editable"
        )

        # Submission renumbers every item ID, so the question text is what
        # identifies this row from here on; the ID is kept only as evidence.
        first_row = page.get_review_metadata(0)
        item_id, question = first_row["Item ID"], first_row["Item"]

        before_row = self.read_row_for_question(page, question)

        edits = {}
        for position, column in enumerate(EDITED_COLUMNS, start=1):
            slug = column.lower().replace("'", "").replace(" ", "_")
            row_index = page.review_row_index_where("Item", question)
            self.shot(run_id, f"{position:02d}_{slug}_before")
            before, after = page.change_review_metadata(column, row_index)
            self.shot(run_id, f"{position:02d}_{slug}_after")
            edits[column] = {
                "before": before,
                "after": after,
                "screenshot_before": self.shots[-2][1],
                "screenshot_after": self.shots[-1][1],
            }

        expected = {column: edit["after"] for column, edit in edits.items()}
        page_evidence.checkpoint(
            f"Retagged {len(edits)} column(s) on {item_id}: "
            + "; ".join(
                f"{column} {edit['before']!r} -> {edit['after']!r}"
                for column, edit in edits.items()
            )
        )
        review_row = self.read_row_for_question(page, question)
        review_values = self.read_edited_values(page, question)
        self.shot(run_id, "05_review_step_after_all_edits")
        self.assert_shows(page, "The review step", item_id, review_values, expected)
        page_evidence.checkpoint(
            f"The review step shows every edited value for {item_id}"
        )

        unchanged = {
            column: {"before": before_row.get(column), "now": review_row.get(column)}
            for column in UNTOUCHED_COLUMNS
            if before_row.get(column) != review_row.get(column)
        }
        page_evidence.checkpoint(
            f"Untouched columns that moved anyway (an edit landing on the wrong "
            f"cell): {list(unchanged) or 'none'}"
        )
        assert not unchanged, (
            "Editing the tagged columns also altered columns that were never "
            f"touched, so an edit landed on the wrong cell: "
            f"{json.dumps(unchanged, indent=2)}"
        )

        # Step 4 - Confirm & Submit, still before anything is submitted.
        page.click_continue()
        page.wait_for_review_step()
        confirm_row = self.read_row_for_question(page, question)
        confirm_values = self.read_edited_values(page, question)
        self.shot(run_id, "06_confirm_and_submit_before_submitting")
        self.assert_shows(page, "Confirm & Submit", item_id, confirm_values, expected)
        page_evidence.checkpoint(
            "Confirm & Submit still carries the edited metadata, before anything "
            "is submitted"
        )

        # Submitting turns the staged upload into a real item set.
        page.click_submit_for_qar_and_wait_for_results(analysis_timeout=300)
        result_item_ids = page.get_qar_result_item_ids() or page.get_review_item_ids()
        item_set_id = page.get_item_set_id_from_item_ids(result_item_ids)
        page_evidence.checkpoint(
            f"Submitted; QAR minted item set {item_set_id or 'UNKNOWN'} with "
            f"{len(result_item_ids)} item(s) — submission renumbers every ID, so "
            "the question text is what identifies the row from here"
        )
        assert result_item_ids, "Submitting produced no item IDs at all."

        # Re-open the stored set rather than trusting the post-submit screen,
        # so the assertion is against what was persisted.
        page.open_sets_module()
        page.open_item_set_from_sets_list(item_set_id)
        page.wait_for_review_step()
        stored_row = self.read_row_for_question(page, question)
        stored_values = self.read_edited_values(page, question)
        self.assert_shows(
            page,
            f"The created item set {item_set_id}",
            item_id,
            stored_values,
            expected,
        )
        self.shot(run_id, "07_created_item_set")
        page_evidence.checkpoint(
            f"Re-opened the stored set {item_set_id} — the edits were persisted, "
            "not just shown on the post-submit screen"
        )

        # Open the item itself. Its ID is the one the set assigned, which is
        # not the staged ID captured before submission.
        stored_item_id = stored_row["Item ID"]
        QARReportPage(self.driver).open_item_report(stored_item_id)
        detail = page.get_item_detail_metadata(DETAIL_LABELS)
        self.shot(run_id, "08_opened_item")

        detail_expected = {
            column: value
            for column, value in expected.items()
            if column in DETAIL_LABELS
        }
        missing = [label for label in detail_expected if label not in detail]
        assert not missing, (
            f"The opened item {stored_item_id} does not show "
            f"{missing}; it showed {json.dumps(detail, indent=2)}"
        )
        self.assert_shows(
            page,
            f"The opened item {stored_item_id}",
            stored_item_id,
            detail,
            detail_expected,
        )
        page_evidence.checkpoint(
            f"The opened item {stored_item_id} shows the edited values on its own "
            f"detail panel: {detail_expected}"
        )

        evidence = {
            "run_id": run_id,
            "sme_username": username,
            "staged_item_id": item_id,
            "question": question,
            "item_set_id": item_set_id,
            "workbook": str(workbook_path),
            "edits": edits,
            "review_row": review_row,
            "confirm_row": confirm_row,
            "stored_row": stored_row,
            "stored_item_id": stored_item_id,
            "opened_item_detail": detail,
            "screenshots": dict(self.shots),
        }
        allure.attach(
            json.dumps(evidence, indent=2, sort_keys=True),
            name="Review-step metadata edit evidence",
            attachment_type=allure.attachment_type.JSON,
        )
        for name, shot_path in self.shots:
            allure.attach.file(
                shot_path, name=name, attachment_type=allure.attachment_type.PNG
            )
        print(f"[METADATA_EDIT_RESULT] {json.dumps(evidence, sort_keys=True)}", flush=True)
        request.node.user_properties.extend(
            [
                ("item_set_id", item_set_id),
                ("metadata_edit_evidence", json.dumps(evidence, sort_keys=True)),
                (
                    "result_description",
                    f"Retagged {', '.join(EDITED_COLUMNS)} on {item_id} at the "
                    "review step, then confirmed the edited values on Confirm & "
                    f"Submit, on the created item set {item_set_id}, and inside "
                    f"the opened item {stored_item_id}.",
                ),
            ]
        )
