"""Merge every Jenkins lane's results into one Extent report for all modules.

Jenkinsfile.full runs the suite as several pytest processes ("lanes") drawn
along account lines: M1 shares a lane with M5, M3 with M4, and M2 is split in
two. Each lane writes its own Extent report, so reading a whole run meant
opening four of them. Every pytest session also saves its results as
run_results.json beside its report (conftest.dump_run_results). This reads
those and renders them with conftest's own report builders, so the merged
report looks like any other run report, with the tests grouped M1 to M5:

    <out-dir>/extent_report.html   every test with its screenshots
    <out-dir>/excel_report.xlsx    the same results as a workbook

Screenshots are re-read from the paths the lanes recorded, so run this before
the workspace's screenshots/ folder is cleaned.

Usage:
    python tools/build_combined_report.py --reports-dir reports_ci \
        --title "All Modules Report - CBSE Daily Regression #42"
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402  (needs the repo root on sys.path)

# Report folders that are not part of the run proper. Preflight runs the M3
# probe that the M3+M4 lane runs again, so it would count twice.
SKIPPED_LANES = {"preflight"}


def load_lanes(reports_dir, out_dir):
    """(lane folder name, saved results) for every lane that finished."""
    lanes = []
    for path in sorted(reports_dir.glob(f"*/{conftest.RUN_RESULTS_FILE}")):
        if path.parent.name in SKIPPED_LANES or path.parent.resolve() == out_dir.resolve():
            continue
        try:
            lanes.append((path.parent.name, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError) as error:
            print(f"warning: skipping unreadable {path}: {error}", file=sys.stderr)
    return lanes


def merge_into_conftest(lanes):
    """Load the lanes' results into the globals conftest's report builders read."""
    module_order = list(conftest.MODULE_NAMES.values())

    def module_position(result):
        module = result.get("module")
        return module_order.index(module) if module in module_order else len(module_order)

    # Grouped by module, M1 first. sort() is stable, so each module keeps the
    # order its tests ran in.
    results = [result for _, payload in lanes for result in payload.get("results") or []]
    results.sort(key=module_position)
    conftest.EXTENT_RESULTS[:] = results

    # The lanes select disjoint tests, so the per-module totals add up. Every
    # module keeps a row, so one whose lane never finished shows as zero.
    counts = dict.fromkeys(module_order, 0)
    for _, payload in lanes:
        for module, count in (payload.get("module_counts") or {}).items():
            counts[module] = counts.get(module, 0) + count
    conftest.MODULE_TEST_COUNTS.clear()
    conftest.MODULE_TEST_COUNTS.update(counts)

    # The lanes overlap in time, so the run spans the first start to the last end.
    starts = [payload["start"] for _, payload in lanes if payload.get("start")]
    ends = [payload["end"] for _, payload in lanes if payload.get("end")]
    conftest.SESSION_TIMING.update(
        start=min(starts, default=None), end=max(ends, default=None)
    )

    last_lane = max(lanes, key=lambda lane: lane[1].get("end") or 0)[1]
    conftest.RUN_ENVIRONMENT.clear()
    conftest.RUN_ENVIRONMENT.update(last_lane.get("environment") or {})


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reports-dir", default="reports_ci", type=Path)
    parser.add_argument(
        "--out-dir", type=Path, help="defaults to <reports-dir>/all_modules"
    )
    parser.add_argument("--title", default="All Modules Report")
    args = parser.parse_args()
    out_dir = args.out_dir or args.reports_dir / "all_modules"

    lanes = load_lanes(args.reports_dir, out_dir)
    if not lanes:
        print(
            f"No {conftest.RUN_RESULTS_FILE} under {args.reports_dir}/*/: "
            "no lane finished, so there is nothing to merge."
        )
        return 1

    merge_into_conftest(lanes)
    # conftest's builders write to PYTEST_REPORTS_DIR.
    out_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PYTEST_REPORTS_DIR"] = str(out_dir.resolve())
    report_path = conftest.build_extent_report(title=args.title)
    conftest.build_excel_report()

    statuses = [result.get("status") for result in conftest.EXTENT_RESULTS]
    print(
        f"{report_path}: {len(statuses)} tests from lanes "
        f"{', '.join(name for name, _ in lanes)} - "
        f"{statuses.count('PASSED')} passed, {statuses.count('FAILED')} failed, "
        f"{statuses.count('SKIPPED')} skipped"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
