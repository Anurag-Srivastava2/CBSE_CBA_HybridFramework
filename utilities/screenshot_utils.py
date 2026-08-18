import re
from datetime import datetime
from pathlib import Path

from utilities.page_settle import wait_until_page_settled


class ScreenshotUtils:
    @staticmethod
    def capture(driver, name, directory="screenshots", settle=True):
        """Save a screenshot and return its path.

        Waits for the page to finish painting first, because a screenshot taken
        the instant a test reaches a page photographs the SPA's global spinner
        rather than the page (see `page_settle`). Pass `settle=False` for a state
        that is meant to be transient - a toast, or a failure where whatever the
        page is stuck on is itself the evidence.
        """
        if settle:
            wait_until_page_settled(driver)

        screenshot_dir = Path.cwd() / directory
        screenshot_dir.mkdir(exist_ok=True)

        safe_name = "".join(char if char.isalnum() or char in ("_", "-") else "_" for char in name)
        # Page labels carry spaces and dashes that each sanitize to an
        # underscore, so collapse the runs instead of shipping "01____Dashboard".
        safe_name = re.sub(r"_{2,}", "_", safe_name).strip("_")
        # Microseconds, because two workers capturing the same page in the same
        # second would otherwise write the same file and one report would show
        # the other's screenshot.
        file_name = f"{safe_name}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S_%f')}.png"
        screenshot_path = screenshot_dir / file_name
        driver.save_screenshot(str(screenshot_path))
        return str(screenshot_path)
