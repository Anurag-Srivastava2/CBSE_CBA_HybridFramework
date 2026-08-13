from datetime import datetime
from pathlib import Path


class ScreenshotUtils:
    @staticmethod
    def capture(driver, name, directory="screenshots"):
        screenshot_dir = Path.cwd() / directory
        screenshot_dir.mkdir(exist_ok=True)

        safe_name = "".join(char if char.isalnum() or char in ("_", "-") else "_" for char in name)
        file_name = f"{safe_name}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.png"
        screenshot_path = screenshot_dir / file_name
        driver.save_screenshot(str(screenshot_path))
        return str(screenshot_path)
