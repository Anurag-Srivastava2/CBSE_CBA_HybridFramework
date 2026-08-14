"""Tell an environment outage apart from a product or test defect.

When the network drops or the API stops answering, every remaining test fails
within seconds and the report cannot distinguish those failures from real ones.
pytest-rerunfailures makes it worse: it spends its retries immediately, against
a still-broken environment, so a blip costs the whole run.

Both happened in one M1 group-2 run: a dropped network turned 9 tests red, and
an API outage later turned 8 red while the SPA host kept serving HTTP 200 - the
browser sat on the app's global "Loading..." screen and never reached a login
form.

This module names the signatures that mean "infrastructure, not the product",
and can hold the run until the environment answers again.
"""

import socket
import urllib.error
import urllib.request
from time import monotonic, sleep

from utilities.logger import LogGenerator
from utilities.read_config import ReadConfig

logger = LogGenerator.loggen()

# Matched against the lowercased failure text. Every entry means "the
# environment or the machine's link to it broke", never "the product is wrong".
INFRA_ERROR_MARKERS = (
    # Chrome could not reach the host at all.
    "err_internet_disconnected",
    "err_name_not_resolved",
    "err_connection_refused",
    "err_connection_reset",
    "err_connection_timed_out",
    "err_connection_closed",
    "err_address_unreachable",
    "err_network_changed",
    "err_empty_response",
    "err_ssl_protocol_error",
    "err_tunnel_connection_failed",
    # The SPA loaded but its bootstrap API never answered, so login never
    # rendered. Raised by LoginPage.wait_for_login_form_or_authenticated_page.
    "remained on its global loading screen",
    # The browser or its driver died underneath the test.
    "chrome not reachable",
    "disconnected: not connected to devtools",
    "invalid session id",
    "session deleted because of page crash",
    "unable to connect to renderer",
)

# A health probe treats any HTTP answer as "serving" - including 401/403, which
# is the API's correct response to an unauthenticated probe and still proves the
# host is up. Only a transport-level failure counts as down.
PROBE_TIMEOUT_SECONDS = 15
DEFAULT_RECOVERY_TIMEOUT_SECONDS = 300
DEFAULT_POLL_SECONDS = 15


def is_infrastructure_failure(failure_text):
    """True when this failure text carries an infrastructure signature."""
    text = str(failure_text or "").casefold()
    return any(marker in text for marker in INFRA_ERROR_MARKERS)


def _host_is_serving(url):
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS):
            return True
    except urllib.error.HTTPError:
        # 401/403/404 all prove the host answered.
        return True
    except (urllib.error.URLError, socket.timeout, OSError):
        return False


def environment_is_serving():
    """True when both the SPA host and the REST API answer.

    Checking the API separately is the point: during the outage this module was
    written for, the SPA host returned HTTP 200 throughout while the API behind
    it was unreachable, which is precisely the state that strands the browser on
    the loading screen.
    """
    urls = [ReadConfig.get_base_url()]
    try:
        urls.append(ReadConfig.get_api_base_url())
    except Exception:
        # API host not configured - fall back to the SPA host alone.
        pass
    return all(_host_is_serving(url) for url in urls)


def wait_for_environment(
    timeout=DEFAULT_RECOVERY_TIMEOUT_SECONDS, poll_seconds=DEFAULT_POLL_SECONDS
):
    """Block until the environment answers again, or until `timeout` elapses.

    Returns True if it recovered. Callers decide what a False means; this
    module never fails a test on its own.
    """
    deadline = monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        if environment_is_serving():
            if attempt > 1:
                logger.info("Environment is answering again after %d probe(s).", attempt)
            return True
        remaining = deadline - monotonic()
        if remaining <= 0:
            logger.warning(
                "Environment still not answering after %ds; continuing anyway.", timeout
            )
            return False
        logger.warning(
            "Environment not answering (probe %d); retrying in %ds (%ds left).",
            attempt,
            poll_seconds,
            int(remaining),
        )
        sleep(min(poll_seconds, remaining))
