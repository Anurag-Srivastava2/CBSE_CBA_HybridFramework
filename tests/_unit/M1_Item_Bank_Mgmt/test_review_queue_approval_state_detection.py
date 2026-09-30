from pages.common.review_queue_page import BaseReviewQueuePage
from pages.sr_rwg.review_queue_page import SRRWGReviewQueuePage
from selenium.webdriver.common.by import By


class StubCriteriaRoot:
    """Stands in for the element get_criteria_root() returns.

    That helper hands back whatever its JS evaluates to, which in a real
    browser is a DOM element - callers then read `.text` off it. A fake that
    returned the panel's text as a bare string modelled the older,
    page-text-scraping behaviour and raised AttributeError once the scoping
    root was introduced.
    """

    def __init__(self, text):
        self.text = text

    def find_elements(self, *_locator):
        return []


class ScriptedDriver:
    def __init__(self, current_url, script_results=()):
        self.current_url = current_url
        self.script_results = list(script_results)

    def execute_script(self, _script, *_args):
        if not self.script_results:
            raise AssertionError("Unexpected execute_script call")
        return self.script_results.pop(0)

    def find_elements(self, *_locator):
        return []


class ImmediateWait:
    def until_condition(self, condition, timeout):
        assert timeout == 30
        assert condition(None)
        return True


class EnabledButton:
    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def get_attribute(self, name):
        return None if name == "disabled" else "false"


class LocatorDriver:
    def __init__(self, enabled_locator):
        self.enabled_locator = enabled_locator

    def find_elements(self, by, value):
        return [EnabledButton()] if (by, value) == self.enabled_locator else []


def build_page(driver, open_title):
    page = BaseReviewQueuePage.__new__(BaseReviewQueuePage)
    page.driver = driver
    page.get_open_item_title = lambda: open_title
    return page


def test_auto_advance_without_approved_card_is_not_reported_as_saved(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Simulate the queue auto-advancing to the next item without the previous "
        "one ever showing an Approved badge.\n"
        "Check that is not reported as a saved approval.",
    )
    driver = ScriptedDriver(
        "https://example.test/review-queue/379/items/1",
        script_results=(False,),
    )
    page = build_page(driver, "Is 20 < 30? Upload run next-2")

    assert not page.is_open_item_approved(
        driver,
        driver.current_url,
        "Is 10 < 20? Upload run first-1",
    )


def test_approval_is_saved_when_original_left_card_has_approved_badge(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Simulate the reviewed item's own card carrying an Approved badge.\n"
        "Check that is recognised as a genuinely saved approval.",
    )
    driver = ScriptedDriver(
        "https://example.test/review-queue/379/items/1",
        script_results=(True,),
    )
    title = "Is 10 < 20? Upload run first-1"
    page = build_page(driver, title)

    assert page.is_open_item_approved(driver, driver.current_url, title)


def test_pending_item_without_transition_is_not_reported_as_approved(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Simulate an item that never transitions at all.\n"
        "Check it is not reported as approved.",
    )
    driver = ScriptedDriver(
        "https://example.test/review-queue/379/items/1",
        script_results=(False, False),
    )
    title = "Is 10 < 20? Upload run first-1"
    page = build_page(driver, title)

    assert not page.is_open_item_approved(driver, driver.current_url, title)


def test_approve_items_keeps_final_split_view_open_for_submit_review(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Approve the items in a set.\n"
        "Check the final split view is left open, so Submit Review can still be "
        "reached afterwards.",
    )
    page = BaseReviewQueuePage.__new__(BaseReviewQueuePage)
    page.wait_utils = ImmediateWait()
    events = []
    page.return_to_item_set_if_needed = lambda item_set_id: events.append(
        ("return", item_set_id)
    )
    page.click_item = lambda item_id: events.append(("click", item_id))
    page.mark_all_criteria_yes = lambda: events.append(("mark", None))
    page.approve_open_item = lambda: events.append(("approve", None))
    page.is_submit_review_enabled = lambda: True

    approved = page.approve_items_with_yes("IS381", ["IS381-i1", "IS381-i2"])

    assert approved == ["IS381-i1", "IS381-i2"]
    assert events[-1] == ("approve", None)
    assert events.count(("return", "IS381")) == 3


def test_enabled_submit_review_is_a_valid_pre_submit_completion_signal(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Simulate a queue where the items do not read as approved but Submit "
        "Review is enabled.\n"
        "Check the enabled button is accepted as a valid signal that the review "
        "is complete.",
    )
    page = BaseReviewQueuePage.__new__(BaseReviewQueuePage)
    page.wait_utils = ImmediateWait()
    page.are_review_items_approved = lambda driver: False
    page.is_submit_review_enabled = lambda: True

    page.wait_until_review_items_approved()


def test_submit_readiness_uses_role_specific_final_action_locator(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Check submit readiness looks for the final action button belonging to "
        "the reviewer's own role.\n"
        "One shared locator would let one role's readiness be judged by another "
        "role's button.",
    )
    sr_submit_locator = (
        By.XPATH,
        "//button[contains(normalize-space(),'Approve Item Set')]",
    )
    page = BaseReviewQueuePage.__new__(BaseReviewQueuePage)
    page.driver = LocatorDriver(sr_submit_locator)
    page.SUBMIT_REVIEW_LOCATORS = [sr_submit_locator]

    assert page.is_submit_review_enabled()


