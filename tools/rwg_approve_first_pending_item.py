import argparse
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from time import sleep

from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pages.common.login_page import LoginPage
from pages.rwg.review_queue_page import RWGReviewQueuePage
from utilities.read_config import ReadConfig


def build_driver(headless=False):
    # FIX #11: Create the profile directory first, then wrap the Chrome
    # initialisation in try/except so the temp dir is cleaned up if the
    # driver fails to start (previously the finally in the caller never
    # ran because build_driver raised before driver was assigned).
    profile_dir = Path(tempfile.mkdtemp(prefix="cbse_rwg_script_chrome_"))
    try:
        options = ChromeOptions()
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--remote-allow-origins=*")
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--window-size=1920,1080")
        if headless:
            options.add_argument("--headless=new")

        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options,
        )
        driver.maximize_window()
        driver.implicitly_wait(5)
        return driver, profile_dir
    except Exception:
        # shutil is a top-level import — no inline import needed.
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise


def click_pending_review_bucket(review_queue_page):
    review_queue_page.open_queue_module()
    review_queue_page.wait_utils.until_condition(
        lambda driver: "loading" not in driver.find_element(By.TAG_NAME, "body").text.casefold(),
        timeout=30,
    )
    clicked_text = review_queue_page.driver.execute_script(
        """
        const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [role="tab"], div, span'))
            .filter((element) => {
                const rect = element.getBoundingClientRect();
                const text = (element.innerText || element.textContent || '').trim();
                return rect.width > 0 &&
                    rect.height > 0 &&
                    /pending\\s+review/i.test(text);
            })
            .sort((left, right) => {
                const leftRect = left.getBoundingClientRect();
                const rightRect = right.getBoundingClientRect();
                const leftClickable = left.matches('button, a, [role="button"], [role="tab"]') ? 0 : 1;
                const rightClickable = right.matches('button, a, [role="button"], [role="tab"]') ? 0 : 1;
                return leftClickable - rightClickable || leftRect.top - rightRect.top || leftRect.left - rightRect.left;
            });
        const target = candidates[0];
        if (!target) return '';
        const clickable = target.closest('button, a, [role="button"], [role="tab"]') || target;
        clickable.scrollIntoView({block: 'center', inline: 'center'});
        clickable.click();
        return clickable.innerText || target.innerText || '';
        """
    )
    if not clicked_text:
        raise TimeoutException("Pending Review bucket was not visible in RWG queue.")

    review_queue_page.wait_utils.until_condition(
        lambda driver: "pending review" in driver.find_element(By.TAG_NAME, "body").text.casefold(),
        timeout=15,
    )
    return clicked_text


def click_first_pending_review_view(review_queue_page):
    click_pending_review_bucket(review_queue_page)
    starting_url = review_queue_page.driver.current_url
    clicked_text = review_queue_page.driver.execute_script(
        """
        const viewControls = Array.from(document.querySelectorAll('button, a, [role="button"]'))
            .filter((element) => {
                const rect = element.getBoundingClientRect();
                const text = (element.innerText || '').trim();
                return rect.width > 0 &&
                    rect.height > 0 &&
                    /^view$/i.test(text);
            })
            .filter((element) => {
                const row = element.closest('tr, [role="row"], article, section, li, div');
                const text = (row ? row.innerText : element.innerText) || '';
                return /\\bPending\\b/i.test(text) || /pending\\s+review/i.test(document.body.innerText || '');
            })
            .sort((left, right) => {
                const leftRect = left.getBoundingClientRect();
                const rightRect = right.getBoundingClientRect();
                return leftRect.top - rightRect.top || leftRect.left - rightRect.left;
            });
        const itemSetLinks = Array.from(document.querySelectorAll('a, button, [role="button"]'))
            .filter((element) => {
                const rect = element.getBoundingClientRect();
                const text = (element.innerText || element.textContent || '').trim();
                return rect.width > 0 &&
                    rect.height > 0 &&
                    /^IS\\d+(?:-[A-Za-z0-9]+)*$/i.test(text) &&
                    !/-i\\d+$/i.test(text);
            })
            .sort((left, right) => {
                const leftRect = left.getBoundingClientRect();
                const rightRect = right.getBoundingClientRect();
                return leftRect.top - rightRect.top || leftRect.left - rightRect.left;
            });
        const target = viewControls[0] || itemSetLinks[0];
        if (!target) return '';
        target.scrollIntoView({block: 'center', inline: 'center'});
        target.click();
        return target.innerText || '';
        """
    )
    if not clicked_text:
        raise TimeoutException("No View button or item-set link was visible in the Pending Review bucket.")

    review_queue_page.wait_utils.until_condition(
        lambda driver: review_queue_page.is_review_item_set_loaded_without_id(driver)
        or review_queue_page.is_review_item_ready(driver)
        or driver.current_url != starting_url,
        timeout=30,
    )
    return clicked_text


