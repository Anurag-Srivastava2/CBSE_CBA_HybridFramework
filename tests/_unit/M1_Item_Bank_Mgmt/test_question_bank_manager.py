import json
from pathlib import Path

import pytest

from utilities.question_bank_manager import (
    QuestionBankExhaustedError,
    content_hash,
    get_manual_item,
    get_questions,
    get_replacement_question,
    load_bank,
    reset_environment_usage,
    validate_record,
)


def _record(record_id, typology="Fill in the Blank", question=None, **overrides):
    question = question or f"Sample question for {record_id}"
    record = {
        "id": record_id,
        "typology": typology,
        "grade": "5",
        "subject": "Mathematics",
        "chapter": "Fixture Chapter",
        "competency": "Fixture Competency",
        "blooms_level": "Understanding",
        "question": question,
        "options": [],
        "answer": "Fixture answer",
        "explanation": "Fixture explanation.",
        "marks": 1,
        "content_hash": content_hash(question),
        "usage": {},
    }
    record.update(overrides)
    return record


def _write_bank(path, records):
    path.write_text(json.dumps(records), encoding="utf-8")
    return str(path)


def test_validate_record_flags_missing_fields():
    incomplete = _record("QB-001")
    del incomplete["explanation"]
    assert "missing required field: explanation" in validate_record(incomplete)


def test_validate_record_flags_mcq_without_four_options():
    mcq = _record("QB-002", typology="Multiple Choice Question", options=["A", "B"], answer="A")
    assert any("4 non-empty options" in problem for problem in validate_record(mcq))


def test_validate_record_flags_mcq_answer_not_in_options():
    mcq = _record(
        "QB-003",
        typology="Multiple Choice Question",
        options=["A", "B", "C", "D"],
        answer="Z",
    )
    assert any("does not match any" in problem for problem in validate_record(mcq))


def test_validate_record_flags_true_or_false_with_non_boolean_answer():
    tof = _record("QB-004", typology="True or False", answer="Maybe")
    assert any("True or False" in problem for problem in validate_record(tof))


def test_load_bank_skips_invalid_records(tmp_path, capsys):
    valid = _record("QB-VALID")
    invalid = _record("QB-INVALID", typology="Not A Real Typology")
    bank_path = _write_bank(tmp_path / "bank.json", [valid, invalid])

    loaded = load_bank(bank_path)

    assert [record["id"] for record in loaded] == ["QB-VALID"]
    assert "QB-INVALID" in capsys.readouterr().out


def test_get_questions_marks_records_used_and_never_returns_them_again(tmp_path):
    records = [_record(f"QB-{index:03d}", typology=typology) for index, typology in enumerate(
        ["Multiple Choice Question", "Fill in the Blank", "Match the Following", "True or False"],
        start=1,
    )]
    for record in records:
        if record["typology"] == "Multiple Choice Question":
            record["options"] = ["A", "B", "C", "D"]
            record["answer"] = "A"
        if record["typology"] == "True or False":
            record["answer"] = "True"
    bank_path = _write_bank(tmp_path / "bank.json", records)

    first_batch = get_questions(4, env="dev", path=bank_path)
    assert len(first_batch) == 4
    assert {item["typology"] for item in first_batch} == {
        "Multiple Choice Question", "Fill in the Blank", "Match the Following", "True or False",
    }

    with pytest.raises(QuestionBankExhaustedError):
        get_questions(1, env="dev", path=bank_path)

    persisted = json.loads(Path(bank_path).read_text(encoding="utf-8"))
    assert all(record["usage"]["dev"]["status"] == "used" for record in persisted)
    assert all(record["usage"]["dev"]["used_at"] for record in persisted)


def test_get_manual_item_returns_full_metadata_shape(tmp_path):
    record = _record(
        "QB-100",
        typology="Fill in the Blank",
        grade="6",
        subject="Science",
        chapter="Electricity",
        competency="Applies circuit concepts",
        blooms_level="Applying",
    )
    bank_path = _write_bank(tmp_path / "bank.json", [record])

    item = get_manual_item(env="dev", path=bank_path)

    assert item["grade"] == "6"
    assert item["subject"] == "Science"
    assert item["chapter"] == "Electricity"
    assert item["competency"] == "Applies circuit concepts"
    assert item["blooms_level"] == "Applying"
    assert item["typology"] == "Fill in the Blank"


def test_usage_is_scoped_per_environment(tmp_path):
    bank_path = _write_bank(tmp_path / "bank.json", [_record("QB-200")])

    get_questions(1, env="dev", path=bank_path)

    persisted = json.loads(Path(bank_path).read_text(encoding="utf-8"))
    assert persisted[0]["usage"]["dev"]["status"] == "used"
    assert persisted[0]["usage"].get("staging", {}).get("status", "unused") == "unused"

    staging_batch = get_questions(1, env="staging", path=bank_path)
    assert staging_batch[0]["question"] == "Sample question for QB-200"


def test_exhaustion_error_for_typology_with_no_unused_match(tmp_path):
    used_record = _record("QB-300", typology="Long Answer Question")
    used_record["usage"] = {"dev": {"status": "used", "used_at": "2026-01-01T00:00:00+00:00", "used_in_run": "prior"}}
    bank_path = _write_bank(tmp_path / "bank.json", [used_record])

    with pytest.raises(QuestionBankExhaustedError):
        get_replacement_question(typology="Long Answer Question", env="dev", path=bank_path)


def test_replacement_question_is_scoped_to_requested_typology(tmp_path):
    records = [
        _record("QB-400", typology="Long Answer Question", question="LAQ question"),
        _record("QB-401", typology="Short Answer Question", question="SAQ question"),
    ]
    bank_path = _write_bank(tmp_path / "bank.json", records)

    replacement = get_replacement_question(typology="Short Answer Question", env="dev", path=bank_path)

    assert replacement["typology"] == "Short Answer Question"
    assert replacement["question"] == "SAQ question"


def test_reset_environment_usage_flips_used_back_to_unused(tmp_path):
    record = _record("QB-500")
    record["usage"] = {"dev": {"status": "used", "used_at": "2026-01-01T00:00:00+00:00", "used_in_run": "prior"}}
    bank_path = _write_bank(tmp_path / "bank.json", [record])

    reset_count = reset_environment_usage("dev", path=bank_path)

    assert reset_count == 1
    persisted = json.loads(Path(bank_path).read_text(encoding="utf-8"))
    assert persisted[0]["usage"]["dev"]["status"] == "unused"
    assert persisted[0]["usage"]["dev"]["used_at"] is None


def test_atomic_write_leaves_no_temp_file_behind(tmp_path):
    bank_path = _write_bank(tmp_path / "bank.json", [_record("QB-600")])

    get_questions(1, env="dev", path=bank_path)

    assert not (tmp_path / "bank.json.tmp").exists()
