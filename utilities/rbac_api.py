"""Delete throwaway RBAC roles, which the portal UI cannot do.

Role Management can create a role but never remove one: the role detail page
offers only Back / Expand All / Cancel / Save Changes, for system and custom
roles alike. The REST API does expose it - `DELETE /admin/rbac/roles/{id}`
with a `{"reason": ...}` body, the call the frontend's role.api chunk wraps as
`deleteRole` - so a test that creates a role has to hand it back through the
API or leave it behind in the shared environment for good.

The token is lifted from the browser session the test already signed in with,
the same way the M1 cross-RBAC API test does it, so this costs no extra login
against an environment that rate-limits them.
"""

import json

import requests

from utilities.logger import LogGenerator
from utilities.read_config import ReadConfig

logger = LogGenerator.loggen()

ROLES_ENDPOINT = "/admin/rbac/roles"


def _auth(driver):
    """Return (session, headers) carrying the signed-in browser's credentials."""
    token = driver.execute_script(
        "return localStorage.getItem('token') || sessionStorage.getItem('token') "
        "|| localStorage.getItem('jwt') || sessionStorage.getItem('jwt') "
        "|| localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');"
    )
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie["name"], cookie["value"])
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return session, headers


def list_roles(driver, include_deleted=False):
    """Every role the RBAC API knows about.

    The grid labels each row `Role-<roleId>`, so `roleId` is the id the page
    object matches a row on.

    Deleted roles are filtered out by default, but note the *grid still renders
    them* - Role-7 and Role-8 on UAT are soft-deleted throwaways sitting in the
    listing looking exactly like seeded roles. That is why nothing may assume
    "the first N rows are the defaults".
    """
    session, headers = _auth(driver)
    response = session.get(
        ReadConfig.get_api_base_url() + ROLES_ENDPOINT,
        headers=headers,
        params={"limit": 200},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    body = payload.get("data") or payload
    items = body.get("items") or payload.get("items") or []
    if include_deleted:
        return items
    return [role for role in items if not role.get("isDeleted")]


def system_role_grid_ids(driver):
    """Grid ids (`Role-N`) of the roles the product protects from deactivation.

    Sourced from `isSystemRole` rather than from a fixed Role-1..Role-8 range,
    because which ids hold the seeded roles differs per environment: on QA they
    are 1-8, on UAT they are 1-6 plus 12-13 (the two Helpdesk roles), with 7 and
    8 taken by deleted junk. A hardcoded range reports that junk as a seeded
    role that has been switched off.
    """
    return [
        f"Role-{role['roleId']}"
        for role in list_roles(driver)
        if role.get("isSystemRole")
    ]


def current_user_display_name(driver):
    """The signed-in account's profile name, as the portal renders it.

    Queues show a display name, never the login. On UAT the admin's profile
    carries junk ("sdvsv hjjhhj"), which bears no relation to its address, so
    attribution can only be checked against the name the account actually has.
    Returns "" when the profile has no name set.
    """
    session, headers = _auth(driver)
    response = session.get(
        ReadConfig.get_api_base_url() + "/auth/me", headers=headers, timeout=30
    )
    response.raise_for_status()
    body = response.json().get("data") or {}
    profile = body.get("userProfile") or {}
    name = f"{profile.get('firstName') or ''} {profile.get('lastName') or ''}"
    return " ".join(name.split())


def _roles_matching(session, headers, name_prefix):
    response = session.get(
        ReadConfig.get_api_base_url() + ROLES_ENDPOINT,
        headers=headers,
        params={"search": name_prefix},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    body = payload.get("data") or payload
    items = body.get("items") or payload.get("items") or []
    return [
        role
        for role in items
        if str(role.get("roleName", "")).startswith(name_prefix)
        and not role.get("isDeleted")
    ]


def delete_roles_with_prefix(driver, name_prefix, reason):
    """Delete every non-deleted role whose name starts with name_prefix.

    Returns the names it removed. Used both to clean up after a test and to
    sweep residue a previous run left behind when its cleanup could not run,
    so leftovers never accumulate in the shared environment.
    """
    session, headers = _auth(driver)
    removed = []
    for role in _roles_matching(session, headers, name_prefix):
        response = session.delete(
            f"{ReadConfig.get_api_base_url()}{ROLES_ENDPOINT}/{role['roleId']}",
            headers=headers,
            data=json.dumps({"reason": reason}),
            timeout=30,
        )
        if response.ok:
            removed.append(role.get("roleName"))
            logger.info(f"Deleted throwaway role {role.get('roleName')!r}.")
        else:
            logger.warning(
                f"Could not delete throwaway role {role.get('roleName')!r}: "
                f"HTTP {response.status_code} {response.text[:200]}"
            )
    return removed