def open_first_pending_item(review_queue_page):
    """Navigate to the first pending RWG item, ready for approval.

    Always opens the Queue module first, then handles:
    1. App navigated to item set detail (items i1-i4 Under Review visible) → click first item
    2. App shows queue list (item sets like IS367 listed) → click first Pending Review item set
    """
    driver = review_queue_page.driver

    # Step 1: Navigate to the Queue module
    print("[RWG Tool] Opening Queue module...")
    review_queue_page.open_queue_module()
    queue_url = driver.current_url
    print(f"[RWG Tool] Queue module URL: {queue_url}")

    # Wait for the page to render (up to 3 seconds)
    sleep(3)

    # Step 2: Check what page we landed on via DOM
    # Case A: Item set detail page — items like IS367-i1, IS367-i2 with "Under Review" status
    under_review_items = driver.find_elements(
        By.XPATH,
        "//table//tr[.//*[contains(normalize-space(),'Under Review')]]"
        "//a[contains(text(),'-i')]"
    )
    # Case B: Item set detail — sidebar with individual item links
    sidebar_item_links = driver.find_elements(
        By.XPATH,
        "//*[contains(@class,'sidebar') or contains(@class,'left') or contains(@class,'nav')]"
        "//a[contains(text(),'-i')]"
    )
    # Case C: Evaluation criteria panel (item is already open for review).
    # NOTE: Intentionally NOT included in on_item_set_detail — "Evaluation Criteria" can
    # appear on the queue list page too, causing a false-positive that bypasses queue navigation.
    eval_criteria = driver.find_elements(
        By.XPATH,
        "//*[contains(normalize-space(),'Evaluation Criteria') "
        "or contains(normalize-space(),'Item Response Sheet')]"
    )

    # Only structural evidence (Under Review table rows or sidebar -i links) determines
    # we are on an item-set detail page.
    on_item_set_detail = bool(under_review_items or sidebar_item_links)

    # If the item detail is already fully rendered (eval criteria visible but no
    # item-set table structure), treat it as "already ready" and return immediately.
    if eval_criteria and not on_item_set_detail:
        if review_queue_page.is_review_item_ready(driver):
            print("[RWG Tool] Item already loaded and ready (eval criteria visible).")
            return

    if on_item_set_detail:
        print(f"[RWG Tool] Landed on item set detail — clicking first Under Review item.")
        # Click the first "Under Review" item link from the table
        if under_review_items:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", under_review_items[0])
            driver.execute_script("arguments[0].click();", under_review_items[0])
            item_text = under_review_items[0].text or under_review_items[0].get_attribute("textContent") or ""
            print(f"[RWG Tool] Clicked item: {item_text.strip()[:60]}")
            review_queue_page.wait_utils.until_condition(
                lambda d: review_queue_page.is_review_item_ready(d),
                timeout=30,
            )
            return
        # Try sidebar item links
        clicked_item = review_queue_page.click_next_left_side_pending_item()
        if clicked_item:
            safe = clicked_item.encode("ascii", errors="replace").decode("ascii")
            print(f"[RWG Tool] Clicked sidebar item: {safe.strip()[:60]}")
            review_queue_page.wait_utils.until_condition(
                lambda d: review_queue_page.is_review_item_ready(d),
                timeout=30,
            )
            return
        if review_queue_page.is_review_item_ready(driver):
            print("[RWG Tool] Item already loaded and ready.")
            return
        raise TimeoutException("On item set page but could not click any individual item for review.")

    # Step 3: Queue list view — find first Pending Review item set and click it
    print("[RWG Tool] On queue list — finding first Pending Review item set...")

    # Capture the queue-list URL NOW (before the JS click navigates away)
    queue_list_url = driver.current_url

    # Wait for the queue table to populate using JS (body.text can be empty in headless mode)
    try:
        review_queue_page.wait_utils.until_condition(
            lambda d: d.execute_script(
                """
                const rows = document.querySelectorAll('table tbody tr, [role="row"]');
                for (const row of rows) {
                    const t = (row.innerText || row.textContent || '').toLowerCase();
                    if (t.includes('pending review') || t.includes('pending_review')) return true;
                }
                return false;
                """
            ),
            timeout=15,
        )
    except TimeoutException:
        pass

    # Click the first Pending Review item set link directly from the table
    clicked = driver.execute_script("""
        const rows = Array.from(document.querySelectorAll('table tbody tr, [role="row"]'));
        for (const row of rows) {
            const text = (row.innerText || row.textContent || '').toLowerCase();
            if (text.includes('pending review') || text.includes('pending_review')) {
                const controls = Array.from(
                    row.querySelectorAll('a, button, [role="button"]')
                );
                const view = controls.find(control =>
                    /^view$/i.test((control.innerText || control.textContent || '').trim())
                );
                const itemSet = controls.find(control => {
                    const value = (control.innerText || control.textContent || '').trim();
                    return /^IS\\d+(?:-[A-Za-z0-9]+)*$/i.test(value)
                        && !/-i\\d+$/i.test(value);
                });
                const setRoute = controls.find(control => {
                    const href = control.getAttribute('href') || '';
                    return /\\/review-queue\\/\\d+\\/?(?:[?#].*)?$/i.test(href);
                });
                const target = view || itemSet || setRoute;
                if (target) {
                    target.scrollIntoView({block: 'center'});
                    target.click();
                    return (target.innerText || target.textContent || '').trim() || 'View';
                }
            }
        }
        // Fallback: click an item-set link, never an individual "-iN" item link.
        const isLinks = Array.from(document.querySelectorAll('table a'))
            .filter(a => {
                const value = (a.innerText || a.textContent || '').trim();
                return /^IS\\d+(?:-[A-Za-z0-9]+)*$/i.test(value)
                    && !/-i\\d+$/i.test(value);
            });
        if (isLinks.length > 0) {
            isLinks[0].scrollIntoView({block: 'center'});
            isLinks[0].click();
            return (isLinks[0].innerText || isLinks[0].textContent || '').trim();
        }
        return '';
    """)

    if not clicked:
        raise TimeoutException(
            "No Pending Review item sets found in the queue table. Queue may be empty."
        )
    safe_clicked = str(clicked).encode("ascii", errors="replace").decode("ascii")
    print(f"[RWG Tool] Clicked item set: {safe_clicked.strip()[:60]}")

    # Wait for the item set detail page to load.
    # Use JS-based checks (not body.text) because body.text is empty during React SPA re-render
    # in headless Chrome. JS document.querySelector always sees the live DOM.
    review_queue_page.wait_utils.until_condition(
        lambda d: d.execute_script(
            """
            const url = window.location.href;
            if (url !== arguments[0]) return true;  // URL changed
            // IS item-set detail: table with IS*-i* links
            const iLinks = document.querySelectorAll('table a[href*="-i"], table a');
            for (const a of iLinks) {
                const t = (a.innerText || a.textContent || '').trim();
                if (/-i\\d+/.test(t)) return true;
            }
            // Item detail: IRS panel
            return !!document.querySelector(
                '[class*="irs"], [class*="response-sheet"], [class*="item-response"]'
            ) || document.body.innerText.includes('Item Response Sheet')
              || document.body.innerText.includes('Mark Yes');
            """,
            queue_list_url,
        ),
        timeout=40,
    )
    # Let the SPA finish rendering (critical in headless mode)
    sleep(3)

    # Second wait: poll until the items table actually renders -i links in the DOM.
    # The first wait only confirmed the URL changed; the React component may still be loading.
    try:
        review_queue_page.wait_utils.until_condition(
            lambda d: d.execute_script(
                """
                const links = Array.from(document.querySelectorAll('a'));
                return links.some(a => /-i\\d+/.test((a.innerText || a.textContent || '').trim()))
                    || document.body.innerText.includes('Item Response Sheet')
                    || document.body.innerText.includes('Mark Yes');
                """
            ),
            timeout=30,
        )
    except TimeoutException:
        pass  # If table never shows -i links, proceed and let the JS click attempt return ''

    # Debug: log what's on the page now
    debug_info = driver.execute_script(
        """
        const iLinks = Array.from(document.querySelectorAll('a')).filter(a =>
            /-i\\d+/.test((a.innerText || a.textContent || '').trim())
        ).map(a => (a.innerText || a.textContent || '').trim());
        return {
            url: window.location.href,
            iLinks: iLinks.slice(0, 5),
            bodyLen: document.body.innerText.length,
            bodySnippet: document.body.innerText.slice(0, 200),
        };
        """
    )
    print(f"[RWG Tool] Item-set page debug: url={debug_info.get('url','?')[:80]}")
    print(f"[RWG Tool]   body len={debug_info.get('bodyLen', 0)}, item links found: {debug_info.get('iLinks', [])}")
    _body_snip = str(debug_info.get('bodySnippet', '')).encode('ascii', errors='replace').decode('ascii')
    print(f"[RWG Tool]   body snippet: {_body_snip[:200]}")

    # Take debug screenshot at item-set page
    _ss_dir = PROJECT_ROOT / "screenshots"
    _ss_dir.mkdir(exist_ok=True)
    try:
        driver.save_screenshot(
            str(_ss_dir / f"rwg_itemset_page_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.png")
        )
    except Exception as exc:
        print(f"[RWG Tool] Warning: debug screenshot failed: {exc}")

    # If already on an individual item detail page, we're done
    if review_queue_page.is_review_item_ready(driver):
        print("[RWG Tool] Item already ready on arrival.")
        return

    item_set_id = extract_item_set_id(review_queue_page)
    if not item_set_id:
        raise TimeoutException("Could not determine the current RWG item-set ID.")

    pending_item_id = review_queue_page.open_next_pending_item_from_item_set(
        item_set_id
    )
    if not pending_item_id:
        raise TimeoutException(
            f"No Pending/Under Review items remain in {item_set_id}."
        )
    print(f"[RWG Tool] Opened pending item from list: {pending_item_id}")


