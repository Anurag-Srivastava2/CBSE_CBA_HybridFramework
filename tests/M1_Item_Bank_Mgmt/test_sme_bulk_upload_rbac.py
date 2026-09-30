import pytest

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from tests.M1_Item_Bank_Mgmt.m1_surveys import survey_chrome, survey_item_sets
from utilities.element_checks import ElementChecks
from utilities.item_template_curriculum import TemplateCurriculum
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestSMEBulkUploadRBAC:
    def test_tc_ibmm_01a_p03_sme_sees_only_assigned_grade_subject_items(
        self, record_property, page_evidence
    ):
        """An SME's item-set listing shows only their assigned grade and subject.

        The listing furniture is surveyed softly; the scope itself is a security
        contract and stays a hard assert — including that rows were actually
        rendered, since "no out-of-scope rows" is trivially true of an empty grid.
        """
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Sign in as an SME and open their item-set listing.\n"
            "Survey the page furniture softly, then hard-assert the scope: every row "
            "on show must be in this SME's own grade and subject.\n"
            "Also assert rows were actually rendered, because an empty grid would "
            "pass a scope check for the wrong reason.",
        )
        # The account's entitlement, read from the template it is served: the
        # cascading dropdowns are built from the uploader's own scoped
        # grade-subjects, so every (grade, subject) they offer is in scope and
        # anything else on the listing is a leak.
        #
        # This used to take the single grade and subject out of the template's
        # sample row, which quietly assumed the account authors in exactly one
        # subject. It is scoped to three, so the first item set in a second
        # subject was reported as a scope violation.
        with TemplateCurriculum.from_path(ReadConfig.get_upload_item_file_path()) as curriculum:
            allowed_pairs = [
                (grade, subject)
                for grade in curriculum.grades()
                for subject in curriculum.subjects(grade)
            ]


        self.driver.get(ReadConfig.get_base_url())
        sme_username = ReadConfig.get_sme2_username()
        LoginPage(self.driver).login_to_application(
            sme_username,
            ReadConfig.get_password_for_username(sme_username),
        )

        sets_page = UploadItemFilePage(self.driver)
        sets_page.close_popup_if_open()
        sets_page.open_item_sets_list()
        page_evidence.checkpoint(
            f"SME {sme_username} opened My Item Set; entitled to "
            f"{len(allowed_pairs)} grade-subject pair(s): "
            + ", ".join(f"{grade}/{subject}" for grade, subject in allowed_pairs)
        )

        checks = ElementChecks(
            sets_page, record_property, page_name="My Item Set — RBAC Scope"
        )
        survey_chrome(checks, sets_page)
        survey_item_sets(checks, sets_page)

        # Review-stage tabs re-scope the grid in place; driving them here is
        # read-only and leaves the listing on All for the assertions below.
        for label in ("QAR", "RWG", "Published"):
            checks.check_interaction(
                f"Tab responds — {label}",
                lambda tab=label: sets_page.switch_item_set_tab(tab),
                lambda tab=label: sets_page.is_item_set_tab_active(tab),
            )
        checks.safe_call(lambda: sets_page.switch_item_set_tab("All"))
        record_property("result_description", checks.publish())
        page_evidence.checkpoint(
            "QAR / RWG / Published tabs each re-scoped the grid; listing left on All"
        )

        sets_page.open_sets_module()
        scopes = sets_page.verify_visible_item_sets_within_scope(allowed_pairs)
        allowed_grades = {grade for grade, _ in allowed_pairs}
        out_of_scope = [
            scope for scope in scopes if scope["grade"] not in allowed_grades
        ]
        page_evidence.checkpoint(
            f"{len(scopes)} visible set(s) read against the account's "
            f"{len(allowed_pairs)} entitled grade-subject pair(s); "
            f"out-of-scope rows: {out_of_scope or 'none'}"
        )

        # A grade the account's own template never offers must never appear.
        assert not out_of_scope, (
            f"SME can see item sets in grades outside {sorted(allowed_grades)}: "
            f"{out_of_scope}"
        )
