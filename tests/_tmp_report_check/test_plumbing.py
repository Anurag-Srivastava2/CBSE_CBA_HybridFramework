import pytest

_attempts = {"n": 0}


def test_plain_pass():
    assert True


def test_plain_skip():
    pytest.skip("synthetic skip for report plumbing check")


@pytest.mark.flaky(reruns=1)
def test_retry_then_pass():
    _attempts["n"] += 1
    assert _attempts["n"] > 1, "first attempt fails on purpose"