def approve_current_item(review_queue_page):
    try:
        review_queue_page.approve_open_item()
        return True
    except TimeoutException:
        page_text = review_queue_page.driver.find_element(By.TAG_NAME, "body").text
        if "Review Completed" in page_text or "Approved" in page_text:
            return True
        raise
    except InvalidSessionIdException:
        return False


def extract_item_set_id(review_queue_page):
    current_url = review_queue_page.driver.current_url
    match = re.search(r"\bIS\d+(?:-[A-Za-z0-9]+)*\b", current_url, re.IGNORECASE)
    if match:
        return match.group(0)
    # Use JS innerText (works even when Selenium body.text returns empty in headless)
    page_text = review_queue_page.driver.execute_script(
        "return document.body.innerText || document.body.textContent || '';"
    )
    ids = re.findall(r"\bIS\d+(?:-[A-Za-z0-9]+)*\b", page_text, re.IGNORECASE)
    if ids:
        return ids[0]
    # Fallback to numerical ID in the URL
    match = re.search(r"review-queue/(\d+)", current_url)
    return match.group(1) if match else None


def select_next_pending_item(review_queue_page, item_set_id, processed_item_ids):
    """Return to the item-set list and open the first pending table row."""
    print("  [nav] Returning to the item-set list...")
    pending_item_id = review_queue_page.open_next_pending_item_from_item_set(
        item_set_id,
        excluded_item_ids=processed_item_ids,
    )
    if not pending_item_id:
        print("  [nav] No more pending items found.")
        return False

    print(f"  [nav] Opened pending item from list: {pending_item_id}")
    sleep(1.5)
    return True


