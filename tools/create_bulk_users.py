"""Bulk-provision role fixture accounts through Admin > User Management.

Drives the same UserManagementPage.create_user() the M2 suites use, so the
accounts are created exactly the way a test would create them - no direct API
or database writes.

    python tools/create_bulk_users.py                 # 5 each of every role
    python tools/create_bulk_users.py --roles sme pit --count 2 --headless

The Role select's option labels are read from the live form rather than
hardcoded: only "SME role" is written down anywhere in this repo, and a wrong
guess for the others would silently create every account under one role.
"""

import argparse
import random
import re
import shutil
import sys
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pages.admin.user_management_page import UserManagementPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig

DEFAULT_PASSWORD = "Test@12345"
DEFAULT_GRADE = "Grade 2"
DEFAULT_SUBJECT = "Mathematics"
EMAIL_DOMAIN = "test.com"

# key -> (email prefix, display first name, normalised role token to match in
# the live Role dropdown). "rwg" and "srwg" are kept distinct deliberately:
# a substring match would file every SRWG account under RWG.
ROLES = {
    "sme": ("sme", "SME", "sme"),
    "teacher": ("teacher", "Teacher", "teacher"),
    "rwg": ("rwg", "RWG", "rwg"),
    "sr_rwg": ("sr_rwg", "SrRWG", "srwg"),
    "pit": ("pit", "PIT", "pit"),
}


def build_driver(headless=False):
    profile_dir = Path(tempfile.mkdtemp(prefix="cbse_bulk_users_chrome_"))
    try:
        options = ChromeOptions()
        for flag in (
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            "--window-size=1920,1080",
        ):
            options.add_argument(flag)
        options.add_argument(f"--user-data-dir={profile_dir}")
        if headless:
            options.add_argument("--headless=new")
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options,
        )
        driver.implicitly_wait(5)
        return driver, profile_dir
    except Exception:
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise


def normalise(label):
    """Turn a dropdown label into its bare role token, e.g. 'SRWG role' -> 'srwg'."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\brole\b", "", label.casefold()))


def read_role_options(page):
    """Open the create-user form, harvest the Role select's option labels, and
    close the form again."""
    page.open_create_user_form()
    page.click_element(page.FORM_ROLE_TRIGGER)
    page.wait_utils.until_visible((By.XPATH, "//*[@role='option']"), timeout=15)
    labels = [
        element.text.strip()
        for element in page.driver.find_elements(By.XPATH, "//*[@role='option']")
        if element.text.strip()
    ]
    page.dismiss_open_overlays()
    close_create_form(page)
    return labels


def resolve_role_labels(available, wanted_keys):
    """Map each role key to the live dropdown label carrying its token."""
    by_token = {}
    for label in available:
        by_token.setdefault(normalise(label), label)

    resolved, unresolved = {}, []
    for key in wanted_keys:
        token = ROLES[key][2]
        label = by_token.get(token)
        if label is None:
            # Fall back to a token that starts with ours, but never one that
            # merely contains it (guards rwg against srwg).
            matches = [
                value for candidate, value in by_token.items() if candidate.startswith(token)
            ]
            label = matches[0] if len(matches) == 1 else None
        if label is None:
            unresolved.append(key)
        else:
            resolved[key] = label
    return resolved, unresolved


def close_create_form(page):
    """Leave the form closed whatever state it is in, so the next iteration can
    click Create User again."""
    for _ in range(3):
        if not page.is_element_visible_quick(page.FORM_FIRST_NAME, timeout=2):
            return True
        page.dismiss_open_overlays()
        try:
            page.click_with_js_fallback(page.FORM_CANCEL_BTN)
        except WebDriverException:
            try:
                page.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except WebDriverException:
                pass
    return not page.is_element_visible_quick(page.FORM_FIRST_NAME, timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roles", nargs="+", choices=sorted(ROLES), default=sorted(ROLES))
    parser.add_argument("--count", type=int, default=5, help="accounts per role")
    parser.add_argument("--start", type=int, default=1, help="first index in the email suffix")
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--grade", default=DEFAULT_GRADE)
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    base_url = ReadConfig.get_base_url()
    admin = ReadConfig.get_admin_username()
    driver, profile_dir = build_driver(args.headless)
    created, failed = [], []

    try:
        driver.get(base_url)
        LoginPage(driver).login_to_application(
            admin, ReadConfig.get_password_for_username(admin)
        )
        page = UserManagementPage(driver)
        page.open(base_url)
        print(f"Signed in as {admin} at {base_url}")

        available = read_role_options(page)
        print(f"Role options on this build: {available}")
        role_labels, unresolved = resolve_role_labels(available, args.roles)
        if unresolved:
            print(f"WARNING: no Role option matched {unresolved}; those are skipped.")

        # Distinct mobile prefix per run so a re-run does not collide with the
        # numbers an earlier run already registered.
        mobile_base = random.randint(700, 899)

        for key in args.roles:
            label = role_labels.get(key)
            if label is None:
                continue
            prefix, display_name, _ = ROLES[key]
            for index in range(args.start, args.start + args.count):
                email = f"{prefix}{index}@{EMAIL_DOMAIN}"
                last_name = f"Auto{index}"
                full_name = f"{display_name} {last_name}"
                mobile = f"{mobile_base}{random.randint(0, 9999999):07d}"
                try:
                    page.create_user(
                        first_name=display_name,
                        last_name=last_name,
                        email=email,
                        mobile=mobile,
                        password=args.password,
                        role=label,
                        grades=(args.grade,),
                        subjects=(args.subject,),
                    )
                except Exception as error:
                    reason = re.sub(r"\s+", " ", str(error))[:200]
                    failed.append((email, label, reason))
                    print(f"  FAILED  {email:24} {label:12} {reason}")
                    close_create_form(page)
                    continue
                created.append((email, full_name, label))
                print(f"  created {email:24} {label:12} as {full_name} / {mobile}")

    finally:
        try:
            driver.quit()
        except WebDriverException:
            pass
        shutil.rmtree(profile_dir, ignore_errors=True)

    print(f"\nCreated {len(created)} account(s); {len(failed)} failed.")
    for email, _, reason in failed:
        print(f"  {email}: {reason}")
    return 0 if created and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
