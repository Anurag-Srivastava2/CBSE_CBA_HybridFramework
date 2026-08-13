import configparser
import os
from pathlib import Path
import re
from urllib.parse import urlparse


def _load_dotenv(path):
    """Load simple KEY=VALUE entries without adding a runtime dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        # Strip inline comments (whitespace + # suffix) — but only when the '#'
        # is preceded by a space so that URL fragments like "/path#anchor" are kept.
        comment_pos = value.find(" #")
        if comment_pos != -1:
            value = value[:comment_pos].strip()
        os.environ.setdefault(key.strip(), value.strip('"').strip("'"))


class ReadConfig:
    # Always read config.ini from the project folder, not from terminal current folder
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "config" / "config.ini"
    _load_dotenv(project_root / ".env")

    config = configparser.ConfigParser()
    config.read(config_path)

    @staticmethod
    def _secret(env_name):
        value = os.getenv(env_name, "").strip()
        if not value:
            raise RuntimeError(
                f"Missing {env_name}. Copy .env.example to .env and set its value."
            )
        return value

    @staticmethod
    def get_base_url():
        return ReadConfig._secret("CBSE_BASE_URL")

    @staticmethod
    def get_browser_name():
        return ReadConfig.config.get("browser", "browser_name")

    @staticmethod
    def get_click_delay_seconds():
        return ReadConfig.config.getfloat("automation", "click_delay_seconds", fallback=0.5)

    @staticmethod
    def should_auto_open_extent():
        return ReadConfig.config.getboolean("reports", "auto_open_extent", fallback=True)

    @staticmethod
    def get_username():
        return ReadConfig._secret("CBSE_TEACHER_USERNAME")

    @staticmethod
    def get_password():
        return ReadConfig._secret("CBSE_TEACHER_PASSWORD")

    @staticmethod
    def get_sme_username():
        return ReadConfig._secret("CBSE_SME_USERNAME")

    @staticmethod
    def get_sme_password():
        return os.getenv("CBSE_SME_PASSWORD") or ReadConfig.get_all_users_password()

    @staticmethod
    def get_sme2_username():
        """The default SME account used by most M1 suites.

        Under pytest-xdist every worker would otherwise drive the same SME
        session, and SME state such as the staged "Added Items" list is shared
        server-side per account — one worker's additions then show up mid-test
        in another's. Each worker therefore gets its own account from
        CBSE_SME_USERNAMES; serial runs are unaffected and still use
        CBSE_SME2_USERNAME.
        """
        worker_id = os.getenv("PYTEST_XDIST_WORKER", "").strip()
        configured_sme_usernames = ReadConfig.get_role_usernames("sme")
        if worker_id.startswith("gw") and configured_sme_usernames:
            worker_number = int(worker_id.removeprefix("gw"))
            return configured_sme_usernames[worker_number % len(configured_sme_usernames)]
        return ReadConfig._secret("CBSE_SME2_USERNAME")

    @staticmethod
    def get_sme2_password():
        """Password for whichever account get_sme2_username() resolved to.

        Resolved from the username rather than a fixed CBSE_SME2_PASSWORD: the
        default SME account varies per xdist worker, and 'SME2' here means "the
        secondary SME slot", which is not necessarily the sme2@ login.
        """
        return ReadConfig.get_password_for_username(ReadConfig.get_sme2_username())

    @staticmethod
    def get_admin2_username():
        """Secondary admin login.

        The portal appears to allow only one active session per account, so a
        suite that runs alongside another admin-driven suite needs its own
        admin. Falls back to the primary admin when none is configured.
        """
        return os.getenv("CBSE_ADMIN2_USERNAME", "").strip() or ReadConfig.get_role_usernames("admin")[0]

    @staticmethod
    def get_pit1_username():
        return ReadConfig._secret("CBSE_PIT1_USERNAME")

    @staticmethod
    def get_pit_usernames():
        return ReadConfig.get_role_usernames("pit")

    @staticmethod
    def get_all_user_username(user_key):
        raw_key = str(user_key).strip().lower().replace(".", "")
        compact_key = re.sub(r"[^a-z0-9]", "", raw_key)
        candidate_keys = [
            raw_key,
            raw_key.replace(" ", ""),
            raw_key.replace("_", ""),
            raw_key.replace("-", ""),
            raw_key.replace(" ", "_"),
        ]

        env_name = f"CBSE_{compact_key.upper()}_USERNAME"
        direct_value = os.getenv(env_name)
        if direct_value:
            return direct_value.strip()

        for role in ("admin", "sme", "teacher", "rwg", "sr_rwg", "pit"):
            for username in ReadConfig.get_role_usernames(role):
                local_part = username.split("@", 1)[0]
                if re.sub(r"[^a-z0-9]", "", local_part.lower()) == compact_key:
                    return username

        raise RuntimeError(f"No username configured for {user_key!r} ({env_name}).")

    @staticmethod
    def get_all_users_password():
        return ReadConfig._secret("CBSE_ALL_USERS_PASSWORD")

    @staticmethod
    def get_password_for_username(username):
        """Per-user password override (CBSE_<LOCALPART>_PASSWORD), falling
        back to the shared CBSE_ALL_USERS_PASSWORD when no override is set.
        """
        local_part = str(username).split("@", 1)[0].strip().lower()
        compact_key = re.sub(r"[^a-z0-9]", "", local_part)
        override = os.getenv(f"CBSE_{compact_key.upper()}_PASSWORD", "").strip()
        return override or ReadConfig.get_all_users_password()

    @staticmethod
    def get_role_usernames(role):
        env_role = str(role).strip().upper().replace("-", "_")
        users = ReadConfig._secret(f"CBSE_{env_role}_USERNAMES")
        return [username.strip() for username in users.split(",") if username.strip()]

    @staticmethod
    def get_manual_item_question():
        return ReadConfig.config.get("manual_item", "question_text")

    @staticmethod
    def get_manual_item_explanation():
        return ReadConfig.config.get("manual_item", "explanation")

    @staticmethod
    def get_manual_item_answer():
        return ReadConfig.config.get("manual_item", "answer")

    @staticmethod
    def get_upload_item_file_path():
        default_path = Path.home() / "Downloads" / "sme_sheet.xlsx"
        configured_path = Path(
            os.getenv("CBSE_UPLOAD_ITEM_FILE", str(default_path))
        )
        if configured_path.exists():
            return str(configured_path)

        matching_files = sorted(
            configured_path.parent.glob("sme_sheet*.xlsx"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matching_files:
            return str(matching_files[0])

        return str(configured_path)

    @staticmethod
    def get_environment_key():
        """Slug identifying the target environment for per-env question-bank usage tracking."""
        explicit_env = os.getenv("CBSE_ENV", "").strip()
        if explicit_env:
            return explicit_env

        hostname = urlparse(ReadConfig.get_base_url()).hostname or "unknown"
        return re.sub(r"[^a-z0-9]+", "-", hostname.lower()).strip("-")

    @staticmethod
    def get_question_bank_path():
        default_path = ReadConfig.project_root / "data" / "question_bank" / "questions.json"
        return str(Path(os.getenv("CBSE_QUESTION_BANK_PATH", str(default_path))))

    @staticmethod
    def get_image_moderation_test_zip_path():
        default_path = Path.home() / "Downloads" / "test-images.zip"
        configured_path = Path(
            os.getenv("CBSE_IMAGE_MODERATION_ZIP", str(default_path))
        )
        if configured_path.exists():
            return str(configured_path)

        matching_files = sorted(
            configured_path.parent.glob("test-images*.zip"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matching_files:
            return str(matching_files[0])

        return str(configured_path)
