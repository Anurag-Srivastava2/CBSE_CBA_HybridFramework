"""Generate one HTML report from a parallel image-moderation upload run."""

import argparse
import base64
import html
import json
from pathlib import Path


def image_data_url(path):
    if not path:
        return None
    image_path = Path(path)
    if not image_path.is_file():
        return None
    mime_type = "image/png" if image_path.suffix.casefold() == ".png" else "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_report(run_dir, output_path, expected_count=22):
    run_dir = Path(run_dir).resolve()
    output_path = Path(output_path).resolve()
    result_files = sorted((run_dir / "results").glob("*.json"))
    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_files]
    by_number = {int(result["case_number"]): result for result in results}

    rows = []
    evidence_cards = []
    matched = accepted = rejected = 0
    for case_number in range(1, expected_count + 1):
        result = by_number.get(case_number)
        if result is None:
            rows.append(
                f"<tr class='missing'><td>{case_number:03d}</td>"
                "<td colspan='8'>No result produced</td></tr>"
            )
            continue

        is_match = bool(result["accepted"]) == bool(result["expected_accepted"])
        matched += int(is_match)
        accepted += int(bool(result["accepted"]))
        rejected += int(not bool(result["accepted"]))
        focused_screenshot_url = image_data_url(
            result.get("focused_evidence_screenshot")
        )
        screenshot_url = image_data_url(
            result.get("viewport_evidence_screenshot")
            or result.get("validation_screenshot")
            or result.get("rejection_screenshot")
        )
        status = "PASS" if is_match else "FAIL"
        css_class = "pass" if is_match else "fail"
        actual = "Accepted" if result["accepted"] else "Rejected"
        expected = "Accepted" if result["expected_accepted"] else "Rejected"
        screenshot_link = (
            f"<a href='#case-{case_number:03d}'>View evidence</a>"
            if screenshot_url
            else "&mdash;"
        )
        rows.append(
            f"<tr class='{css_class}'>"
            f"<td>{case_number:03d}</td>"
            f"<td>{html.escape(result['source_filename'])}</td>"
            f"<td>{html.escape(result['uploaded_filename'])}</td>"
            f"<td>{html.escape(result['sme_username'])}</td>"
            f"<td>{expected}</td><td>{actual}</td><td>{status}</td>"
            f"<td>{html.escape(result.get('message') or '')}</td>"
            f"<td>{screenshot_link}</td></tr>"
        )
        focused_evidence = (
            "<div class='focused-evidence'><h3>Focused product evidence</h3>"
            f"<img src='{focused_screenshot_url}' alt='Focused validation evidence "
            f"for case {case_number:03d}'></div>"
            if focused_screenshot_url
            else ""
        )
        context_evidence = (
            "<div class='context-evidence'><h3>Viewport context</h3>"
            f"<img src='{screenshot_url}' alt='Validation context for case "
            f"{case_number:03d}'></div>"
            if screenshot_url
            else "<p class='missing-evidence'>Screenshot was not produced.</p>"
        )
        evidence_cards.append(
            f"<section class='case-card {css_class}' id='case-{case_number:03d}'>"
            f"<div class='case-heading'><h2>Case {case_number:03d}: "
            f"{html.escape(result['source_filename'])}</h2>"
            f"<span class='result-badge'>{status}</span></div>"
            "<div class='case-meta'>"
            f"<div><b>Uploaded name</b><br>{html.escape(result['uploaded_filename'])}</div>"
            f"<div><b>SME user</b><br>{html.escape(result['sme_username'])}</div>"
            f"<div><b>Expected</b><br>{expected}</div>"
            f"<div><b>Actual</b><br>{actual}</div></div>"
            f"<p class='validation-message'><b>Validation message:</b> "
            f"{html.escape(result.get('message') or '')}</p>"
            f"<p class='evidence-text'><b>Product evidence:</b> "
            f"{html.escape(result.get('evidence_text') or '')}</p>"
            f"<div class='evidence-image'>{focused_evidence}{context_evidence}</div>"
            "</section>"
        )

    missing = expected_count - len(by_number)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        """<!doctype html>
<html><head><meta charset="utf-8"><title>Image Moderation Upload Report</title>
<style>
body{font-family:Arial,sans-serif;margin:24px;background:#f5f7fa;color:#172033}
h1{margin-bottom:8px}.summary{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}
.card{background:white;border:1px solid #d8dee9;border-radius:8px;padding:12px 18px}
table{width:100%;border-collapse:collapse;background:white;font-size:13px}
th,td{border:1px solid #d8dee9;padding:9px;text-align:left;vertical-align:top}
th{background:#eaf0f8;position:sticky;top:0}.pass td:nth-child(7){color:#087443;font-weight:bold}
.fail td:nth-child(7),.missing{color:#b42318;font-weight:bold}
td:nth-child(8){max-width:420px;word-break:break-word}.evidence-pages{margin-top:32px}
.case-card{background:#fff;border:1px solid #d8dee9;border-radius:10px;padding:18px;margin:20px auto;max-width:1200px}
.case-heading{display:flex;justify-content:space-between;align-items:center;gap:16px}.case-heading h2{margin:0}
.result-badge{font-weight:700;padding:6px 12px;border-radius:16px;background:#e7f7ef;color:#087443}
.case-card.fail .result-badge{background:#fdecec;color:#b42318}
.case-meta{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}
.case-meta div{background:#f6f8fb;border-radius:6px;padding:9px}
.validation-message{background:#f6f8fb;padding:10px;border-radius:6px}
.evidence-text{background:#eef6ff;padding:10px;border-radius:6px}
.evidence-image{text-align:center}.evidence-image h3{font-size:14px;margin:10px 0 5px}.evidence-image img{max-width:100%;max-height:720px;object-fit:contain;border:1px solid #ccd4df}
.focused-evidence img{max-height:90px}.context-evidence img{max-height:620px}
.missing-evidence{color:#b42318;font-weight:bold}
@media print{
  @page{size:A4 landscape;margin:10mm}
  body{margin:0;background:#fff;font-size:9pt}.summary-page{break-after:page}.summary{gap:6px;margin:8px 0}
  .card{padding:6px 10px}table{font-size:7.5pt}th,td{padding:4px}.evidence-pages{margin:0}
  .case-card{box-sizing:border-box;width:100%;max-width:none;height:185mm;margin:0 !important;padding:8mm;border:none;border-radius:0;break-before:page;page-break-before:always;break-after:auto;page-break-after:auto;overflow:hidden;position:relative;left:0}
  .case-heading h2{font-size:16pt}.case-meta{margin:4mm 0}.case-meta div{padding:3mm}
  .validation-message,.evidence-text{margin:2mm 0;padding:2mm}.evidence-image h3{font-size:10pt;margin:1.5mm 0 1mm}
  .focused-evidence img{max-width:100%;max-height:14mm;object-fit:contain}.context-evidence img{max-width:100%;max-height:108mm;object-fit:contain}
}
</style></head><body>"""
        + "<section class='summary-page'>"
        + f"<h1>Image Moderation Upload Report</h1><p>Run: {html.escape(run_dir.name)}</p>"
        + "<div class='summary'>"
        + f"<div class='card'><b>Expected</b><br>{expected_count}</div>"
        + f"<div class='card'><b>Produced</b><br>{len(by_number)}</div>"
        + f"<div class='card'><b>Matched</b><br>{matched}</div>"
        + f"<div class='card'><b>Accepted</b><br>{accepted}</div>"
        + f"<div class='card'><b>Rejected</b><br>{rejected}</div>"
        + f"<div class='card'><b>Missing</b><br>{missing}</div></div>"
        + "<table><thead><tr><th>#</th><th>Source image</th><th>Uploaded name</th>"
        + "<th>SME user</th><th>Expected</th><th>Actual</th><th>Result</th>"
        + "<th>Validation message</th><th>Screenshot</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></section><main class='evidence-pages'>"
        + "".join(evidence_cards)
        + "</main></body></html>",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output_path),
                "expected": expected_count,
                "produced": len(by_number),
                "matched": matched,
                "accepted": accepted,
                "rejected": rejected,
                "missing": missing,
            },
            sort_keys=True,
        )
    )
    return 0 if missing == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("output_path")
    parser.add_argument("--expected-count", type=int, default=22)
    args = parser.parse_args()
    raise SystemExit(render_report(args.run_dir, args.output_path, args.expected_count))


if __name__ == "__main__":
    main()
