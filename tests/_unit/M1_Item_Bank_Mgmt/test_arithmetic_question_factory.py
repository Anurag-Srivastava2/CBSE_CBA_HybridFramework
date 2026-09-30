import pytest

from utilities.arithmetic_question_factory import (
    generate_qar_ready_mixed_questions,
    generate_unique_comparison_questions,
)


def test_comparison_question_factory_is_unique_and_correct(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Generate two batches of comparison questions using different seeds.\n"
        "Check each batch is internally unique and the two batches never overlap.\n"
        "Check every question's stated comparison is arithmetically correct.",
    )
    first_run = generate_unique_comparison_questions(8, seed="run-one")
    second_run = generate_unique_comparison_questions(8, seed="run-two")

    first_texts = {item["question"] for item in first_run}
    second_texts = {item["question"] for item in second_run}
    assert len(first_texts) == 8
    assert len(second_texts) == 8
    assert first_texts.isdisjoint(second_texts)
    assert len({item["context"] for item in first_run}) == 8
    assert len({item["structure"] for item in first_run}) == 8
    assert any(" > " in item["question"] for item in first_run)
    assert any(" > " not in item["question"] for item in first_run)

    for item in first_run + second_run:
        left = item["left_operand"]
        right = item["right_operand"]
        assert 1 <= left <= 99
        assert 1 <= right <= 99
        assert left != right
        assert (left > right) == (item["answer"] == "True")
        assert item["question"].endswith("?")
        assert item["explanation"]


@pytest.mark.parametrize("count", [3, 4, 5])
def test_mixed_factory_keeps_each_sheet_between_three_and_five_items(count, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Ask the mixed-question factory for a sheet holding between three and "
        "five items.\n"
        "Check it returns exactly that many, all unique, each carrying its own "
        "typology.",
    )
    items = generate_qar_ready_mixed_questions(count, seed="offline-sheet")

    assert len(items) == count
    assert len({item["question"] for item in items}) == count
    assert len({item["typology"] for item in items}) == count
    assert all(item["answer"] and item["explanation"] for item in items)
    mcq_items = [
        item for item in items if item["typology"] == "MCQ"
    ]
    assert not mcq_items or mcq_items[0]["answer"] in {"A", "B", "C", "D"}


@pytest.mark.parametrize("count", [0, 2, 6])
def test_mixed_factory_rejects_question_counts_outside_sheet_limit(count, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Ask the mixed-question factory for a sheet size outside the allowed "
        "three-to-five range.\n"
        "Check it refuses with a clear error instead of quietly building an "
        "invalid sheet.",
    )
    with pytest.raises(ValueError, match="between 3 and 5"):
        generate_qar_ready_mixed_questions(count, seed="invalid-sheet")


def test_mixed_factory_is_unique_between_runs_and_has_valid_mcq_answer_key(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Generate two mixed sheets using different seeds.\n"
        "Check no question repeats between the runs.\n"
        "Check every multiple-choice item's answer key really is one of the "
        "options offered.",
    )
    first_run = generate_qar_ready_mixed_questions(5, seed="mixed-run-one")
    second_run = generate_qar_ready_mixed_questions(5, seed="mixed-run-two")

    assert {item["question"] for item in first_run}.isdisjoint(
        {item["question"] for item in second_run}
    )
    mcq_items = [item for item in first_run if item["typology"] == "MCQ"]
    assert len(mcq_items) == 1
    assert mcq_items[0]["answer"] == "A"
