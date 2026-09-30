"""Split the 50-pair set into 5 batches of 10, since a single 50-item QAR
submission failed server-side twice in a row (POST /qar/run did not complete,
then a stalled pipeline with no progress indicator). 10-item batches have
completed reliably all session.

Reuses the exact same 50 pairs from build_fifty_pairs.py - same content, same
chapter, same curriculum - just uploaded as 5 baseline/paraphrase pairs of 10
rows each instead of one pair of 50. Batches split along the typology
boundaries already in PAIRS (10 True/False, 10 MCQ, 10 FITB, 10 VSAQ, 10 SAQ).
"""
import json
from pathlib import Path

from tools.build_fifty_pairs import BLOOM_EXP, CURRICULUM, PAIRS, TEMPLATE
from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")
BATCH_SIZE = 10
BATCH_NAMES = ["TF", "MCQ", "FIB", "VSAQ", "SAQ"]


def rows_for(batch_pairs, side):
    out = []
    for i, (kind, typ, comp_lo, blooms, marks, qa, qb, ans, exp, opts) in enumerate(batch_pairs, start=1):
        comp, lo = comp_lo
        out.append(row(str(i), typ, comp, lo, blooms, BLOOM_EXP, marks,
                       qb if side == "B" else qa, answer=ans, explanation=exp, options=opts))
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for bi, name in enumerate(BATCH_NAMES):
        batch = PAIRS[bi * BATCH_SIZE:(bi + 1) * BATCH_SIZE]
        a_path = OUTPUT_DIR / f"sheet_R{name}_A.xlsx"
        b_path = OUTPUT_DIR / f"sheet_R{name}_B.xlsx"
        build_sheet(rows_for(batch, "A"), "A", a_path, TEMPLATE, CURRICULUM, {})
        build_sheet(rows_for(batch, "B"), "A", b_path, TEMPLATE, CURRICULUM, {})
        manifest.append({
            "batch": name, "a_file": str(a_path), "b_file": str(b_path),
            "pairs": [{"local_sno": j + 1, "global_sno": bi * BATCH_SIZE + j + 1,
                       "kind": p[0], "typology": p[1], "A": p[5], "B": p[6], "answer": p[7]}
                      for j, p in enumerate(batch)],
        })
        print(f"batch {name}: {a_path.name} / {b_path.name}  ({len(batch)} pairs)")
    (OUTPUT_DIR / "manifest_fifty_batches.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
