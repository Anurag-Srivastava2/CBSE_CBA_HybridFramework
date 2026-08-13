import time
from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pages.sme.upload_item_file_page import UploadItemFilePage


class BulkUploadPage(UploadItemFilePage):
    """Prefix-safe bulk Excel upload actions for independent QAR checks."""

    def upload_excel(self, file_path):
        _, message = self.upload_item_file_and_validate(file_path)
        return message

    def upload_excel_for_validation(self, file_path, timeout=60):
        self.open_item_creation_module()
        self.open_upload_item_file_tab()
        self.open_upload_step()
        self.discard_active_upload_if_present()
        self.discard_staged_upload_files()
        self.upload_file(file_path)
        try:
            message = self.wait_for_upload_validation_success()
            self.activate_uploaded_file(Path(file_path).name)
            return {"accepted": True, "message": message}
        except Exception:
            message = self.wait_for_upload_rejection(timeout=timeout)
            return {"accepted": False, "message": message}

    UPLOAD_IMAGES_ZIP_PANEL = (
        By.XPATH,
        "//*[contains(normalize-space(),'Upload Images ZIP') "
        "or contains(normalize-space(),'drop the images ZIP') "
        "or contains(normalize-space(),'Excel has been staged')]",
    )
    IMAGE_ZIP_REJECTION = (
        By.XPATH,
        "//*[contains(normalize-space(.),'Image rejected:') "
        "and not(.//*[contains(normalize-space(.),'Image rejected:')])]",
    )
    # Distinct from IMAGE_ZIP_REJECTION: this fires when the *Excel workbook*
    # itself is rejected (e.g. "Upload failed — 0 of 1 rows added"), which
    # can surface after the images ZIP is dropped even though it's not
    # actually an images-ZIP problem. Without this, zip_upload_outcome()
    # never recognizes the failure and polls the full timeout before
    # falling back to a generic, unhelpful page dump.
    EXCEL_ROWS_REJECTION = (
        By.XPATH,
        "//*[contains(normalize-space(.),'Upload failed') "
        "and not(.//*[contains(normalize-space(.),'Upload failed')])]",
    )
    IMAGE_ZIP_UPLOAD_SUCCESS = (
        By.XPATH,
        "//*[contains(normalize-space(.),'All files uploaded and validated successfully') "
        "and not(.//*[contains(normalize-space(.),"
        "'All files uploaded and validated successfully')])]",
    )
    IMAGE_ZIP_REVIEW_SUCCESS = (
        By.XPATH,
        "//*[contains(normalize-space(.),'File Validation Passed') "
        "and not(.//*[contains(normalize-space(.),'File Validation Passed')])]",
    )

    @staticmethod
    def _resolve_excel_and_images_zip(xlsx_path, zip_path):
        """Validate the complete upload pair before staging either file."""
        resolved_paths = []
        for label, file_path, expected_suffix in (
            ("Excel workbook", xlsx_path, ".xlsx"),
            ("images ZIP", zip_path, ".zip"),
        ):
            resolved_path = Path(file_path).expanduser().resolve()
            if not resolved_path.is_file():
                raise FileNotFoundError(f"{label} not found: {resolved_path}")
            if resolved_path.suffix.casefold() != expected_suffix:
                raise ValueError(
                    f"{label} must be a {expected_suffix} file: {resolved_path}"
                )
            resolved_paths.append(resolved_path)
        return tuple(resolved_paths)

    def upload_excel_and_images_zip_for_validation(self, xlsx_path, zip_path, timeout=90):
        """Upload the item workbook, then its images .zip, as the app's two-step flow.

        The image-item workbook references each image by filename (in an
        Image column) but the binary images only exist in the separate .zip.
        After the workbook is staged, the app swaps the dropzone to a
        dedicated "Upload Images ZIP" panel ("Your Excel has been staged --
        drop the images ZIP (.zip) to finalise the upload."). We must wait
        for that panel to render before sending the zip, otherwise the zip
        lands on the old (about-to-be-replaced) file input and is dropped.

        We deliberately do NOT trust wait_for_upload_validation_success()'s
        generic fallback here: its broad success locator matches any text
        containing "Upload Status" / "File Upload Status", which is also the
        header of the ever-present "Previously Uploaded Files" history table
        further down the page -- so it reports false-positive success even
        when the zip silently failed to attach. Instead we require the
        "Upload Images ZIP" panel to actually disappear (proof the zip was
        accepted) before trusting any success message.
        """
        xlsx_path, zip_path = self._resolve_excel_and_images_zip(xlsx_path, zip_path)

        self.open_item_creation_module()
        self.open_upload_item_file_tab()
        self.open_upload_step()
        self.discard_active_upload_if_present()
        self.discard_staged_upload_files()
        self.upload_file(xlsx_path)
        self.wait_utils.until_visible(self.UPLOAD_IMAGES_ZIP_PANEL, timeout=30)
        self.pause_before_action()
        self.upload_file(zip_path)

        def zip_upload_outcome(driver):
            for locator in (self.IMAGE_ZIP_REJECTION, self.EXCEL_ROWS_REJECTION):
                rejection = next(
                    (
                        element.text.strip()
                        for element in driver.find_elements(*locator)
                        if element.is_displayed() and element.text.strip()
                    ),
                    "",
                )
                if rejection:
                    return {"accepted": False, "message": rejection}
            if not driver.find_elements(*self.UPLOAD_IMAGES_ZIP_PANEL):
                return {"accepted": True, "message": ""}
            return False

        try:
            outcome = self.wait_utils.until_condition(zip_upload_outcome, timeout=timeout)
        except TimeoutException:
            # Best-effort: surface whatever specific rejection line is on the
            # page rather than a raw page dump, even for a rejection shape
            # neither locator above recognizes yet.
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            specific_line = next(
                (
                    line.strip()
                    for line in page_text.splitlines()
                    if "upload failed" in line.casefold()
                    or "rejected" in line.casefold()
                ),
                None,
            )
            reason = specific_line or (
                "the 'Upload Images ZIP' panel was still showing with no "
                "recognizable rejection message"
            )
            raise AssertionError(
                f"The images ZIP did not appear to attach after {timeout}s: {reason}"
            )

        if not outcome["accepted"]:
            return outcome

        try:
            success = self.wait_utils.until_visible(
                self.IMAGE_ZIP_UPLOAD_SUCCESS,
                timeout=5,
            )
            message = success.text.strip()
        except TimeoutException:
            continue_button = self.wait_utils.until_visible(
                self.CONTINUE_BUTTON,
                timeout=20,
            )
            assert continue_button.is_enabled(), (
                "The images ZIP panel closed, but Continue remained disabled."
            )
            message = (
                "Images ZIP accepted: the ZIP panel closed and Continue is enabled."
            )
        return {"accepted": True, "message": message}

    def get_images_zip_validation_evidence(self, accepted):
        """Return a visible product element proving this upload outcome.

        Rejections remain on the ZIP panel and expose the exact validation error.
        Accepted uploads advance to Review so the screenshot contains the product's
        explicit "File Validation Passed" indicator instead of a generic upload page.
        """
        if not accepted:
            element = self.wait_utils.until_visible(
                self.IMAGE_ZIP_REJECTION,
                timeout=20,
            )
            return element, "image_rejection_message"

        direct_success = next(
            (
                element
                for element in self.driver.find_elements(*self.IMAGE_ZIP_UPLOAD_SUCCESS)
                if element.is_displayed() and element.text.strip()
            ),
            None,
        )
        if direct_success is not None:
            return direct_success, "upload_success_message"

        self.click_continue()
        element = self.wait_utils.until_visible(
            self.IMAGE_ZIP_REVIEW_SUCCESS,
            timeout=120,
        )
        return element, "review_file_validation_passed"

    def submit_for_qar(self, unique_prefix, analysis_timeout=180):
        self.click_continue()

        def scoped_review_is_ready(driver):
            review_text = driver.find_element(By.TAG_NAME, "body").text
            normalized = review_text.casefold()
            still_loading = any(
                marker in normalized
                for marker in (
                    "loading uploaded file items",
                    "loading file items",
                    "loading items",
                )
            )
            return review_text if unique_prefix in review_text and not still_loading else False

        try:
            review_text = self.wait_utils.until_condition(
                scoped_review_is_ready,
                timeout=120,
            )
        except Exception as error:
            review_text = self.driver.find_element(By.TAG_NAME, "body").text
            raise AssertionError(
                f"Fresh upload marker {unique_prefix!r} did not finish loading on "
                f"the review step. Page: {review_text[:1500]}"
            ) from error
        item_ids = self.get_review_item_ids()
        assert item_ids, (
            f"Review step loaded marker {unique_prefix!r} but exposed no item IDs."
        )
        # The review table can still be streaming rows in for a moment after the
        # "loading" banner clears, so a single read can catch a transient partial
        # or duplicated row set. Only trust the count once two reads agree.
        stable_reads = 0
        deadline = time.time() + 15
        while stable_reads < 2 and time.time() < deadline:
            time.sleep(1)
            current_item_ids = self.get_review_item_ids()
            if current_item_ids == item_ids:
                stable_reads += 1
            else:
                stable_reads = 0
                item_ids = current_item_ids
        item_set_id = self.get_item_set_id_from_item_ids(item_ids)
        self.click_continue()
        self.click_submit_for_qar_and_wait_for_results(analysis_timeout=analysis_timeout)
        result_item_ids = self.get_qar_result_item_ids()
        if result_item_ids:
            item_ids = result_item_ids
            item_set_id = self.get_item_set_id_from_item_ids(item_ids)
        return {
            "item_ids": item_ids,
            "item_set_id": item_set_id,
            "current_url": self.driver.current_url,
        }
