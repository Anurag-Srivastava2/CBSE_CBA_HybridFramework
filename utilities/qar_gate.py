"""Let one QAR run at a time start from this machine.

The QA backend allows a single QAR run per grade + subject. A second
submission is refused - after about 150s, as HTTP 201 "success" with
`"alreadyRunning": true` and no items - and the UI just returns to Confirm &
Submit, so the test reports "QAR never completed" (captured 2026-10-01).
Nearly every M1/M5 QAR test uploads Grade 1 Mathematics, so parallel Jenkins
lanes and xdist workers were refusing each other's runs.

Every QAR submission therefore takes a turn from a gate shared through the
temp directory, and holds it until that run finishes. This only covers our
own processes on this machine: a run stuck on the backend, or a teammate's
run on shared QA, can still block a submission.

Set CBSE_QAR_GATE=0 to turn the gate off.
"""

import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from utilities.logger import LogGenerator

logger = LogGenerator.loggen()

# The longest a submission legitimately holds the gate is its own QAR wait
# (90s to start + up to 420s to finish), so a lock older than this belongs to
# a process that died mid-run.
STALE_LOCK_SECONDS = 15 * 60
# Several tests can queue behind one another; past this, run anyway rather
# than fail on the gate itself.
MAX_WAIT_SECONDS = 30 * 60


def _lock_path():
    folder = os.getenv("CBSE_QAR_GATE_DIR", "").strip() or tempfile.gettempdir()
    return Path(folder) / "cbse_qar_gate.lock"


@contextmanager
def qar_turn(label="QAR run"):
    """Hold the machine-wide QAR turn for the duration of the block."""
    if os.getenv("CBSE_QAR_GATE", "1").strip() == "0":
        yield
        return
    lock = _lock_path()
    started = time.monotonic()
    acquired = False
    while time.monotonic() - started < MAX_WAIT_SECONDS:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"pid={os.getpid()} {label}".encode("utf-8"))
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > STALE_LOCK_SECONDS:
                    logger.warning("QAR gate: removing a stale lock older than %ss.", STALE_LOCK_SECONDS)
                    lock.unlink()
                    continue
            except OSError:
                pass  # released between the two calls; just retry
            time.sleep(2)
    waited = time.monotonic() - started
    if acquired and waited >= 5:
        logger.info("QAR gate: waited %.0fs for another QAR run to finish (%s).", waited, label)
    if not acquired:
        logger.warning("QAR gate still busy after %ss; submitting without a turn (%s).", MAX_WAIT_SECONDS, label)
    try:
        yield
    finally:
        if acquired:
            try:
                lock.unlink()
            except OSError:
                pass
