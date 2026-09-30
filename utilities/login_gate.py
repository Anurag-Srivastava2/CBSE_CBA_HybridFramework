"""Space sign-ins out across every pytest process on this machine.

The portal's sign-in rate limit keys on the client IP, not the account (see
pages/common/login_page.py). Once it trips, *every* login from this machine
stalls on a filled-in form, whichever account it uses. A parallel run trips it
on its own: Jenkinsfile.full starts four lanes and up to seven xdist workers at
once, and each of them signs in within the same half-minute. The first CI run
lost tests in M1, M2 and M4 that way before a single assertion ran.

xdist's per-account groups cannot help here - they keep two workers off one
*account*, and this limit is per *machine*. So every login attempt first takes
a slot from a gate shared through the temp directory: at most one sign-in per
CBSE_LOGIN_MIN_INTERVAL_SECONDS across all processes, including a local run
started beside a Jenkins build.

Set CBSE_LOGIN_MIN_INTERVAL_SECONDS=0 to turn the gate off.
"""

import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from utilities.logger import LogGenerator

logger = LogGenerator.loggen()

DEFAULT_MIN_INTERVAL_SECONDS = 4.0
# A crashed process can leave the lock file behind. Nobody holds the lock for
# longer than one interval, so anything this old is abandoned.
STALE_LOCK_SECONDS = 60.0
# Never hang a test on the gate itself: past this, sign in anyway.
MAX_WAIT_SECONDS = 180.0


def min_interval_seconds():
    raw = os.getenv("CBSE_LOGIN_MIN_INTERVAL_SECONDS", "").strip()
    try:
        return max(0.0, float(raw)) if raw else DEFAULT_MIN_INTERVAL_SECONDS
    except ValueError:
        return DEFAULT_MIN_INTERVAL_SECONDS


def _gate_dir():
    return Path(os.getenv("CBSE_LOGIN_GATE_DIR", "").strip() or tempfile.gettempdir())


@contextmanager
def _machine_lock(deadline):
    lock_path = _gate_dir() / "cbse_login_gate.lock"
    acquired = False
    while time.monotonic() < deadline:
        try:
            os.close(os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            acquired = True
            break
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > STALE_LOCK_SECONDS:
                    lock_path.unlink()
                    continue
            except OSError:
                pass  # released or replaced between the two calls; just retry
            time.sleep(0.2)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock_path.unlink()
            except OSError:
                pass


def wait_for_login_slot():
    """Block until this process may submit a sign-in, then claim the slot."""
    interval = min_interval_seconds()
    if interval <= 0:
        return
    stamp_path = _gate_dir() / "cbse_login_gate.last"
    started = time.monotonic()
    with _machine_lock(started + MAX_WAIT_SECONDS) as acquired:
        if not acquired:
            logger.warning(
                "Login gate still busy after %.0fs; signing in without a slot.",
                MAX_WAIT_SECONDS,
            )
            return
        try:
            last = float(stamp_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last = 0.0
        # Clamped so a stamp from a skewed clock cannot park the gate.
        wait = min(last + interval - time.time(), interval)
        if wait > 0:
            time.sleep(wait)
        stamp_path.write_text(repr(time.time()), encoding="utf-8")
    waited = time.monotonic() - started
    if waited >= 1:
        logger.info("Login gate: waited %.1fs for a sign-in slot.", waited)
