"""Second post-deployment retest: same design as build_retest_today.py, fresh
content on CH-9 (Patterns) since the bank now holds the CH-7 items from the
previous retest and re-uploading those would be rejected as exact duplicates
or trivially self-match.

Same controlled comparison: 5 numeric-anchored pairs vs 5 number-free pairs,
matched on paraphrase distance, so any gap between groups is attributable to
the presence of numbers rather than to difficulty.

All 10 pairs keep the same answer, so all 10 must be flagged as duplicates.
"""
import json
import re
from pathlib import Path

from openpyxl import load_workbook

from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")
TEMPLATE = Path("data/upload_templates/sme_sheet_r2.xlsx")

CURRICULUM = {
    "grade": "Grade 1", "subject": "Mathematics", "book": "Book 1", "unit": None,
    "chapter": "CH-9: Utsav (Patterns)",
}
BLOOM_EXP = "The learner identifies and extends a simple repeating pattern."

NUMBER = (r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
          r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
          r"half|first|second|third|fourth)\b")


def _pattern_lo():
    wb = load_workbook(TEMPLATE)
    ws = wb["Items"]

    def vals(name):
        ref = wb.defined_names[name].value.split("!")[1].replace("$", "")
        cells = ws[ref]
        if not isinstance(cells, tuple):
            cells = (cells,)
        return [c.value for row_ in cells
                for c in (row_ if isinstance(row_, tuple) else (row_,)) if c.value is not None]

    gi = vals("Grades").index(CURRICULUM["grade"]) + 1
    si = vals(f"G{gi}_Subjects").index(CURRICULUM["subject"]) + 1
    comps = vals(f"G{gi}_S{si}_Competencies")
    ci = next(i for i, c in enumerate(comps, start=1)
              if c.startswith("Identifies and extends simple patterns"))
    los = vals(f"G{gi}_S{si}_C{ci}_LOs")
    chapters = vals(f"G{gi}_S{si}_B1_Chapters")
    wb.close()
    if CURRICULUM["chapter"] not in chapters:
        raise SystemExit(f"{CURRICULUM['chapter']!r} not in {chapters}")
    return comps[ci - 1], los[0]


COMP, LO = _pattern_lo()

# kind, typology, blooms, marks, A, B, answer, explanation, options
PAIRS = [
    ("numeric", "Fill in the Blank", "Applying", "1",
     "In the pattern 2, 4, 6, 8, ____, the missing number is next.",
     "Following the sequence two, four, six, eight, ____, what number comes next.",
     "10", "The pattern adds 2 each time, so after 8 comes 10.", None),
    ("numeric", "Multiple Choice Question", "Applying", "1",
     "A pattern goes 5, 10, 15, 20. What comes after 20?",
     "Looking at the sequence five, ten, fifteen, twenty, work out which number should be written next.",
     "25", "The pattern adds 5 each time, so after 20 comes 25.", ["22", "23", "24", "25"]),
    ("numeric", "Very Short Answer Question", "Understanding", "1",
     "In the pattern 3, 6, 9, 12, how many numbers come before 12?",
     "Counting the terms three, six, nine, twelve, how many numbers appear before twelve.",
     "3", "3, 6 and 9 come before 12, which is 3 numbers.", None),
    ("numeric", "True or False", "Analysing", "1",
     "The pattern 4, 8, 12, 16 adds 4 each time, so the 5th number is 20.",
     "Since the sequence four, eight, twelve, sixteen grows by four each step, the fifth term is twenty.",
     "TRUE", "16 plus 4 makes 20, so the fifth number is 20.", None),
    ("numeric", "Short Answer Question", "Applying", "2",
     "Explain how you would find the 6th number in the pattern 1, 3, 5, 7, 9.",
     "A student wants to continue the sequence one, three, five, seven, nine one more step. Describe how the next term is found.",
     "The pattern adds 2 each time, so after 9 the sixth number is 11.",
     "Extending the pattern by the same step gives the next term.", None),

    ("number-free", "True or False", "Understanding", "1",
     "A pattern of red, blue, red, blue always repeats the same colours in order.",
     "Whichever colour begins a red, blue, red, blue sequence keeps reappearing at that same spot as the sequence carries on.",
     "TRUE", "The pattern cycles between the same colours in order.", None),
    ("number-free", "Very Short Answer Question", "Understanding", "1",
     "In a pattern of circle, square, circle, square, which shape comes after a circle?",
     "Following a sequence of circle, square, circle, square, what shape follows a circle?",
     "A square", "The pattern alternates circle and square.", None),
    ("number-free", "Fill in the Blank", "Applying", "1",
     "Look at the pattern: big, small, big, small. The next shape should be ____.",
     "In a sequence that goes large, tiny, large, tiny, what should come right after is ____.",
     "big", "The pattern alternates between big and small.", None),
    ("number-free", "Short Answer Question", "Analysing", "2",
     "Explain the rule of the pattern star, moon, star, moon, star.",
     "Describe what rule the sequence star, moon, star, moon, star is following.",
     "The pattern repeats star and moon turn by turn.",
     "Identifying the repeating unit is the expected answer.", None),
    ("number-free", "Multiple Choice Question", "Understanding", "1",
     "Which shape completes the pattern triangle, circle, triangle, circle, ____?",
     "Look at how the shapes triangle and circle keep swapping places in turn. Choose whichever shape belongs at the end.",
     "Triangle", "The pattern alternates triangle and circle.",
     ["Triangle", "Circle", "Square", "Star"]),
]


def rows_for(side):
    out = []
    for i, (kind, typ, blooms, marks, qa, qb, ans, exp, opts) in enumerate(PAIRS, start=1):
        out.append(row(str(i), typ, COMP, LO, blooms, BLOOM_EXP, marks,
                       qb if side == "B" else qa,
                       answer=ans, explanation=exp, options=opts))
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pa = build_sheet(rows_for("A"), "A", OUTPUT_DIR / "sheet_PA_r2.xlsx", TEMPLATE, CURRICULUM, {})
    pb = build_sheet(rows_for("B"), "A", OUTPUT_DIR / "sheet_PB_r2.xlsx", TEMPLATE, CURRICULUM, {})
    tok = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))
    spec, wrong = [], []
    for i, (kind, typ, blooms, marks, qa, qb, ans, exp, opts) in enumerate(PAIRS, start=1):
        ov = len(tok(qa) & tok(qb)) / len(tok(qa) | tok(qb))
        free = not (re.search(NUMBER, qa, re.I) or re.search(NUMBER, qb, re.I))
        if (kind == "number-free") != free:
            wrong.append(f"{i} tagged {kind} but number_free={free}")
        spec.append({"sno": str(i), "kind": kind, "typology": typ, "A": qa, "B": qb,
                     "answer": ans, "overlap": round(ov, 2), "number_free": free, "expect": "FLAG"})
    (OUTPUT_DIR / "spec_retest_r2.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PA: {pa}\nPB: {pb}   ({len(PAIRS)} pairs)\n")
    for s in spec:
        print(f"{s['sno']:>3} {s['kind']:<12} {s['typology']:<26} {s['overlap']:>5.2f} num-free={s['number_free']}")
    for k in ("numeric", "number-free"):
        v = [s["overlap"] for s in spec if s["kind"] == k]
        print(f"  {k:<12} mean overlap {sum(v)/len(v):.2f}")
    print("tag mismatches:", wrong or "none")


if __name__ == "__main__":
    main()
