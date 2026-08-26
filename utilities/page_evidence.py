import json
import re

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
        return self._shoot(lambda index: f"{index:02d} - {page_name}", driver, settle)

    def checkpoint(self, detail, driver=None, settle=True):
        """Record a numbered checkpoint - what the test just established, shot.

        `capture` names a page the test arrived at; this names the thing that
        was proved on it, so the report reads as the test's reasoning rather
        than its route:

            01 - QAR Report
            Checkpoint 02 - Duplicate Check card rendered: score=0.0, colour=fail
            Checkpoint 03 - Duplicate Check scored 0.0% against a 100% clean mark

        Numbering is shared with `capture`, so page visits and checkpoints
        interleave in the order they actually happened. `detail` is collapsed to
        one line because the report renders it as a caption.
        """
        detail = re.sub(r"\s+", " ", str(detail)).strip()
        return self._shoot(
            lambda index: f"Checkpoint {index:02d} - {detail}", driver, settle
        )

    def attach(self, detail, path):
        """Number an already-captured screenshot into the same series.

        Some tests take their own shots for reasons the recorder cannot serve -
        an element-focused crop, a page object's own review screenshot, a file
        that also has to land in an artifacts directory for Allure. Filing them
        here keeps them in one ordered story with the rest instead of a second,
        competing list. Returns the label, or None if there is nothing to file.
        """
        if not path:
            return None
        detail = re.sub(r"\s+", " ", str(detail)).strip()
        recorded = self.recorded()
        label = f"Checkpoint {len(recorded) + 1:02d} - {detail}"
        recorded.append({"name": label, "path": str(path)})
        self._publish(recorded)
        return label

    def _shoot(self, label_for, driver, settle):
        driver = driver if driver is not None else self.driver_getter()
        # Non-UI tests and the unreachable-environment stub have no camera.
        if not hasattr(driver, "save_screenshot"):
            return None
        recorded = self.recorded()
        label = label_for(len(recorded) + 1)
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


def attach(detail, path):
    """Number an already-captured screenshot onto the running test's recorder.

    The module-level counterpart to `PageEvidence.attach`, for helpers that
    cannot ask for the `page_evidence` fixture. Never raises.
    """
    recorder = current_recorder()
    if recorder is None:
        return None
    return recorder.attach(detail, path)


def checkpoint(detail, driver=None, settle=True):
    """Record a checkpoint on whichever test is running. Never raises.

    For fixtures and page-object helpers, which sit below the test function and
    so cannot ask for the `page_evidence` fixture. Test bodies should name that
    fixture and call `page_evidence.checkpoint(...)` instead - the plumbing is
    then visible in the signature.
    """
    recorder = current_recorder()
    if recorder is None:
        return None
    return recorder.checkpoint(detail, driver=driver, settle=settle)
