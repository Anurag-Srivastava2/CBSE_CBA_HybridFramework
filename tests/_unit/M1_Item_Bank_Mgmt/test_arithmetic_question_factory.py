import pytest

from utilities.arithmetic_question_factory import (
    generate_qar_ready_mixed_questions,
    generate_unique_comparison_questions,
)


def test_comparison_question_factory_is_unique_and_correct():
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
def test_mixed_factory_keeps_each_sheet_between_three_and_five_items(count):
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
def test_mixed_factory_rejects_question_counts_outside_sheet_limit(count):
    with pytest.raises(ValueError, match="between 3 and 5"):
        generate_qar_ready_mixed_questions(count, seed="invalid-sheet")


def test_mixed_factory_is_unique_between_runs_and_has_valid_mcq_answer_key():
    first_run = generate_qar_ready_mixed_questions(5, seed="mixed-run-one")
    second_run = generate_qar_ready_mixed_questions(5, seed="mixed-run-two")

    assert {item["question"] for item in first_run}.isdisjoint(
        {item["question"] for item in second_run}
    )
    mcq_items = [item for item in first_run if item["typology"] == "MCQ"]
    assert len(mcq_items) == 1
    assert mcq_items[0]["answer"] == "A"
