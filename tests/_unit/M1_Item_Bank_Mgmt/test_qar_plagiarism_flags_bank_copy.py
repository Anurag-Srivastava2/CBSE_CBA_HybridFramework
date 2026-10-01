"""TC-IBMM-06-N01: Plagiarism Detection flags a copy of an item bank question.

Moved out of the daily run on 2026-10-01, at the team's request. On QA every
copy of bank content scores Plagiarism Detection 0% - near-verbatim copies of
"Convert 2 hours into minutes." (IS1531-IS1535) and the rewording "2 hours is
equal to how many minutes?" (IS1536) alike - so this test was red on every run
for a reason that sits with the backend team, not the suite. Duplicate
Detection does flag the rewording (86%), and that test stays in the daily run.

The cbse-M1 module job still runs tests/_unit, so the requirement is still
exercised. Move it back into
tests/M1_Item_Bank_Mgmt/test_qar_plagiarism_and_bias_sections.py once the
plagiarism check recognises bank content.

The bank item, its rewordings, the upload and the report snapshot all come
from QARBankCopyReport in that file. It is imported through the module rather
than by name, because a test class imported by name into this module would be
collected here a second time.
"""
import pytest

from tests.M1_Item_Bank_Mgmt import test_qar_plagiarism_and_bias_sections as bank_copy


@pytest.mark.rtm
@pytest.mark.e2e
# serial: same SME account and same shared upload as the M1 suite.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestQARPlagiarismFlagsBankCopy(bank_copy.QARBankCopyReport):
    def test_tc_ibmm_06_n01_plagiarism_check_flags_copied_items(
        self, qar_report, page_evidence, record_property
    ):
        """Plagiarism Detection must not report a clean result on items copied out of IB1."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a set holding a reworded copy of an item bank "
            "question ('Convert 2 hours into minutes.').\n"
            "Expect Plagiarism Detection to notice: it must not hand that item a "
            "clean 0%.",
        )
        report, _ = qar_report
        score = self.assert_check_is_not_clean(
            page_evidence, report, self.PLAGIARISM_CHECK, record_property
        )
        record_property(
            "result_description",
            f"Plagiarism Detection scored {score}% on a rewording of the item bank "
            "question, so the copied content was detected.",
        )
