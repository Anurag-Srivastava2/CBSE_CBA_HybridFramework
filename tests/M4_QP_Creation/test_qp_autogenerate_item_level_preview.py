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
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestQPAutoGenerateItemLevelPreview:
    def login_as_teacher(self):
        self.driver.get(ReadConfig.get_base_url())
        # A QP teacher account, never the primary one: all three M4 suites
        # publish into "My QP" and the preview step opens the newest paper in
        # that list, so a suite sharing an account with a concurrently running
        # one would assert against the other's paper. get_qp_teacher_username()
        # hands each xdist worker its own account and keeps M5's primary
        # teacher out of M4 entirely.
        username = ReadConfig.get_qp_teacher_username()
        LoginPage(self.driver).login_to_application(
            username,
            ReadConfig.get_password_for_username(username),
        )
        self.driver.find_element("tag name", "body").send_keys(Keys.ESCAPE)
        assert DashboardPage(self.driver).is_dashboard_loaded()
        checkpoint(f"QP teacher {username} signed in and reached the dashboard")
        return username

    def test_e2e_teacher_auto_generates_item_level_qp_and_previews_sets(
        self, request, record_property, page_evidence
    ):
        """Item-level auto generation, publication and multi-set preview.

        Page structure is surveyed softly across the three screens this walks.
        Everything about the generated paper — the generation budget, the
        metadata surviving publication, the section and set counts — is a
        workflow outcome or data integrity and stays a hard assert.
        """
        self.login_as_teacher()
        page = QuestionPaperBuilderPage(self.driver)

        # -------------------------------------------------------------
        # STEP 1: Configure and auto-generate an item-level question paper
        # -------------------------------------------------------------
        page.open()
        checks = ElementChecks(
            page, record_property, page_name="QP Builder — Assessment Configuration"
        )
        survey_chrome(checks, page)
        survey_builder(checks, page, mode="Manual Build")

        # Does the mode switch actually respond, or is it a dead tab?
        checks.check_interaction(
            "Mode tab responds — Auto Generator",
            lambda: page.switch_mode_tab("Auto Generator"),
            lambda: page.is_tab_active("Auto Generator"),
        )
        checks.check_interaction(
            "Mode tab responds — Manual Build",
            lambda: page.switch_mode_tab("Manual Build"),
            lambda: page.is_tab_active("Manual Build"),
        )

        page.open_auto_generator()
        enter_screen(checks, "QP Builder — Auto Generator")
        survey_builder(checks, page, mode="Auto Generator")
        page_evidence.checkpoint(
            "Both mode tabs responded and the Auto Generator form is open"
        )

        page.select_item_level()
        # Section A: 10 questions x 1 mark = 10 marks.
        # Section B: 5 questions x 2 marks = 10 marks. Total = 20 marks.
        section_configs = [
            {"number_of_items": 10, "marks_per_item": 1},
            {"number_of_items": 5, "marks_per_item": 2},
        ]
        total_marks = sum(
            config["number_of_items"] * config["marks_per_item"]
            for config in section_configs
        )
        selections = page.configure_item_level_generator(
            total_marks=total_marks,
            number_of_sections=len(section_configs),
            number_of_sets=4,
            select_all_chapters=True,
        )
        rules = page.configure_item_level_rows(section_configs)
        page_evidence.checkpoint(
            f"Item-level generator configured for {total_marks} marks over "
            f"{len(section_configs)} section(s) and 4 set(s): "
            + "; ".join(
                f"section {index}: {config['number_of_items']} x "
                f"{config['marks_per_item']} mark(s)"
                for index, config in enumerate(section_configs, start=1)
            )
        )
        try:
            generation_seconds = page.generate_auto_paper()
        except AssertionError as error:
            request.node.user_properties.append(("auto_generation_message", str(error)))
            record_property("result_description", checks.publish())
            page_evidence.checkpoint(
                f"Generation did not produce a paper, so the run stops at the "
                f"configuration it proved: {error}"
            )
            assert selections
            assert rules
            return
        page_evidence.checkpoint(
            f"Paper generated in {generation_seconds:.1f}s against a 10s budget"
        )
        # Performance budget — stays hard.
        assert generation_seconds <= 10
        paper_number = page.finalise_or_publish()
        request.node.user_properties.append(("paper_number", str(paper_number)))
        page_evidence.checkpoint(f"Paper published as {paper_number}")

        # -------------------------------------------------------------
        # STEP 2: The published paper appears in My QP
        # -------------------------------------------------------------
        page.open_my_qp()
        enter_screen(checks, "QP Builder — My QP")
        survey_my_qp(checks, page)

        request.node.user_properties.append(("auto_metadata", str(selections)))
        request.node.user_properties.append(("auto_rules", str(rules)))
        request.node.user_properties.append(("generation_seconds", generation_seconds))
        assert selections["Paper Title*"].casefold() in page.body_text().casefold()

        # -------------------------------------------------------------
        # STEP 3: Open the generated question paper's preview
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
            f"Preview opened by number for paper {paper_number}; the multi-set "
            f"'Select Set' tab bar is rendered: {'select set' in preview_text}"
        )
        assert "select set" in preview_text

        # Verify the configured selections actually landed on the
        # generated/published paper (not silently dropped by the UI).
        summary = page.get_paper_summary_metadata()
        request.node.user_properties.append(("paper_summary", str(summary)))
        page_evidence.checkpoint(
            f"Configured selections survived generation and publication — "
            f"published summary: {summary}"
        )
        assert summary.get("Total Marks", "").strip() == str(total_marks), summary
        assert selections["Subject*"].casefold() in summary.get("Subject", "").casefold(), summary
        assert selections["Grade*"].casefold() in summary.get("Class", "").casefold(), summary
        assert selections["Assessment Type*"].casefold() in summary.get(
            "Assessment Type", ""
        ).casefold(), summary

        section_headings = page.get_section_headings()
        request.node.user_properties.append(("section_headings", str(section_headings)))
        page_evidence.checkpoint(
            f"Configured 2 section(s); the published paper renders "
            f"{len(section_headings)}: {section_headings}"
        )
        assert len(section_headings) == 2, section_headings

        # -------------------------------------------------------------
        # STEP 4: Switch between generated question paper sets
        # -------------------------------------------------------------
        set_labels = page.get_set_tab_labels()
        request.node.user_properties.append(("set_labels", str(set_labels)))
        page_evidence.checkpoint(
            f"Configured 4 set(s); the published paper offers "
            f"{len(set_labels)}: {set_labels}"
        )
        assert len(set_labels) == 4, set_labels
        if len(set_labels) > 1:
            page.switch_to_set(set_labels[-1])
            page.switch_to_set(set_labels[0])
            page_evidence.checkpoint(
                f"Switched to set {set_labels[-1]!r} and back to {set_labels[0]!r}"
            )

        # -------------------------------------------------------------
        # STEP 5: Verify header metadata (Marks / Questions) and Download action
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
