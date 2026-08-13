import logging
import requests
import pytest
from time import monotonic

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from utilities.read_config import ReadConfig


@pytest.mark.rtm
@pytest.mark.usefixtures("setup")
class TestSMECrossRBACAPI:
    """TC-NEG-M1-08 — SME Cannot View Another SME's Item Sets (Cross-SME RBAC)"""

    logger = logging.getLogger(__name__)

    def step(self, n, message):
        print(f"\n[STEP {n}] {message}", flush=True)
        self.logger.info(f"[STEP {n}] {message}")

    def get_auth_session(self, username, password):
        """Helper to log in via Selenium and transfer credentials to a requests Session."""
        self.driver.get(ReadConfig.get_base_url())
        LoginPage(self.driver).login_to_application(username, password)
        page = UploadItemFilePage(self.driver)
        page.close_popup_if_open()
        
        session = requests.Session()
        # Transfer cookies
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])
            
        # Transfer authorization headers from localStorage / sessionStorage
        token = self.driver.execute_script(
            "return localStorage.getItem('token') || sessionStorage.getItem('token') "
            "|| localStorage.getItem('jwt') || sessionStorage.getItem('jwt') "
            "|| localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');"
        )
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        return session, headers

    def discover_api_url(self, session, base_url, path, headers):
        """Autodetect API path structure by trying prefixed /api path first."""
        url_with_api = base_url.rstrip("/") + "/api" + path
        url_direct = base_url.rstrip("/") + path
        
        try:
            response = session.get(url_with_api, headers=headers, timeout=10)
            if response.status_code != 404:
                return url_with_api, response
        except Exception:
            pass
            
        try:
            response = session.get(url_direct, headers=headers, timeout=10)
            return url_direct, response
        except Exception as error:
            self.logger.warning(f"Connection failed for direct endpoint {url_direct}: {error}")
            return url_direct, None

    def test_tc_neg_m1_08_cross_sme_rbac_returns_403_forbidden(self):
        """TC-NEG-M1-08: Verify that cross-SME item set access returns 403 Forbidden at API level.
        
        Steps:
        1. Login as SME1 via Selenium, extract auth cookies and bearer token.
        2. Query GET /item-sets to get list of item sets belonging to SME1.
        3. Login as SME2 via Selenium, extract auth cookies and bearer token.
        4. Request GET /item-sets/{id_from_sme1} as SME2 -> assert 403 Forbidden.
        5. Request PUT /items/{item_id_from_sme1} as SME2 -> assert 403 Forbidden.
        6. Request DELETE /item-sets/{id_from_sme1} as SME2 -> assert 403 Forbidden.
        """
        base_url = ReadConfig.get_base_url()
        sme_usernames = ReadConfig.get_role_usernames("sme")
        
        if len(sme_usernames) < 2:
            print("[SKIP] At least 2 distinct SME users are required for cross-SME RBAC tests.", flush=True)
            pytest.skip("Insufficient SME users in configuration.")
            
        sme1_user = sme_usernames[0]
        sme2_user = sme_usernames[1]
        
        # Step 1: Login as SME1
        self.step(1, f"Logging in as SME1 ({sme1_user}) and extracting auth session")
        sme1_session, sme1_headers = self.get_auth_session(sme1_user, ReadConfig.get_password_for_username(sme1_user))
        
        # Step 2: Get item sets of SME1
        self.step(2, "Querying SME1's item sets via GET /item-sets")
        api_path = "/item-sets"
        endpoint_url, response = self.discover_api_url(sme1_session, base_url, api_path, sme1_headers)
        
        item_set_id = None
        item_id = None
        
        if response is not None and response.status_code == 200:
            try:
                data = response.json()
                self.logger.info(f"Retrieved SME1 item sets count: {len(data)}")
                if isinstance(data, list) and len(data) > 0:
                    first_set = data[0]
                    if isinstance(first_set, dict):
                        item_set_id = first_set.get("id") or first_set.get("item_set_id")
                        # Try to get an item ID if present in the item set structure
                        items = first_set.get("items")
                        if items and len(items) > 0:
                            if isinstance(items[0], dict):
                                item_id = items[0].get("id") or items[0].get("item_id")
                            else:
                                item_id = items[0]
                elif isinstance(data, dict):
                    item_set_id = data.get("id") or data.get("item_set_id")
            except Exception as parse_error:
                self.logger.warning(f"Could not parse item sets JSON: {parse_error}")

        # Cross-owner RBAC is meaningful only with a real resource owned by SME1.
        if not item_set_id or not item_id:
            pytest.skip(
                "SME1 has no discoverable owned item set/item; fabricated IDs would not "
                "prove cross-SME RBAC enforcement."
            )
            
        print(f"[PASS] SME1 identifiers: Set ID = {item_set_id}, Item ID = {item_id}", flush=True)

        # Step 3: Login as SME2
        self.step(3, f"Logging in as SME2 ({sme2_user}) and extracting auth session")
        # Clear cookies/session first
        UploadItemFilePage(self.driver).reset_browser_session_to_login()
        sme2_session, sme2_headers = self.get_auth_session(sme2_user, ReadConfig.get_password_for_username(sme2_user))

        # Determine target URLs for SME2 requests
        api_root = endpoint_url.rsplit("/item-sets", 1)[0]
        get_set_url = f"{api_root}/item-sets/{item_set_id}"
        put_item_url = f"{api_root}/items/{item_id}"
        delete_set_url = f"{api_root}/item-sets/{item_set_id}"

        # Step 4: Verify GET /item-sets/{id} returns 403 Forbidden
        self.step(4, f"Verifying SME2 GET access to SME1's set {item_set_id} is forbidden")
        print(f"[CHECK] GET {get_set_url} returns 403 Forbidden", flush=True)
        get_response = sme2_session.get(get_set_url, headers=sme2_headers, timeout=10)
        self.logger.info(f"GET Response status: {get_response.status_code}")
        assert get_response.status_code == 403, (
            f"Expected status 403 Forbidden for cross-SME GET, but got {get_response.status_code}"
        )
        print("[PASS] Cross-SME GET returned 403 Forbidden.", flush=True)

        # Step 5: Verify PUT /items/{id} returns 403 Forbidden
        self.step(5, f"Verifying SME2 PUT access to SME1's item {item_id} is forbidden")
        print(f"[CHECK] PUT {put_item_url} returns 403 Forbidden", flush=True)
        dummy_put_body = {"item_content": "Unauthorized update attempt"}
        put_response = sme2_session.put(put_item_url, json=dummy_put_body, headers=sme2_headers, timeout=10)
        self.logger.info(f"PUT Response status: {put_response.status_code}")
        assert put_response.status_code == 403, (
            f"Expected status 403 Forbidden for cross-SME PUT, but got {put_response.status_code}"
        )
        print("[PASS] Cross-SME PUT returned 403 Forbidden.", flush=True)

        # Step 6: Verify DELETE /item-sets/{id} returns 403 Forbidden
        self.step(6, f"Verifying SME2 DELETE access to SME1's set {item_set_id} is forbidden")
        print(f"[CHECK] DELETE {delete_set_url} returns 403 Forbidden", flush=True)
        delete_response = sme2_session.delete(delete_set_url, headers=sme2_headers, timeout=10)
        self.logger.info(f"DELETE Response status: {delete_response.status_code}")
        assert delete_response.status_code == 403, (
            f"Expected status 403 Forbidden for cross-SME DELETE, but got {delete_response.status_code}"
        )
        print("[PASS] Cross-SME DELETE returned 403 Forbidden.", flush=True)
