from dataclasses import dataclass


def _unique_item_ids(item_ids):
    unique_ids = []
    seen = set()
    for item_id in item_ids or ():
        if item_id is None:
            continue
        normalized = str(item_id).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            unique_ids.append(normalized)
    return tuple(unique_ids)


@dataclass(frozen=True)
class QARRetryResult:
    item_set_id: str
    retry_count: int
    revised_item_ids_by_retry: tuple
    rerun_messages: tuple
    final_need_improvement_item_ids: tuple


def run_qar_need_improvement_retry_loop(
    *,
    item_set_id,
    get_need_improvement_item_ids,
    correct_items,
    rerun_qar,
    assert_blocked_from_rwg,
    assert_routed_to_rwg,
    max_retries=3,
):
    """Correct and recheck QAR failures with a strict retry ceiling.

    Callbacks keep the control flow reusable across SME, teacher, and API-backed
    suites. ``rerun_qar`` represents the application's set-level QAR action.
    """
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1.")

    failed_item_ids = _unique_item_ids(get_need_improvement_item_ids())
    revised_history = []
    rerun_messages = []

    if not failed_item_ids:
        assert_routed_to_rwg(item_set_id)
        return QARRetryResult(
            item_set_id=item_set_id,
            retry_count=0,
            revised_item_ids_by_retry=(),
            rerun_messages=(),
            final_need_improvement_item_ids=(),
        )

    for retry_number in range(1, max_retries + 1):
        assert_blocked_from_rwg(item_set_id, failed_item_ids)

        revised_item_ids = _unique_item_ids(
            correct_items(failed_item_ids, retry_number)
        )
        revised_history.append(revised_item_ids)
        revised_keys = {item_id.casefold() for item_id in revised_item_ids}
        not_revised = [
            item_id
            for item_id in failed_item_ids
            if item_id.casefold() not in revised_keys
        ]
        if not_revised:
            raise AssertionError(
                "QAR retry could not edit every Need Improvement item on "
                f"attempt {retry_number}: {', '.join(not_revised)}."
            )

        rerun_messages.append(str(rerun_qar(retry_number) or ""))
        failed_item_ids = _unique_item_ids(get_need_improvement_item_ids())
        if not failed_item_ids:
            assert_routed_to_rwg(item_set_id)
            return QARRetryResult(
                item_set_id=item_set_id,
                retry_count=retry_number,
                revised_item_ids_by_retry=tuple(revised_history),
                rerun_messages=tuple(rerun_messages),
                final_need_improvement_item_ids=(),
            )

    assert_blocked_from_rwg(item_set_id, failed_item_ids)
    item_label = "Item" if len(failed_item_ids) == 1 else "Items"
    raise AssertionError(
        f"{item_label} {', '.join(failed_item_ids)} still 'Need Improvement' "
        f"after {max_retries} retries; item set {item_set_id} remains blocked from RWG."
    )
