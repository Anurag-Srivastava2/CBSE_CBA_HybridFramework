import pytest

_attempts = {"n": 0}


def test_plain_pass(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "A synthetic test that simply passes.\n"
        "It exists only to check the run report renders a passing result "
        "correctly.",
    )
    assert True


def test_plain_skip(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "A synthetic test that skips itself straight away.\n"
        "It exists only to check the run report renders a skipped result "
        "correctly.",
    )
    pytest.skip("synthetic skip for report plumbing check")


@pytest.mark.flaky(reruns=1)
def test_retry_then_pass(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "A synthetic test that fails on its first attempt and passes on the "
        "retry.\n"
        "It exists only to check the run report renders a retried result "
        "correctly.",
    )
    _attempts["n"] += 1
    assert _attempts["n"] > 1, "first attempt fails on purpose"
