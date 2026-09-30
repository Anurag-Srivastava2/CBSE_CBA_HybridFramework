import pytest

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestSMEItemSetFilters:
    def login_and_open_item_sets(self):
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(
            ReadConfig.get_sme2_username(),
            ReadConfig.get_password_for_username(ReadConfig.get_sme2_username()),
        )
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        page.wait_for_application_to_load()
        page.open_sets_module()
        return page

    @staticmethod
    def row_matches_filter(row, field_name, expected_value):
        return row[field_name].strip().casefold() == expected_value.strip().casefold()

    def test_grade_subject_chapter_and_status_filters_apply_validate_and_clear(
        self,
        request,
        page_evidence, record_property,
    ):
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open My Item Sets as an SME and note the unfiltered rows.\n"
            "Apply the grade, subject, chapter and status filters in turn, checking "
            "each one narrows the list correctly.\n"
            "Clear them again and check the list returns to what it was at the start.",
        )
        page = self.login_and_open_item_sets()
        baseline_rows = page.get_item_set_list_rows()
        page_evidence.checkpoint(
            f"SME2 opened My Item Set; baseline listing holds "
            f"{len(baseline_rows)} row(s), which every Clear below must restore"
        )
        assert baseline_rows, "At least one SME item set is required to test filters."

        baseline_ids = {row["item_set_id"] for row in baseline_rows}
        filter_specs = [
            ("Grade", "grade"),
            ("Subject", "subject"),
            ("Chapter", "chapter"),
            ("Status", "item_set_status"),
        ]

        for filter_name, field_name in filter_specs:
            selected_value = baseline_rows[0][field_name]
            assert selected_value, (
                f"Cannot test the {filter_name} filter because the first baseline row "
                f"has no {field_name!r} value: {baseline_rows[0]}"
            )

            page.apply_item_set_filter(filter_name, selected_value)
            assert page.is_item_set_filter_option_selected(filter_name, selected_value), (
                f"{filter_name} option {selected_value!r} did not show a selected state."
            )

            filtered_rows = page.wait_utils.until_condition(
                lambda driver: (
                    rows
                    if (rows := page.get_item_set_list_rows())
                    and all(
                        self.row_matches_filter(row, field_name, selected_value)
                        for row in rows
                    )
                    else False
                ),
                timeout=30,
            )
            assert filtered_rows
            page_evidence.checkpoint(
                f"{filter_name} filter applied with {selected_value!r}; all "
                f"{len(filtered_rows)} visible row(s) match the selected value"
            )

            page.clear_item_set_filter(filter_name, selected_value)
            assert not page.is_item_set_filter_option_selected(filter_name, selected_value), (
                f"{filter_name} option {selected_value!r} remained selected after Clear."
            )
            restored_rows = page.wait_utils.until_condition(
                lambda driver: (
                    rows
                    if (rows := page.get_item_set_list_rows())
                    and {row["item_set_id"] for row in rows} == baseline_ids
                    else False
                ),
                timeout=30,
            )
            page_evidence.checkpoint(
                f"{filter_name} filter cleared; the original {len(restored_rows)} "
                "item-set row(s) were restored before applying the next filter"
            )

        request.node.user_properties.extend(
            [
                (
                    "result_description",
                    "Grade, Subject, Chapter, and Status filters each applied, "
                    "validated their rows, cleared, and restored the baseline list.",
                ),
                ("filter_baseline_item_sets", ", ".join(sorted(baseline_ids))),
            ]
        )
