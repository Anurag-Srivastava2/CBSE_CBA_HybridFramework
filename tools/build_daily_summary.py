"""Merge every lane's junit.xml into one report the whole team can read.

Jenkinsfile.full runs the suite as several pytest processes ("lanes") drawn
along account boundaries, so M1 and M5 share a lane and M2 is split across two.
Each lane publishes its own report, which is right for debugging but wrong for
a daily status mail: nobody outside QA should have to open five reports and add
them up. This regroups the results by *module* and writes:

    <reports-dir>/daily_summary.html   email-safe HTML (inline styles only)
    <reports-dir>/daily_summary.txt    one-line status, used as the mail subject

Failures are split the same way the run report splits them: a failure carrying
an infrastructure signature (see utilities/environment_health.py) is an
environment outage, not a product defect, and is listed separately so a bad
morning on the server does not read as thirty regressions.

Usage:
    python tools/build_daily_summary.py --reports-dir reports_ci \
        --title "CBSE Daily Regression #42" --env-url https://... \
        --build-url https://jenkins/job/cbse-daily/42/
"""

import argparse
import html
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from utilities.environment_health import is_infrastructure_failure
except Exception:  # the summary must still render if the suite's config is gone
    def is_infrastructure_failure(_failure_text):
        return False

# Same folders and display names conftest.MODULE_NAMES uses for the run report.
MODULE_NAMES = {
    "m1_item_bank_mgmt": "M1 - Item Bank Mgmt",
    "m2_web_portal_admin": "M2 - Web Portal Admin",
    "m3_item_testing": "M3 - Item Testing",
    "m4_qp_creation": "M4 - QP Creation",
    "m5_teacher_contribution": "M5 - Teacher Contribution",
}
# tests/test_qar_retry_flow.py and friends sit outside any module folder; the
# module job files them under M1, so the summary does too.
FALLBACK_MODULE = MODULE_NAMES["m1_item_bank_mgmt"]

# Lane directory under reports_ci -> the name Jenkins publishes its report as.
LANE_NAMES = {
    "m1_m5": "M1 + M5",
    "m2": "M2",
    "m2_serial": "M2 serial",
    "m3_m4": "M3 + M4",
    "logic": "Logic",
}

OUTCOMES = ("passed", "failed", "environment", "skipped", "xfailed")

COLOURS = {
    "passed": "#1a7f37",
    "failed": "#cf222e",
    "environment": "#9a6700",
    "skipped": "#57606a",
    "xfailed": "#57606a",
}


def module_for(classname):
    parts = classname.casefold().replace("/", ".").split(".")
    for folder, display_name in MODULE_NAMES.items():
        if folder in parts:
            return display_name
    return FALLBACK_MODULE


def outcome_for(testcase):
    """Return (outcome, message, detail) for one <testcase>."""
    for tag in ("failure", "error"):
        node = testcase.find(tag)
        if node is not None:
            message = node.get("message") or ""
            detail = node.text or ""
            if is_infrastructure_failure(f"{message}\n{detail}"):
                return "environment", message, detail
            return "failed", message, detail
    node = testcase.find("skipped")
    if node is not None:
        message = node.get("message") or ""
        if node.get("type") == "pytest.xfail" or message.startswith("xfail"):
            return "xfailed", message, ""
        return "skipped", message, ""
    return "passed", "", ""


def collect(reports_dir):
    """Every testcase from every lane's junit.xml, one dict per test."""
    results = []
    lane_seconds = {}
    for junit in sorted(reports_dir.glob("*/junit.xml")):
        lane = junit.parent.name
        try:
            root = ET.parse(junit).getroot()
        except ET.ParseError as exc:
            print(f"warning: skipping unreadable {junit}: {exc}", file=sys.stderr)
            continue
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        lane_seconds[lane] = sum(float(s.get("time") or 0) for s in suites)
        # A test that pytest-rerunfailures retried appears once per attempt,
        # and the failed first attempt carries no <failure>, so it read as a
        # pass: build #5 (2026-10-06) counted a test that failed twice as one
        # pass and one fail. Keep the last attempt, which is the verdict.
        final_attempts = {}
        for testcase in root.iter("testcase"):
            final_attempts[(testcase.get("classname"), testcase.get("name"))] = testcase
        for testcase in final_attempts.values():
            classname = testcase.get("classname") or ""
            outcome, message, detail = outcome_for(testcase)
            results.append({
                "lane": lane,
                "module": module_for(classname),
                # test_file.TestClass::test_name - the class alone is ambiguous.
                "name": f"{'.'.join(classname.split('.')[-2:])}::{testcase.get('name')}",
                "file": classname,
                "seconds": float(testcase.get("time") or 0),
                "outcome": outcome,
                "message": message,
                "detail": detail,
            })
    return results, lane_seconds


