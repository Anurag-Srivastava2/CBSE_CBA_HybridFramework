import json

from selenium.common.exceptions import WebDriverException

from utilities.screenshot_utils import ScreenshotUtils

# The recorder belonging to the test currently executing. ElementChecks reaches
# for this so a page survey contributes its screenshot without every test having
# to thread the recorder down through its helpers. One process runs one test at a
# time - xdist workers are separate processes - so a single slot is enough.
_CURRENT = {"recorder": None}


def set_current_recorder(recorder):
    _CURRENT["recorder"] = recorder


def current_recorder():
    return _CURRENT["recorder"]


class PageEvidence:
    """Capture one screenshot per page a test visits, numbered in visit order.

    A single end-of-test screenshot shows where a test stopped, not the route it
    took. These captures land in the report's screenshot section in the order
    they were taken, so a reader walks the same pages the test did:

        01 - Login
        02 - Admin Dashboard
        03 - Audit Trail
        PASS - 12/12 checks passed

    The recorder keeps no list of its own. Every capture re-reads the published
    property, appends, and writes the whole list back, so it interoperates with
    tests that record evidence through their own helpers and so evidence taken
    before a crash still reaches the report.

    Waiting for the page to paint is `ScreenshotUtils.capture`'s job, so every
    screenshot in the framework gets it, not only the ones filed through here.
    """

    PROPERTY = "evidence_screenshots"

    def __init__(self, node, driver_getter):
        self.node = node
        self.driver_getter = driver_getter

    def capture(self, page_name, driver=None, settle=True):
        """Screenshot `page_name` and publish it. Never raises, returns the path.

        Waits for the page to finish painting first. Pass `settle=False` for a
        deliberately transient state - a toast, a spinner you are documenting -
        where waiting would photograph the page after the thing had gone.
        """
        driver = driver if driver is not None else self.driver_getter()
        # Non-UI tests and the unreachable-environment stub have no camera.
        if not hasattr(driver, "save_screenshot"):
            return None
        recorded = self.recorded()
        label = f"{len(recorded) + 1:02d} - {page_name}"
        try:
            screenshot_path = ScreenshotUtils.capture(driver, label, settle=settle)
        except (WebDriverException, OSError):
            # A dead session or unwritable path costs one screenshot, not the test.
            return None
        recorded.append({"name": label, "path": screenshot_path})
        self._publish(recorded)
        return screenshot_path

    def recorded(self):
        for property_name, property_value in self.node.user_properties:
            if property_name == self.PROPERTY:
                try:
                    return json.loads(property_value)
                except (TypeError, ValueError):
                    return []
        return []

    def reset(self):
        """Drop evidence carried over from an earlier attempt at this test."""
        self.node.user_properties[:] = [
            entry for entry in self.node.user_properties if entry[0] != self.PROPERTY
        ]

    def _publish(self, recorded):
        self.reset()
        self.node.user_properties.append((self.PROPERTY, json.dumps(recorded)))
