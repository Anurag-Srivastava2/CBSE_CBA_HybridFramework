import pytest
from selenium.webdriver.common.keys import Keys

from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from pages.teacher.question_paper_builder_page import QuestionPaperBuilderPage
from tests.M4_QP_Creation.qp_surveys import (
    enter_screen,
    survey_builder,
    survey_chrome,
    survey_my_qp,
    survey_preview,
)
from utilities.element_checks import ElementChecks
from utilities.page_evidence import checkpoint
from utilities.qp_question_budget import cap_manual_marks, get_question_cap
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestQPManualBuildPreview:
    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        # A QP teacher account, never the primary one the M5 suites drive.
        username = ReadConfig.get_qp_teacher_username()
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys(Keys.ESCAPE)
        assert DashboardPage(self.driver).is_dashboard_loaded()
        checkpoint(f"QP teacher {username} signed in and reached the dashboard")
        return username

    def test_e2e_teacher_manually_builds_qp_and_previews_it(
        self, request, record_property, page_evidence
    ):
        """Manual build, publication and single-set preview.

        The builder, listing and preview furniture are surveyed softly. Marks
        allocation, the published metadata and the section count are workflow
        outcomes and data integrity, so they stay hard.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Sign in as a teacher and build a question paper by hand, then publish it "
            "and preview the single set.\n"
            "The builder, listing and preview furniture are surveyed softly.\n"
            "Marks allocation, the published metadata and the section count are "
            "workflow outcomes and data integrity, so they stay hard.",
        )
        self.login_as_teacher()
        page = QuestionPaperBuilderPage(self.driver)

        # -------------------------------------------------------------
        # STEP 1: Configure assessment metadata on the Manual Build tab
        # -------------------------------------------------------------
        page.open_new_paper()
        checks = ElementChecks(
            page, record_property, page_name="QP Builder — Assessment Configuration"
        )
        survey_chrome(checks, page)
        survey_builder(checks, page, mode="Manual Build")

        assert "manual build" in page.body_text().casefold()
        # Items are added until the marks target is met, one mark per
        # question in the worst case, so CBSE_QP_MAX_QUESTIONS - when set -
        # caps the marks the paper is built for.
        total_marks = cap_manual_marks(10)
        selections = page.configure_assessment(
            select_all_chapters=True, total_marks=total_marks
        )
        request.node.user_properties.append(("manual_metadata", str(selections)))
        page_evidence.checkpoint(
            f"Assessment configured on the Manual Build tab for {total_marks} "
            f"marks: {selections}"
        )

        # -------------------------------------------------------------
        # STEP 2: Drag/add an item from the Item Bank into Section A
        # -------------------------------------------------------------
        page.continue_to_build_paper()
        enter_screen(checks, "QP Builder — Build Paper")
        item_bank_filters = checks.safe_call(page.get_item_bank_filter_labels, [])
        checks.check_condition(
            "Item Bank filters rendered",
            item_bank_filters,
            detail=f"filters: {item_bank_filters}",
        )
        marks_before = checks.safe_call(page.get_marks_allocation, ())
        checks.check_condition(
            "Marks allocation counter rendered",
            marks_before,
            detail=f"allocation: {marks_before}",
        )

        allocation = page.add_items_until_marks_target_met(
            max_items=get_question_cap() or 30
        )
        request.node.user_properties.append(("marks_allocation", str(allocation)))
        page_evidence.checkpoint(
            f"Items added from the Item Bank into Section A until the marks "
            f"target was met — allocation now {allocation[0]}/{allocation[1]}"
            if allocation
            else "Items added from the Item Bank, but no marks allocation was read"
        )
        assert allocation and allocation[0] == allocation[1], (
            f"Manual paper marks not fully allocated: {allocation}"
        )

        # -------------------------------------------------------------
        # STEP 3: Continue to Preview & Publish
        # -------------------------------------------------------------
        page.continue_to_preview()
        paper_number = page.finalise_or_publish()
        request.node.user_properties.append(("paper_number", str(paper_number)))
        page_evidence.checkpoint(f"Paper published as {paper_number}")
        page.open_my_qp()
        enter_screen(checks, "QP Builder — My QP")
        survey_my_qp(checks, page)

        assert selections["Paper Title"].casefold() in page.body_text().casefold()

        # -------------------------------------------------------------
        # STEP 4: Open the manually built paper's preview
        # -------------------------------------------------------------
        # By number, not by listing position: the M4 suites share an account
        # and the listing is ordered by publication date, so the top row is
        # not reliably the paper this test just published.
        page.open_published_qp_preview(paper_number)
        enter_screen(checks, "QP Builder — Paper Preview")
        survey_preview(checks, page)
        record_property("result_description", checks.publish())

        preview_text = page.body_text().casefold()
        page_evidence.checkpoint(
            f"Preview opened by number for paper {paper_number}; reads as "
            f"published: {'published' in preview_text}"
        )
        assert "published" in preview_text

        # A manually built paper has a single set, so the "Select Set" tab bar
        # that multi-set auto-generated papers show is not rendered here.
        summary = page.get_paper_summary_metadata()
        request.node.user_properties.append(("paper_summary", str(summary)))
        page_evidence.checkpoint(
            f"Published paper summary carries the configured metadata: {summary}"
        )
        assert summary.get("Total Marks", "").strip() == str(total_marks), summary
        assert selections["Subject"].casefold() in summary.get("Subject", "").casefold(), summary
        assert selections["Grade"].casefold() in summary.get("Class", "").casefold(), summary
        assert selections["Assessment Type"].casefold() in summary.get(
            "Assessment Type", ""
        ).casefold(), summary

        section_headings = page.get_section_headings()
        request.node.user_properties.append(("section_headings", str(section_headings)))
        page_evidence.checkpoint(
            f"A manually built paper renders one set, so exactly one section "
            f"heading is expected — got {len(section_headings)}: {section_headings}"
        )
        assert len(section_headings) == 1, section_headings

        # -------------------------------------------------------------
        # STEP 5: Verify header metadata and Download action
        # -------------------------------------------------------------
        header_text = page.get_header_metadata_text().casefold()
        page_evidence.checkpoint(
            f"Preview header names marks: {'marks' in header_text} and "
            f"questions: {'questions' in header_text}; Download offered: "
            f"{page.is_download_button_visible()}"
        )
        assert "marks" in header_text
        assert "questions" in header_text
        assert page.is_download_button_visible()

        # -------------------------------------------------------------
        # STEP 6: Navigate back to the My QP listing
        # -------------------------------------------------------------
        page.click_back_from_preview()
        page_evidence.checkpoint(
            f"Back from the preview returns to My QP: "
            f"{'my qp' in page.body_text().casefold()}"
        )
        assert "my qp" in page.body_text().casefold()
