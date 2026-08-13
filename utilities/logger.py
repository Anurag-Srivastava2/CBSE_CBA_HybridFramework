import logging
from pathlib import Path
from datetime import datetime


class LogGenerator:

    @staticmethod
    def loggen():
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"automation_{datetime.now().strftime('%Y_%m_%d')}.log"

        logger = logging.getLogger("selenium_pytest_framework")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            file_handler = logging.FileHandler(log_file)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger
