"""Verify the @test.com fixture accounts created by tools/create_bulk_users.py.

Two independent checks, because a create-user form that closed is not proof of
an account that works:

  1. Read the accounts back out of Admin > User Management (role, User Code,
     Active status).
  2. Sign in as one account per role, so the provisioned password is proven
     against the real login rather than assumed.

    python tools/verify_fixture_users.py --headless
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pages.admin.user_management_page import UserManagementPage
from pages.common.login_page import LoginPage
from utilities.read_config import ReadConfig

# (email prefix, display first name) - mirrors ROLES in create_bulk_users.py.
ROLES = {
    "sme": ("sme", "SME"),
    "teacher": ("teacher", "Teacher"),
    "rwg": ("rwg", "RWG"),
    "sr_rwg": ("sr_rwg", "SrRWG"),
    "pit": ("pit", "PIT"),
}
EMAIL_DOMAIN = "test.com"


def build_driver(headless=False):
    profile_dir = Path(tempfile.mkdtemp(prefix="cbse_verify_users_chrome_"))
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


def check_grid(page, count, start):
    """Read every provisioned account back out of the grid."""
    rows = []
    for key, (prefix, display_name) in ROLES.items():
        for index in range(start, start + count):
            email = f"{prefix}{index}@{EMAIL_DOMAIN}"
            full_name = f"{display_name} Auto{index}"
            try:
                page.search_user(full_name)
                if not page.is_user_listed(full_name):
                    rows.append((email, full_name, "", "", "NOT LISTED"))
                    continue
                listed = {
                    user["name"]: user
                    for user in page.get_listed_users()
                    if user.get("name") == full_name
                }
                user = listed.get(full_name, {})
                rows.append(
                    (
                        email,
                        full_name,
                        page.get_user_code(full_name),
                        user.get("role", "?"),
                        page.get_user_status(full_name) or "?",
                    )
                )
            except WebDriverException as error:
                rows.append((email, full_name, "", "", f"ERROR {type(error).__name__}"))
    return rows


def check_logins(driver, base_url, index):
    """Sign in as one account per role and confirm the app shell renders."""
    login_page = LoginPage(driver)
    results = []
    for key, (prefix, _) in ROLES.items():
        email = f"{prefix}{index}@{EMAIL_DOMAIN}"
        password = ReadConfig.get_password_for_username(email)
        try:
            driver.get(base_url)
            login_page.login_to_application(email, password)
            signed_in = not login_page.is_login_form_displayed(timeout=8)
            detail = "" if signed_in else (login_page.get_login_error_text() or "login form still shown")
        except Exception as error:
            signed_in = False
            detail = f"{type(error).__name__}: {str(error)[:120]}"
        results.append((email, signed_in, detail))
        try:
            login_page.logout(base_url)
        except Exception:
            driver.delete_all_cookies()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--login-index", type=int, default=1, help="which account per role to sign in as")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    base_url = ReadConfig.get_base_url()
    admin = ReadConfig.get_admin_username()
    driver, profile_dir = build_driver(args.headless)

    try:
        driver.get(base_url)
        LoginPage(driver).login_to_application(admin, ReadConfig.get_password_for_username(admin))
        page = UserManagementPage(driver)
        page.open(base_url)

        print(f"== Grid read-back (as {admin}) ==")
        rows = check_grid(page, args.count, args.start)
        for email, full_name, code, role, status in rows:
            print(f"  {email:24} {code:12} {full_name:16} {role:14} {status}")
        listed = [row for row in rows if row[4].casefold() == "active"]
        print(f"  -> {len(listed)}/{len(rows)} listed and Active")

        try:
            LoginPage(driver).logout(base_url)
        except Exception:
            driver.delete_all_cookies()

        print(f"\n== Login check (account #{args.login_index} of each role) ==")
        logins = check_logins(driver, base_url, args.login_index)
        for email, ok, detail in logins:
            print(f"  {email:24} {'OK' if ok else 'FAILED'}{('  ' + detail) if detail else ''}")
        working = [row for row in logins if row[1]]
        print(f"  -> {len(working)}/{len(logins)} roles can sign in")

    finally:
        try:
            driver.quit()
        except WebDriverException:
            pass
        shutil.rmtree(profile_dir, ignore_errors=True)

    return 0 if len(listed) == len(rows) and len(working) == len(logins) else 1


if __name__ == "__main__":
    sys.exit(main())
