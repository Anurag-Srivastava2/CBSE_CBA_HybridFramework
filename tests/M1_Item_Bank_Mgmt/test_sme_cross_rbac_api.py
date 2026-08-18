import logging
import requests
import pytest
from time import monotonic

from pages.common.login_page import LoginPage
from pages.sme.upload_item_file_page import UploadItemFilePage
from tests.M1_Item_Bank_Mgmt.m1_surveys import survey_chrome
from utilities.element_checks import ElementChecks
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

    def get_owned_item_set_and_item(self, session, headers):
        """Return (item_set_id, item_id) for a set this session's SME owns.

        Queries the REST API host, not CBSE_BASE_URL: that serves only the SPA,
        so item-set paths under it answer with index.html and a 404 -- which is
        why this test skipped for want of a resource on every run. The listing
        is an envelope ({"data": {"itemSets": [...]}}) rather than a bare list,
        and carries no items, so the set's items need a second call.
        """
        api_base = ReadConfig.get_api_base_url()
        listing = session.get(
            f"{api_base}/item-sets/mine",
            params={"page_index": 1, "perpage_records": 10},
            headers=headers,
            timeout=15,
        )
        if listing.status_code != 200:
            self.logger.warning(
                f"GET /item-sets/mine returned {listing.status_code}: {listing.text[:200]}"
            )
            return None, None

        item_sets = (listing.json().get("data") or {}).get("itemSets") or []
        # Only a set that actually holds items can back the item-level check.
        owned = next((entry for entry in item_sets if entry.get("total_items")), None)
        if not owned:
            return None, None
        item_set_id = owned.get("item_set_id")

        detail = session.get(
            f"{api_base}/item-sets/{item_set_id}/items", headers=headers, timeout=15
        )
        if detail.status_code != 200:
            self.logger.warning(
                f"GET /item-sets/{item_set_id}/items returned {detail.status_code}"
            )
            return item_set_id, None
        items = (detail.json().get("data") or {}).get("items") or []
        return item_set_id, (items[0].get("item_id") if items else None)

    def test_tc_neg_m1_08_cross_sme_rbac_returns_403_forbidden(self, record_property):
        """TC-NEG-M1-08: Verify that cross-SME item set access returns 403 Forbidden at API level.
        
        Steps:
        1. Login as SME1 via Selenium, extract auth cookies and bearer token.
        2. Resolve an item set SME1 owns, and one item inside it, from the API.
        3. Login as SME2 via Selenium, extract auth cookies and bearer token.
        4. Request GET /item-sets/{id_from_sme1}/items as SME2 -> assert 403.
        5. Re-request the same URL as SME1 -> assert 200, so the 403 above is
           attributable to ownership rather than to a bad URL or dead token.
        """
        sme_usernames = ReadConfig.get_role_usernames("sme")
        
        if len(sme_usernames) < 2:
            print("[SKIP] At least 2 distinct SME users are required for cross-SME RBAC tests.", flush=True)
            pytest.skip("Insufficient SME users in configuration.")
            
        sme1_user = sme_usernames[0]
        sme2_user = sme_usernames[1]
        
        # Step 1: Login as SME1
        self.step(1, f"Logging in as SME1 ({sme1_user}) and extracting auth session")
        sme1_session, sme1_headers = self.get_auth_session(sme1_user, ReadConfig.get_password_for_username(sme1_user))

        # This test reaches its API assertions through a real browser login,
        # so the landing page it authenticates on is worth recording. The 403
        # contract itself stays a hard assert - it is the whole point of the test.
        landing = UploadItemFilePage(self.driver)
        checks = ElementChecks(
            landing, record_property, page_name="SME Cross-RBAC — Authenticated Landing"
        )
        survey_chrome(checks, landing)
        record_property("result_description", checks.publish())
        
        # Step 2: Resolve a real item set (and item) owned by SME1
        self.step(2, "Resolving an item set owned by SME1 via the REST API")
        item_set_id, item_id = self.get_owned_item_set_and_item(sme1_session, sme1_headers)

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

        # SME2 must not be able to read SME1's set. This targets
        # /item-sets/{id}/items because that endpoint exists. The routes this
        # test used to assert on -- GET /item-sets/{id}, PUT /items/{id} and
        # DELETE /item-sets/{id} -- are not served at all, so they answer 404
        # for owner and non-owner alike and proved nothing about RBAC.
        self.step(4, f"Verifying SME2 cannot read SME1's item set {item_set_id}")
        cross_url = f"{ReadConfig.get_api_base_url()}/item-sets/{item_set_id}/items"
        print(f"[CHECK] GET {cross_url} as SME2 returns 403 Forbidden", flush=True)
        cross_response = sme2_session.get(cross_url, headers=sme2_headers, timeout=15)
        self.logger.info(f"Cross-SME GET status: {cross_response.status_code}")
        assert cross_response.status_code == 403, (
            f"Expected 403 Forbidden when SME2 reads SME1's item set {item_set_id}, "
            f"got {cross_response.status_code}: {cross_response.text[:300]}"
        )
        print("[PASS] Cross-SME GET returned 403 Forbidden.", flush=True)

        # Positive control: a 403 alone would also be produced by a mistyped URL
        # or an expired token, neither of which says anything about ownership.
        self.step(5, "Confirming SME1 still reads its own set (control)")
        owner_response = sme1_session.get(cross_url, headers=sme1_headers, timeout=15)
        self.logger.info(f"Owner GET status: {owner_response.status_code}")
        assert owner_response.status_code == 200, (
            f"Owner SME1 should still read its own item set {item_set_id}, got "
            f"{owner_response.status_code}: {owner_response.text[:300]}"
        )
        print("[PASS] Owner still gets 200 - the 403 is ownership, not a broken URL.", flush=True)
