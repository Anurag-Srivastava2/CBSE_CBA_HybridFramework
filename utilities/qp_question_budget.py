"""Run-scoped cap on how many questions an M4 question paper is built for.

CBSE_QP_MAX_QUESTIONS shrinks every generated/manual paper so a run can be
driven through a thin item bank or finished quickly. Unset - the default -
leaves each suite's own configuration exactly as it was.
"""

import os

ENV_VAR = "CBSE_QP_MAX_QUESTIONS"


def get_question_cap():
    """Largest number of questions a paper may be configured for, or None."""
    raw = os.getenv(ENV_VAR, "").strip()
    if not raw:
        return None
    try:
        cap = int(raw)
    except ValueError:
        raise ValueError(f"{ENV_VAR} must be a whole number, got {raw!r}") from None
    if cap < 1:
        raise ValueError(f"{ENV_VAR} must be at least 1, got {raw!r}")
    return cap


def cap_item_counts(counts, cap=None):
    """Scale per-section question counts down to fit the cap.

    The shape of the paper is preserved: every section keeps at least one
    question (so a cap below the section count is honoured only as far as the
    sections allow), and the remaining budget is shared out in proportion to
    the counts the suite asked for.
    """
    counts = [int(count) for count in counts]
    cap = get_question_cap() if cap is None else cap
    if cap is None or not counts or sum(counts) <= cap:
        return counts

    allowance = [1] * len(counts)
    spare = cap - len(counts)
    if spare > 0:
        total = sum(counts)
        shares = [count * spare / total for count in counts]
        for index, share in enumerate(shares):
            allowance[index] += int(share)
        remainder = spare - sum(int(share) for share in shares)
        by_fraction = sorted(
            range(len(shares)),
            key=lambda index: shares[index] - int(shares[index]),
            reverse=True,
        )
        for index in by_fraction[:remainder]:
            allowance[index] += 1
    return [min(count, allowed) for count, allowed in zip(counts, allowance)]


def cap_even_section_marks(total_marks, section_count):
    """Marks to generate a Section Level paper for, under the cap.

    Section Level derives its per-section question count from
    total_marks // section_count at one mark each, so the only way to cap the
    questions it generates is to lower the marks it is generated for.
    """
    cap = get_question_cap()
    if cap is None or total_marks <= cap:
        return total_marks
    return max(1, cap // section_count) * section_count


def cap_manual_marks(total_marks):
    """Manual Build adds items until the marks target is met, so its question
    count is bounded by the target: one mark per question in the worst case."""
    cap = get_question_cap()
    return total_marks if cap is None else min(total_marks, cap)
