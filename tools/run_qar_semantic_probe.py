"""Upload one sheet, run QAR on it, and record what the Duplicate Check said.

Run once per sheet, in order - Sheet A first, so the bank holds its items
before Sheet B's paraphrases are measured against them:

    python -m tools.run_qar_semantic_probe A data/qar_semantic/sheet_A_originals.xlsx
    python -m tools.run_qar_semantic_probe B data/qar_semantic/sheet_B_semantic.xlsx

Each run signs in once. There is no retry loop anywhere in here on purpose:
repeated failed logins return 429 on this environment and lock the shared test
accounts for the whole team, so a credential problem must surface as one
failure rather than three.

Everything read off the page is written to JSON next to the sheet, because a
QAR pass costs ~30 minutes and re-reading a stale browser is not an option if
the analysis is worth anything.
"""
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from pages.common.login_page import LoginPage
from pages.qar.qar_report_page import QARReportPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.read_config import ReadConfig

# Every check the QAR Report panel renders, as the app labels them. Note the
# app says "Duplicate Check" and "Plagiarism Check" but "Bias Detection" -
# these are not derivable from one naming rule.
ALL_QAR_CHECKS = (
    "Meta Data Alignment",
    "Hard Validation",
    "Image Moderation",
    "Bias Detection",
    "Grammar Check",
    "Clarity Check",
    "Duplicate Check",
    "Plagiarism Check",
)

# An hour. Not a budget - a ceiling high enough that a 20-item set produces a
# measurement instead of a timeout. Observed rate on this environment is
# 77-100 s/item, and Sheet B is compared against a bank 20 items larger.
ANALYSIS_TIMEOUT = 3600


def make_driver():
    options = ChromeOptions()
    for flag in (
        "--disable-dev-shm-usage", "--disable-extensions", "--disable-gpu",
        "--no-sandbox", "--no-first-run", "--no-default-browser-check",
        "--disable-background-timer-throttling", "--remote-allow-origins=*",
        "--window-size=1920,1080", "--headless=new",
    ):
        options.add_argument(flag)
    options.add_argument(f"--user-data-dir={Path(tempfile.mkdtemp(prefix='cbse_qar_'))}")
    return webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )


def say(message):
    """Print and flush - this runs in the background, so buffered output is
    output nobody sees until the process exits."""
    print(message, flush=True)


def main():
    label, sheet = sys.argv[1], Path(sys.argv[2]).resolve()
    out_path = sheet.parent / f"result_sheet_{label}.json"
    result = {"label": label, "sheet": str(sheet), "started": time.strftime("%H:%M:%S")}

    driver = make_driver()
    try:
        user = ReadConfig.get_sme2_username()
        say(f"[{label}] signing in as {user}")
        driver.get(ReadConfig.get_base_url())
        LoginPage(driver).login_to_application(
            user, ReadConfig.get_password_for_username(user)
        )

        page = UploadItemFilePage(driver)
        page.wait_for_application_to_load()
        page.close_popup_if_open()
        page.open_item_creation_module()
        page.open_upload_item_file_tab()
        page.open_upload_step()

        say(f"[{label}] uploading {sheet.name}")
        page.upload_file(str(sheet))
        result["upload_message"] = page.wait_for_upload_validation_success()
        say(f"[{label}] upload validation: {result['upload_message']}")

        page.click_continue()
        result["review_item_ids"] = page.get_review_item_ids()
        say(f"[{label}] {len(result['review_item_ids'])} item(s) staged for QAR")
        page.click_continue()

        say(f"[{label}] submitting for QAR (ceiling {ANALYSIS_TIMEOUT}s) ...")
        started = time.time()
        page.click_submit_for_qar_and_wait_for_results(analysis_timeout=ANALYSIS_TIMEOUT)
        result["qar_seconds"] = round(time.time() - started, 1)
        result["toast"] = page.wait_for_ocr_success_message()
        say(f"[{label}] QAR finished in {result['qar_seconds']}s - toast: {result['toast']}")

        item_ids = page.get_qar_result_item_ids() or result["review_item_ids"]
        result["item_ids"] = item_ids
        result["item_set_id"] = page.get_item_set_id_from_item_ids(item_ids)
        result["status_summary"] = page.get_item_set_status_summary()
        result["body_text"] = driver.find_element("tag name", "body").text
        say(f"[{label}] set {result['item_set_id']} - statuses: {result['status_summary']}")

        report = QARReportPage(driver)
        # The check cards hang off an expanded result ROW, not off any
        # panel-level control, and opening an item navigates away from the
        # results view - so the set-level cards have to be read first.
        result["row_expanded"] = report.expand_result_row(item_ids[0]) if item_ids else False
        say(f"[{label}] result row expanded: {result['row_expanded']}")

        result["checks"] = {}
        for check in ALL_QAR_CHECKS:
            card = report.get_check_card_text(check)
            result["checks"][check] = {
                "score": report.get_check_score(check),
                "color": report.get_check_card_status_color(check),
                "card": (card or "")[:600],
            }
            say(f"[{label}]   {check:22} score={result['checks'][check]['score']} "
                f"colour={result['checks'][check]['color']}")

        # Per-item detail. This is what gives the tier ladder its resolution;
        # if the build has no per-item breakdown it degrades to an error per
        # item rather than taking the run down.
        result["per_item"] = {}
        for index, item_id in enumerate(item_ids, start=1):
            try:
                evidence = report.get_open_item_check_evidence(
                    item_id, "Duplicate Detection", expand=True
                )
                result["per_item"][item_id] = {
                    "score": evidence["score"],
                    "threshold": evidence["threshold"],
                    "status_color": evidence["status_color"],
                    "status": report.get_item_status(item_id),
                    "card": (evidence["card"] or "")[:400],
                }
            except Exception as error:  # noqa: BLE001 - one bad item must not lose the rest
                result["per_item"][item_id] = {"error": f"{type(error).__name__}: {error}"[:200]}
            say(f"[{label}]   item {index}/{len(item_ids)} {item_id}: "
                f"{result['per_item'][item_id]}")
    except Exception:
        result["fatal"] = traceback.format_exc()
        say(f"[{label}] FAILED:\n{result['fatal']}")
    finally:
        try:
            driver.save_screenshot(str(sheet.parent / f"result_sheet_{label}.png"))
        except Exception:
            pass
        driver.quit()
        out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        say(f"[{label}] wrote {out_path}")


if __name__ == "__main__":
    main()
