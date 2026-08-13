from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from pages.common.review_queue_page import BaseReviewQueuePage


class RWGReviewQueuePage(BaseReviewQueuePage):
    """Page object for RWG item review, revision, and submission."""

    SUBMIT_REVIEW_LOCATORS = [
        (By.XPATH, "//button[normalize-space()='Submit RWG Review' and not(@disabled)]"),
        (
            By.XPATH,
            "//*[self::button or @role='button']"
            "[contains(normalize-space(),'Submit RWG Review') and not(@disabled)]",
        ),
        (By.XPATH, "//button[contains(normalize-space(),'Submit Review') and not(@disabled)]"),
        (By.XPATH, "//button[contains(normalize-space(),'Submit') and not(@disabled)]"),
    ]

    def confirm_approve_if_prompted(self):
        """Confirm an approval only inside a visible popup, if one appears."""
        def find_confirm_button(driver):
            return driver.execute_script(
                """
                const visible = element => {
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return rect.width > 0 && rect.height > 0
                        && style.visibility !== 'hidden'
                        && style.display !== 'none';
                };
                const isPopupContainer = element => {
                    const role = (element.getAttribute('role') || '').toLowerCase();
                    const className = String(element.className || '').toLowerCase();
                    const style = getComputedStyle(element);
                    return role === 'dialog'
                        || role === 'alertdialog'
                        || element.getAttribute('aria-modal') === 'true'
                        || /(^|[\\s_-])(modal|dialog|popup|confirm)([\\s_-]|$)/.test(className)
                        || (style.position === 'fixed'
                            && Number.parseInt(style.zIndex || '0', 10) >= 10);
                };
                const priorities = ['confirm', 'yes', 'ok', 'approve'];
                const buttons = Array.from(document.querySelectorAll(
                    'button:not([disabled]), [role="button"]'
                )).filter(button => {
                    if (!visible(button)
                        || button.getAttribute('aria-disabled') === 'true') return false;
                    const text = (button.innerText || button.textContent || '')
                        .trim().toLowerCase();
                    return priorities.includes(text);
                });

                for (const priority of priorities) {
                    for (const button of buttons) {
                        const text = (button.innerText || button.textContent || '')
                            .trim().toLowerCase();
                        if (text !== priority) continue;
                        let container = button.parentElement;
                        while (container && container !== document.body) {
                            if (visible(container) && isPopupContainer(container)) {
                                return button;
                            }
                            container = container.parentElement;
                        }
                    }
                }
                return null;
                """
            )

        try:
            confirm_button = WebDriverWait(self.driver, 4).until(find_confirm_button)
        except (TimeoutException, StaleElementReferenceException):
            return False
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            confirm_button,
        )
        try:
            confirm_button.click()
        except StaleElementReferenceException:
            # The approval completed and auto-navigation removed the popup.
            return False
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", confirm_button)
            except StaleElementReferenceException:
                return False

        return True

    def get_approve_button(self):
        """Find Approve inside the verified current item's detail container."""
        expected_title = getattr(self, "current_item_title", "")

        def find_scoped_approve(driver):
            return driver.execute_script(
                """
                const expected = arguments[0].trim().toLowerCase();
                const titleElements = Array.from(
                    document.querySelectorAll('input, textarea, div, p, span')
                ).filter(element => {
                    const rect = element.getBoundingClientRect();
                    const text = (element.value || element.innerText
                        || element.textContent || '').trim().toLowerCase();
                    return rect.width > 0
                        && rect.height > 0
                        && rect.right > window.innerWidth * 0.45
                        && rect.left < window.innerWidth * 0.82
                        && text === expected;
                }).sort((left, right) => {
                    const leftArea = left.getBoundingClientRect().width
                        * left.getBoundingClientRect().height;
                    const rightArea = right.getBoundingClientRect().width
                        * right.getBoundingClientRect().height;
                    return leftArea - rightArea;
                });

                for (const titleElement of titleElements) {
                    let container = titleElement.parentElement;
                    while (container && container !== document.body) {
                        const containerText = container.innerText || container.textContent || '';
                        if (containerText.includes('Item Response Sheet')) {
                            const buttons = Array.from(container.querySelectorAll('button'))
                                .filter(button => {
                                    const rect = button.getBoundingClientRect();
                                    return rect.width > 0
                                        && rect.height > 0
                                        && /^Approve$/i.test(
                                            (button.innerText || button.textContent || '').trim()
                                        )
                                        && !button.disabled
                                        && button.getAttribute('aria-disabled') !== 'true';
                                });
                            if (buttons[0]) return buttons[0];
                        }
                        container = container.parentElement;
                    }
                }
                return null;
                """,
                expected_title,
            )

        if expected_title:
            try:
                return WebDriverWait(self.driver, 15).until(find_scoped_approve)
            except TimeoutException:
                # The queue table can collapse an item's title to a generic
                # "Expand to view the item content..." placeholder once it
                # has an image attached (instead of the literal question
                # text) - that placeholder never appears verbatim inside the
                # item's own detail panel, so the scoped match above can
                # never succeed. Fall back to the single-item-page Approve
                # button rather than failing outright, mirroring the base
                # class's own get_approve_button() fallback.
                pass
        return self.wait_utils.until_clickable(self.APPROVE_ITEM_BUTTON, timeout=30)

    def submit_rwg_review(self):
        self.wait_until_review_items_approved()
        self.click_required_and_confirm(
            self.SUBMIT_REVIEW_LOCATORS,
            "Submit RWG Review",
        )
        self.wait_utils.until_condition(
            lambda driver: self.is_rwg_review_submitted(driver),
            timeout=30,
        )
        return True

    @staticmethod
    def is_rwg_review_submitted(driver):
        page_text = driver.execute_script(
            "return document.body.innerText || document.body.textContent || '';"
        )
        return any(
            marker in page_text
            for marker in (
                "Review submitted",
                "PENDING_SR_RWG",
                "Review Completed",
            )
        )

    def open_next_pending_item_from_item_set(
        self,
        item_set_id,
        excluded_item_ids=(),
    ):
        """Return to the item-set table and open its first pending item."""
        self.return_to_item_set_if_needed(item_set_id)
        self.wait_utils.until_condition(
            lambda driver: (
                "/items/" not in driver.current_url
                and item_set_id
                in (
                    driver.execute_script(
                        "return document.body.innerText || document.body.textContent || '';"
                    )
                    or ""
                )
            ),
            timeout=30,
        )

        visible_items = self.driver.execute_script(
            """
            return Array.from(document.querySelectorAll('table tbody tr'))
                .map((row, rowIndex) => {
                    const rowText = (row.innerText || row.textContent || '').trim();
                    const itemMatch = rowText.match(
                        /\\bIS\\d+(?:-[A-Za-z0-9]+)*-i\\d+\\b/i
                    );
                    if (!itemMatch) return null;
                    const itemId = itemMatch[0];
                    const lines = rowText.split('\\n').map(line => line.trim()).filter(Boolean);
                    const itemIndex = lines.findIndex(
                        line => line.toLowerCase().includes(itemId.toLowerCase())
                    );
                    const statusMatch = rowText.match(
                        /\\b(Approved|Pending|Under\\s+Review|Revise|Rejected)\\b/i
                    );
                    const controls = Array.from(
                        row.querySelectorAll('a, button, [role="button"]')
                    );
                    const target = controls.find(control =>
                        (control.innerText || control.textContent || '')
                            .trim().toLowerCase() === itemId.toLowerCase()
                    ) || controls.find(control =>
                        /^view$/i.test(
                            (control.innerText || control.textContent || '').trim()
                        )
                    ) || controls[0];
                    return {
                        itemId,
                        rowIndex,
                        status: statusMatch ? statusMatch[1] : '',
                        targetUrl: target
                            ? (target.href || target.getAttribute('href') || '')
                            : '',
                        title: lines.find(line =>
                            /^Is\\s+/i.test(line) || /Upload run/i.test(line)
                        ) || (itemIndex >= 0 ? (lines[itemIndex + 1] || '') : ''),
                    };
                })
                .filter(Boolean);
            """
        )
        unique_items = {
            item["itemId"]: item
            for item in visible_items
        }
        self.current_item_ids = tuple(unique_items)
        self.current_item_urls = {
            item_id: item.get("targetUrl", "")
            for item_id, item in unique_items.items()
        }
        self.current_item_titles = {
            item_id: item.get("title", "")
            for item_id, item in unique_items.items()
        }

        excluded = {item_id.casefold() for item_id in excluded_item_ids}
        pending_items = [
            item
            for item in visible_items
            if item["itemId"].casefold() not in excluded
            and item.get("status", "").casefold() in {"pending", "under review"}
        ]
        pending_items.sort(
            key=lambda item: int(item["itemId"].rsplit("-i", 1)[-1])
        )
        if not pending_items:
            return ""

        pending_item = pending_items[0]
        pending_item_id = pending_item["itemId"]
        expected_title = pending_item.get("title", "")
        if not expected_title:
            raise TimeoutException(
                f"Could not resolve the question title for {pending_item_id} from its table row."
            )
        self.click_item_row_and_wait_for_split_view(
            pending_item_id,
            expected_title,
            item_set_id,
        )
        if expected_title.casefold() not in self.get_open_item_title(expected_title).casefold():
            if not self.click_left_item_by_title(expected_title):
                raise TimeoutException(
                    f"Could not click the left-side card for {pending_item_id}: "
                    f"{expected_title}"
                )
        self.wait_utils.until_condition(
            lambda driver: expected_title.casefold()
            in self.get_open_item_title(expected_title).casefold(),
            timeout=30,
        )
        self.current_item_id = pending_item_id
        self.current_item_set_id = pending_item_id.rsplit("-i", 1)[0]
        self.current_item_title = expected_title
        return pending_item_id

    def click_item_row_and_wait_for_split_view(
        self,
        item_id,
        expected_title,
        item_set_id,
    ):
        """Native-click the exact item row and wait until its left card exists."""
        item_link = (
            By.XPATH,
            "//table//tbody/tr"
            f"[.//*[contains(normalize-space(),'{item_id}')]]"
            "//*[self::a or self::button or @role='button']"
            f"[contains(normalize-space(),'{item_id}')][1]",
        )
        last_error = None
        for attempt in range(2):
            starting_url = self.driver.current_url
            try:
                link = self.wait_utils.until_clickable(item_link, timeout=15)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    link,
                )
                link.click()
                self.wait_utils.until_condition(
                    lambda driver: (
                        driver.current_url != starting_url
                        and self.is_left_item_title_visible(expected_title)
                    ),
                    timeout=30,
                )
                return
            except (StaleElementReferenceException, TimeoutException) as error:
                last_error = error
                if attempt == 1:
                    break
                self.driver.back()
                self.wait_utils.until_condition(
                    lambda driver: (
                        "/items/" not in driver.current_url
                        and item_set_id
                        in (
                            driver.execute_script(
                                "return document.body.innerText || document.body.textContent || '';"
                            )
                            or ""
                        )
                    ),
                    timeout=30,
                )
        raise TimeoutException(
            f"Could not open the split view for {item_id} after two native-click attempts."
        ) from last_error

    def is_left_item_title_visible(self, expected_title):
        return bool(
            self.driver.execute_script(
                """
                const expected = arguments[0].trim().toLowerCase();
                return Array.from(document.querySelectorAll('div, p, span, button, a'))
                    .some(element => {
                        const rect = element.getBoundingClientRect();
                        const text = (element.innerText || element.textContent || '')
                            .trim().toLowerCase();
                        return rect.width > 0
                            && rect.height > 0
                            && rect.left < window.innerWidth * 0.20
                            && (text === expected || text.includes(expected));
                    });
                """,
                expected_title,
            )
        )

    def click_left_item_by_title(self, expected_title):
        """Click the exact left-side item card by its question text."""
        return bool(
            self.driver.execute_script(
                """
                const expected = arguments[0].trim().toLowerCase();
                const candidates = Array.from(
                    document.querySelectorAll('button, a, [role="button"], div, p, span')
                ).filter(element => {
                    const rect = element.getBoundingClientRect();
                    const text = (element.innerText || element.textContent || '')
                        .trim().toLowerCase();
                    return rect.width > 0
                        && rect.height > 0
                        && rect.left < window.innerWidth * 0.20
                        && (text === expected || text.includes(expected));
                }).sort((left, right) => {
                    const leftText = (left.innerText || left.textContent || '').trim();
                    const rightText = (right.innerText || right.textContent || '').trim();
                    return leftText.length - rightText.length;
                });
                const target = candidates[0];
                if (!target) return false;
                target.scrollIntoView({block: 'center'});
                target.click();
                return true;
                """,
                expected_title,
            )
        )

    def sync_current_item_from_url(self):
        """Update the canonical item ID after the SPA auto-advances."""
        current_url = self.driver.current_url.rstrip("/")
        for item_id, item_url in getattr(self, "current_item_urls", {}).items():
            if item_url and item_url.rstrip("/") == current_url:
                self.current_item_id = item_id
                self.current_item_set_id = item_id.rsplit("-i", 1)[0]
                self.current_item_title = getattr(
                    self,
                    "current_item_titles",
                    {},
                ).get(item_id, "")
                return item_id
        return getattr(self, "current_item_id", None)

    def approve_item_set_as_rwg(self, item_set_id, item_ids, item_set_url=""):
        self.open_review_item_set(item_set_id, item_set_url)
        approved_item_ids = self.approve_items_with_yes(item_set_id, item_ids)
        self.submit_rwg_review()
        return approved_item_ids

    def send_item_set_back_as_rwg(self, item_set_id, item_ids, item_set_url=""):
        self.open_review_item_set(item_set_id, item_set_url)
        revised_item_ids = self.send_items_back_for_revision(item_set_id, item_ids)
        self.click_required_and_confirm(self.SUBMIT_REVIEW_LOCATORS, "Submit RWG Review")
        return revised_item_ids

    def revise_some_and_approve_rest_as_rwg(
        self,
        item_set_id,
        item_ids,
        item_set_url="",
        revision_count=2,
    ):
        self.open_review_item_set(item_set_id, item_set_url)
        revised_item_ids, approved_item_ids = self.revise_some_items_and_approve_rest(
            item_set_id,
            item_ids,
            revision_count=revision_count,
        )
        self.click_required_and_confirm(self.SUBMIT_REVIEW_LOCATORS, "Submit RWG Review")
        return revised_item_ids, approved_item_ids


# Backward-compatible name for existing RWG-only imports.
ReviewQueuePage = RWGReviewQueuePage