def tally(results, key):
    counts = defaultdict(lambda: dict.fromkeys(OUTCOMES, 0))
    for result in results:
        counts[result[key]][result["outcome"]] += 1
    return counts


def pass_rate(counts):
    # Skips and xfails are known, deliberate non-runs; the rate is over the
    # tests that actually had a verdict.
    ran = counts["passed"] + counts["failed"] + counts["environment"]
    return (100.0 * counts["passed"] / ran) if ran else 0.0


def overall_status(totals, total_tests):
    if total_tests == 0:
        return "NO RESULTS", COLOURS["failed"]
    if totals["failed"]:
        return "FAILURES", COLOURS["failed"]
    if totals["environment"]:
        return "ENVIRONMENT ISSUES", COLOURS["environment"]
    return "ALL PASSED", COLOURS["passed"]


def fmt_duration(seconds):
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m {secs:02d}s"


def first_line(text, limit=220):
    line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    return line if len(line) <= limit else line[: limit - 1] + "…"


# --- HTML ------------------------------------------------------------------
# Mail clients strip <style> blocks, so every rule is inline.

TABLE = "border-collapse:collapse;width:100%;margin:8px 0 20px;font-size:13px;"
TH = ("text-align:left;padding:8px 10px;background:#f3f6fb;color:#57606a;"
      "font-size:11px;text-transform:uppercase;border-bottom:1px solid #d0d7de;")
TD = "padding:7px 10px;border-bottom:1px solid #eaeef2;vertical-align:top;"
NUM = TD + "text-align:right;font-variant-numeric:tabular-nums;"


def cell(value, colour=None, numeric=True):
    style = NUM if numeric else TD
    if colour and value:
        style += f"color:{colour};font-weight:600;"
    return f"<td style='{style}'>{html.escape(str(value))}</td>"


def counts_table(first_header, rows, totals):
    header = "".join(
        f"<th style='{TH}{'' if i == 0 else 'text-align:right;'}'>{h}</th>"
        for i, h in enumerate(
            [first_header, "Total", "Passed", "Failed", "Env issue",
             "Skipped", "Known issue (xfail)", "Pass rate"]
        )
    )
    body = []
    for label, counts in rows + [("Total", totals)]:
        total = sum(counts.values())
        weight = "font-weight:700;" if label == "Total" else ""
        body.append(
            f"<tr style='{weight}'>"
            f"<td style='{TD}{weight}'>{html.escape(label)}</td>"
            + cell(total)
            + cell(counts["passed"], COLOURS["passed"])
            + cell(counts["failed"], COLOURS["failed"])
            + cell(counts["environment"], COLOURS["environment"])
            + cell(counts["skipped"])
            + cell(counts["xfailed"])
            + (cell(f"{pass_rate(counts):.1f}%") if total else cell("no results", COLOURS["failed"]))
            + "</tr>"
        )
    return f"<table style='{TABLE}'><tr>{header}</tr>{''.join(body)}</table>"


def failures_table(failures):
    header = "".join(f"<th style='{TH}'>{h}</th>" for h in ("Module", "Test", "Reason"))
    rows = []
    for result in sorted(failures, key=lambda r: (r["module"], r["name"])):
        rows.append(
            "<tr>"
            + cell(result["module"], numeric=False)
            + f"<td style='{TD}font-family:Consolas,monospace;font-size:12px;'>"
              f"{html.escape(result['name'])}</td>"
            + cell(first_line(result["message"] or result["detail"]), numeric=False)
            + "</tr>"
        )
    return f"<table style='{TABLE}'><tr>{header}</tr>{''.join(rows)}</table>"


