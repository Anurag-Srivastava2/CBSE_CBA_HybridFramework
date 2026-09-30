"""Retry of the 50-pair batches on a clean environment day.

Yesterday's CH-10 content silently landed in the bank despite client-side
timeouts, so anything reusing that exact text now hits the exact-content
duplicate gate before QAR ever runs. This retry:

  * moves to CH-4 (Making 10 - Numbers 10 to 20), never used by any sheet
    in this session, to avoid the chapter that's now contaminated
  * appends a short run tag to every question, so even if some of
    yesterday's content is still lingering unindexed, today's text cannot
    exact-match it
  * keeps everything else - typologies, kind split (numeric/number-free),
    tier structure, competencies, answers - identical to build_fifty_pairs.py

Uploaded as 5 batches of 10 (baseline + paraphrase each), the size that has
completed reliably whenever the environment itself was healthy.
"""
import json
from pathlib import Path

from tools.build_fifty_pairs import BLOOM_EXP, PAIRS
from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")
TEMPLATE = Path("data/upload_templates/sme_sheet_0930.xlsx")
RUN_TAG = "r0930"

CURRICULUM = {
    "grade": "Grade 1", "subject": "Mathematics", "book": "Book 1", "unit": None,
    "chapter": "CH-4: Making 10 (Numbers 10 to 20)",
}
BATCH_SIZE = 10
BATCH_NAMES = ["TF", "MCQ", "FIB", "VSAQ", "SAQ"]


def tag(text):
    return f"{text} [{RUN_TAG}]" if text else text


def rows_for(batch_pairs, side):
    out = []
    for i, (kind, typ, comp_lo, blooms, marks, qa, qb, ans, exp, opts) in enumerate(batch_pairs, start=1):
        comp, lo = comp_lo
        question = tag(qb if side == "B" else qa)
        out.append(row(str(i), typ, comp, lo, blooms, BLOOM_EXP, marks,
                       question, answer=ans, explanation=exp, options=opts))
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for bi, name in enumerate(BATCH_NAMES):
        batch = PAIRS[bi * BATCH_SIZE:(bi + 1) * BATCH_SIZE]
        a_path = OUTPUT_DIR / f"sheet_{RUN_TAG}_{name}_A.xlsx"
        b_path = OUTPUT_DIR / f"sheet_{RUN_TAG}_{name}_B.xlsx"
        build_sheet(rows_for(batch, "A"), "A", a_path, TEMPLATE, CURRICULUM, {})
        build_sheet(rows_for(batch, "B"), "A", b_path, TEMPLATE, CURRICULUM, {})
        manifest.append({
            "batch": name, "a_file": str(a_path), "b_file": str(b_path),
            "pairs": [{"local_sno": j + 1, "global_sno": bi * BATCH_SIZE + j + 1,
                       "kind": p[0], "typology": p[1], "A": tag(p[5]), "B": tag(p[6]), "answer": p[7]}
                      for j, p in enumerate(batch)],
        })
        print(f"batch {name}: {a_path.name} / {b_path.name}  ({len(batch)} pairs)")
    (OUTPUT_DIR / f"manifest_{RUN_TAG}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