def test_no_criteria_completion_uses_irs_summary_counts(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Simulate a review with no criteria marked, showing only an IRS summary "
        "of Yes, No and N/A counts.\n"
        "Check completion is judged from those counts.",
    )
    driver = ScriptedDriver(
        "https://example.test/review-queue/385/items/1",
        script_results=(StubCriteriaRoot("0 Yes 22 No 0 N/A"),),
    )
    page = build_page(driver, "Teacher upload run first-1")

    assert page.are_all_criteria_marked_no(driver)


def test_revision_enters_long_remark_before_marking_item_for_revision(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Send an item back for revision.\n"
        "Check a full-length remark is entered before the item is marked, not "
        "after.",
    )
    driver = ScriptedDriver("https://example.test/review-queue/386/items/1")
    page = build_page(driver, "Teacher upload run first-1")
    page.wait_utils = ImmediateWait()
    events = []
    page.mark_all_criteria_no = lambda: events.append(("mark_no", None))
    page.open_revision_form = lambda: events.append(("open_revision", None)) or True

    def enter_remark(remark):
        events.append(("remark", remark))
        return len(remark) > 50

    page.enter_revision_remark_if_available = enter_remark
    page.click_required_and_confirm = lambda locators, name, timeout: events.append(
        ("revision", name)
    )
    page.is_open_item_sent_back_for_revision = (
        lambda driver, starting_url, starting_title: True
    )

    page.send_open_item_back_for_revision("IS386-G1-Mathematics-Ch38-i1")

    assert [event[0] for event in events] == [
        "mark_no",
        "open_revision",
        "remark",
        "revision",
    ]
    assert len(events[2][1]) > 50


def test_revision_preserves_explicit_audit_comment_for_pit_sme_history(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Send an item back carrying an explicit audit comment.\n"
        "Check that exact comment survives into the PIT and SME history rather "
        "than being replaced by a generic one.",
    )
    driver = ScriptedDriver("https://example.test/review-queue/386/items/1")
    page = build_page(driver, "Teacher upload run first-1")
    page.wait_utils = ImmediateWait()
    expected_comment = (
        "PIT audit token abc123: clarify the item stem and explanation before SME resubmission."
    )
    entered_comments = []
    page.mark_all_criteria_no = lambda: None
    page.open_revision_form = lambda: True
    page.enter_revision_remark_if_available = (
        lambda comment: entered_comments.append(comment) or True
    )
    page.click_required_and_confirm = lambda locators, name, timeout: None
    page.is_open_item_sent_back_for_revision = (
        lambda driver, starting_url, starting_title: True
    )

    returned_comment = page.send_open_item_back_for_revision_with_comment(
        "IS386-G1-Mathematics-Ch38-i1",
        expected_comment,
    )

    assert entered_comments == [expected_comment]
    assert returned_comment == expected_comment


def test_qar_timeline_revision_text_does_not_confirm_item_send_back(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Simulate a page whose QAR timeline merely mentions a revision.\n"
        "Check that text alone is not treated as confirmation that the item was "
        "sent back.",
    )
    driver = ScriptedDriver(
        "https://example.test/review-queue/386/items/1",
        script_results=(False, False),
    )
    page = build_page(driver, "Teacher upload run first-1")

    assert not page.is_open_item_sent_back_for_revision(
        driver,
        driver.current_url,
        "Teacher upload run first-1",
    )


def test_locked_no_criteria_with_no_revision_action_confirms_send_back(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Simulate a locked review with no criteria and no revision action still "
        "available.\n"
        "Check that state does confirm the item was sent back.",
    )
    driver = ScriptedDriver(
        "https://example.test/review-queue/386/items/1",
        script_results=(False, True),
    )
    page = build_page(driver, "Teacher upload run first-1")

    assert page.is_open_item_sent_back_for_revision(
        driver,
        driver.current_url,
        "Teacher upload run first-1",
    )


def test_revision_confirmation_locator_accepts_send_for_revision_button(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Read the revision confirmation locators.\n"
        "Check they include the Send for Revision button wording, so the "
        "confirmation is actually found.",
    )
    assert any(
        "Send for Revision" in locator
        for _by, locator in BaseReviewQueuePage.CONFIRM_LOCATORS
    )


def test_sr_rwg_submit_locator_cannot_match_an_approved_item_card(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Read the Senior RWG submit locators.\n"
        "Check they target that role's own review action and cannot accidentally "
        "match an approved item card.",
    )
    locator_texts = [locator for _by, locator in SRRWGReviewQueuePage.SUBMIT_REVIEW_LOCATORS]

    assert any("rwg review" in locator.casefold() for locator in locator_texts)
    assert not any("contains(normalize-space(),'Approve')" in locator for locator in locator_texts)


def test_open_item_title_accepts_question_stems_without_legacy_prefixes(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Open an item whose title is a plain question stem carrying none of the "
        "legacy prefixes.\n"
        "Check it is still matched and opened.",
    )
    expected_title = (
        "On attendance board WT79C9QE-1, Class Blue shows 38 learners "
        "and Class Green shows 23 learners. Is 38 > 23?"
    )

    class GenericTitleDriver:
        def execute_script(self, script, *args):
            assert "exactMatch" in script
            assert args == (expected_title,)
            return expected_title

    page = BaseReviewQueuePage.__new__(BaseReviewQueuePage)
    page.driver = GenericTitleDriver()

    assert page.get_open_item_title(expected_title) == expected_title
