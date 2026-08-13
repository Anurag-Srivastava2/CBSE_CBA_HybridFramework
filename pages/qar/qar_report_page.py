import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pages.common.base_page import BasePage


class QARReportPage(BasePage):
    """QAR report polling and per-item check assertions."""

    REPORT_TAB_LOCATORS = (
        (
            By.XPATH,
            "//*[self::button or @role='tab' or @role='button']"
            "[contains(normalize-space(),'QAR Report')]",
        ),
        (
            By.XPATH,
            "//*[contains(normalize-space(),'QAR Report') and not(self::body)]",
        ),
    )

    PROCESSING_MARKERS = (
        "processing qar",
        "running qar",
        "generating report",
        "analysing items",
        "analyzing items",
    )
    COMPLETE_MARKERS = (
        "qar completed",
        "qar report",
        "approved",
        "need improvement",
        "needs improvement",
        "needs revision",
        "rejected",
        "hard validation",
    )

    def body_text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def open_report_if_available(self):
        """Open the per-item QAR report tab when the detail view provides one."""
        for locator in self.REPORT_TAB_LOCATORS:
            for target in self.driver.find_elements(*locator):
                try:
                    if not target.is_displayed():
                        continue
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        target,
                    )
                    try:
                        target.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", target)
                    try:
                        self.wait_utils.until_condition(
                            lambda driver: any(
                                marker
                                in driver.find_element(By.TAG_NAME, "body").text.casefold()
                                for marker in (
                                    "hard validation",
                                    "metadata alignment",
                                    "duplicate detection",
                                    "plagiarism detection",
                                    "bias detection",
                                    "grammar",
                                    "clarity",
                                )
                            ),
                            timeout=10,
                        )
                    except TimeoutException:
                        pass
                    return True
                except Exception:
                    continue
        return False

    def inspect_item_feedback(self, item_id):
        """Return the visible QAR status, score, and failing checks for one item."""
        self.open_report_if_available()
        return {
            "status": self.get_item_status(item_id),
            "score": self.get_item_score(item_id),
            "failure_reasons": self.get_item_failure_reasons(item_id),
        }

    def open_item_report(self, item_id):
        """Open one result item before reading its criterion cards."""
        compact_item_id = re.sub(r"[^a-z0-9]", "", item_id.casefold())
        item_number_match = re.search(r"-i(\d+)$", item_id, re.IGNORECASE)
        item_number = item_number_match.group(1) if item_number_match else ""
        starting_url = self.driver.current_url
        clicked = self.driver.execute_script(
            r"""
            const expected = arguments[0];
            const itemNumber = arguments[1];
            const compact = value => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0
                    && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const candidates = Array.from(document.querySelectorAll(
                'a, button, [role="button"], table tbody tr, [data-testid*="item"], article'
            )).filter(element => visible(element)
                && compact(element.innerText || element.textContent).includes(expected));
            candidates.sort((left, right) => {
                const leftClickable = left.matches('a, button, [role="button"]') ? 0 : 1;
                const rightClickable = right.matches('a, button, [role="button"]') ? 0 : 1;
                if (leftClickable !== rightClickable) return leftClickable - rightClickable;
                return compact(left.innerText || left.textContent).length
                    - compact(right.innerText || right.textContent).length;
            });
            let target = candidates[0] || null;
            // The item-set detail screen shown to reviewers displays only a
            // numbered item card on the left; the full item ID appears in the
            // detail header after that card is selected.
            if (!target && itemNumber) {
                const numberLabels = Array.from(document.querySelectorAll(
                    'span, div, p, td, button, [role="button"]'
                )).filter(element => visible(element)
                    && (element.innerText || element.textContent || '').trim() === itemNumber);
                const numberedCards = [];
                for (const label of numberLabels) {
                    let card = label;
                    for (let depth = 0; card && depth < 6; depth += 1, card = card.parentElement) {
                        const text = (card.innerText || card.textContent || '').trim();
                        const rect = card.getBoundingClientRect();
                        if (visible(card) && text.startsWith(itemNumber)
                            && text.length > itemNumber.length && text.length < 1000
                            && rect.width >= 150 && rect.width <= 600
                            && rect.height >= 35 && rect.height <= 300
                            && /true or false|pending|approved|improvement|revision|rejected/i.test(text)) {
                            numberedCards.push(card);
                            break;
                        }
                    }
                }
                numberedCards.sort((left, right) =>
                    (left.innerText || left.textContent || '').length
                    - (right.innerText || right.textContent || '').length
                );
                target = numberedCards[0] || null;
            }
            if (!target) return false;
            if (target.matches('tr')) {
                // QAR overview rows contain several editable dropdown buttons.
                // Open the item through its dedicated View cell (or ID link),
                // never through the first arbitrary button in the row.
                const lastCell = target.querySelector('td:last-child');
                const firstCell = target.querySelector('td:first-child');
                const nested = (lastCell && Array.from(lastCell.querySelectorAll(
                    'a, button, [role="button"], [tabindex]'
                )).find(element => visible(element)))
                    || (lastCell && lastCell.querySelector('svg, [class*="chevron" i]'))
                    || lastCell
                    || (firstCell && Array.from(firstCell.querySelectorAll(
                        'a, button, [role="button"], [tabindex]'
                    )).find(element => visible(element)))
                    || null;
                if (nested) target = nested;
            } else if (target.matches('article, [data-testid*="item"]')) {
                const nested = Array.from(target.querySelectorAll('a, button, [role="button"]'))
                    .find(element => visible(element)) || null;
                if (nested) target = nested;
            }
            target.scrollIntoView({block: 'center'});
            target.click();
            return true;
            """,
            compact_item_id,
            item_number,
        )
        if not clicked:
            raise AssertionError(f"Could not open QAR result item {item_id}.")
        self.wait_utils.until_condition(
            lambda driver: (
                driver.current_url != starting_url
                or any(
                    element.is_displayed()
                    for locator in self.REPORT_TAB_LOCATORS
                    for element in driver.find_elements(*locator)
                )
            ),
            timeout=30,
        )
        self.open_report_if_available()
        return True

    def expand_open_check_card(self, check_name):
        """Expand a criterion card when the current UI provides an Expand button."""
        return bool(
            self.driver.execute_script(
                r"""
                const expected = arguments[0].trim().toLowerCase();
                const visible = element => {
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return rect.width > 0 && rect.height > 0
                        && style.display !== 'none' && style.visibility !== 'hidden';
                };
                const containers = Array.from(document.querySelectorAll(
                    'article, section, div, li, tr'
                )).filter(element => {
                    const text = (element.innerText || element.textContent || '').trim();
                    return visible(element) && text.toLowerCase().includes(expected)
                        && text.length < 2500;
                }).sort((left, right) =>
                    (left.innerText || left.textContent || '').length
                    - (right.innerText || right.textContent || '').length
                );
                for (const container of containers) {
                    const button = Array.from(container.querySelectorAll(
                        'button, [role="button"]'
                    )).find(element => visible(element)
                        && /expand|details|view/i.test(
                            [element.innerText, element.textContent,
                             element.getAttribute('aria-label'), element.getAttribute('title')]
                                .filter(Boolean).join(' ')
                        ));
                    if (button) {
                        button.click();
                        return true;
                    }
                }
                return false;
                """,
                check_name,
            )
        )

    def get_open_item_check_evidence(self, item_id, check_name, expand=False):
        """Open an item and return one check's visible card, percentage and color.

        Some checks (e.g. Image Moderation) never render a numeric percentage --
        they show a plain "--" and signal pass/fail purely through the card's
        border/text color instead. `status_color` reports that as "pass",
        "fail", or None (unrecognised) so callers can fall back to it when
        `score` is None.
        """
        self.open_item_report(item_id)
        check_labels = [check_name]
        short_label = re.sub(r"\s+Detection$", "", check_name, flags=re.IGNORECASE)
        if short_label.casefold() != check_name.casefold():
            check_labels.append(short_label)

        def _normalize(value):
            return re.sub(r"[_\s]+", " ", value.casefold()).strip()

        try:
            self.wait_utils.until_condition(
                lambda driver: any(
                    _normalize(label) in _normalize(driver.find_element(By.TAG_NAME, "body").text)
                    for label in check_labels
                ),
                timeout=30,
            )
        except TimeoutException:
            pass

        if expand:
            for label in check_labels:
                if self.expand_open_check_card(label):
                    self.pause_before_action()
                    break
        card = ""
        status_color = None
        for label in check_labels:
            card = self.get_check_card_text(label, item_id=item_id)
            color_item_id = item_id
            if not card:
                # In split/detail views the item ID is in the header, not repeated
                # in every report card. The item has already been explicitly opened.
                card = self.get_check_card_text(label)
                color_item_id = ""
            if card:
                status_color = self.get_check_card_status_color(
                    label, item_id=color_item_id
                )
                break
        match = re.search(
            r"(?:score\s*[:\-]?\s*)?(\d+(?:\.\d+)?)\s*%",
            card or "",
            re.IGNORECASE,
        )
        threshold_match = re.search(
            r"threshold\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*%",
            card or "",
            re.IGNORECASE,
        )
        return {
            "item_id": item_id,
            "check_name": check_name,
            "card": card,
            "score": float(match.group(1)) if match else None,
            "threshold": float(threshold_match.group(1)) if threshold_match else None,
            "status_color": status_color,
        }

    def get_check_card_status_color(self, check_name, item_id=""):
        """Classify a check card's border/text color as "pass", "fail" or None.

        Checks that never expose a numeric score (e.g. Image Moderation, which
        shows "--" and only a red/green accent) still need a pass/fail signal;
        this reads the rendered color instead of the text.
        """
        return self.driver.execute_script(
            r"""
            const norm = value => (value || '').toLowerCase().replace(/[_\s]+/g, ' ').trim();
            const checkName = norm(arguments[0]);
            const itemId = arguments[1].replace(/\s+/g, '').toLowerCase();
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0
                    && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const candidates = Array.from(document.querySelectorAll(
                'tr, article, section, div, li'
            )).filter(element => {
                if (!visible(element)) return false;
                const text = (element.innerText || element.textContent || '').trim();
                const compact = text.replace(/\s+/g, '').toLowerCase();
                return norm(text).includes(checkName)
                    && (!itemId || compact.includes(itemId))
                    && text.length < 2500;
            }).sort((left, right) => {
                const a = (left.innerText || left.textContent || '').length;
                const b = (right.innerText || right.textContent || '').length;
                return a - b;
            });
            const target = candidates[0];
            if (!target) return null;
            const parseRgb = value => {
                const match = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(value || '');
                return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null;
            };
            const seen = new Set();
            const elements = [target, ...target.querySelectorAll('*')];
            for (const element of elements) {
                const style = getComputedStyle(element);
                for (const value of [
                    style.borderLeftColor,
                    style.borderColor,
                    style.backgroundColor,
                    style.color,
                ]) {
                    if (!value || seen.has(value)) continue;
                    seen.add(value);
                    const rgb = parseRgb(value);
                    if (!rgb) continue;
                    const [r, g, b] = rgb;
                    if (r > g + 30 && r > b + 30) return 'fail';
                    if (g > r + 30 && g > b + 30) return 'pass';
                }
            }
            return null;
            """,
            check_name,
            item_id,
        )

    def wait_until_processed(self, item_set_id, timeout=180):
        def processed(driver):
            text = driver.find_element(By.TAG_NAME, "body").text
            normalized = text.casefold()
            return (
                item_set_id.casefold() in normalized
                and not any(marker in normalized for marker in self.PROCESSING_MARKERS)
                and any(marker in normalized for marker in self.COMPLETE_MARKERS)
            )

        try:
            self.wait_utils.until_condition(processed, timeout=timeout)
        except TimeoutException as error:
            raise TimeoutException(
                f"QAR report for {item_set_id} did not finish within {timeout} seconds. "
                f"URL: {self.driver.current_url}; page: {self.body_text()[:1200]}"
            ) from error
        return self.body_text()

    def get_item_status(self, item_id):
        status = self.driver.execute_script(
            r"""
            const expected = arguments[0].replace(/\s+/g, '').toLowerCase();
            const row = Array.from(document.querySelectorAll('table tbody tr')).find(
                candidate => (candidate.innerText || candidate.textContent || '')
                    .replace(/\s+/g, '').toLowerCase().includes(expected)
            );
            if (!row) return '';
            const text = row.innerText || row.textContent || '';
            const match = text.match(
                /\b(Approved|Passed|Needs? Improvement|Needs Revision|Revise|Rejected|Failed|Blocked|Pending)\b/i
            );
            return match ? match[1] : '';
            """,
            item_id,
        )
        if status:
            return status
        text = self.body_text()
        match = re.search(
            rf"{re.escape(item_id)}[\s\S]{{0,500}}?"
            r"\b(Approved|Passed|Needs? Improvement|Needs Revision|Revise|Rejected|Failed|Blocked|Pending)\b",
            text,
            re.IGNORECASE,
        )
        return match.group(1) if match else ""

    def get_check_card_text(self, check_name, item_id=""):
        return self.driver.execute_script(
            r"""
            const norm = value => (value || '').toLowerCase().replace(/[_\s]+/g, ' ').trim();
            const checkName = norm(arguments[0]);
            const itemId = arguments[1].replace(/\s+/g, '').toLowerCase();
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0
                    && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const candidates = Array.from(document.querySelectorAll(
                'tr, article, section, div, li'
            )).filter(element => {
                if (!visible(element)) return false;
                const text = (element.innerText || element.textContent || '').trim();
                const compact = text.replace(/\s+/g, '').toLowerCase();
                return norm(text).includes(checkName)
                    && (!itemId || compact.includes(itemId))
                    && text.length < 2500;
            }).sort((left, right) => {
                const a = (left.innerText || left.textContent || '').length;
                const b = (right.innerText || right.textContent || '').length;
                return a - b;
            });
            return candidates[0]
                ? (candidates[0].innerText || candidates[0].textContent || '').trim()
                : '';
            """,
            check_name,
            item_id,
        )

    def get_check_score(self, check_name, item_id=""):
        text = self.get_check_card_text(check_name, item_id=item_id)
        match = re.search(r"(?:score\s*[:\-]?\s*)?(\d+(?:\.\d+)?)\s*%", text, re.I)
        return float(match.group(1)) if match else None

    def get_item_score(self, item_id):
        """Return the overall/average QAR score associated with one item row/card."""
        text = self.driver.execute_script(
            r"""
            const expected = arguments[0].replace(/\s+/g, '').toLowerCase();
            const candidates = Array.from(document.querySelectorAll(
                'table tbody tr, article, section, [data-testid*="item"]'
            )).filter(element => {
                const compact = (element.innerText || element.textContent || '')
                    .replace(/\s+/g, '').toLowerCase();
                return compact.includes(expected);
            }).sort((left, right) => {
                const a = (left.innerText || left.textContent || '').length;
                const b = (right.innerText || right.textContent || '').length;
                return a - b;
            });
            return candidates[0]
                ? (candidates[0].innerText || candidates[0].textContent || '').trim()
                : '';
            """,
            item_id,
        )
        patterns = (
            r"(?:overall|average|qar|final)\s+score\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*%",
            r"\bscore\s*[:\-]\s*(\d+(?:\.\d+)?)\s*%",
        )
        for pattern in patterns:
            match = re.search(pattern, text or "", re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def get_item_failure_reasons(self, item_id):
        """Return failing/flagged QAR check cards for one item."""
        reasons = {}
        for check_name in (
            "Hard Validation",
            "Metadata Alignment",
            "Bias Detection",
            "Grammar",
            "Clarity",
            "Duplicate Detection",
            "Plagiarism Detection",
        ):
            text = self.get_check_card_text(check_name, item_id=item_id)
            if text and re.search(
                r"\b(fail(?:ed)?|flag(?:ged)?|blocked|need(?:s)? improvement|revision)\b",
                text,
                re.IGNORECASE,
            ):
                reasons[check_name] = text
        return reasons

    def assert_check_result(
        self,
        item_id,
        check_name,
        expected_layer,
        expected_outcome,
    ):
        text = self.get_check_card_text(check_name, item_id=item_id)
        assert text, f"No {check_name} card was found for {item_id}."
        normalized = re.sub(r"[^a-z0-9]+", "", text.casefold())
        layer = re.sub(r"[^a-z0-9]+", "", expected_layer.casefold())
        assert layer in normalized, (
            f"{check_name} for {item_id} did not show {expected_layer}: {text}"
        )
        outcomes = (
            expected_outcome
            if isinstance(expected_outcome, (tuple, list, set))
            else (expected_outcome,)
        )
        assert any(outcome.casefold() in text.casefold() for outcome in outcomes), (
            f"{check_name} for {item_id} did not show {outcomes}: {text}"
        )
        return text
