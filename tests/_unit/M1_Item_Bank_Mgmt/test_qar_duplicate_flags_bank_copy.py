"""TC-IBMM-03-N01: Duplicate Detection flags a reworded copy of an item bank question.

Moved out of the daily run on 2026-10-06, at the team's request. Whether it
passes depends on which rewording of "Convert 2 hours into minutes." the day's
run uploads, not on the build. QA's duplicate check compares wording, not
meaning, so a light edit scores high and a restructured question scores clean:

    "Convert two hours into minutes."         98%   (IS1580, 2026-10-05)
    "2 hours is equal to how many minutes?"   86%   (IS1536, 2026-10-01)
    "Two hours equal how many minutes?"        0%   (IS1600, 2026-10-06)

The cbse-M1 module job still runs tests/_unit, so the requirement is still
exercised.

The bank item, its rewordings, the upload and the report snapshot all come
from QARBankCopyReport in
tests/_unit/M1_Item_Bank_Mgmt/test_qar_plagiarism_and_bias_sections.py. It is
imported through the module rather than by name, because a test class
imported by name into this module would be collected here a second time.
"""
import pytest

from tests._unit.M1_Item_Bank_Mgmt import test_qar_plagiarism_and_bias_sections as bank_copy


@pytest.mark.rtm
@pytest.mark.e2e
# serial: same SME account and same shared upload as the M1 suite.
@pytest.mark.serial
@pytest.mark.usefixtures("setup")
class TestQARDuplicateFlagsBankCopy(bank_copy.QARBankCopyReport):
    def test_tc_ibmm_03_n01_duplicate_check_flags_copied_items(
        self, qar_report, page_evidence, record_property
    ):
        """Duplicate Detection must not report a clean result on items copied out of IB1."""
        # Plain-English orientation for the report, for a reader who does
        # not know this test. One line per step, in the order they happen.
        record_property(
            "test_summary",
            "Open the QAR report for a set holding a reworded copy of an item bank "
            "question ('Convert 2 hours into minutes.').\n"
            "Expect Duplicate Detection to notice: it must not hand that item a "
            "clean 0%.",
        )
        report, _ = qar_report
        score = self.assert_check_is_not_clean(
            page_evidence, report, self.DUPLICATE_CHECK, record_property
        )
        record_property(
            "result_description",
            f"Duplicate Detection scored {score}% on a rewording of the item bank "
            "question, so the duplicate content was detected.",
        )
