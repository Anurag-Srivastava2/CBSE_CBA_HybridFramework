import base64
from pathlib import Path
import re
from time import sleep

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from pages.common.base_page import BasePage
from pages.qar.qar_report_page import QARReportPage
from utilities.screenshot_utils import ScreenshotUtils
from utilities.read_config import ReadConfig


def _safe_print(message):
    """Print without crashing on consoles using a narrow codec (e.g. Windows cp1252)."""
    print(str(message).encode("ascii", errors="replace").decode("ascii"))


class UploadItemFilePage(BasePage):
    """SME upload item file page."""

    # --- Item creation navigation locators ---
    ITEM_CREATION_MENU_LOCATORS = [
        (
            By.XPATH,
            "//*[self::button or self::a][normalize-space()='Create' "
            "or .//*[normalize-space()='Create']]",
        ),
        (By.CSS_SELECTOR, ".lucide-pen-line"),
        (By.XPATH, "//button[.//*[name()='svg' and contains(@class,'lucide-pen-line')]]"),
        (By.XPATH, "(//div[@id='root']//ul/li[3]/button)[1]"),
    ]
    GLOBAL_LOADING_INDICATOR = (
        By.XPATH,
        "//*[starts-with(normalize-space(), 'Loading')]",
    )
    # --- Item creation navigation actions ---
    def close_popup_if_open(self):
        self.pause_before_action()
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def open_item_creation_module(self):
        last_error = None
        for attempt in range(3):
            self.wait_for_application_to_load()
            try:
                self.click_any_element(self.ITEM_CREATION_MENU_LOCATORS)
                state = self.wait_utils.until_condition(
                    lambda driver: (
                        "dynamic_import_error"
                        if "failed to fetch dynamically imported module"
                        in driver.find_element(By.TAG_NAME, "body").text.casefold()
                        else (
                            "ready"
                            if any(
                                element.is_displayed()
                                for locator in self.UPLOAD_ITEM_FILE_TAB_LOCATORS
                                for element in driver.find_elements(*locator)
                            )
                            else False
                        )
                    ),
                    timeout=30,
                )
                if state == "ready":
                    return
            except Exception as error:
                last_error = error
            if attempt < 2:
                self.driver.refresh()
        raise TimeoutException(
            "Item creation module did not load after retrying a dynamic-import failure."
        ) from last_error

    def wait_for_application_to_load(self):
        def loading_indicator_cleared(driver):
            if driver.find_elements(*self.GLOBAL_LOADING_INDICATOR):
                return False
            # A clear read straight after navigation can race the very first
            # paint (nothing rendered yet, so the indicator hasn't appeared).
            # Confirm it stays clear a moment later before trusting it.
            sleep(0.3)
            return not driver.find_elements(*self.GLOBAL_LOADING_INDICATOR)

        for attempt in range(2):
            try:
                self.wait_utils.until_condition(loading_indicator_cleared, timeout=45)
                return
            except TimeoutException:
                if attempt == 0:
                    self.driver.refresh()
        raise TimeoutException("Application remained on the global Loading screen after refresh.")

    # --- Upload item file locators ---
    UPLOAD_ITEM_FILE_TAB_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Upload Item File')]"),
        (By.XPATH, "//*[contains(normalize-space(),'Upload Item File')]"),
    ]

    FILE_INPUT = (
        By.XPATH,
        "//input[@type='file' and not(@disabled)]",
    )
    UPLOADED_FILE_DELETE_LOCATORS = [
        (
            By.XPATH,
            "//button[contains(@aria-label,'Delete') or contains(@aria-label,'Remove') "
            "or contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove')]",
        ),
        (
            By.XPATH,
            "//*[name()='svg' and (contains(@class,'trash') or contains(@class,'Trash'))]"
            "/ancestor::button[1]",
        ),
        (
            By.XPATH,
            "//button[.//*[name()='svg' and (contains(@class,'trash') or contains(@class,'Trash'))]]",
        ),
    ]
    DELETE_CONFIRM_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
            "//button[contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove') "
            "or contains(normalize-space(),'Confirm') or contains(normalize-space(),'Yes')]",
        ),
        (
            By.XPATH,
            "//button[contains(normalize-space(),'Delete') or contains(normalize-space(),'Remove') "
            "or contains(normalize-space(),'Confirm') or contains(normalize-space(),'Yes')]",
        ),
    ]
    UPLOAD_SUCCESS_MESSAGE = (
        By.XPATH,
        "//*[contains(normalize-space(), 'All files uploaded and validated successfully') "
        "and contains(normalize-space(), 'Status: PASSED')]",
    )
    UPLOADED_FILE_NAME = (
        By.XPATH,
        "//*[contains(normalize-space(), '.xlsx') "
        "or contains(normalize-space(), '.xls') "
        "or contains(normalize-space(), '.csv')]",
    )
    UPLOAD_DOCUMENTS_HEADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'Upload Documents')]",
    )
    DOWNLOAD_TEMPLATE_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Download Template')]"),
        (By.XPATH, "//a[contains(normalize-space(),'Download Template')]"),
        (By.XPATH, "//*[contains(normalize-space(),'Download') and contains(normalize-space(),'Template')]"),
    ]
    UPLOAD_HISTORY_ROWS = (
        By.XPATH,
        "//table[.//th[contains(translate(normalize-space(), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
        "'file upload status')]]//tbody/tr",
    )
    UPLOAD_REJECTION_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='alert' or @role='status' or contains(@class,'toast') "
            "or contains(@class,'Toast') or contains(@class,'error') or contains(@class,'Error')]"
            "[contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'invalid') "
            "or contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'failed') "
            "or contains(translate(normalize-space(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'error')]",
        ),
        (
            By.XPATH,
            "//*[contains(normalize-space(),'Invalid file format') "
            "or contains(normalize-space(),'Upload Failed') "
            "or contains(normalize-space(),'Header row') "
            "or contains(normalize-space(),'Only .xlsx') "
            "or contains(normalize-space(),'Missing required columns') "
            "or contains(normalize-space(),'required columns')]",
        ),
    ]

    # --- Upload item file actions ---
    def open_upload_item_file_tab(self):
        self.click_any_element(self.UPLOAD_ITEM_FILE_TAB_LOCATORS)

    def download_latest_template(self, download_directory, timeout=30):
        download_directory = Path(download_directory).resolve()
        download_directory.mkdir(parents=True, exist_ok=True)
        self.driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_directory)},
        )
        before = set(download_directory.glob("*"))
        self.click_any_element(self.DOWNLOAD_TEMPLATE_LOCATORS)
        for _ in range(timeout * 2):
            candidates = [
                path for path in download_directory.glob("*.xlsx")
                if path not in before and not path.name.endswith(".crdownload")
            ]
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime)
            sleep(0.5)
        raise TimeoutException("Latest item-upload template was not downloaded.")

    def get_upload_history_statuses(self, timeout=30):
        """Return the statuses shown in the Previously Uploaded Files table."""
        try:
            rows = self.wait_utils.until_condition(
                lambda driver: [
                    row
                    for row in driver.find_elements(*self.UPLOAD_HISTORY_ROWS)
                    if row.is_displayed()
                ]
                or False,
                timeout=timeout,
            )
        except TimeoutException:
            return []
        statuses = []
        for row in rows:
            row_lines = {line.strip().upper() for line in row.text.splitlines() if line.strip()}
            for status in ("PASSED", "FAILED"):
                if status in row_lines:
                    statuses.append(status)
                    break
        return statuses

    def get_upload_history_row(self, status, action_text=None, timeout=30):
        normalized_status = str(status).strip().upper()
        if normalized_status not in ("PASSED", "FAILED"):
            raise ValueError(f"Unsupported upload-history status: {status!r}")

        def matching_row(driver):
            for row in driver.find_elements(*self.UPLOAD_HISTORY_ROWS):
                try:
                    if not row.is_displayed():
                        continue
                    row_lines = {
                        line.strip().upper()
                        for line in row.text.splitlines()
                        if line.strip()
                    }
                    if normalized_status not in row_lines:
                        continue
                    if action_text:
                        matching_actions = row.find_elements(
                            By.XPATH,
                            ".//*[self::button or self::a]"
                            f"[contains(normalize-space(), '{action_text}')]",
                        )
                        if not any(
                            action.is_displayed() and action.is_enabled()
                            for action in matching_actions
                        ):
                            continue
                    return row
                except Exception:
                    continue
            return False

        return self.wait_utils.until_condition(matching_row, timeout=timeout)

    def capture_upload_history_status_screenshot(
        self,
        status,
        screenshot_name,
        action_text=None,
    ):
        row = self.get_upload_history_row(status, action_text=action_text)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            row,
        )
        return ScreenshotUtils.capture(self.driver, screenshot_name)

    def download_upload_history_file(self, status, download_directory, timeout=45):
        """Download the first PASSED or FAILED upload-history workbook."""
        normalized_status = str(status).strip().upper()
        action_text = {
            "PASSED": "Download File",
            "FAILED": "Download Annotated File",
        }.get(normalized_status)
        if not action_text:
            raise ValueError(f"Unsupported upload-history status: {status!r}")

        download_directory = Path(download_directory).resolve()
        download_directory.mkdir(parents=True, exist_ok=True)
        self.driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_directory)},
        )
        before = {path.resolve() for path in download_directory.iterdir() if path.is_file()}

        row = self.get_upload_history_row(
            normalized_status,
            action_text=action_text,
            timeout=timeout,
        )
        buttons = row.find_elements(
            By.XPATH,
            ".//*[self::button or self::a]"
            f"[contains(normalize-space(), '{action_text}')]",
        )
        download_button = next(
            (button for button in buttons if button.is_displayed() and button.is_enabled()),
            None,
        )
        if download_button is None:
            raise TimeoutException(
                f"{action_text!r} was not available for the {normalized_status} upload row."
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            download_button,
        )
        self.pause_before_action()
        try:
            download_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", download_button)

        for _ in range(timeout * 2):
            candidates = [
                path
                for path in download_directory.iterdir()
                if path.is_file()
                and path.resolve() not in before
                and not path.name.casefold().endswith((".crdownload", ".tmp"))
                and path.stat().st_size > 0
            ]
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime)
            sleep(0.5)
        raise TimeoutException(
            f"The {normalized_status} upload-history workbook was not downloaded."
        )

    VIEW_ERRORS_DIALOG_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]",
        ),
    ]

    def get_upload_history_row_by_file_name(self, file_name, timeout=45):
        """Poll the Previously Uploaded Files table for a row for this file name.

        Used to confirm a just-uploaded file shows up in the history listing in
        real time (i.e. without needing a manual page refresh).
        """
        normalized_name = str(file_name).strip().casefold()

        def matching_row(driver):
            for row in driver.find_elements(*self.UPLOAD_HISTORY_ROWS):
                try:
                    if row.is_displayed() and normalized_name in row.text.casefold():
                        return row
                except Exception:
                    continue
            return False

        return self.wait_utils.until_condition(matching_row, timeout=timeout)

    @staticmethod
    def get_upload_history_row_status(row):
        row_lines = {line.strip().upper() for line in row.text.splitlines() if line.strip()}
        for status in ("PASSED", "FAILED"):
            if status in row_lines:
                return status
        return None

    def click_upload_history_row_action(self, row, action_text):
        buttons = row.find_elements(
            By.XPATH,
            ".//*[self::button or self::a]"
            f"[contains(normalize-space(), '{action_text}')]",
        )
        button = next(
            (button for button in buttons if button.is_displayed() and button.is_enabled()),
            None,
        )
        if button is None:
            raise TimeoutException(
                f"{action_text!r} was not available in the upload-history row."
            )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        self.pause_before_action()
        try:
            button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", button)
        return button

    def click_view_errors_and_get_message(self, row, timeout=20):
        """Click 'View Errors' on a FAILED row and return the error details shown."""
        self.click_upload_history_row_action(row, "View Errors")

        def error_content(driver):
            for locator in self.VIEW_ERRORS_DIALOG_LOCATORS:
                for element in driver.find_elements(*locator):
                    try:
                        if element.is_displayed() and element.text.strip():
                            return element.text.strip()
                    except Exception:
                        continue
            return False

        try:
            return self.wait_utils.until_condition(error_content, timeout=timeout)
        except TimeoutException:
            # Some layouts expand the error inline instead of opening a dialog.
            return row.text.strip()

    def close_view_errors_dialog(self):
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def download_file_from_upload_history_row(self, row, action_text, download_directory, timeout=45):
        """Click a row action (e.g. 'Download Annotated File') and return the downloaded path."""
        download_directory = Path(download_directory).resolve()
        download_directory.mkdir(parents=True, exist_ok=True)
        self.driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_directory)},
        )
        before = {path.resolve() for path in download_directory.iterdir() if path.is_file()}

        self.click_upload_history_row_action(row, action_text)

        for _ in range(timeout * 2):
            candidates = [
                path
                for path in download_directory.iterdir()
                if path.is_file()
                and path.resolve() not in before
                and not path.name.casefold().endswith((".crdownload", ".tmp"))
                and path.stat().st_size > 0
            ]
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime)
            sleep(0.5)
        raise TimeoutException(f"{action_text!r} did not produce a download.")

    def upload_file(self, file_path):
        upload_path = Path(file_path).expanduser().resolve()
        if not upload_path.exists():
            raise FileNotFoundError(f"Upload item file not found: {upload_path}")

        file_input = self.wait_utils.until_present(self.FILE_INPUT, timeout=20)
        self.driver.execute_script(
            """
            const input = arguments[0];
            input.style.display = 'block';
            input.style.visibility = 'visible';
            input.style.opacity = 1;
            input.style.height = '1px';
            input.style.width = '1px';
            """,
            file_input,
        )
        file_input.send_keys(str(upload_path))
        # Selenium's file-input send_keys operation already emits the native
        # input/change events. Dispatching them again makes the SPA enqueue the
        # same workbook twice and produces duplicated QAR rows (6 -> 12).
        return upload_path

    def get_active_upload_delete_button(self):
        return self.driver.execute_script(
            """
            const markers = Array.from(document.querySelectorAll('*')).filter(element =>
                (element.innerText || element.textContent || '')
                    .trim().toLowerCase() === 'currently working on this file.'
            );
            const marker = markers[0];
            if (!marker) return null;

            let card = marker.closest('li, [role="listitem"], tr');
            if (!card) {
                card = marker.parentElement;
                while (card && card !== document.body) {
                    const text = (card.innerText || card.textContent || '').trim();
                    if (/\\.xlsx?/i.test(text) && text.length < 1200) break;
                    card = card.parentElement;
                }
            }
            if (!card || card === document.body) return null;

            return Array.from(card.querySelectorAll('button, [role="button"]'))
                .find(button => {
                    const label = [
                        button.getAttribute('aria-label'),
                        button.getAttribute('title'),
                        button.innerText,
                        button.textContent,
                    ].filter(Boolean).join(' ').toLowerCase();
                    return /delete|remove|discard|trash/.test(label)
                        || Boolean(button.querySelector(
                            'svg[class*="trash" i], [data-lucide*="trash" i]'
                        ));
                }) || null;
            """
        )

    def discard_active_upload_if_present(self):
        self.pause_before_action()

        def has_active_upload(driver):
            return (
                "currently working on this file"
                in driver.find_element(By.TAG_NAME, "body").text.casefold()
            )

        if not has_active_upload(self.driver):
            return False

        for _ in range(20):
            if not has_active_upload(self.driver):
                break

            delete_button = self.get_active_upload_delete_button()
            if delete_button is None:
                for locator in self.UPLOADED_FILE_DELETE_LOCATORS:
                    delete_button = next(
                        (
                            button
                            for button in self.driver.find_elements(*locator)
                            if button.is_displayed() and button.is_enabled()
                        ),
                        None,
                    )
                    if delete_button is not None:
                        break

            if delete_button is None:
                raise AssertionError(
                    "A previous unfinished upload is still active and has no "
                    "available delete control. Refusing to read stale item rows."
                )

            visible_delete_ids_before = {
                button.id
                for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                for button in self.driver.find_elements(*locator)
                if button.is_displayed()
            }
            self.driver.execute_script("arguments[0].click();", delete_button)
            self.confirm_delete_uploaded_file_if_prompted()
            try:
                self.wait_utils.until_condition(
                    lambda driver: (
                        not has_active_upload(driver)
                        or len(
                            {
                                button.id
                                for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                                for button in driver.find_elements(*locator)
                                if button.is_displayed()
                            }
                        )
                        < len(visible_delete_ids_before)
                    ),
                    timeout=15,
                )
            except TimeoutException:
                pass
            self.pause_before_action()
        else:
            raise AssertionError(
                "The previous unfinished upload remained active after deleting "
                "all available stale rows."
            )

        if has_active_upload(self.driver):
            raise AssertionError(
                "The previous unfinished upload could not be fully discarded."
            )

        try:
            self.wait_for_upload_slot_ready()
        except TimeoutException:
            self.driver.refresh()
            self.wait_for_application_to_load()
            self.open_item_creation_module()
            self.open_upload_item_file_tab()
            self.open_upload_step()
        return True

    def discard_staged_upload_files(self):
        """Remove files left in the upload wizard by an interrupted test run."""
        removed_any = False
        for _ in range(20):
            delete_button = None
            for locator in self.UPLOADED_FILE_DELETE_LOCATORS:
                delete_button = next(
                    (
                        button
                        for button in self.driver.find_elements(*locator)
                        if button.is_displayed() and button.is_enabled()
                    ),
                    None,
                )
                if delete_button is not None:
                    break
            if delete_button is None:
                return removed_any

            visible_delete_ids_before = {
                button.id
                for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                for button in self.driver.find_elements(*locator)
                if button.is_displayed()
            }
            self.driver.execute_script("arguments[0].click();", delete_button)
            self.confirm_delete_uploaded_file_if_prompted()
            removed_any = True
            self.wait_utils.until_condition(
                lambda driver: len(
                    {
                        button.id
                        for locator in self.UPLOADED_FILE_DELETE_LOCATORS
                        for button in driver.find_elements(*locator)
                        if button.is_displayed()
                    }
                )
                < len(visible_delete_ids_before),
                timeout=20,
            )
            self.pause_before_action()

        raise AssertionError(
            "Upload staging still contained files after 20 cleanup attempts."
        )

    def activate_uploaded_file(self, file_name):
        normalized_name = str(file_name).strip().casefold()

        def activate_exact_file(driver):
            return driver.execute_script(
                """
                const expected = arguments[0];
                const labels = Array.from(document.querySelectorAll('*'))
                    .filter(element => {
                        const text = (element.innerText || element.textContent || '')
                            .trim().toLowerCase();
                        return text === expected
                            && !Array.from(element.children).some(child =>
                                (child.innerText || child.textContent || '')
                                    .trim().toLowerCase() === expected
                            );
                    });
                const label = labels[0];
                if (!label) return false;

                let card = label.closest('li, [role="listitem"], tr');
                if (!card) {
                    card = label.parentElement;
                    while (card && card !== document.body) {
                        const text = (card.innerText || card.textContent || '').trim();
                        if (/\\.xlsx?/i.test(text) && text.length < 1200) break;
                        card = card.parentElement;
                    }
                }
                if (!card || card === document.body) return false;
                const cardText = (card.innerText || card.textContent || '').toLowerCase();
                if (cardText.includes('currently working on this file')) return true;
                const pageText = (document.body.innerText || document.body.textContent || '')
                    .toLowerCase();
                if (!pageText.includes('currently working on this file')
                    && !pageText.includes('finish editing first file')
                    && cardText.includes(expected)) {
                    return true;
                }

                const target = label.closest('a, button, [role="button"], [tabindex]')
                    || card.closest('a, button, [role="button"], [tabindex]')
                    || label;
                target.scrollIntoView({block: 'center'});
                target.click();
                return false;
                """,
                normalized_name,
            )

        self.wait_utils.until_condition(activate_exact_file, timeout=60)
        return True

    def delete_uploaded_file_if_present(self):
        """Remove the current upload card so the next file starts from a clean state."""
        last_error = None
        for locator in self.UPLOADED_FILE_DELETE_LOCATORS:
            for button in self.driver.find_elements(*locator):
                try:
                    if not button.is_displayed() or not button.is_enabled():
                        continue
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        button,
                    )
                    self.pause_before_action()
                    self.driver.execute_script("arguments[0].click();", button)
                    self.confirm_delete_uploaded_file_if_prompted()
                    self.wait_for_upload_slot_ready()
                    return True
                except Exception as error:
                    last_error = error
                    continue
        if last_error:
            raise last_error
        return False

    def confirm_delete_uploaded_file_if_prompted(self):
        for locator in self.DELETE_CONFIRM_LOCATORS:
            try:
                confirm_button = self.wait_utils.until_clickable(locator, timeout=3)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", confirm_button)
                return True
            except Exception:
                continue
        return False

    def wait_for_upload_slot_ready(self):
        self.wait_utils.until_present(self.FILE_INPUT, timeout=20)
        self.pause_before_action()
        return True

    def reset_upload_step(self):
        """Prefer deleting the file card; fall back to reopening the upload step."""
        try:
            if self.delete_uploaded_file_if_present():
                return True
        except Exception:
            pass
        self.driver.refresh()
        self.wait_for_application_to_load()
        self.open_item_creation_module()
        self.open_upload_item_file_tab()
        self.open_upload_step()
        return True

    def wait_for_upload_validation_success(self):
        """Return the upload's validation-success message.

        Tries the primary UPLOAD_SUCCESS_MESSAGE locator (the multi-file
        wording), then a broader scan that also covers the single-file wording.
        Raises AssertionError if neither reports success -- callers assert on
        the returned text, so returning an assumed-success string here would
        make a rejected upload indistinguishable from an accepted one.
        """
        # Try primary success message locator
        try:
            element = self.wait_utils.until_visible(self.UPLOAD_SUCCESS_MESSAGE, timeout=20)
            return self.extract_upload_status_message(element.text)
        except TimeoutException:
            pass

        # Broader fallback: wait for any success/status text to appear in the body.
        # Deliberately no 'Upload Status' / 'File Upload Status' clause: that is the
        # header of the ever-present "Previously Uploaded Files" history table, so it
        # matches whether or not this upload succeeded and reports false-positive
        # success. Single-file uploads word it "All N rows added successfully"
        # rather than the multi-file "validated successfully", so both are listed.
        broad_success = (
            By.XPATH,
            "//*[contains(normalize-space(),'PASSED') "
            "or contains(normalize-space(),'validated successfully') "
            "or contains(normalize-space(),'added successfully') "
            "or contains(normalize-space(),'Validation Passed')]",
        )
        try:
            element = self.wait_utils.until_visible(broad_success, timeout=60)
            return self.extract_upload_status_message(element.text)
        except TimeoutException:
            pass

        # Nothing on screen reports success. This used to return a hardcoded
        # "All files uploaded and validated successfully Status: PASSED", which
        # is the exact wording callers assert on -- so a rejected upload passed
        # as a success. Raise instead: the caller wanted proof of validation and
        # there is none. Include what the page does say, since the app reports
        # row-level failures ("All 1 row(s) failed validation") right here.
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.strip()
        except Exception:
            page_text = ""
        raise AssertionError(
            "Upload did not report validation success: no status message "
            "appeared within the wait. Page text follows:\n"
            f"{page_text[:2000]}"
        )

    def wait_for_upload_rejection(self, timeout=30):
        def visible_rejection(driver):
            for locator in self.UPLOAD_REJECTION_LOCATORS:
                for element in driver.find_elements(*locator):
                    try:
                        if element.is_displayed() and element.text.strip():
                            return element.text.strip()
                    except Exception:
                        continue
            page_text = driver.find_element(By.TAG_NAME, "body").text
            if any(
                token in page_text.casefold()
                for token in (
                    "invalid file format",
                    "upload failed",
                    "header row",
                    "only .xlsx",
                    "missing required columns",
                    "required columns",
                )
            ):
                return page_text
            return False

        return self.wait_utils.until_condition(visible_rejection, timeout=timeout)

    @staticmethod
    def extract_upload_status_message(message_text):
        message_lines = [line.strip() for line in message_text.splitlines() if line.strip()]
        for index, line in enumerate(message_lines):
            if "All files uploaded and validated successfully" in line:
                if index + 1 < len(message_lines) and "Status:" in message_lines[index + 1]:
                    return f"{line} {message_lines[index + 1]}"
                return line
        # "File Upload Status" is a column heading in the uploaded-files history
        # table, not a status value -- matching it here returned the header row
        # ("File Name Uploaded On File Upload Status ...") as the success message.
        for line in message_lines:
            if "added successfully" in line or "Status:" in line:
                return line
        return message_text.strip()

    @staticmethod
    def extract_upload_id(message_text):
        match = re.search(r"Upload ID:\s*(\d+)", message_text)
        return match.group(1) if match else ""

    # --- Submit for QAR locators ---
    CONTINUE_BUTTON = (By.XPATH, "//button[contains(normalize-space(),'Continue')]")
    # NOTE: This locator MUST only match the QAR submission button on Step 4 of the wizard.
    # Do NOT broaden it to contain('Submit') — that matches metadata buttons on Step 3,
    # which causes the wizard to reset to Step 1.
    SUBMIT_FOR_QAR_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(),'Submit Set for QAR')"
        " or contains(normalize-space(),'Submit for QAR')"
        " or contains(normalize-space(),'Submit Set For QAR')]",
    )
    SUBMIT_CONFIRM_LOCATORS = [
        (
            By.XPATH,
            "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
            "//button[(contains(normalize-space(),'Submit') or normalize-space()='Confirm' or normalize-space()='Yes') "
            "and not(@disabled)]",
        ),
        (By.XPATH, "//button[normalize-space()='Confirm' or normalize-space()='Yes']"),
    ]
    FILE_VALIDATION_PASSED = (
        By.XPATH,
        "//*[contains(normalize-space(),'File Validation Passed')]",
    )
    REVIEW_ITEM_ID_CELLS = (
        By.XPATH,
        "//table//tbody/tr/td[1]//*[normalize-space()] | //table//tbody/tr/td[1]",
    )
    QAR_RESULT_ITEM_ID_CELLS = (
        By.XPATH,
        "//table//tbody/tr/td[1]//*[normalize-space()] | //table//tbody/tr/td[1]",
    )
    OCR_SUCCESS_MESSAGE = (
        By.XPATH,
        "//*[contains(normalize-space(), 'QAR completed') "
        "or contains(normalize-space(), 'QAR ran') "
        "or contains(normalize-space(), 'returned') "
        "or contains(normalize-space(), 'Needs Revision')]",
    )
    QAR_RESULTS_HEADING = (
        By.XPATH,
        "//*[contains(normalize-space(),'QAR Results')]",
    )

    # --- Submit for QAR actions ---
    def click_continue(self):
        """Click the Continue button using JS to avoid Selenium clickability issues.

        Waits for any global loading overlay to disappear, then locates the Continue
        button (or any visible button/link containing 'Continue') and triggers a JS
        click after scrolling it into view.
        """
        # Wait for loading overlay to clear first
        try:
            self.wait_utils.until_condition(
                lambda driver: not driver.find_elements(*self.GLOBAL_LOADING_INDICATOR),
                timeout=20,
            )
        except Exception:
            pass

        # Primary: explicit CONTINUE_BUTTON locator
        try:
            button = self.wait_utils.until_present(self.CONTINUE_BUTTON, timeout=15)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            self.driver.execute_script("arguments[0].click();", button)
            self.pause_before_action()
            return
        except Exception:
            pass

        # Fallback: any visible button or link containing 'Continue'
        generic = (By.XPATH, "//*[self::button or self::a][contains(normalize-space(),'Continue')]")
        try:
            button = self.wait_utils.until_present(generic, timeout=10)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            self.driver.execute_script("arguments[0].click();", button)
            self.pause_before_action()
            return
        except Exception:
            pass

        raise TimeoutException("Continue button not found or not clickable after all attempts")

    def click_submit_for_qar(self):
        # Use until_present instead of until_clickable — loading overlay blocks clickability check
        try:
            self.wait_utils.until_present(self.SUBMIT_FOR_QAR_BUTTON, timeout=30)
        except TimeoutException:
            # The SPA can accept the request and redirect between the caller's
            # presence check and this second lookup. That transition is success.
            if self.has_qar_results_or_progress(self.driver):
                return True
            raise
        self.pause_before_action()
        click_attempts = (
            self.click_visible_submit_button_with_action_chain,
            self.click_visible_submit_button,
            self.js_click_visible_submit_button,
            self.dispatch_pointer_events_to_visible_submit_button,
            self.press_enter_on_visible_submit_button,
        )
        for click_attempt in click_attempts:
            try:
                click_attempt()
                self.confirm_submit_if_prompted()
                # A successful request can take a while before React replaces
                # this step. Do not fire the remaining click fallbacks while
                # the first request may still be in flight; that can add the
                # same uploaded rows to a set more than once.
                try:
                    self.wait_utils.until_condition(
                        lambda driver: self.has_qar_results_or_progress(driver)
                        or not self.has_visible_submit_for_qar_button(driver),
                        timeout=45,
                    )
                    return True
                except TimeoutException:
                    # The click itself completed without an exception. Treat it
                    # as submitted and let the result wait report any timeout;
                    # clicking again can duplicate every uploaded item.
                    return True
            except Exception:
                continue
        return False

    def dispatch_pointer_events_to_visible_submit_button(self):
        clicked = self.driver.execute_script(
            """
            const button = Array.from(document.querySelectorAll('button')).find(candidate => {
                const rect = candidate.getBoundingClientRect();
                const style = getComputedStyle(candidate);
                const label = (candidate.innerText || candidate.textContent || '')
                    .trim().toLowerCase();
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && !candidate.disabled
                    && label.includes('submit set for qar');
            });
            if (!button) return false;
            button.scrollIntoView({block: 'center'});
            for (const eventName of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                button.dispatchEvent(new MouseEvent(eventName, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                }));
            }
            return true;
            """
        )
        if not clicked:
            raise TimeoutException("No enabled Submit Set for QAR button accepted pointer events.")

    def get_visible_submit_for_qar_button(self):
        buttons = self.driver.find_elements(*self.SUBMIT_FOR_QAR_BUTTON)
        for button in buttons:
            try:
                if button.is_displayed() and button.is_enabled():
                    label = button.text.strip().casefold()
                    if "submit set for qar" in label or "submit for qar" in label:
                        return button
            except Exception:
                continue
        return self.wait_utils.until_present(self.SUBMIT_FOR_QAR_BUTTON, timeout=10)

    def click_visible_submit_button_with_action_chain(self):
        submit_button = self.get_visible_submit_for_qar_button()
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        ActionChains(self.driver).move_to_element(submit_button).pause(0.2).click().perform()

    def click_visible_submit_button(self):
        submit_button = self.get_visible_submit_for_qar_button()
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        submit_button.click()

    def js_click_visible_submit_button(self):
        clicked = self.driver.execute_script(
            """
            const isVisible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return rect.width > 0
                    && rect.height > 0
                    && style.visibility !== 'hidden'
                    && style.display !== 'none'
                    && !element.disabled;
            };
            const button = [...document.querySelectorAll('button')]
                .find((candidate) => isVisible(candidate)
                    && candidate.innerText.trim().toLowerCase().includes('submit set for qar'));
            if (!button) return false;
            button.scrollIntoView({block: 'center'});
            button.click();
            return true;
            """
        )
        if not clicked:
            raise TimeoutException("No visible enabled Submit Set for QAR button found.")

    def press_enter_on_visible_submit_button(self):
        submit_button = self.get_visible_submit_for_qar_button()
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
        submit_button.send_keys(Keys.ENTER)

    def did_leave_submit_step(self):
        try:
            self.wait_utils.until_condition(
                lambda driver: self.has_qar_results_or_progress(driver)
                or not self.has_visible_submit_for_qar_button(driver),
                timeout=8,
            )
            return True
        except Exception:
            return False

    def confirm_submit_if_prompted(self):
        def visible_submit_confirmation(driver):
            return driver.execute_script(
                """
                const visible = element => {
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return rect.width > 0
                        && rect.height > 0
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const isPopup = element => {
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
                const priorities = [
                    'submit', 'confirm', 'yes', 'proceed', 'continue', 'ok'
                ];
                const candidates = Array.from(document.querySelectorAll(
                    'button:not([disabled]), [role="button"]'
                )).filter(button => {
                    if (!visible(button) || button.getAttribute('aria-disabled') === 'true') {
                        return false;
                    }
                    const label = (button.innerText || button.textContent || '')
                        .trim().toLowerCase();
                    if (/submit\\s+(set\\s+)?for\\s+qar/.test(label)) return false;
                    let container = button.parentElement;
                    while (container && container !== document.body) {
                        if (visible(container) && isPopup(container)) return true;
                        container = container.parentElement;
                    }
                    return false;
                });
                for (const priority of priorities) {
                    const exact = candidates.find(button =>
                        (button.innerText || button.textContent || '')
                            .trim().toLowerCase() === priority
                    );
                    if (exact) return exact;
                }
                return candidates.find(button => {
                    const text = (button.innerText || button.textContent || '')
                        .trim().toLowerCase();
                    return !/cancel|back|no|close/.test(text)
                        && /submit|confirm|yes|proceed|continue|ok/.test(text);
                }) || null;
                """
            )

        try:
            confirm_button = self.wait_utils.until_condition(
                visible_submit_confirmation,
                timeout=5,
            )
        except TimeoutException:
            return False
        confirm_label = (confirm_button.text or "").strip().casefold()
        if re.search(r"submit\s+(set\s+)?for\s+qar", confirm_label):
            return False
        self.pause_before_action()
        try:
            confirm_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", confirm_button)
        return True

    def get_visible_qar_submit_blocker(self):
        return self.driver.execute_script(
            """
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const candidates = Array.from(document.querySelectorAll(
                '[role="alert"], [role="alertdialog"], .toast, .Toastify__toast, '
                + '[class*="error"], [class*="Error"], [class*="snackbar"], [class*="Snackbar"]'
            )).filter(visible);
            return candidates
                .map(element => (element.innerText || element.textContent || '').trim())
                .filter(Boolean)
                .sort((left, right) => left.length - right.length)[0] || '';
            """
        )

    def recover_active_upload_submit_step(self):
        def reopen_active_file():
            return self.driver.execute_script(
                """
                const marker = Array.from(document.querySelectorAll('*')).find(element =>
                    (element.innerText || element.textContent || '')
                        .trim().toLowerCase() === 'currently working on this file.'
                );
                if (!marker) return false;
                const card = marker.closest('li, [role="listitem"], tr')
                    || marker.parentElement?.parentElement
                    || marker.parentElement;
                if (!card) return false;
                const fileLabel = Array.from(card.querySelectorAll('*')).find(element => {
                    const text = (element.innerText || element.textContent || '').trim();
                    return /\\.xlsx?$/i.test(text)
                        && !Array.from(element.children).some(child =>
                            /\\.xlsx?$/i.test((child.innerText || child.textContent || '').trim())
                        );
                });
                if (!fileLabel) return false;
                const target = fileLabel.closest('a, button, [role="button"], [tabindex]')
                    || fileLabel;
                target.scrollIntoView({block: 'center'});
                target.click();
                return true;
                """
            )

        if reopen_active_file():
            try:
                self.wait_utils.until_condition(
                    lambda driver: self.has_visible_submit_for_qar_button(driver),
                    timeout=15,
                )
                return True
            except TimeoutException:
                pass

        self.driver.refresh()
        self.wait_utils.wait_for_page_ready(timeout=30)
        reopen_active_file()
        try:
            self.wait_utils.until_condition(
                lambda driver: self.has_visible_submit_for_qar_button(driver),
                timeout=30,
            )
            return True
        except TimeoutException:
            return False

    def click_submit_for_qar_and_wait_for_results(self, analysis_timeout=180):
        """Click Submit Set for QAR and wait for analysis to finish.

        analysis_timeout controls only the final "is QAR analysis complete"
        wait. Larger item sets (e.g. many real images going through Image
        Moderation) can legitimately take longer than the 180s default used
        by lighter-weight text-only item sets.
        """
        last_error = None
        for attempt in range(3):
            clicked = self.click_submit_for_qar()
            if not clicked:
                blocker = self.get_visible_qar_submit_blocker()
                last_error = TimeoutException(
                    "Submit Set for QAR remained on the confirmation step"
                    + (f": {blocker}" if blocker else ".")
                )
                if attempt < 2:
                    self.recover_active_upload_submit_step()
                continue
            try:
                self.wait_utils.until_condition(
                    lambda driver: self.has_qar_results_or_progress(driver),
                    timeout=90,
                )
                self.wait_utils.until_condition(
                    lambda driver: self.is_qar_analysis_complete(driver),
                    timeout=analysis_timeout,
                )
                return
            except Exception as error:
                last_error = error
                if clicked:
                    # Never issue a second submit after a click was accepted.
                    # A slow or failed response must surface as a timeout rather
                    # than mutating the item set a second time.
                    break
        blocker = self.get_visible_qar_submit_blocker()
        if blocker:
            raise TimeoutException(f"QAR submission was blocked: {blocker}") from last_error
        raise last_error

    def has_visible_submit_for_qar_button(self, driver):
        for button in driver.find_elements(*self.SUBMIT_FOR_QAR_BUTTON):
            try:
                label = button.text.strip().casefold()
                if button.is_displayed() and button.is_enabled() and "submit set for qar" in label:
                    return True
            except Exception:
                continue
        return False

    def has_qar_results_or_progress(self, driver):
        if self.is_qar_submission_redirect(driver):
            return True
        if driver.find_elements(*self.QAR_RESULTS_HEADING):
            for element in driver.find_elements(*self.QAR_RESULTS_HEADING):
                try:
                    if element.is_displayed():
                        return True
                except Exception:
                    continue
        page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
        return any(
            marker in page_text
            for marker in (
                "qar completed",
                "qar ran",
                "qar analysis in progress",
                "analysis in progress",
                "total items",
                "average score",
                "exception report",
            )
        )

    @staticmethod
    def is_qar_submission_redirect(driver):
        page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
        return (
            "my item set" in page_text
            and "item set status" in page_text
            and "item set review stage" in page_text
            and any(
                status in page_text
                for status in ("under review", "qar failed", "published", "disabled")
            )
        )

    def is_qar_analysis_complete(self, driver):
        if self.is_qar_submission_redirect(driver):
            return True
        page_text = driver.find_element(By.TAG_NAME, "body").text.casefold()
        if "analysis in progress" in page_text or "qar analysis in progress" in page_text:
            return False
        return any(
            marker in page_text
            for marker in (
                "qar completed",
                "qar ran",
                "total items",
                "average score",
                "exception report",
            )
        )

    def open_upload_step(self):
        self.click_continue()
        self.wait_utils.until_visible(self.UPLOAD_DOCUMENTS_HEADING, timeout=20)

    def upload_item_file_and_validate(self, file_path):
        self.open_item_creation_module()
        self.open_upload_item_file_tab()
        self.open_upload_step()
        self.discard_active_upload_if_present()
        self.discard_staged_upload_files()
        upload_path = self.upload_file(file_path)
        self.activate_uploaded_file(upload_path.name)
        success_message = self.wait_for_upload_validation_success()
        self.wait.until(EC.visibility_of_element_located(self.UPLOADED_FILE_NAME))
        return upload_path, success_message

    def get_review_item_ids(self):
        """Wait for the review step to load, then collect item IDs from the table.

        Accepts any of the following as confirmation that the review step is ready:
        - Visible text matching FILE_VALIDATION_PASSED ("File Validation Passed")
        - The Submit for QAR button becoming clickable
        - A table row appearing in the DOM
        Falls back gracefully if the exact text is not present.
        """
        # Try the dedicated "File Validation Passed" indicator first
        validated = False
        try:
            self.wait_utils.until_visible(self.FILE_VALIDATION_PASSED, timeout=15)
            validated = True
        except Exception:
            pass

        if not validated:
            # Fallback 1: Submit for QAR button present means we reached the review step
            try:
                self.wait_utils.until_present(self.SUBMIT_FOR_QAR_BUTTON, timeout=15)
                validated = True
            except Exception:
                pass

        if not validated:
            # Fallback 2: Any table row present
            try:
                self.wait_utils.until_condition(
                    lambda driver: bool(driver.find_elements(By.XPATH, "//table//tbody/tr[.//td]"))
                    or bool(driver.find_elements(*self.FILE_VALIDATION_PASSED)),
                    timeout=30,
                )
            except Exception:
                pass  # Collect whatever is on the page

        item_ids = []
        for cell in self.driver.find_elements(*self.REVIEW_ITEM_ID_CELLS):
            text = cell.text.strip()
            if text and text.lower() != "item id" and text not in item_ids:
                item_ids.append(text)
        return item_ids

    def get_qar_result_item_ids(self):
        item_ids = []
        for cell in self.driver.find_elements(*self.QAR_RESULT_ITEM_ID_CELLS):
            text = cell.text.strip()
            if re.search(r"-i\d+$", text, re.IGNORECASE) and text not in item_ids:
                item_ids.append(text)
        return item_ids

    @staticmethod
    def get_item_set_id_from_item_ids(item_ids):
        if not item_ids:
            return ""
        match = re.match(r"(.+)-i\d+$", item_ids[0])
        return match.group(1) if match else ""

    def wait_for_ocr_success_message(self):
        if self.is_qar_submission_redirect(self.driver):
            return "QAR submission accepted; item set is under review."
        try:
            element = self.wait_utils.until_visible(self.OCR_SUCCESS_MESSAGE, timeout=120)
            return self.extract_ocr_success_message(element.text)
        except TimeoutException:
            self.wait_utils.until_visible(self.QAR_RESULTS_HEADING, timeout=20)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            return self.extract_ocr_success_message(page_text)

    @staticmethod
    def extract_ocr_success_message(message_text):
        message_lines = [line.strip() for line in message_text.splitlines() if line.strip()]
        for line in message_lines:
            if "QAR completed" in line or "QAR ran" in line or "OCR" in line:
                return line
        for line in message_lines:
            if "returned" in line or "Needs Revision" in line:
                return line
        for line in message_lines:
            if "successfully" in line or "submitted" in line:
                return line
        return message_text.strip()

    def submit_uploaded_item_set_for_qar(self):
        """Navigate through the upload wizard steps and trigger QAR submission.

        The app wizard flow can vary:
          - upload → [Continue] → review → [Continue] → submit
          - upload → [Continue] → review/submit combined (no second Continue)
        This method handles both cases adaptively.
        """
        # Step 1: Navigate from upload validation to the next wizard step
        self.click_continue()
        self.pause_before_action()

        # Step 2: Collect item IDs from the review table (best-effort)
        item_ids = self.get_review_item_ids()

        # Step 3: Check if Submit button already on page (some app versions combine steps)
        submit_already_present = bool(
            self.driver.find_elements(*self.SUBMIT_FOR_QAR_BUTTON)
        )

        if not submit_already_present:
            # Step 3b: Click Continue to move from review → submit step
            try:
                self.click_continue()
                self.pause_before_action()
            except TimeoutException:
                # No second Continue button — we may already be on the submit page
                pass

        # Step 4: Wait for the Submit for QAR button to appear
        # Only match QAR-specific buttons — broad 'Submit' matches step 3 metadata buttons
        submit_found = False
        for locator in [
            self.SUBMIT_FOR_QAR_BUTTON,
            (By.XPATH, "//button[contains(normalize-space(),'QAR')]"),
        ]:
            try:
                self.wait_utils.until_present(locator, timeout=20)
                submit_found = True
                break
            except TimeoutException:
                continue

        if not submit_found:
            # Capture current URL + page text to diagnose where we are
            url = self.driver.current_url
            body = self.driver.find_element(By.TAG_NAME, "body").text[:500]
            raise TimeoutException(
                f"Submit for QAR button not found. URL={url}\nPage preview:\n{body}"
            )

        self.click_submit_for_qar_and_wait_for_results()
        success_message = self.wait_for_ocr_success_message()
        final_item_ids = self.get_qar_result_item_ids()
        return final_item_ids or item_ids, success_message


    def upload_item_file_and_submit_for_qar(self, file_path):
        upload_path, upload_success_message = self.upload_item_file_and_validate(file_path)
        item_ids, ocr_success_message = self.submit_uploaded_item_set_for_qar()
        return upload_path, upload_success_message, item_ids, ocr_success_message

    # --- Evidence capture actions ---
    def capture_ocr_success_screenshot(self, test_name):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_ocr_success")

    def capture_sets_verification_screenshot(self, test_name):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_sets_verification")

    def capture_reviewer_approval_screenshot(self, test_name):
        return ScreenshotUtils.capture(self.driver, f"{test_name}_reviewer_approval")

    # --- Sets verification locators ---
    # Older builds exposed a dedicated "Sets" menu item. Newer ones drop it and
    # render the "My Item Sets" table on the dashboard reached via "Home", so try
    # the explicit entries before falling back to a positional guess.
    SETS_MENU_LOCATORS = [
        (By.XPATH, "//*[normalize-space()='Sets']/ancestor::*[self::button or self::a][1]"),
        (By.XPATH, "//button[contains(normalize-space(),'Sets')]"),
        (By.XPATH, "//*[normalize-space()='Home']/ancestor::*[self::button or self::a][1]"),
        (By.XPATH, "(//div[@id='root']//ul/li[2]/button)[1]"),
    ]

    # --- Sets verification actions ---
    MY_ITEM_SETS_HEADING = (By.XPATH, "//*[contains(normalize-space(),'My Item Set')]")

    def open_sets_module(self):
        self.click_any_element(self.SETS_MENU_LOCATORS)
        try:
            self.wait_utils.until_visible(self.MY_ITEM_SETS_HEADING, timeout=30)
        except TimeoutException:
            # Builds without a "Sets" menu render the table on the dashboard, and
            # the sidebar click can be swallowed by an overlay on result screens.
            # Navigating straight there is deterministic either way.
            self.driver.get(ReadConfig.get_base_url().rstrip("/") + "/dashboard")
            self.wait_utils.until_visible(self.MY_ITEM_SETS_HEADING, timeout=30)

    ITEM_SET_LIST_ROWS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item Set ID')]]//tbody/tr[.//td]",
    )

    @staticmethod
    def xpath_literal(value):
        value = str(value)
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"

    def get_item_set_list_rows(self):
        rows = self.wait_utils.until_condition(
            lambda driver: driver.find_elements(*self.ITEM_SET_LIST_ROWS) or False,
            timeout=30,
        )
        results = []
        for row in rows:
            try:
                if not row.is_displayed():
                    continue
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < 7:
                    continue
                cell_lines = [
                    [line.strip() for line in cell.text.splitlines() if line.strip()]
                    for cell in cells
                ]
                subject_chapter = cell_lines[2]
                results.append(
                    {
                        "item_set_id": cell_lines[0][0] if cell_lines[0] else "",
                        "grade": cell_lines[1][0] if cell_lines[1] else "",
                        "subject": subject_chapter[0] if subject_chapter else "",
                        "chapter": subject_chapter[1] if len(subject_chapter) > 1 else "",
                        "item_status": " ".join(cell_lines[4]),
                        "item_set_status": " ".join(cell_lines[5]),
                        "review_stage": " ".join(cell_lines[6]),
                    }
                )
            except Exception:
                continue
        return results

    # --- Uploaded File column on the full My Item Set list ---
    # open_sets_module() reaches the dashboard, whose "My Item Sets" widget only
    # previews a few sets and paints "Loading item sets..." first. The full list
    # -- and the only place the Uploaded File column renders -- is /item-sets,
    # behind the widget's "View All".
    ITEM_SETS_LIST_PATH = "/item-sets"
    ITEM_SET_TABLE_HEADERS = (
        By.XPATH,
        "//table[.//th[contains(normalize-space(),'Item Set ID')]]//th",
    )
    # Sets authored manually have no source workbook and render an em dash.
    UPLOADED_FILE_EMPTY_MARKERS = {"", "—", "–", "-"}

    # The dashboard widget's link through to the full list.
    MY_ITEM_SETS_VIEW_ALL = (
        By.XPATH,
        "//*[normalize-space()='View All'][not(.//*[normalize-space()='View All'])]",
    )

    def open_item_sets_list(self, timeout=45):
        """Open the full My Item Set list and wait for its rows to render.

        Prefers the dashboard's "View All" link to navigating straight at
        /item-sets: a hard driver.get() reloads the SPA and lands on its global
        Loading screen, which this environment can sit on for longer than the
        wait. The direct URL stays as the fallback for builds without the link.
        """
        self.open_sets_module()
        try:
            link = self.wait_utils.until_clickable(self.MY_ITEM_SETS_VIEW_ALL, timeout=15)
            self.driver.execute_script("arguments[0].click();", link)
        except TimeoutException:
            self.driver.get(ReadConfig.get_base_url().rstrip("/") + self.ITEM_SETS_LIST_PATH)
        self.wait_utils.until_visible(self.MY_ITEM_SETS_HEADING, timeout=timeout)
        # Rows only exist once the "Loading item sets..." placeholder clears.
        self.wait_utils.until_condition(
            lambda driver: driver.find_elements(*self.ITEM_SET_LIST_ROWS) or False,
            timeout=timeout,
        )
        return True

    def get_uploaded_file_column_index(self, timeout=30):
        """1-based index of the 'Uploaded File' column, or 0 when it is absent.

        Resolved from the header rather than hard-coded: this list has gained
        columns across builds (Item Count, Last Review Submit Date), and a fixed
        td index silently reads a neighbouring cell when that happens.
        """
        headers = self.wait_utils.until_condition(
            lambda driver: driver.find_elements(*self.ITEM_SET_TABLE_HEADERS) or False,
            timeout=timeout,
        )
        for index, header in enumerate(headers, start=1):
            if "uploaded file" in header.text.casefold():
                return index
        return 0

    @classmethod
    def uploaded_file_name(cls, cell):
        """The full workbook name in an Uploaded File cell, or '' if it has none.

        Reads the title attribute rather than the cell text: long names are
        truncated for display ("smoke_item_set_b935079…"), so the visible text
        is not the file name. Cells for manually authored sets carry no title
        and hold an em dash, which yields ''.
        """
        for element in cell.find_elements(By.XPATH, ".//*[@title]"):
            title = (element.get_attribute("title") or "").strip()
            if title:
                return title
        text = cell.text.strip()
        return "" if text in cls.UPLOADED_FILE_EMPTY_MARKERS else text

    def get_item_set_uploaded_files(self):
        """Map item set ID -> source workbook name for rows that name one.

        Rows for manually authored sets are omitted, so an empty result means
        this page lists no uploaded sets rather than that the column failed.
        """
        column = self.get_uploaded_file_column_index()
        if not column:
            return {}
        uploads = {}
        for row in self.driver.find_elements(*self.ITEM_SET_LIST_ROWS):
            try:
                if not row.is_displayed():
                    continue
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < column:
                    continue
                set_id_lines = [
                    line.strip() for line in cells[0].text.splitlines() if line.strip()
                ]
                name = self.uploaded_file_name(cells[column - 1])
                if set_id_lines and name:
                    uploads[set_id_lines[0]] = name
            except Exception:
                continue
        return uploads

    def get_item_set_filter_trigger(self, filter_name, timeout=20):
        label = self.xpath_literal(filter_name)
        locator = (
            By.XPATH,
            "//*[self::button or @role='button']"
            f"[normalize-space()={label} or .//*[normalize-space()={label}]]",
        )
        for element in self.driver.find_elements(*locator):
            try:
                if element.is_displayed() and element.is_enabled():
                    return element
            except Exception:
                continue

        filter_order = {"Grade": 0, "Subject": 1, "Chapter": 2, "Status": 3}
        if filter_name not in filter_order:
            raise ValueError(f"Unsupported item-set filter: {filter_name!r}")
        funnel_buttons = (
            By.XPATH,
            "//button[.//*[name()='svg' and "
            "(contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'filter') "
            "or contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'funnel'))]]",
        )
        return self.wait_utils.until_condition(
            lambda driver: (
                buttons[filter_order[filter_name]]
                if len(
                    buttons := [
                        element
                        for element in driver.find_elements(*funnel_buttons)
                        if element.is_displayed() and element.is_enabled()
                    ]
                ) > filter_order[filter_name]
                else False
            ),
            timeout=timeout,
        )

    def open_item_set_filter(self, filter_name):
        trigger = self.get_item_set_filter_trigger(filter_name)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            trigger,
        )
        self.pause_before_action()
        try:
            trigger.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", trigger)
        return trigger

    def get_item_set_filter_option(self, option_text, timeout=15):
        expected_text = re.sub(r"\s+", " ", str(option_text)).strip().casefold()
        expected_prefix = expected_text.rstrip(".") if expected_text.endswith("...") else ""
        locator = (
            By.XPATH,
            "//*[@role='option' or @role='menuitem' or @role='menuitemcheckbox' "
            "or @role='checkbox']"
            " | //*[@role='listbox' or @role='menu']"
            "//*[self::button or @role='button']",
        )

        def matching_option(driver):
            for element in driver.find_elements(*locator):
                try:
                    if not element.is_displayed() or not element.is_enabled():
                        continue
                    actual_text = re.sub(r"\s+", " ", element.text or "").strip().casefold()
                    if actual_text == expected_text:
                        return element
                    if expected_prefix and actual_text.startswith(expected_prefix):
                        return element
                except Exception:
                    continue
            return False

        return self.wait_utils.until_condition(
            matching_option,
            timeout=timeout,
        )

    def close_item_set_filter(self):
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

    def apply_item_set_filter(self, filter_name, option_text):
        self.open_item_set_filter(filter_name)
        option = self.get_item_set_filter_option(option_text)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'nearest'});",
            option,
        )
        self.pause_before_action()
        try:
            option.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", option)
        self.close_item_set_filter()
        self.wait_utils.until_condition(
            lambda driver: bool(self.get_item_set_list_rows()),
            timeout=30,
        )
        return option_text

    @staticmethod
    def is_filter_option_element_selected(option):
        selected_values = {
            str(option.get_attribute("aria-selected") or "").casefold(),
            str(option.get_attribute("aria-checked") or "").casefold(),
            str(option.get_attribute("data-state") or "").casefold(),
        }
        if selected_values.intersection({"true", "checked", "selected", "on"}):
            return True
        inputs = option.find_elements(By.XPATH, ".//input[@type='checkbox' or @type='radio']")
        return any(input_element.is_selected() for input_element in inputs)

    def is_item_set_filter_option_selected(self, filter_name, option_text):
        trigger = self.get_item_set_filter_trigger(filter_name)
        trigger_text = re.sub(r"\s+", " ", trigger.text or "").strip().casefold()
        expected_text = re.sub(r"\s+", " ", option_text).strip().casefold()
        expected_prefix = expected_text.rstrip(".") if expected_text.endswith("...") else ""
        if expected_text in trigger_text or (
            expected_prefix and expected_prefix in trigger_text
        ):
            return True
        if trigger_text == filter_name.strip().casefold():
            return False

        self.open_item_set_filter(filter_name)
        try:
            option = self.get_item_set_filter_option(option_text)
            return self.is_filter_option_element_selected(option)
        finally:
            self.close_item_set_filter()

    def clear_item_set_filter(self, filter_name, option_text):
        self.open_item_set_filter(filter_name)
        clear_locators = [
            (
                By.XPATH,
                "//*[self::button or @role='button']"
                "[normalize-space()='Clear' or normalize-space()='Clear Filter' "
                "or normalize-space()='Clear filters' or normalize-space()='Reset']",
            ),
        ]
        cleared = False
        for locator in clear_locators:
            for element in self.driver.find_elements(*locator):
                try:
                    if element.is_displayed() and element.is_enabled():
                        self.driver.execute_script("arguments[0].click();", element)
                        cleared = True
                        break
                except Exception:
                    continue
            if cleared:
                break
        if not cleared:
            option = self.get_item_set_filter_option(option_text)
            if not self.is_filter_option_element_selected(option):
                self.close_item_set_filter()
                return True
            try:
                option.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", option)
        self.close_item_set_filter()
        return True

    def get_visible_item_set_scopes(self):
        rows = self.wait_utils.until_condition(
            lambda driver: driver.find_elements(By.XPATH, "//table//tbody/tr[.//td]"),
            timeout=30,
        )
        scopes = []
        for row in rows:
            row_text = row.text
            grade_match = re.search(r"\bGrade\s+\d+\b", row_text, re.IGNORECASE)
            if not grade_match:
                continue
            lines = [line.strip() for line in row_text.splitlines() if line.strip()]
            grade_index = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if re.fullmatch(r"Grade\s+\d+", line, re.IGNORECASE)
                ),
                None,
            )
            if grade_index is None or grade_index + 1 >= len(lines):
                continue
            scopes.append(
                {
                    "item_set_id": lines[0],
                    "grade": lines[grade_index],
                    "subject": lines[grade_index + 1],
                }
            )
        return scopes

    def verify_visible_item_sets_within_scope(self, expected_grade, expected_subject):
        scopes = self.get_visible_item_set_scopes()
        if not scopes:
            raise AssertionError("No item-set rows were visible for RBAC verification.")
        outside_scope = [
            scope
            for scope in scopes
            if scope["grade"].casefold() != expected_grade.casefold()
            or scope["subject"].casefold() != expected_subject.casefold()
        ]
        if outside_scope:
            raise AssertionError(
                "SME can see item sets outside the assigned grade-subject scope: "
                f"{outside_scope}"
            )
        return scopes

    FIND_LINK_BY_COLLAPSED_TEXT_JS = r"""
        const targetId = arguments[0].replace(/\s+/g, '');
        const links = Array.from(document.querySelectorAll('a'));
        return links.find(link => {
            const collapsed = (link.innerText || link.textContent || '').replace(/\s+/g, '');
            return collapsed === targetId || collapsed.includes(targetId);
        }) || null;
        """

    def find_item_set_link_by_id(self, item_set_id):
        """Locate the item-set link by comparing whitespace-collapsed text.

        Some environments wrap a long item-set ID across multiple lines
        inside the anchor (see get_item_set_list_rows(), which already
        splitlines() the cell text) - XPath's normalize-space() turns that
        internal line break into a single space, which breaks both the
        exact-match and contains() checks against the space-free
        item_set_id. Comparing with all whitespace stripped (via JS,
        matching how splitlines()-based scraping already treats this) finds
        the link regardless of how it wraps.
        """
        return self.driver.execute_script(
            self.FIND_LINK_BY_COLLAPSED_TEXT_JS, item_set_id
        )

    @staticmethod
    def item_set_numeric_prefix(item_set_id):
        """The 'IS<number>' portion of an item-set ID.

        Some environments render the same item set's ID with a different
        chapter-code suffix on the QAR results page (e.g. "...-Ch29") than
        on the "My Item Set" list page (e.g. "...-CH-1") for reasons that
        appear to be a backend metadata-resolution timing quirk, not a
        display bug - searching/matching on the full ID then reliably finds
        nothing. The "IS<number>" prefix is stable across both views, so
        it's used as a fallback identifier when the full-ID search comes up
        empty.
        """
        match = re.match(r"(IS\d+)", str(item_set_id), re.IGNORECASE)
        return match.group(1) if match else str(item_set_id)

    def open_item_set_from_sets_list(self, item_set_id):
        # A fresh item set isn't guaranteed to land on the default list's
        # first page (busy accounts can have 100+ sets across many pages) -
        # filter down to it via search first so the link scan below only
        # ever has to look at a single, small result set.
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        try:
            self.search_open_item_set(item_set_id)
        except Exception:
            pass
        link = self.find_item_set_link_by_id(item_set_id)
        if not link and numeric_prefix != item_set_id:
            # Full ID (with its chapter-code suffix) matched nothing - the
            # set may be rendered under a different chapter label here, so
            # retry scoped to just the stable numeric prefix.
            try:
                self.search_open_item_set(numeric_prefix)
            except Exception:
                pass
            link = self.wait_utils.until_condition(
                lambda driver: self.find_item_set_link_by_id(numeric_prefix),
                timeout=30,
            )
        elif not link:
            link = self.wait_utils.until_condition(
                lambda driver: self.find_item_set_link_by_id(item_set_id),
                timeout=30,
            )
        starting_url = self.driver.current_url
        target_url = link.get_attribute("href")
        try:
            link.click()
            self.wait_utils.until_condition(
                lambda driver: driver.current_url != starting_url,
                timeout=15,
            )
        except Exception:
            if target_url:
                self.driver.get(target_url)
            else:
                self.driver.execute_script("arguments[0].click();", link)
            self.wait_utils.until_condition(
                lambda driver: driver.current_url != starting_url,
                timeout=30,
            )
        self.wait_utils.until_condition(
            lambda driver: numeric_prefix in driver.find_element(By.TAG_NAME, "body").text,
            timeout=60,
        )
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=120,
        )

    ITEM_SET_SEARCH_INPUT = (
        By.XPATH,
        "//input[contains(@placeholder,'Search') or contains(@aria-label,'Search')]",
    )

    def search_open_item_set(self, search_text):
        search_input = self.wait_utils.until_visible(self.ITEM_SET_SEARCH_INPUT, timeout=20)
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        search_input.send_keys(search_text)
        search_input.send_keys(Keys.ENTER)
        self.wait_utils.until_condition(
            lambda driver: search_text in re.sub(
                r"\s+",
                "",
                self.get_rendered_page_text(driver),
            ),
            timeout=30,
        )

    def clear_open_item_set_search(self):
        try:
            search_input = self.wait_utils.until_visible(self.ITEM_SET_SEARCH_INPUT, timeout=5)
            search_input.send_keys(Keys.CONTROL, "a")
            search_input.send_keys(Keys.DELETE)
            search_input.send_keys(Keys.ENTER)
            self.pause_before_action()
        except Exception:
            return False
        return True

    @classmethod
    def item_id_loose_pattern(cls, item_id):
        """Regex matching an item ID's stable 'IS<number>' prefix and
        trailing 'i<number>' item-number suffix, with anything in between.

        Some environments render an item set's ID with a different
        chapter-code component on this detail page (e.g. "...-CH-1-i1")
        than the one captured right after upload (e.g. "...-Ch29-i1") -
        see item_set_numeric_prefix(). An exact compacted-ID substring
        match then never succeeds even though it's the same item, so this
        loosens the match to the two components that stay stable.
        """
        match = re.match(r"(IS\d+).*?[Ii](\d+)$", cls.compact_item_id(item_id))
        if not match:
            return None
        prefix, item_number = match.groups()
        return re.compile(
            rf"{re.escape(prefix)}.*?[Ii]{re.escape(item_number)}(?!\d)"
        )

    def verify_items_in_opened_item_set(self, item_ids):
        expected_item_ids = [self.compact_item_id(item_id) for item_id in item_ids]
        loose_patterns = {
            item_id: self.item_id_loose_pattern(item_id) for item_id in item_ids
        }

        def visible_item_ids(driver):
            if self.is_item_set_detail_loading(driver):
                return set()
            # Match against each row's own ID cell, not one compacted blob of
            # page text. Compacting the whole page glues an item ID to the
            # question text right after it ("...-i2" + "2 multiplied by...")
            # and the loose pattern's "not followed by a digit" boundary then
            # rejects the very row it is looking at.
            id_cells = self.get_rendered_item_id_cells(driver)
            normalized_page_text = self.compact_item_id(
                self.get_rendered_page_text(driver)
            )
            found = set()
            for original_id, item_id in zip(item_ids, expected_item_ids):
                if any(item_id == cell for cell in id_cells):
                    found.add(item_id)
                    continue
                pattern = loose_patterns.get(original_id)
                if pattern and any(pattern.search(cell) for cell in id_cells):
                    found.add(item_id)
                    continue
                # No ID cells at all (a non-table view): fall back to the
                # page-text match rather than reporting everything missing.
                if not id_cells and item_id in normalized_page_text:
                    found.add(item_id)
            return found

        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=120,
        )
        try:
            found_item_ids = self.wait_utils.until_condition(
                lambda driver: (
                    current_ids
                    if len(
                        current_ids := visible_item_ids(driver)
                    ) == len(expected_item_ids)
                    else False
                ),
                timeout=30,
            )
        except TimeoutException:
            found_item_ids = visible_item_ids(self.driver)

        if len(found_item_ids) != len(expected_item_ids) and item_ids:
            # Searching each missing item's full ID is unreliable here: the
            # detail page can render a different chapter-code component than
            # the ID captured after upload (see item_id_loose_pattern), so
            # that search matches nothing and just leaves the table filtered
            # empty. Search the stable "IS<number>" prefix instead, which
            # re-queries the same set and brings every row back.
            try:
                self.search_open_item_set(
                    self.item_set_numeric_prefix(item_ids[0])
                )
                found_item_ids.update(visible_item_ids(self.driver))
            except Exception:
                pass

        self.clear_open_item_set_search()
        try:
            # Re-check against the full, unfiltered table: a single read here
            # can land while the rows are still re-rendering after the search
            # was cleared and report items missing that are simply not painted
            # yet.
            found_item_ids.update(
                self.wait_utils.until_condition(
                    lambda driver: (
                        current_ids
                        if len(
                            current_ids := visible_item_ids(driver)
                        ) == len(expected_item_ids)
                        else False
                    ),
                    timeout=30,
                )
            )
        except TimeoutException:
            found_item_ids.update(visible_item_ids(self.driver))
        missing_item_ids = [
            item_id for item_id in expected_item_ids if item_id not in found_item_ids
        ]
        if missing_item_ids:
            raise AssertionError(
                f"Uploaded item IDs not found in opened item set: {missing_item_ids}"
            )
        return True

    @staticmethod
    def compact_item_id(value):
        return re.sub(r"[^A-Za-z0-9]", "", value or "")

    @staticmethod
    def get_rendered_page_text(driver):
        """Page text read through JS innerText.

        Selenium's element .text only returns text the browser considers
        rendered, which in headless Chrome can come back empty or partial
        for table rows below the viewport - table content then reads as
        "missing" when it is simply off-screen.
        """
        return driver.execute_script(
            "return document.body.innerText || document.body.textContent || '';"
        )

    @classmethod
    def get_rendered_item_id_cells(cls, driver):
        """Compacted text of every table row's first (item ID) cell."""
        cells = driver.execute_script(
            """
            return Array.from(document.querySelectorAll('table tbody tr'))
                .map(row => row.querySelector('td'))
                .filter(Boolean)
                .map(cell => (cell.innerText || cell.textContent || '').trim())
                .filter(text => text);
            """
        )
        return [cls.compact_item_id(cell) for cell in cells or []]

    @classmethod
    def is_item_set_detail_loading(cls, driver):
        page_text = cls.get_rendered_page_text(driver)
        return any(
            loading_text in page_text
            for loading_text in (
                "Loading item set",
                "Loading item set details",
            )
        )

    def open_item_set_detail(self, item_set_id):
        """Open one item set's own page, via the list rather than a captured URL.

        The status-count widget ("All / Pending / Approved / ...") only exists on
        the detail page. A URL captured earlier in a flow can still be pointing at
        the list, and the list also contains the item set ID - so a text-based
        load check cannot tell the two apart and the counts silently read as the
        list's own filter tallies instead.
        """
        self.open_sets_module()
        self.open_item_set_from_sets_list(item_set_id)

    def verify_item_set_from_sets_module(self, item_set_id, item_ids):
        self.open_sets_module()
        self.open_item_set_from_sets_list(item_set_id)
        return self.verify_items_in_opened_item_set(item_ids)

    # --- Assignee and status helpers ---
    def get_item_set_reviewer(self):
        return self.get_item_set_assignee("rwg")

    def get_item_set_sr_rwg(self):
        return self.get_item_set_assignee("sr_rwg")

    def get_scoped_item_set_assignee_text(self, role):
        """Read only the "Reviewer:"/"Assigned ..." label's own value text.

        Reading the whole page body text (as the regex fallback below does)
        can silently concatenate an unrelated adjacent number - e.g. a
        notification-badge count rendered right after "Reviewer: rwg 2" with
        no line break in the accessibility text tree - into the captured
        value (producing garbage like "rwg29"). Querying the label element
        directly and reading just its own text avoids that entirely.
        """
        label_words = {
            "rwg": ["reviewer", "assigned rwg", "rwg reviewer", "assigned to"],
            "sr_rwg": [
                "reviewer",
                "assigned sr rwg",
                "assigned srrwg",
                "sr rwg reviewer",
                "srrwg reviewer",
                "assigned to",
            ],
        }[role]
        return self.driver.execute_script(
            r"""
            const labelWords = arguments[0].map(word => word.toLowerCase());
            const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                    && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const candidates = Array.from(document.querySelectorAll('*')).filter(el => {
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                return visible(el) && labelWords.some(word => text === word + ':' || text === word);
            });
            for (const label of candidates) {
                // Value is usually the immediate next sibling, or a sibling
                // of the label's parent (label and value each in their own
                // small wrapper element).
                const siblingCandidates = [
                    label.nextElementSibling,
                    label.parentElement && label.parentElement.nextElementSibling,
                ].filter(Boolean);
                for (const sibling of siblingCandidates) {
                    const text = (sibling.innerText || sibling.textContent || '').trim();
                    if (text) return text;
                }
                // Fall back to text after the label within the same parent,
                // e.g. "Reviewer: rwg 2" as one text node's sibling text.
                const parentText = (label.parentElement?.innerText
                    || label.parentElement?.textContent || '').trim();
                const labelText = (label.innerText || label.textContent || '').trim();
                if (parentText.toLowerCase().startsWith(labelText.toLowerCase())) {
                    const remainder = parentText.slice(labelText.length).replace(/^[:\-\s]+/, '');
                    if (remainder) return remainder.split('\n')[0].trim();
                }
            }
            return '';
            """,
            label_words,
        )

    def get_item_set_assignee(self, role):
        scoped_text = self.get_scoped_item_set_assignee_text(role)
        if scoped_text:
            assignee = self.normalize_assignee_key(scoped_text)
            expected_pattern = {"rwg": r"rwg\d+", "sr_rwg": r"srrwg\d+"}[role]
            if re.fullmatch(expected_pattern, assignee):
                return assignee

        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        role_patterns = {
            "rwg": (
                r"(?:Assigned\s+RWG|RWG\s+Reviewer|Reviewer|Assigned\s+to)\s*[:\-]?\s*(?:\r?\n\s*)?([^\r\n]+)",
                r"\b(rwg[\s_-]*\d+)\b",
            ),
            "sr_rwg": (
                r"(?:Assigned\s+SR\s*RWG|Assigned\s+SRRWG|SR\s*RWG\s+Reviewer|SRRWG\s+Reviewer|Assigned\s+to)\s*[:\-]?\s*(?:\r?\n\s*)?([^\r\n]+)",
                r"\b(sr[\s_-]*rwg[\s_-]*\d+|srrwg[\s_-]*\d+)\b",
            ),
        }
        expected_pattern = {
            "rwg": r"rwg\d+",
            "sr_rwg": r"srrwg\d+",
        }[role]

        for pattern in role_patterns[role]:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if not match:
                continue
            assignee = self.normalize_assignee_key(match.group(1))
            if re.fullmatch(expected_pattern, assignee):
                return assignee
        return ""

    @staticmethod
    def normalize_assignee_key(value):
        normalized = re.sub(r"[^a-z0-9]", "", value.strip().lower())
        normalized = normalized.replace("srrwg", "srrwg")
        if normalized.startswith("srrwg"):
            return normalized
        if normalized.startswith("srrw"):
            return normalized.replace("srrw", "srrwg", 1)
        if normalized.startswith("sr") and "rwg" in normalized:
            return "srrwg" + re.sub(r"\D", "", normalized)
        if normalized.startswith("rwg"):
            return normalized
        return normalized

    def require_item_set_assignee(self, role):
        assignee = self.get_item_set_assignee(role)
        if not assignee:
            role_label = "SRRWG" if role == "sr_rwg" else "RWG"
            raise AssertionError(f"Could not detect assigned {role_label} from the item set page.")
        return assignee

    def open_item_set_url_and_wait(self, item_set_url, item_set_id):
        # Match on the stable "IS<number>" prefix, not the full item_set_id -
        # some environments render this page's chapter-code suffix
        # differently than the one captured right after upload (see
        # item_set_numeric_prefix()), so an exact-string check can time out
        # even once the right page has fully loaded.
        numeric_prefix = self.item_set_numeric_prefix(item_set_id)
        self.driver.get(item_set_url)
        self.wait_utils.until_condition(
            lambda driver: numeric_prefix in driver.find_element(By.TAG_NAME, "body").text,
            timeout=60,
        )
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=120,
        )

    def get_item_set_status_count(self, status_name):
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        match = re.search(rf"{status_name}\s+(\d+)", page_text)
        return int(match.group(1)) if match else 0

    def get_visible_item_statuses(self):
        # Read all values in one browser-side snapshot so a React table
        # refresh cannot stale individual WebElements midway through the loop.
        return self.driver.execute_script(
            """
            const statuses = Array.from(
                document.querySelectorAll('table tbody tr td:nth-child(3)')
            ).map(cell => (cell.innerText || cell.textContent || '').trim())
             .filter(Boolean);
            return Array.from(new Set(statuses));
            """
        )

    def get_item_set_status_summary(self):
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        status_counts = {}
        for status_name in (
            "All",
            "Pending",
            "Approved",
            "Need Improvement",
            "Needs Improvement",
            "Needs Revision",
            "Revise",
            "Rejected",
            "Revised",
        ):
            match = re.search(rf"{status_name}\s+(\d+)", page_text)
            if match:
                status_counts[status_name] = match.group(1)

        visible_statuses = self.get_visible_item_statuses()
        if visible_statuses:
            status_counts["Visible item statuses"] = ", ".join(visible_statuses)
        return status_counts

    @staticmethod
    def format_status_summary(status_summary):
        return ", ".join(
            f"{status_name}: {status_count}"
            for status_name, status_count in status_summary.items()
        )

    # --- User session locators ---
    USER_MENU_LOCATORS = [
        (By.XPATH, "//button[.//*[contains(@class,'avatar')]]"),
        (By.XPATH, "//button[contains(@class,'avatar') or contains(@class,'Avatar')]"),
        (By.XPATH, "//button[contains(normalize-space(),'SM') or contains(normalize-space(),'RWG')]"),
        (By.XPATH, "//*[normalize-space()='SM' or normalize-space()='RWG' or normalize-space()='RW']"),
    ]
    LOGOUT_LOCATORS = [
        (By.XPATH, "//*[self::button or self::div or self::span][contains(normalize-space(),'Logout')]"),
        (By.XPATH, "//*[self::button or self::div or self::span][contains(normalize-space(),'Sign out')]"),
        (By.XPATH, "//*[self::button or self::div or self::span][contains(normalize-space(),'Log out')]"),
    ]

    # --- User session actions ---
    def open_user_menu(self):
        last_error = None
        for locator in self.USER_MENU_LOCATORS:
            try:
                user_menu = self.wait_utils.until_visible(locator, timeout=8)
                clickable_target = user_menu
                ancestors = user_menu.find_elements(
                    By.XPATH,
                    "./ancestor::*[self::button or @role='button' or self::div][1]",
                )
                if ancestors:
                    clickable_target = ancestors[0]
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    clickable_target,
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", clickable_target)
                return
            except Exception as error:
                last_error = error
        raise last_error

    def logout(self):
        self.open_user_menu()
        self.click_any_element(self.LOGOUT_LOCATORS)
        self.wait_utils.until_visible((By.ID, "identifier"), timeout=30)

    def reset_browser_session_to_login(self, retries=2):
        """Retry once on any transport-level hiccup (e.g. a stalled WebDriver

        navigation command), since flaky infra shouldn't abort a multi-role
        E2E flow at a plain session reset.
        """
        last_error = None
        for attempt in range(retries):
            try:
                self.driver.delete_all_cookies()
                try:
                    # A freshly-launched browser (or one on a blank/chrome:
                    # page between sessions) has no http(s) document loaded
                    # yet, and localStorage access there is blocked by the
                    # browser itself ("Access is denied for this document")
                    # - there's nothing to clear in that case anyway, so
                    # this step is best-effort rather than fatal.
                    self.driver.execute_script(
                        "window.localStorage.clear(); window.sessionStorage.clear();"
                    )
                except Exception:
                    pass
                self.driver.get(ReadConfig.get_base_url())
                self.wait_utils.until_visible((By.ID, "identifier"), timeout=30)
                return
            except Exception as error:
                last_error = error
                if attempt == retries - 1:
                    break
                sleep(2)
        raise last_error

    # --- Revision item locators ---
    EDIT_ITEM_LOCATORS = [
        (By.XPATH, "//button[normalize-space()='Edit' or contains(normalize-space(),'Edit Item')]"),
        (By.XPATH, "//*[self::button or self::a][contains(normalize-space(),'Edit')]"),
    ]
    SAVE_REVISION_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Save Revision')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Save')]"),
    ]
    RERUN_QAR_LOCATORS = [
        (By.XPATH, "//button[contains(normalize-space(),'Re-run QAR')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Rerun QAR')]"),
        (By.XPATH, "//button[contains(normalize-space(),'Run QAR')]"),
    ]
    TEACHER_RESUBMIT_REVIEW_LOCATORS = [
        (By.XPATH, "//button[normalize-space()='Resubmit set for review']"),
        (By.XPATH, "//button[contains(normalize-space(),'Resubmit') and contains(normalize-space(),'review')]"),
    ]
    REVISION_NOTE_INPUT_LOCATORS = [
        (
            By.XPATH,
            "//*[contains(normalize-space(),'Revision Notes')]/following::textarea[1]",
        ),
        (
            By.XPATH,
            "//*[contains(normalize-space(),'Revision Notes')]/following::*[@contenteditable='true'][1]",
        ),
        (
            By.XPATH,
            "//textarea[contains(@placeholder,'Revision') or contains(@aria-label,'Revision')]",
        ),
    ]
    ITEM_CONTENT_EDITORS = [
        (By.CSS_SELECTOR, "[aria-label='itemContent'] .tiptap"),
        (By.CSS_SELECTOR, "[aria-label='itemContent'] [contenteditable='true']"),
        # Newer builds label the editor with its visible field name instead.
        (By.CSS_SELECTOR, "[aria-label='Statement'] .tiptap"),
        (By.CSS_SELECTOR, "[aria-label='Statement'] [contenteditable='true']"),
        (By.XPATH, "(//*[@contenteditable='true'])[1]"),
        (By.XPATH, "(//textarea)[1]"),
    ]
    QAR_RETRY_STATUS_LABELS = (
        "Need Improvement",
        "Needs Improvement",
        "Needs Revision",
        "Revise",
    )

    # --- Revision item actions ---
    def find_first_pending_item_link(self):
        return self.wait_utils.until_clickable(
            (
                By.XPATH,
                "//table//tbody/tr[.//td[contains(normalize-space(),'Pending')]][1]"
                "//td[1]//*[self::a or self::button][normalize-space()][1]",
            ),
            timeout=20,
        )

    def get_item_ids_by_status(self, status_text):
        rows = self.driver.find_elements(
            By.XPATH,
            f"//table//tbody/tr[.//td[contains(normalize-space(),'{status_text}')]]",
        )
        item_ids = []
        for row in rows:
            try:
                item_cell = row.find_element(
                    By.XPATH,
                    ".//td[1]//*[normalize-space()] | .//td[1]",
                )
                item_id = item_cell.text.strip()
                if item_id and item_id.lower() != "item id" and item_id not in item_ids:
                    item_ids.append(item_id)
            except Exception:
                continue
        return item_ids

    def get_qar_item_statuses(self, item_set_id=None):
        """Return the visible QAR/RWG-facing status for every item table row.

        Pass item_set_id to keep only that set's own item rows. Set-level
        tables (the Sets list, upload history) render one row per item set,
        whose ID carries no "-i<n>" suffix and whose status is the set's, not
        an item's - a read taken while such a table is on screen otherwise
        reports unrelated sets' failures as this set's items.
        """
        rows = self.driver.execute_script(
            r"""
            const statusPattern = /\b(Needs? Improvement|Needs Revision|Revise|Rejected|Failed|Blocked|Approved|Passed|Pending|Revised)\b/i;
            return Array.from(document.querySelectorAll('table tbody tr')).map(row => {
                const cells = Array.from(row.querySelectorAll('td'));
                if (!cells.length) return null;
                const compactItemText = (cells[0].innerText || cells[0].textContent || '')
                    .replace(/\s+/g, '')
                    .trim();
                const uploadedItemMatch = compactItemText.match(
                    /IS\d+(?:-[A-Za-z0-9]+)*-i\d+/i
                );
                const itemId = uploadedItemMatch
                    ? uploadedItemMatch[0]
                    : compactItemText;
                const statusCells = cells.length > 2
                    ? [cells[2], ...cells.slice(1, 2), ...cells.slice(3)]
                    : cells.slice(1);
                const statusText = statusCells
                    .map(cell => (cell.innerText || cell.textContent || '').trim())
                    .find(text => statusPattern.test(text)) || '';
                const match = statusText.match(statusPattern);
                return itemId && match ? [itemId, match[1]] : null;
            }).filter(Boolean);
            """
        )
        statuses = dict(rows or [])
        if item_set_id is None:
            return statuses
        set_prefix = self.compact_item_id(
            self.item_set_numeric_prefix(item_set_id)
        ).casefold()
        return {
            row_item_id: status
            for row_item_id, status in statuses.items()
            if (compact := self.compact_item_id(row_item_id).casefold())
            and re.match(rf"{re.escape(set_prefix)}(?!\d)", compact)
            and re.search(r"i\d+$", compact)
        }

    def get_qar_need_improvement_item_ids(self):
        """Return every item that must be corrected before RWG routing."""
        retry_statuses = {
            status.casefold() for status in self.QAR_RETRY_STATUS_LABELS
        }
        return [
            item_id
            for item_id, status in self.get_qar_item_statuses().items()
            if status.casefold() in retry_statuses
        ]

    def click_item_by_id(self, item_id):
        self.pause_before_action()
        item_link = self.wait_utils.until_clickable(
            (
                By.XPATH,
                f"//table//tbody/tr//td[1]//*[normalize-space()='{item_id}' or normalize-space()=\"{item_id}\"]",
            ),
            timeout=20,
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item_link)
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", item_link)
        self.wait_utils.until_condition(
            lambda driver: item_id in driver.find_element(By.TAG_NAME, "body").text,
            timeout=30,
        )
        return item_id

    def click_edit_item(self):
        if any(
            self.wait_utils.is_visible(locator, timeout=1)
            for locator in self.SAVE_REVISION_LOCATORS
        ):
            return
        self.click_any_element(self.EDIT_ITEM_LOCATORS)

    def get_visible_element_from_locators(self, locators):
        for locator in locators:
            for element in self.driver.find_elements(*locator):
                try:
                    if element.is_displayed() and element.is_enabled():
                        return element
                except Exception:
                    continue
        return None

    @staticmethod
    def get_editable_element_text(element):
        if element.tag_name.lower() in ("input", "textarea"):
            return element.get_attribute("value") or ""
        return element.get_attribute("innerText") or element.text or ""

    def set_first_available_editor_text(self, value):
        editor = self.wait_utils.until_condition(
            lambda driver: self.get_visible_element_from_locators(self.ITEM_CONTENT_EDITORS),
            timeout=20,
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", editor)
        self.pause_before_action()
        try:
            editor.click()
            editor.send_keys(Keys.CONTROL, "a")
            editor.send_keys(Keys.BACKSPACE)
            editor.send_keys(value)
        except Exception:
            self.driver.execute_script(
                """
                const editor = arguments[0];
                const value = arguments[1];
                if ('value' in editor) editor.value = value;
                else editor.innerHTML = '<p>' + value + '</p>';
                editor.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    inputType: 'insertText',
                    data: value,
                }));
                editor.dispatchEvent(new Event('change', { bubbles: true }));
                editor.dispatchEvent(new Event('blur', { bubbles: true }));
                """,
                editor,
                value,
            )
        try:
            self.wait_utils.until_condition(
                lambda driver: value in self.get_editable_element_text(editor),
                timeout=15,
            )
        except TimeoutException:
            try:
                actual_text = self.get_editable_element_text(editor)
            except Exception as read_error:
                actual_text = f"<could not read editor text: {read_error}>"
            raise AssertionError(
                "set_first_available_editor_text: expected text not found in "
                f"editor after edit.\nExpected (value): {value!r}\n"
                f"Actual (editor text): {actual_text!r}"
            )

    def enter_revision_notes(self, note_text):
        last_error = None
        for locator in self.REVISION_NOTE_INPUT_LOCATORS:
            try:
                note_input = self.wait_utils.until_visible(locator, timeout=8)
                tag_name = note_input.tag_name.lower()
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", note_input)
                self.pause_before_action()
                if tag_name == "textarea":
                    note_input.clear()
                    note_input.send_keys(note_text)
                else:
                    self.driver.execute_script(
                        """
                        const input = arguments[0];
                        const value = arguments[1];
                        input.innerHTML = '<p>' + value + '</p>';
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        note_input,
                        note_text,
                    )
                return
            except Exception as error:
                last_error = error
        return False

    def get_teacher_revised_count(self):
        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r"\b(\d+)\s+items?\s+revised\b", body_text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def click_save_revision(self):
        last_error = None
        revised_count_before = self.get_teacher_revised_count()
        for locator in self.SAVE_REVISION_LOCATORS:
            try:
                save_button = self.wait_utils.until_clickable(locator, timeout=15)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    save_button,
                )
                self.pause_before_action()
                try:
                    save_button.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", save_button)
                self.wait_utils.until_condition(
                    lambda driver: self.get_teacher_revised_count() > revised_count_before
                    or not any(
                        self.wait_utils.is_visible(save_locator, timeout=1)
                        for save_locator in self.SAVE_REVISION_LOCATORS
                    ),
                    timeout=45,
                )
                return
            except Exception as error:
                last_error = error
        raise last_error

    ITEM_ID_PATTERN = re.compile(r"IS\d+(?:-[A-Za-z0-9]+)*-i\d+", re.IGNORECASE)

    @classmethod
    def _extract_item_id_key(cls, text):
        """Return a normalized item-id key from free text, or None if absent.

        Used to reconcile the table-row scan below with the broader
        card-based scan that follows it: both can surface the same
        underlying item through different DOM shapes (e.g. a single-item
        set that renders both a table row and a standalone detail card for
        the same item), and only a real item-id match reliably identifies
        that they're duplicates - a raw label/element-id does not.
        """
        match = cls.ITEM_ID_PATTERN.search(text or "")
        return cls.compact_item_id(match.group(0)).casefold() if match else None

    def get_revision_item_targets(self):
        targets = []
        seen = set()
        seen_item_ids = set()
        revision_rows = self.driver.find_elements(
            By.XPATH,
            "//table//tbody/tr[.//*[normalize-space()='Revise' "
            "or normalize-space()='Needs Revision' "
            "or normalize-space()='Need Improvement' "
            "or normalize-space()='Needs Improvement']]",
        )
        for row in revision_rows:
            try:
                if not row.is_displayed():
                    continue
                first_cell = row.find_element(By.XPATH, "./td[1]")
                item_label = re.sub(r"\s+", "", first_cell.text)
                links = first_cell.find_elements(
                    By.XPATH,
                    ".//*[self::a or self::button or @role='button']",
                )
                target = next(
                    (
                        link
                        for link in links
                        if link.is_displayed() and link.is_enabled()
                    ),
                    None,
                )
                if not target:
                    continue
                key = item_label or target.id
                if key in seen:
                    continue
                seen.add(key)
                item_id_key = self._extract_item_id_key(row.text)
                if item_id_key:
                    seen_item_ids.add(item_id_key)
                targets.append((target, item_label or "revision item"))
            except Exception:
                continue

        # Always also scan for card-rendered revision items and merge them in
        # (deduped via `seen`). A table-based match set can be legitimately
        # incomplete - e.g. an item whose typology renders a different card
        # layout - and returning early here would silently drop it instead
        # of falling through to the broader card-based scan below.
        status_elements = self.driver.find_elements(
            By.XPATH,
            "//*[normalize-space()='Revise' or normalize-space()='Needs Revision' "
            "or normalize-space()='Need Improvement' "
            "or normalize-space()='Needs Improvement']",
        )
        for status_element in status_elements:
            try:
                if not status_element.is_displayed():
                    continue
                target = self.driver.execute_script(
                    """
                    let node = arguments[0];
                    while (node && node !== document.body) {
                        const text = (node.innerText || '').trim();
                        const role = node.getAttribute && node.getAttribute('role');
                        const clickable = node.matches &&
                            node.matches('a, button, [role="button"], [tabindex]');
                        const compactItem = text.length > 10 && text.length < 600 &&
                            !/^Revise\\s+\\d+$/i.test(text);
                        if (clickable && compactItem) return node;
                        node = node.parentElement;
                    }
                    node = arguments[0];
                    while (node && node !== document.body) {
                        const text = (node.innerText || '').trim();
                        if (text.length > 10 && text.length < 600 &&
                            !/^Revise\\s+\\d+$/i.test(text)) return node;
                        node = node.parentElement;
                    }
                    return arguments[0];
                    """,
                    status_element,
                )
                item_id_key = self._extract_item_id_key(target.text)
                if item_id_key and item_id_key in seen_item_ids:
                    # Same underlying item already captured by the table scan
                    # above (e.g. a single-item set rendering both a table
                    # row and a standalone detail card) - not a second item.
                    continue

                key = target.id
                if key in seen:
                    continue
                seen.add(key)
                if item_id_key:
                    seen_item_ids.add(item_id_key)
                label_lines = [
                    line.strip()
                    for line in target.text.splitlines()
                    if line.strip() and line.strip() not in self.QAR_RETRY_STATUS_LABELS
                ]
                targets.append((target, label_lines[0] if label_lines else "revision item"))
            except Exception:
                continue
        return targets

    def click_first_revision_item(self):
        targets = self.get_revision_item_targets()
        if not targets:
            return ""
        target, item_label = targets[0]
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        self.pause_before_action()
        self.driver.execute_script("arguments[0].click();", target)
        self.wait_utils.until_condition(
            lambda driver: any(
                self.wait_utils.is_visible(locator, timeout=1)
                for locator in self.SAVE_REVISION_LOCATORS
            )
            or any(
                self.wait_utils.is_visible(locator, timeout=1)
                for locator in self.EDIT_ITEM_LOCATORS
            ),
            timeout=20,
        )
        return item_label

    @staticmethod
    def _find_image_file_input(driver):
        for el in driver.find_elements(By.XPATH, "//input[@type='file']"):
            accept = el.get_attribute("accept") or ""
            if "image" in accept or not accept:
                return el
        return None

    def attach_image_to_item_editor(self, image_path, allow_native_dialog_risk=True):
        """Attach an image to the currently-open item editor.

        Strategy (in order):
        1. Look for an already-mounted (but hidden) file <input type="file">
           and send_keys the path straight to it - no clicks at all, so this
           never triggers a native dialog. If none is mounted yet and
           `allow_native_dialog_risk` is True, click the toolbar image
           button (never "Upload from device" or any other menu entry
           whose handler is likely to call `fileInputRef.current.click()`
           directly - that specific click is what invokes a real native OS
           file-picker dialog, which Selenium cannot see or dismiss and
           hangs the whole browser session indefinitely behind it) to
           reveal the input, then retry. This produces a real `blob:` URL
           image that the app's own upload flow serializes and persists.
        2. Only if no file input can be found at all: fall back to
           injecting a <img data-test-image="true"> element directly into
           the editor via a base64 data-URI. This is pure DOM manipulation
           - safe, but NOT reliable: the app's rich-text editor (TipTap/
           ProseMirror) keeps its own internal document model and can
           silently drop a DOM node that was never part of one of its own
           transactions, so the image can appear to attach successfully in
           the browser and then vanish once the item is saved and reloaded.
           Only use this as an absolute last resort.
        """
        image_path = Path(image_path).resolve()
        assert image_path.exists(), f"Test image not found: {image_path}"

        # --- Attempt 1: locate an already-mounted file input, no clicks ---
        file_input = self._find_image_file_input(self.driver)

        # --- Reveal the input via the toolbar button only, if allowed ---
        if not file_input and allow_native_dialog_risk:
            image_toolbar_locators = [
                (By.XPATH, "//button[@aria-label='image' or @aria-label='Insert image' or @aria-label='Add image' or @title='Image' or @title='Insert image']"),
                (By.XPATH, "//button[.//*[contains(@class,'lucide-image') or contains(@class,'image-icon') or contains(@class,'photo')]]"),
                (By.CSS_SELECTOR, "button[title*='mage'], button[aria-label*='mage']"),
            ]
            for locator in image_toolbar_locators:
                try:
                    btn = self.wait_utils.until_visible(locator, timeout=2)
                    if btn.is_enabled():
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        self.driver.execute_script("arguments[0].click();", btn)
                        break
                except Exception:
                    continue

            try:
                file_input = self.wait_utils.until_condition(
                    self._find_image_file_input, timeout=5
                )
            except Exception:
                file_input = None

        if file_input:
            self.driver.execute_script(
                "arguments[0].style.display='block'; arguments[0].style.visibility='visible'; arguments[0].style.opacity='1';",
                file_input,
            )
            file_input.send_keys(str(image_path))

            # After selecting the file, the app shows a preview dialog with an
            # explicit "Insert" button that must be clicked to commit the image
            # into the editor — selecting the file alone does not insert it.
            insert_button_locators = [
                (
                    By.XPATH,
                    "//*[@role='dialog' or contains(@class,'modal') or contains(@class,'Dialog')]"
                    "//button[normalize-space()='Insert' or normalize-space()='Insert Image' "
                    "or normalize-space()='Add' or normalize-space()='Upload' "
                    "or normalize-space()='Add Image' and not(@disabled)]",
                ),
                (
                    By.XPATH,
                    "//button[normalize-space()='Insert' or normalize-space()='Insert Image' "
                    "or normalize-space()='Add Image']",
                ),
            ]
            for locator in insert_button_locators:
                try:
                    insert_button = self.wait_utils.until_visible(locator, timeout=10)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", insert_button
                    )
                    self.pause_before_action()
                    self.driver.execute_script("arguments[0].click();", insert_button)
                    break
                except Exception:
                    continue

            # The app renders the inserted image as <img src="blob:..."> wrapped in
            # a `.rte-img-wrap` span (not a data-URI and not aria-label='itemContent').
            # Requiring img.complete && naturalWidth > 0 (not just a non-zero
            # bounding box) avoids racing ahead while the blob is still
            # loading - a placeholder/broken-image icon can already report a
            # non-zero rendered size before the real bytes have decoded.
            self.wait_utils.until_condition(
                lambda driver: bool(
                    driver.execute_script(
                        """
                        return Array.from(document.querySelectorAll(
                            "[contenteditable='true'] img"
                        )).some(function(img) {
                            const rect = img.getBoundingClientRect();
                            return !img.classList.contains('ProseMirror-separator')
                                && rect.width > 10
                                && rect.height > 10
                                && img.complete
                                && img.naturalWidth > 0;
                        });
                        """
                    )
                ),
                timeout=45,
            )
            return

        # --- Last resort: DOM injection (not guaranteed to persist) ---
        if not self._inject_image_data_uri(image_path):
            raise TimeoutException(
                "attach_image_to_item_editor: no file input could be found/revealed "
                "and DOM data-URI injection also failed (no visible contenteditable "
                "editor found)."
            )

    def _inject_image_data_uri(self, image_path, append=True):
        """Insert an <img data-test-image> into the item editor via pure DOM
        manipulation - no clicks, so this can never trigger a native OS
        file-picker dialog. Returns True on success, False if no visible
        contenteditable editor was found (caller decides how to fall back).

        When `append` is True (the default) the image is added alongside
        whatever is already in the editor rather than clearing it first -
        callers that want a from-scratch editor should clear it themselves
        before calling this.
        """
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        data_uri = f"data:{mime};base64," + base64.b64encode(image_path.read_bytes()).decode()

        inserted = self.driver.execute_script(
            """
            const dataUri = arguments[0];
            const selectors = [
                "[aria-label='itemContent'] .tiptap",
                "[aria-label='itemContent'] [contenteditable='true']",
                "[aria-label='Statement'] .tiptap",
                "[aria-label='Statement'] [contenteditable='true']",
                ".tiptap[contenteditable='true']",
                "[contenteditable='true']"
            ];
            let editor = null;
            for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) { editor = el; break; }
                }
                if (editor) break;
            }
            if (!editor) return false;
            editor.focus();
            const img = document.createElement('img');
            img.src = dataUri;
            img.setAttribute('data-test-image', 'true');
            img.setAttribute('alt', 'test-attachment');
            img.style.maxWidth = '200px';
            img.style.display = 'block';
            editor.appendChild(img);
            editor.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText'}));
            editor.dispatchEvent(new Event('change', {bubbles: true}));
            editor.dispatchEvent(new Event('blur', {bubbles: true}));
            return true;
            """,
            data_uri,
        )
        if not inserted:
            return False
        try:
            self.wait_utils.until_condition(
                lambda driver: bool(
                    driver.find_elements(
                        By.CSS_SELECTOR, "[contenteditable='true'] img[data-test-image]"
                    )
                ),
                timeout=10,
            )
        except TimeoutException:
            # A rich-text editor (TipTap/ProseMirror) can discard a raw DOM
            # node injected outside its own transaction system - e.g. on the
            # blur/change events dispatched above - so the node we just
            # appended may already be gone. Report failure so the caller can
            # fall back, rather than raising here.
            return False
        return True

    def edit_open_revision_item(
        self,
        item_id,
        revised_question=None,
        revision_note=None,
        image_path=None,
    ):
        revised_question = revised_question or (
            f"Updated revision for {item_id}: Is 98765 > 12345?"
        )
        revised_count_before = self.get_teacher_revised_count()
        self.click_edit_item()
        self.set_first_available_editor_text(revised_question)
        if image_path:
            try:
                self.attach_image_to_item_editor(image_path)
            except Exception as img_err:
                _safe_print(f"[WARN] Image attach skipped for {item_id}: {img_err}")
        self.enter_revision_notes(
            revision_note or f"Automation revision note for {item_id}."
        )
        self.click_save_revision()
        try:
            self.wait_utils.until_condition(
                lambda driver: self.get_teacher_revised_count() > revised_count_before,
                timeout=10,
            )
        except TimeoutException:
            # click_save_revision() can report success when the save button
            # merely disappears without the edit actually persisting (a
            # validation hiccup for some typologies). Don't fail here - the
            # caller re-checks QAR status and retries with a fresh
            # correction on the next round if this item is still flagged.
            pass
        return revised_question

    def revise_qar_need_improvement_items(
        self,
        item_set_id,
        expected_item_ids,
        correction_factory,
        retry_number,
        image_path_by_item_id=None,
    ):
        """Open and correct each currently retriable QAR item once."""
        expected_item_ids = tuple(dict.fromkeys(expected_item_ids))
        expected_by_key = {
            self.compact_item_id(item_id).casefold(): item_id
            for item_id in expected_item_ids
        }
        revised_item_ids = []
        # Track processed keys so we never re-edit an item whose UI status hasn't
        # refreshed yet (the status badge stays "Need Improvement" until QAR re-runs).
        processed_keys = set()
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=60,
        )

        while True:
            targets = self.get_revision_item_targets()

            # Find the first target whose normalized item-key has not been processed.
            next_item = None
            for target_elem, raw_label in targets:
                normalized = raw_label
                if not self.compact_item_id(raw_label).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", raw_label)
                    if m:
                        normalized = f"{item_set_id}-i{m.group(1)}"
                key = self.compact_item_id(normalized).casefold()
                if key not in processed_keys:
                    next_item = (target_elem, normalized, key)
                    break

            if next_item is None:
                break  # No unprocessed revision items remain.

            target_elem, item_label, item_key = next_item

            # Click the specific, unprocessed target element.
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target_elem
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", target_elem)
                self.wait_utils.until_condition(
                    lambda driver: any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.SAVE_REVISION_LOCATORS
                    ) or any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.EDIT_ITEM_LOCATORS
                    ),
                    timeout=20,
                )
            except Exception:
                # Element went stale — fall back to clicking whatever "first revision
                # item" is currently in the list and check it isn't already processed.
                fallback_label = self.click_first_revision_item()
                if not fallback_label:
                    break
                if not self.compact_item_id(fallback_label).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", fallback_label)
                    if m:
                        fallback_label = f"{item_set_id}-i{m.group(1)}"
                fb_key = self.compact_item_id(fallback_label).casefold()
                if fb_key in processed_keys:
                    break  # Only already-processed items left.
                item_label, item_key = fallback_label, fb_key

            canonical_item_id = expected_by_key.get(item_key, item_label)
            try:
                qar_feedback = QARReportPage(self.driver).inspect_item_feedback(
                    canonical_item_id
                )
            except Exception:
                # Some legacy/minimal review builds expose the actionable row
                # without rendering report cards. The correction still runs,
                # but full E2E builds retain the inspected report evidence.
                qar_feedback = {
                    "status": "",
                    "score": None,
                    "failure_reasons": {},
                }
            try:
                correction = correction_factory(
                    canonical_item_id,
                    retry_number,
                    qar_feedback,
                )
            except TypeError:
                correction = correction_factory(canonical_item_id, retry_number)
            if isinstance(correction, str):
                correction = {"question": correction}
            revised_question = correction.get("question", "").strip()
            if not revised_question:
                raise AssertionError(
                    f"Correction fixture returned no question for {canonical_item_id}."
                )
            feedback_parts = []
            if qar_feedback.get("status"):
                feedback_parts.append(f"status={qar_feedback['status']}")
            if qar_feedback.get("score") is not None:
                feedback_parts.append(f"score={qar_feedback['score']}%")
            feedback_parts.extend(qar_feedback.get("failure_reasons", {}).keys())
            revision_note = correction.get("revision_note") or (
                f"Automation QAR correction for {canonical_item_id}."
            )
            if feedback_parts:
                revision_note = (
                    f"{revision_note} QAR feedback reviewed: "
                    f"{', '.join(feedback_parts)}."
                )
            edit_arguments = {
                "revised_question": revised_question,
                "revision_note": revision_note,
            }
            image_path = (image_path_by_item_id or {}).get(canonical_item_id)
            if image_path:
                edit_arguments["image_path"] = image_path
            self.edit_open_revision_item(canonical_item_id, **edit_arguments)
            revised_item_ids.append(canonical_item_id)
            processed_keys.add(item_key)

            # Wait for the page to settle (NOT for the revision-list badge to update —
            # the app keeps "Need Improvement" until QAR is re-run).
            self.wait_utils.until_condition(
                lambda driver: not self.is_item_set_detail_loading(driver),
                timeout=30,
            )

        return revised_item_ids

    def is_rerun_qar_enabled(self):
        """Check if Re-run QAR button is enabled without clicking it."""
        for locator in self.RERUN_QAR_LOCATORS:
            try:
                rerun_button = self.wait_utils.until_visible(locator, timeout=5)
                if rerun_button.is_enabled() and not rerun_button.get_attribute("disabled") and rerun_button.get_attribute("aria-disabled") != "true":
                    return True
            except Exception:
                continue
        return False

    def _revise_items_loop(self, item_set_id, edit_fn):
        """Core revision loop shared by revise_items_in_open_item_set variants.

        Iterates revision targets, skipping ones already processed, until none
        remain unprocessed.  The app keeps the 'Need Improvement' badge visible
        until QAR is re-run, so we track processed items ourselves instead of
        relying on the list to shrink.
        """
        results = []
        processed_keys = set()
        self.wait_utils.until_condition(
            lambda driver: not self.is_item_set_detail_loading(driver),
            timeout=60,
        )

        while True:
            targets = self.get_revision_item_targets()

            next_item = None
            for target_elem, raw_label in targets:
                normalized = raw_label
                if not self.compact_item_id(raw_label).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", raw_label)
                    if m:
                        normalized = f"{item_set_id}-i{m.group(1)}"
                key = self.compact_item_id(normalized).casefold()
                if key not in processed_keys:
                    next_item = (target_elem, normalized, key)
                    break

            if next_item is None:
                break

            target_elem, item_label, item_key = next_item
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target_elem
                )
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", target_elem)
                self.wait_utils.until_condition(
                    lambda driver: any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.SAVE_REVISION_LOCATORS
                    ) or any(
                        self.wait_utils.is_visible(loc, timeout=1)
                        for loc in self.EDIT_ITEM_LOCATORS
                    ),
                    timeout=20,
                )
            except Exception:
                fallback = self.click_first_revision_item()
                if not fallback:
                    break
                if not self.compact_item_id(fallback).casefold().startswith(
                    self.compact_item_id(item_set_id).casefold()
                ):
                    m = re.match(r"\s*(\d+)\b", fallback)
                    if m:
                        fallback = f"{item_set_id}-i{m.group(1)}"
                fb_key = self.compact_item_id(fallback).casefold()
                if fb_key in processed_keys:
                    break
                item_label, item_key = fallback, fb_key

            result = edit_fn(item_label)
            results.append(result)
            processed_keys.add(item_key)

            self.wait_utils.until_condition(
                lambda driver: not self.is_item_set_detail_loading(driver),
                timeout=30,
            )

        return results

    def revise_items_in_open_item_set(self, item_set_id):
        """Edit every revision item without leaving the open item-set screen."""
        return self._revise_items_loop(
            item_set_id,
            lambda label: (self.edit_open_revision_item(label), label)[1],
        )

    def revise_items_with_image_in_open_item_set(self, item_set_id, image_path):
        """Like revise_items_in_open_item_set but attaches image_path to every revised item."""
        def _edit_with_image(label):
            revised_question = self.edit_open_revision_item(label, image_path=image_path)
            return (label, revised_question)

        return self._revise_items_loop(item_set_id, _edit_with_image)

    def rerun_qar_if_enabled(self):
        for locator in self.TEACHER_RESUBMIT_REVIEW_LOCATORS:
            try:
                submit_button = self.wait_utils.until_clickable(locator, timeout=10)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    submit_button,
                )
                self.pause_before_action()
                try:
                    submit_button.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", submit_button)
                self.confirm_submit_if_prompted()
                self.wait_utils.until_condition(
                    lambda driver: not any(
                        self.wait_utils.is_visible(submit_locator, timeout=1)
                        for submit_locator in self.TEACHER_RESUBMIT_REVIEW_LOCATORS
                    ),
                    timeout=30,
                )
                return "Teacher resubmitted the revised set for review."
            except Exception:
                continue

        disabled_found = False
        for locator in self.RERUN_QAR_LOCATORS:
            try:
                rerun_button = self.wait_utils.until_visible(locator, timeout=10)
                if not rerun_button.is_enabled() or rerun_button.get_attribute("disabled") or rerun_button.get_attribute("aria-disabled") == "true":
                    disabled_found = True
                    continue
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", rerun_button)
                self.pause_before_action()
                self.driver.execute_script("arguments[0].click();", rerun_button)
                return self.wait_for_ocr_success_message()
            except Exception:
                continue
        if disabled_found:
            return "Re-run QAR button found but disabled."
        return "Re-run QAR button not available."

    def resubmit_revised_item_set_for_review(self):
        """Resubmit SME revisions without changing the legacy QAR helper contract."""
        result = self.rerun_qar_if_enabled()
        if "resubmitted" not in result.casefold():
            raise AssertionError(
                "The revised item set was not resubmitted for review. "
                f"Observed action result: {result}"
            )
        return result.replace("Teacher", "SME", 1)
