"""Load normalized RTM test cases for pytest parameterization."""

from dataclasses import dataclass
import json
from pathlib import Path


MANIFEST_PATH = Path(__file__).with_name("rtm_test_cases.json")


@dataclass(frozen=True)
class RTMCase:
    tc_id: str
    module: str
    fr_number: str
    feature: str
    scenario: str
    preconditions: str
    steps: str
    expected_result: str
    test_data: str
    priority: str
    status: str
    business_rule: str
    test_phase: str
    execution_mode: str
    automation_component: str
    source_row: int
    automation: dict | None


def load_cases():
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [RTMCase(**case) for case in payload["cases"]]


def cases_for_module(module_name):
    return [case for case in load_cases() if case.module == module_name]
