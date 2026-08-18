import json

from selenium.common.exceptions import WebDriverException

from utilities.page_evidence import current_recorder


class ElementChecks:
    """Collect per-element presence results without failing the test.

    A hard `assert` on element visibility stops at the first missing element,
    so a page with five gaps takes five runs to survey. These checks record
    every element's verdict instead and hand the whole table to the report, so
    one run answers "what is actually rendered on this page?".

    The test outcome is deliberately left alone — a missing element shows as a
    FAILED row inside the report card, not as a failed test. Pair this with a
    hard assertion on whatever the test genuinely gates on.
    """

    # Kept short on purpose: a page survey runs many checks back to back, and
    # every absent element costs its full timeout.
    DEFAULT_TIMEOUT = 5

    def __init__(self, page, record_property, page_name, capture_evidence=True):
        self.page = page
        self.record_property = record_property
        self.page_name = page_name
        self.results = []
        # A survey is already scoped to one named page, which makes this the one
        # moment we know both which page the test is on and that it has finished
        # loading - so the report gets a screenshot per page for free. Taken
        # before the checks run, so it shows the page as the test found it rather
        # than as check_interaction left it. Pass capture_evidence=False for a
        # survey that re-uses a page an earlier ElementChecks already shot.
        if capture_evidence:
            self.capture_page_evidence()

    def capture_page_evidence(self, page_name=None):
        """Add this page to the report's screenshot section. Never raises."""
        recorder = current_recorder()
        if recorder is None:
            return None
        return recorder.capture(
            page_name or self.page_name, driver=getattr(self.page, "driver", None)
        )

    def check(self, name, locator, timeout=DEFAULT_TIMEOUT):
        """Record whether `locator` is visible. Never raises, always returns bool."""
        try:
            present = bool(self.page.is_element_visible_quick(locator, timeout))
            error = ""
        except WebDriverException as failure:
            # A stale/invalid lookup is a failed check, not a broken run.
            present = False
            error = type(failure).__name__
        self._record(name, present, locator=locator, error=error)
        return present

    def safe_call(self, reader, default=None):
        """Read a value from the page without letting a failure abort the run.

        Survey helpers gather lists like missing_columns() or get_all_kpi_values()
        before recording them. Those calls sit outside check_condition's guard,
        so one raising helper took the whole test down - the exact failure mode
        these soft checks exist to avoid.
        """
        try:
            return reader()
        except Exception:  # noqa: BLE001 - an unreadable value is just absent
            return default if default is not None else []

    def text_of(self, locator, default=""):
        """Read an element's text without raising, so a missing element leaves
        the surrounding content checks recordable instead of aborting the run."""
        try:
            return self.page.get_text(locator)
        except (WebDriverException, AssertionError, ValueError):
            return default

    def check_condition(self, name, condition, detail=""):
        """Record a non-locator expectation (row counts, header text, ...).

        `condition` may be a value or a callable. Pass a callable when reading
        the state can raise — several page helpers throw NoSuchElementException
        when the row they inspect is absent, and a value argument would raise at
        the call site, outside this guard.
        """
        error = ""
        try:
            present = bool(condition() if callable(condition) else condition)
        except Exception as failure:  # noqa: BLE001 - any failure is a failed check
            present = False
            error = f"{type(failure).__name__}"
        self._record(name, present, detail=detail, error=error)
        return present

    def check_interaction(self, name, action, verify, detail=""):
        """Record whether a control actually *works*, not just that it renders.

        `action` drives the control (type in a search box, flip a toggle, pick a
        dropdown option); `verify` returns truthy when the page responded as it
        should. Both run inside the same guard, so a control that throws when
        driven is recorded as a failed interaction rather than aborting the run.

        Presence checks answer "is the control on screen"; this answers "does
        clicking it do anything", which is the failure mode a rendered-but-dead
        control produces.
        """
        try:
            action()
            responded = bool(verify())
            error = ""
        except Exception as failure:  # noqa: BLE001 - any failure is a failed check
            responded = False
            error = f"{type(failure).__name__}: {failure}"[:160]
        self._record(name, responded, detail=detail, error=error, kind="interaction")
        return responded

    def _record(self, name, present, locator=None, detail="", error="", kind="presence"):
        note = detail
        if error:
            note = f"{detail} ({error})".strip()
        self.results.append(
            {
                "page": self.page_name,
                "element": name,
                "kind": kind,
                "status": "PASSED" if present else "FAILED",
                "locator": f"{locator[0]}={locator[1]}" if locator else "",
                "detail": note,
            }
        )

    @property
    def passed(self):
        return [result for result in self.results if result["status"] == "PASSED"]

    @property
    def failed(self):
        return [result for result in self.results if result["status"] == "FAILED"]

    def summary(self):
        interactions = [r for r in self.results if r.get("kind") == "interaction"]
        working = [r for r in interactions if r["status"] == "PASSED"]
        parts = [
            f"{len(self.passed)}/{len(self.results)} checks passed on {self.page_name}"
        ]
        if interactions:
            parts.append(f"{len(working)}/{len(interactions)} controls responded")
        if self.failed:
            parts.append("failed: " + ", ".join(r["element"] for r in self.failed))
        return "; ".join(parts)

    def publish(self):
        """Hand the collected rows to the report. Call once, at test end."""
        self.record_property("element_checks", json.dumps(self.results))
        return self.summary()