# Safety cap: prevents runaway while-True loops if approval logic stalls.
_MAX_ITEMS_PER_SET = 50


def approve_all_items_in_current_item_set(review_queue_page):
    """Mark all IRS criteria Y for every pending item in the current item-set,
    then wait until the Submit Review button becomes enabled.

    When the application auto-opens the next item, continue in place. Otherwise,
    return to the item-set list and open the next unprocessed item. Uses JS-based
    checks throughout to avoid the empty body.text issue in headless Chrome.
    """
    approved_count = 0

    # Capture the item-set ID once so every navigation call can anchor to it.
    item_set_id = getattr(review_queue_page, "current_item_set_id", None)
    if not item_set_id:
        item_set_id = extract_item_set_id(review_queue_page)
    if not item_set_id:
        print("  [loop] Warning: could not determine item-set ID; list navigation may fail.")
    print(f"  [loop] Item-set ID: {item_set_id}")
    processed_item_ids = set()

    while approved_count < _MAX_ITEMS_PER_SET:
        # Wait for the item detail page to be fully rendered before marking.
        # Use JS-based check (body.text can be empty in headless).
        review_queue_page.wait_utils.until_condition(
            lambda d: d.execute_script(
                """
                return document.body.innerText.includes('Item Response Sheet')
                    || document.body.innerText.includes('Mark Yes')
                    || document.body.innerText.includes('Evaluation Criteria');
                """
            ),
            timeout=30,
        )
        sleep(1)  # Let the IRS panel finish rendering

        current_item_id = getattr(review_queue_page, "current_item_id", None)
        if review_queue_page.is_open_item_approved(
            review_queue_page.driver,
            review_queue_page.driver.current_url,
        ):
            if current_item_id:
                processed_item_ids.add(current_item_id)
            print(f"  Already approved; skipping: {current_item_id}")
            current_item_ids = set(
                getattr(review_queue_page, "current_item_ids", ())
            )
            if current_item_ids and current_item_ids.issubset(processed_item_ids):
                print("  All items in the set are approved; keeping the final item open.")
                break
            if not select_next_pending_item(
                review_queue_page,
                item_set_id,
                processed_item_ids,
            ):
                break
            continue

        item_being_approved = current_item_id
        review_queue_page.mark_all_criteria_yes()
        review_queue_page.approve_open_item()
        approved_count += 1
        if item_being_approved:
            processed_item_ids.add(item_being_approved)
        print(
            f"  Approved item #{approved_count}: "
            f"{item_being_approved or 'unknown item ID'}"
        )

        current_item_ids = set(
            getattr(review_queue_page, "current_item_ids", ())
        )
        if current_item_ids and current_item_ids.issubset(processed_item_ids):
            print("  All items in the set were approved; keeping the final item open.")
            break

        auto_opened_item_id = review_queue_page.sync_current_item_from_url()
        if auto_opened_item_id and auto_opened_item_id != item_being_approved:
            print(f"  [nav] Application opened next item: {auto_opened_item_id}")
            continue

        if not select_next_pending_item(
            review_queue_page,
            item_set_id,
            processed_item_ids,
        ):
            # No more items were clickable — check if Submit Review is now available
            print("  No clickable pending item found — checking Submit Review button...")
            break

    if approved_count >= _MAX_ITEMS_PER_SET:
        print(f"  [loop] Safety cap reached ({_MAX_ITEMS_PER_SET} items). Exiting approval loop.")

    print("Waiting for Submit Review button to become active...")
    # Use JS fallback if is_submit_review_enabled uses body.text internally
    review_queue_page.wait_utils.until_condition(
        lambda d: review_queue_page.is_submit_review_enabled() or d.execute_script(
            """
            const btns = Array.from(document.querySelectorAll('button'));
            return btns.some(b =>
                /Submit.*Review/i.test(b.innerText) && !b.disabled
                && b.getAttribute('aria-disabled') !== 'true'
            );
            """
        ),
        timeout=90,
    )

    return approved_count


