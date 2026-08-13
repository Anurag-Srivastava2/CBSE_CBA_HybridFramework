"""Persisted, per-environment-tracked question bank for Excel upload and manual item creation.

Questions are authored once (see data/question_bank/questions.json) and consumed here so the
same question is never handed to a given environment twice: every selection flips that record's
usage status for the requesting environment before it is returned.
"""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from utilities.read_config import ReadConfig


TYPOLOGIES = (
    "Multiple Choice Question",
    "Fill in the Blank",
    "Match the Following",
    "True or False",
    "Very Short Answer Question",
    "Short Answer Question",
    "Long Answer Question",
    "Case Based Question",
    "Source Based Question",
    "Assertion and Reasoning",
    "FA Activity",
    "Free Response",
)

OPTION_BASED_TYPOLOGIES = {"Multiple Choice Question", "Case Based Question", "Source Based Question"}

REQUIRED_FIELDS = ("id", "typology", "question", "answer", "explanation", "marks", "content_hash")


class QuestionBankExhaustedError(RuntimeError):
    """Raised when no unused question matches the requested filters for an environment."""


def content_hash(question_text):
    normalized = " ".join(str(question_text or "").strip().casefold().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_record(record):
    """Return a list of human-readable problems; an empty list means the record is usable."""
    errors = []
    for field in REQUIRED_FIELDS:
        if not record.get(field):
            errors.append(f"missing required field: {field}")

    typology = str(record.get("typology", "")).strip()
    if typology not in TYPOLOGIES:
        errors.append(f"unknown typology: {typology!r}")

    if typology in OPTION_BASED_TYPOLOGIES:
        options = [str(option).strip() for option in record.get("options") or [] if str(option).strip()]
        if len(options) != 4:
            errors.append("option-based typology requires exactly 4 non-empty options")
        answer = str(record.get("answer", "")).strip()
        if answer and options and answer not in options:
            errors.append("answer does not match any of the provided options")
    elif typology == "True or False":
        if str(record.get("answer", "")).strip().casefold() not in {"true", "false"}:
            errors.append("True or False typology requires answer to be 'True' or 'False'")

    return errors


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _atomic_write_json(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(temp_path, path)


def load_bank(path=None):
    """Load and structurally validate every record; invalid records are dropped with a note."""
    resolved_path = Path(path or ReadConfig.get_question_bank_path())
    records = _read_json(resolved_path)
    valid_records = []
    for record in records:
        problems = validate_record(record)
        if problems:
            print(f"[question_bank_manager] skipping invalid record {record.get('id')!r}: {problems}")
            continue
        valid_records.append(record)
    return valid_records


def _load_all_records(path):
    """Load every record (including invalid ones) so writes never silently drop data."""
    resolved_path = Path(path or ReadConfig.get_question_bank_path())
    return resolved_path, _read_json(resolved_path)


def _current_run_id():
    return os.environ.get("PYTEST_CURRENT_TEST", "manual")


def _is_unused(record, env):
    return record.get("usage", {}).get(env, {}).get("status", "unused") == "unused"


def _mark_used(record, env):
    record.setdefault("usage", {})[env] = {
        "status": "used",
        "used_at": datetime.now(timezone.utc).isoformat(),
        "used_in_run": _current_run_id(),
    }


def _matches_filters(record, typologies, filters):
    if typologies and record.get("typology") not in typologies:
        return False
    for key, value in filters.items():
        if value is None:
            continue
        if str(record.get(key, "")).casefold() != str(value).casefold():
            return False
    return True


def _normalize_typologies(typology, typologies):
    if typology is not None:
        return [typology]
    if typologies is None:
        return None
    if isinstance(typologies, str):
        return [typologies]
    return list(typologies)


def _candidates(all_records, env, typologies, exclude_ids, filters):
    for record in all_records:
        if record.get("id") in exclude_ids:
            continue
        if validate_record(record):
            continue
        if not _matches_filters(record, typologies, filters):
            continue
        if not _is_unused(record, env):
            continue
        yield record


def _select_diverse(candidates, count):
    """Round-robin across distinct typologies so a multi-question pull is typology-mixed
    instead of exhausting whichever typology happens to appear first in the file."""
    groups = {}
    for record in candidates:
        groups.setdefault(record["typology"], []).append(record)

    selected = []
    while len(selected) < count and groups:
        for typology_key in list(groups.keys()):
            if len(selected) >= count:
                break
            bucket = groups[typology_key]
            selected.append(bucket.pop(0))
            if not bucket:
                del groups[typology_key]
    return selected


def _select_and_mark(path, env, count, typologies, exclude_ids, filters):
    env = env or ReadConfig.get_environment_key()
    resolved_path, all_records = _load_all_records(path)
    exclude_ids = set(exclude_ids or [])

    candidates = _candidates(all_records, env, typologies, exclude_ids, filters)
    if typologies:
        # An explicit typology filter already narrows intent (e.g. a same-typology
        # duplicate replacement) - take matches in file order rather than diversifying.
        selected = []
        for record in candidates:
            if len(selected) >= count:
                break
            selected.append(record)
    else:
        selected = _select_diverse(candidates, count)

    if len(selected) < count:
        raise QuestionBankExhaustedError(
            f"Question bank has no unused match for env={env!r}, "
            f"typologies={typologies!r}, filters={filters!r} "
            f"(needed {count}, found {len(selected)})."
        )

    for record in selected:
        _mark_used(record, env)
    _atomic_write_json(resolved_path, all_records)

    return [copy.deepcopy(record) for record in selected]


def get_questions(count, *, typology=None, typologies=None, env=None, path=None, exclude_ids=None, **filters):
    """Select `count` unused questions and mark them used for `env`, shaped for workbook rows."""
    resolved_typologies = _normalize_typologies(typology, typologies)
    records = _select_and_mark(path, env, count, resolved_typologies, exclude_ids, filters)
    return [
        {
            "typology": record["typology"],
            "question": record["question"],
            "options": list(record.get("options") or []),
            "answer": record["answer"],
            "explanation": record["explanation"],
            "marks": record["marks"],
            "question_image": None,
        }
        for record in records
    ]


def get_manual_item(*, typology=None, typologies=None, env=None, path=None, exclude_ids=None, **filters):
    """Select one unused question shaped for ManualItemPage, marking it used for `env`."""
    resolved_typologies = _normalize_typologies(typology, typologies)
    records = _select_and_mark(path, env, 1, resolved_typologies, exclude_ids, filters)
    record = records[0]
    return {
        "typology": record["typology"],
        "grade": record.get("grade"),
        "subject": record.get("subject"),
        "chapter": record.get("chapter"),
        "competency": record.get("competency"),
        "blooms_level": record.get("blooms_level"),
        "question": record["question"],
        "options": list(record.get("options") or []),
        "answer": record["answer"],
        "explanation": record["explanation"],
        "marks": record["marks"],
        "question_image": None,
    }


def get_replacement_question(*, typology, env=None, path=None, exclude_ids=None, **filters):
    """Select one unused question of the same typology to swap in for a QAR-flagged duplicate."""
    records = _select_and_mark(path, env, 1, [typology], exclude_ids, filters)
    record = records[0]
    return {
        "typology": record["typology"],
        "question": record["question"],
        "options": list(record.get("options") or []),
        "answer": record["answer"],
        "explanation": record["explanation"],
        "marks": record["marks"],
    }


def reset_environment_usage(env, path=None):
    """Flip every record's usage for `env` back to unused (e.g. after a dev environment wipe)."""
    resolved_path, all_records = _load_all_records(path)
    reset_count = 0
    for record in all_records:
        usage = record.get("usage", {})
        if env in usage and usage[env].get("status") != "unused":
            usage[env] = {"status": "unused", "used_at": None, "used_in_run": None}
            reset_count += 1
    _atomic_write_json(resolved_path, all_records)
    return reset_count