def build_html(results, lane_seconds, args):
    totals = dict.fromkeys(OUTCOMES, 0)
    for result in results:
        totals[result["outcome"]] += 1
    status, colour = overall_status(totals, len(results))

    by_module = tally(results, "module")
    # Every module gets a row even with no results: a lane that crashed before
    # writing junit.xml must show up as a zero, not silently vanish.
    module_rows = [(name, by_module[name]) for name in MODULE_NAMES.values()]
    by_lane = tally(results, "lane")
    lane_rows = [(LANE_NAMES.get(lane, lane), by_lane[lane]) for lane in sorted(by_lane)]

    failed = [r for r in results if r["outcome"] == "failed"]
    environment = [r for r in results if r["outcome"] == "environment"]

    # Lanes run concurrently, so the longest lane plus the serial tail is the
    # test wall clock; Jenkins passes the true build duration when it has it.
    test_seconds = max(
        (s for lane, s in lane_seconds.items() if lane != "m2_serial"), default=0
    ) + lane_seconds.get("m2_serial", 0)
    duration = args.duration or fmt_duration(test_seconds)

    links = ""
    if args.build_url:
        build_url = args.build_url.rstrip("/")
        links = (
            f"<p style='margin:0 0 16px;font-size:13px;'>"
            f"<a href='{html.escape(build_url)}/CBSE_20All_20Modules_20Report/'>"
            f"All Modules Report</a> &middot; "
            f"<a href='{html.escape(build_url)}/'>Jenkins build</a> &middot; "
            f"<a href='{html.escape(build_url)}/testReport/'>All test results</a> &middot; "
            f"<a href='{html.escape(build_url)}/artifact/'>Reports &amp; screenshots</a>"
            f"</p>"
        )

    sections = [
        f"<div style='font-family:Segoe UI,Arial,sans-serif;color:#1f2328;max-width:980px;'>",
        f"<h2 style='margin:0 0 4px;font-size:20px;'>{html.escape(args.title)}</h2>",
        f"<p style='margin:0 0 12px;color:#57606a;font-size:13px;'>"
        f"{html.escape(args.env_url or '')} &middot; "
        f"{datetime.now().strftime('%d %b %Y %H:%M')} &middot; duration {html.escape(duration)}</p>",
        f"<p style='margin:0 0 12px;'><span style='display:inline-block;padding:6px 12px;"
        f"border-radius:6px;background:{colour};color:#fff;font-weight:700;'>{status}</span>"
        f"&nbsp; <b>{totals['passed']}</b> of <b>{len(results)}</b> passed"
        f" &middot; {totals['failed']} failed &middot; {totals['environment']} environment"
        f" &middot; pass rate {pass_rate(totals):.1f}%</p>",
        links,
        "<h3 style='font-size:15px;margin:18px 0 4px;'>By module</h3>",
        counts_table("Module", module_rows, totals),
    ]
    if failed:
        sections += [
            f"<h3 style='font-size:15px;margin:18px 0 4px;color:{COLOURS['failed']};'>"
            f"Failed tests ({len(failed)})</h3>",
            "<p style='margin:0;font-size:12px;color:#57606a;'>Candidate product defects "
            "&mdash; confirm with a re-run before raising a bug; shared-account "
            "contention can look identical.</p>",
            failures_table(failed),
        ]
    if environment:
        sections += [
            f"<h3 style='font-size:15px;margin:18px 0 4px;color:{COLOURS['environment']};'>"
            f"Environment issues ({len(environment)})</h3>",
            "<p style='margin:0;font-size:12px;color:#57606a;'>Failed on a transport-level "
            "signature (connection refused, DNS, timeout to the host) &mdash; the "
            "environment dropped, not the feature.</p>",
            failures_table(environment),
        ]
    if not results:
        sections.append(
            "<p>No junit results were found. The run stopped before any lane "
            "produced results &mdash; check the Preflight stage in the Jenkins console.</p>"
        )
    sections += [
        "<h3 style='font-size:15px;margin:18px 0 4px;'>By pipeline lane</h3>",
        counts_table("Lane", lane_rows, totals),
        "</div>",
    ]
    subject = (
        f"{args.title} - {status}: {totals['passed']}/{len(results)} passed"
        + (f", {totals['failed']} failed" if totals["failed"] else "")
        + (f", {totals['environment']} env" if totals["environment"] else "")
    )
    return "\n".join(sections), subject


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reports-dir", default="reports_ci", type=Path)
    parser.add_argument("--title", default="CBSE Daily Regression")
    parser.add_argument("--env-url", default="")
    parser.add_argument("--build-url", default="")
    parser.add_argument("--duration", default="", help="wall clock, e.g. from Jenkins")
    args = parser.parse_args()

    results, lane_seconds = collect(args.reports_dir)
    body, subject = build_html(results, lane_seconds, args)

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(args.title)}</title></head>"
        f"<body style='margin:16px;background:#ffffff;'>{body}</body></html>"
    )
    (args.reports_dir / "daily_summary.html").write_text(page, encoding="utf-8")
    (args.reports_dir / "daily_summary.txt").write_text(subject, encoding="utf-8")
    print(subject)


if __name__ == "__main__":
    main()