def submit_rwg_review_or_accept_queue_approved(review_queue_page):
    try:
        review_queue_page.submit_rwg_review()
        return
    except TimeoutException:
        page_text = review_queue_page.driver.execute_script(
            "return document.body.innerText || document.body.textContent || '';"
        )
        completion_markers = (
            "Review Completed",
            "Review submitted",
            "PENDING_SR_RWG",
        )
        if any(marker in page_text for marker in completion_markers) or re.search(
            r"\b0\s+items\b",
            page_text,
            re.IGNORECASE,
        ):
            return
        raise


def approve_first_pending_rwg_set(username=None, password=None, headless=False, pause_seconds=5):
    # Resolve default arguments lazily at runtime rather than import time.
    if not username:
        username = ReadConfig.get_role_usernames("rwg")[0]
    if not password:
        password = ReadConfig.get_all_users_password()

    print(f"\n[RWG Tool] Launching Chrome (headless={headless})...")
    driver, profile_dir = build_driver(headless=headless)
    print(f"[RWG Tool] Chrome launched successfully.")
    try:
        base_url = ReadConfig.get_base_url()
        print(f"[RWG Tool] Navigating to: {base_url}")
        driver.get(base_url)

        print(f"[RWG Tool] Logging in as: {username}")
        LoginPage(driver).login_to_application(username, password)
        print(f"[RWG Tool] Login complete. Current URL: {driver.current_url}")

        review_queue_page = RWGReviewQueuePage(driver)
        print("[RWG Tool] Opening RWG review queue...")
        try:
            open_first_pending_item(review_queue_page)
        except TimeoutException as error:
            no_pending_markers = (
                "No Pending Review item sets found",
                "No Pending/Under Review items remain",
                "Queue may be empty",
            )
            if not any(marker in str(error) for marker in no_pending_markers):
                raise
            print("[RWG Tool] No pending RWG items were found in the queue. Please verify there are pending items for this RWG role.")
            print(f"[RWG Tool] Reason: {error}")
            # Take screenshot so we can see the queue state
            screenshot_dir = PROJECT_ROOT / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            screenshot_path = screenshot_dir / (
                "rwg_queue_empty_"
                f"{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.png"
            )
            try:
                driver.save_screenshot(str(screenshot_path))
                print(f"[RWG Tool] Queue screenshot saved: {screenshot_path}")
                body_text = driver.find_element(By.TAG_NAME, "body").text
                print("[RWG Tool] Visible page text (first 1000 chars):")
                enc = sys.stdout.encoding or "utf-8"
                print(body_text[:1000].encode(enc, errors="replace").decode(enc))
            except Exception as exc:
                print(f"[RWG Tool] Warning: screenshot/page-text capture failed: {exc}")
            if pause_seconds > 0:
                print(f"[RWG Tool] Keeping browser open for {pause_seconds}s so you can observe...")
                sleep(pause_seconds)
            return

        approved_count = approve_all_items_in_current_item_set(review_queue_page)
        submit_rwg_review_or_accept_queue_approved(review_queue_page)

        print(f"[RWG Tool] SUCCESS: Approved {approved_count} RWG item(s) and submitted RWG review.")

        # Take success screenshot
        screenshot_dir = PROJECT_ROOT / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        screenshot_path = screenshot_dir / (
            "rwg_approve_success_"
            f"{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.png"
        )
        try:
            driver.save_screenshot(str(screenshot_path))
            print(f"[RWG Tool] Success screenshot: {screenshot_path}")
        except Exception as exc:
            print(f"[RWG Tool] Warning: success screenshot failed: {exc}")

        if pause_seconds > 0:
            print(f"[RWG Tool] Keeping browser open for {pause_seconds}s so you can observe...")
            sleep(pause_seconds)
    except Exception:
        screenshot_dir = PROJECT_ROOT / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        screenshot_path = screenshot_dir / (
            "rwg_approve_first_pending_item_failed_"
            f"{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.png"
        )
        try:
            driver.save_screenshot(str(screenshot_path))
            print(f"[RWG Tool] Failure screenshot: {screenshot_path}")
            body_text = driver.find_element(By.TAG_NAME, "body").text
            print("[RWG Tool] Visible page text excerpt:")
            enc = sys.stdout.encoding or "utf-8"
            print(body_text[:2000].encode(enc, errors="replace").decode(enc))
        except Exception as exc:
            print(f"[RWG Tool] Warning: failure screenshot/page-text capture failed: {exc}")
        raise
    finally:
        print("[RWG Tool] Closing browser...")
        driver.quit()
        # shutil is a top-level import — no inline import needed.
        shutil.rmtree(profile_dir, ignore_errors=True)
        print("[RWG Tool] Done.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Login as RWG, approve the first pending item by marking IRS criteria Y, then submit RWG review."
    )
    parser.add_argument(
        "--username",
        default=None,
        help="RWG username. Defaults to first CBSE_RWG_USERNAMES entry.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="RWG password. Defaults to CBSE_ALL_USERS_PASSWORD.",
    )
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode.")
    parser.add_argument(
        "--pause",
        type=int,
        default=5,
        help="Seconds to keep browser open after completion so you can observe it (default: 5).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    approve_first_pending_rwg_set(
        username=args.username,
        password=args.password,
        headless=args.headless,
        pause_seconds=args.pause,
    )
