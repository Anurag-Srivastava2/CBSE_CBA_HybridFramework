from selenium.webdriver.common.by import By

from pages.common.review_queue_page import BaseReviewQueuePage


class SRRWGReviewQueuePage(BaseReviewQueuePage):
    """Page object for Senior RWG approval and submission."""

    SUBMIT_REVIEW_LOCATORS = [
        (
            By.XPATH,
            "//button[contains(translate(normalize-space(),"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit') "
            "and contains(translate(normalize-space(),"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'rwg review') "
            "and not(@disabled)]",
        ),
        (By.XPATH, "//button[contains(normalize-space(),'Submit SRRWG Review') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Submit SR RWG Review') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Submit Review') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Submit') and not(@disabled)]"),
    ]
    def submit_sr_rwg_review(self):
        self.wait_until_review_items_approved()
        return self.click_required_and_confirm(
            self.SUBMIT_REVIEW_LOCATORS,
            "Submit SRRWG Review",
        )

    def approve_item_set_as_sr_rwg(self, item_set_id, item_ids, item_set_url=""):
        self.open_review_item_set(item_set_id, item_set_url)
        approved_item_ids = self.approve_items_with_yes(item_set_id, item_ids)
        self.submit_sr_rwg_review()
        return approved_item_ids
