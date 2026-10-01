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
    def get_api_base_url():
        """Base URL of the REST API, which is a different host to the web app.

        CBSE_BASE_URL serves only the SPA - every /api/* path under it returns
        the app's own HTML 404 page, so API tests must not derive their URLs
        from it. The frontend bundle points at this separate host instead.
        """
        return ReadConfig._secret("CBSE_API_BASE_URL").rstrip("/")

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
    def get_teacher_usernames():
        """Every configured teacher login, primary first.

        CBSE_TEACHER_USERNAME names the primary; CBSE_TEACHER_USERNAMES is the
        pool. The primary is moved to the front rather than assumed to be there,
        so a serial run always drives the same account regardless of the order
        the pool happens to be configured in.
        """
        usernames = list(ReadConfig.get_role_usernames("teacher"))
        primary = os.getenv("CBSE_TEACHER_USERNAME", "").strip()
        if primary:
            remaining = [name for name in usernames if name.casefold() != primary.casefold()]
            usernames = [primary] + remaining
        return usernames

    @staticmethod
    def get_teacher_username():
        """The teacher login this worker should drive.

        Same reason as get_admin_username(): the portal keeps one active session
        per account, so two xdist workers both driving the primary teacher sign
        each other out mid-test — and M4/M5 are entirely teacher-driven. Each
        worker takes its own account from the configured teacher pool instead; a
        serial run is unaffected and still gets the primary teacher.

        Parallelism is capped by the pool size: with N teachers configured,
        `-n N` is the maximum before workers start sharing an account again.
        """
        teachers = ReadConfig.get_teacher_usernames()
        worker_id = os.getenv("PYTEST_XDIST_WORKER", "").strip()
        if worker_id.startswith("gw") and teachers:
            worker_number = int(worker_id.removeprefix("gw"))
            return teachers[worker_number % len(teachers)]
        return teachers[0]

    @staticmethod
    def get_qp_teacher_usernames():
        """Teacher pool for the QP Creation (M4) suites.

        Excludes the primary teacher, which the M5 contribution flows drive:
        the portal keeps one active session per account, so an M4 suite sharing
        it would sign an M5 test out mid-run.
        """
        teachers = ReadConfig.get_teacher_usernames()
        return teachers[1:] or teachers

    @staticmethod
    def get_qp_teacher_username():
        """The QP teacher this worker should drive.

        Every M4 suite publishes into "My QP" and its preview step opens the
        newest paper in that list, so two suites running *concurrently* on one
        account would read each other's paper. Splitting per worker gives each
        its own account; a serial run shares one safely, because each suite
        publishes and reads back before the next one starts.
        """
        pool = ReadConfig.get_qp_teacher_usernames()
        worker_id = os.getenv("PYTEST_XDIST_WORKER", "").strip()
        if worker_id.startswith("gw") and pool:
            worker_number = int(worker_id.removeprefix("gw"))
            return pool[worker_number % len(pool)]
        return pool[0]

    @staticmethod
    def get_teacher_password():
        """Password for whichever account get_teacher_username() resolved to.

        Resolved from the username rather than read from CBSE_TEACHER_PASSWORD,
        which only ever describes the primary teacher.
        """
        return ReadConfig.get_password_for_username(ReadConfig.get_teacher_username())

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
    def get_configured_sme2_username():
        """CBSE_SME2_USERNAME itself, never the per-worker slot.

        get_sme2_username() trades the configured account for one out of
        CBSE_SME_USERNAMES so that two xdist workers never drive the same SME
        session. That trade assumes the pool's accounts are interchangeable,
        and they are not: their grade/subject access is disjoint, so a worker
        can be handed an SME that cannot reach the curriculum its tests need.
        A suite pinned to a particular subject asks for the configured account
        instead, which is the one documented to carry full curriculum access.
        """
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
    def get_admin_usernames():
        """Every configured portal-admin login, primary first."""
        usernames = list(ReadConfig.get_role_usernames("admin"))
        secondary = os.getenv("CBSE_ADMIN2_USERNAME", "").strip()
        if secondary and secondary not in usernames:
            usernames.append(secondary)
        return usernames

    @staticmethod
    def get_admin_username():
        """The portal-admin login this worker should drive.

        Same reason as get_sme2_username: the portal keeps one active session
        per account, so two xdist workers both driving the primary admin sign
        each other out mid-test. Each worker takes its own account from the
        configured admin pool instead; a serial run is unaffected and still
        gets the primary admin.
        """
        admins = ReadConfig.get_admin_usernames()
        worker_id = os.getenv("PYTEST_XDIST_WORKER", "").strip()
        if worker_id.startswith("gw") and admins:
            worker_number = int(worker_id.removeprefix("gw"))
            return admins[worker_number % len(admins)]
        return admins[0]

    @staticmethod
    def get_admin2_username():
        """Secondary admin login.

        The portal appears to allow only one active session per account, so a
        suite that runs alongside another admin-driven suite needs its own
        admin. Falls back to the primary admin when none is configured.
        """
        return os.getenv("CBSE_ADMIN2_USERNAME", "").strip() or ReadConfig.get_role_usernames("admin")[0]

    @staticmethod
    def get_helpdesk_l1_username():
        """First-line helpdesk agent. Works tickets on /l1/helpdesk."""
        return ReadConfig._secret("CBSE_HELPDESK_L1_USERNAME")

    @staticmethod
    def get_helpdesk_l2_username():
        """Second-line helpdesk agent. Works tickets on /l2/helpdesk."""
        return ReadConfig._secret("CBSE_HELPDESK_L2_USERNAME")

    @staticmethod
    def get_pit1_username():
        return ReadConfig._secret("CBSE_PIT1_USERNAME")

    @staticmethod
    def get_pit_usernames():
        return ReadConfig.get_role_usernames("pit")

    # Publication needs a 3/3 PIT quorum, and the portal allows one active
    # session per account - so two heavy E2E suites that both take
    # get_pit_usernames()[:3] cannot run at the same time. They sign each
    # other out mid-quorum. That is why both were marked `serial` and queued
    # back to back on one worker, which is the M1 critical path.
    #
    # A lane takes its own disjoint slice instead. With 6 PIT accounts the two
    # suites hold quorum concurrently; with fewer, every lane falls back to the
    # same first three and conftest keeps them serial, so this is safe to land
    # before the extra account is provisioned.
    PIT_QUORUM_SIZE = 3

    @staticmethod
    def pit_quorum_lanes_available():
        """How many suites can hold a PIT quorum at once."""
        return len(ReadConfig.get_pit_usernames()) // ReadConfig.PIT_QUORUM_SIZE

    @staticmethod
    def get_pit_quorum(lane=0):
        """The PIT accounts this lane votes with.

        Falls back to lane 0 when the pool cannot cover the requested lane, so
        an under-provisioned environment still runs - just not concurrently.
        """
        pool = ReadConfig.get_pit_usernames()
        size = ReadConfig.PIT_QUORUM_SIZE
        if lane < 0 or (lane + 1) * size > len(pool):
            lane = 0
        return pool[lane * size:(lane + 1) * size]

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
    def get_new_user_password():
        """Password given to accounts the suite creates (user lifecycle test,
        tools/create_bulk_users.py). Read from .env like every other secret:
        it was once hardcoded in both files, which published it on GitHub."""
        return ReadConfig._secret("CBSE_NEW_USER_PASSWORD")

    @staticmethod
    def get_password_for_username(username):
        """Resolve a login's password, most specific override first.

        The local part alone does not identify an account: sme1@dev.com and
        sme1@test.com both compact to 'sme1', so a CBSE_SME1_PASSWORD set for
        one of them silently reassigns the other's password too. The two
        domain-aware keys below disambiguate.

        Lookup order:
          1. CBSE_<LOCALPART>_<DOMAIN>_PASSWORD - one specific account
          2. CBSE_<LOCALPART>_PASSWORD          - any account with that name
          3. CBSE_<DOMAIN>_DEFAULT_PASSWORD     - every account at that domain
          4. CBSE_ALL_USERS_PASSWORD            - the shared fallback

        The domain default sits *below* the local-part key rather than above
        it, so that adding one gives an existing account whose local-part
        override is already configured - admin@test.com being the case here -
        exactly the password it resolves to today.
        """
        local_part, _, domain = str(username).strip().lower().partition("@")
        compact_local = re.sub(r"[^a-z0-9]", "", local_part)
        compact_domain = re.sub(r"[^a-z0-9]", "", domain)

        candidate_keys = []
        if compact_local and compact_domain:
            candidate_keys.append(f"CBSE_{compact_local.upper()}_{compact_domain.upper()}_PASSWORD")
        if compact_local:
            candidate_keys.append(f"CBSE_{compact_local.upper()}_PASSWORD")
        if compact_domain:
            candidate_keys.append(f"CBSE_{compact_domain.upper()}_DEFAULT_PASSWORD")

        for key in candidate_keys:
            override = os.getenv(key, "").strip()
            if override:
                return override
        return ReadConfig.get_all_users_password()

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

    #: Repo-owned copy of the app's item-upload template, refreshed by
    #: tools/migrate_item_templates.py. The default is this rather than a file
    #: in the operator's Downloads folder so a fresh clone can run the upload
    #: suites without anyone first downloading a template by hand — and so the
    #: columns the suites write against are the ones under version control.
    BUNDLED_UPLOAD_TEMPLATE = (
        Path(__file__).resolve().parent.parent / "data" / "upload_templates" / "sme_sheet.xlsx"
    )

    _reported_stale_templates = set()

    @staticmethod
    def _carries_current_columns(path):
        """Does this workbook match the column contract the target env expects?

        A template downloaded before Book and Unit existed still opens, still
        looks like a valid sheet, and still resolves most fields — it just has
        no Book column and puts everything from Chapter rightwards one place to
        the left. Uploads built from it fail row validation with a message that
        says nothing about the real cause, so it is caught here instead.
        """
        from openpyxl import load_workbook  # local: keeps config import cheap

        from utilities.item_template_columns import resolve_columns

        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except Exception:  # noqa: BLE001 - unreadable is as unusable as stale
            return False
        try:
            for worksheet in workbook.worksheets:
                columns = resolve_columns(worksheet)
                if columns and columns["book"] and columns["unit"]:
                    return True
            return False
        finally:
            workbook.close()

    @staticmethod
    def get_upload_item_file_path():
        configured = os.getenv("CBSE_UPLOAD_ITEM_FILE", "").strip()
        candidates = []
        if configured:
            configured_path = Path(configured)
            if configured_path.exists():
                candidates.append(configured_path)
            else:
                # A configured path that has gone away still names the folder
                # the operator keeps their downloads in, so sheets there beat
                # falling back to the bundled copy they chose to override.
                candidates.extend(
                    sorted(
                        configured_path.parent.glob("sme_sheet*.xlsx"),
                        key=lambda path: path.stat().st_mtime,
                        reverse=True,
                    )
                )

        for candidate in candidates:
            if ReadConfig._carries_current_columns(candidate):
                return str(candidate)
            # Loud rather than silent: the operator asked for this file, and
            # quietly using a different one would make a green run misleading.
            # Reported once per path so it does not bury the run output.
            if str(candidate) not in ReadConfig._reported_stale_templates:
                ReadConfig._reported_stale_templates.add(str(candidate))
                print(
                    f"WARNING: CBSE_UPLOAD_ITEM_FILE points at {candidate}, which "
                    "predates the Book/Unit columns. Falling back to the bundled "
                    f"{ReadConfig.BUNDLED_UPLOAD_TEMPLATE.name}. Download a fresh "
                    "template from the app, or drop the CBSE_UPLOAD_ITEM_FILE "
                    "override, to silence this.",
                    flush=True,
                )

        return str(ReadConfig.BUNDLED_UPLOAD_TEMPLATE)

    @staticmethod
    def get_qp_subject():
        """Subject the M4 question papers are built for.

        Unset, the QP Builder's first offered subject is taken - the
        behaviour every M4 suite had before this knob existed. Set it to build
        against a different one (e.g. Mathematics) on an environment whose
        item bank carries it.
        """
        return os.getenv("CBSE_QP_SUBJECT", "").strip() or None

    @staticmethod
    def get_environment_key():
        """Slug identifying the target environment for per-env question-bank usage tracking."""
        explicit_env = os.getenv("CBSE_ENV", "").strip()
        if explicit_env:
            return explicit_env

        hostname = urlparse(ReadConfig.get_base_url()).hostname or "unknown"
        return re.sub(r"[^a-z0-9]+", "-", hostname.lower()).strip("-")

    @staticmethod
    def get_docx_template_dir():
        """Directory holding the Word item-upload sample documents.

        These ship in the repo beside the Excel typology templates, so a fresh
        checkout can run the Word suite without anyone fetching a download
        first. Point CBSE_DOCX_TEMPLATE_DIR at a newer drop when the template
        changes rather than editing the checked-in copies, so the suite can be
        run against a candidate template without a commit.
        """
        default_path = ReadConfig.project_root / "data" / "typology_templates_docx"
        return str(Path(os.getenv("CBSE_DOCX_TEMPLATE_DIR", str(default_path))))

    @staticmethod
    def get_docx_images_zip_path():
        """The companion image .zip the Word documents reference by filename."""
        return str(Path(ReadConfig.get_docx_template_dir()) / "images.zip")

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
