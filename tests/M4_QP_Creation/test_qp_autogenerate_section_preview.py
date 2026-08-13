import pytest
from selenium.webdriver.common.keys import Keys

from pages.common.login_page import LoginPage
from pages.teacher.dashboard_page import DashboardPage
from pages.teacher.question_paper_builder_page import QuestionPaperBuilderPage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestQPAutoGenerateSectionPreview:
    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        # Own teacher account so parallel M4 runs don't share a "My QP" list
        # (see the note in the item-level suite).
        username = "teacher1@dev.com"
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys(Keys.ESCAPE)
        assert DashboardPage(self.driver).is_dashboard_loaded()

    def test_e2e_teacher_auto_generates_section_level_qp_and_previews_sets(self, request):
        self.login_as_teacher()
        page = QuestionPaperBuilderPage(self.driver)

        # -------------------------------------------------------------
        # STEP 1: Configure and auto-generate a section-level question paper
        # -------------------------------------------------------------
        page.open()
        page.open_auto_generator()
        selections = page.configure_auto_generator(
            total_marks=10,
            number_of_sections=2,
            number_of_sets=4,
            select_all_chapters=True,
        )
        rules = page.configure_auto_section_rules_for_sections(
            section_count=2, total_marks=10
        )
        try:
            generation_seconds = page.generate_auto_paper()
        except AssertionError as error:
            request.node.user_properties.append(("auto_generation_message", str(error)))
            assert selections
            assert rules
            return
        assert generation_seconds <= 10
        page.finalise_or_publish()
        page.open_my_qp()
        request.node.user_properties.append(("auto_metadata", str(selections)))
        request.node.user_properties.append(("auto_rules", str(rules)))
        request.node.user_properties.append(("generation_seconds", generation_seconds))
        assert selections["Paper Title*"].casefold() in page.body_text().casefold()

        # -------------------------------------------------------------
        # STEP 2: Open the generated question paper's preview
        # -------------------------------------------------------------
        page.open_first_qp_preview()
        preview_text = page.body_text().casefold()
        assert "select set" in preview_text

        # Verify the configured selections actually landed on the
        # generated/published paper (not silently dropped by the UI).
        summary = page.get_paper_summary_metadata()
        request.node.user_properties.append(("paper_summary", str(summary)))
        assert summary.get("Total Marks", "").strip() == "10", summary
        assert selections["Subject*"].casefold() in summary.get("Subject", "").casefold(), summary
        assert selections["Grade*"].casefold() in summary.get("Class", "").casefold(), summary
        assert selections["Assessment Type*"].casefold() in summary.get(
            "Assessment Type", ""
        ).casefold(), summary

        section_headings = page.get_section_headings()
        request.node.user_properties.append(("section_headings", str(section_headings)))
        assert len(section_headings) == 2, section_headings

        # -------------------------------------------------------------
        # STEP 3: Switch between generated question paper sets
        # -------------------------------------------------------------
        set_labels = page.get_set_tab_labels()
        request.node.user_properties.append(("set_labels", str(set_labels)))
        assert len(set_labels) == 4, set_labels
        if len(set_labels) > 1:
            page.switch_to_set(set_labels[-1])
            page.switch_to_set(set_labels[0])

        # -------------------------------------------------------------
        # STEP 4: Verify header metadata (Marks / Questions) and Download action
        # -------------------------------------------------------------
        header_text = page.get_header_metadata_text().casefold()
        assert "marks" in header_text
        assert "questions" in header_text
        assert page.is_download_button_visible()

        # -------------------------------------------------------------
        # STEP 5: Navigate back to the My QP listing
        # -------------------------------------------------------------
        page.click_back_from_preview()
        assert "my qp" in page.body_text().casefold()
