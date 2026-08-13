import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pages.sme.upload_item_file_page import UploadItemFilePage


class ItemSetPage(UploadItemFilePage):
    """Item-set lookup restricted to a unique automation prefix."""

    def find_item_set_by_unique_prefix(self, prefix):
        if not prefix.startswith("QAR_AUTO_"):
            raise ValueError(f"Unsafe QAR item-set prefix: {prefix!r}")
        self.open_sets_module()
        search_input = self.wait_utils.until_visible(self.ITEM_SET_SEARCH_INPUT, timeout=20)
        search_input.clear()
        search_input.send_keys(prefix)

        def matching_row(driver):
            return driver.execute_script(
                """
                const prefix = arguments[0].toLowerCase();
                return Array.from(document.querySelectorAll('table tbody tr')).find(row =>
                    (row.innerText || row.textContent || '').toLowerCase().includes(prefix)
                ) || null;
                """,
                prefix,
            )

        row = self.wait_utils.until_condition(matching_row, timeout=30)
        row_text = row.text
        match = re.search(r"\b(IS\d+(?:-[A-Za-z0-9]+)*)\b", row_text)
        if not match:
            raise TimeoutException(
                f"Prefix {prefix!r} matched a row without an item-set ID: {row_text}"
            )
        return {
            "item_set_id": match.group(1),
            "row_text": row_text,
            "row": row,
        }

    def open_item_set_by_unique_prefix(self, prefix):
        evidence = self.find_item_set_by_unique_prefix(prefix)
        control = self.driver.execute_script(
            """
            const row = arguments[0];
            return row.querySelector('a, button, [role="button"], [tabindex]') || row;
            """,
            evidence["row"],
        )
        self.driver.execute_script("arguments[0].click();", control)
        self.wait_utils.until_condition(
            lambda driver: evidence["item_set_id"]
            in driver.find_element(By.TAG_NAME, "body").text,
            timeout=60,
        )
        return evidence

    def submit_for_qar(self):
        result = self.rerun_qar_if_enabled()
        if "not available" in result.casefold() or "disabled" in result.casefold():
            raise TimeoutException(f"Submit for QAR was unavailable: {result}")
        return result

