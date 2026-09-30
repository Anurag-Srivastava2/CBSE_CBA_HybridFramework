"""Number-free pure-intent paraphrases in Mathematics.

Every earlier Maths pair carried a numeric anchor - 0 of 10 in the last retest
were number-free - so we could not tell whether the Maths failures came from
the subject's configuration or from removing the digits the matcher leans on.
These 10 pairs contain no numeral and no number word anywhere, in either side.

Shapes (CH-2) is the vehicle because rolling/sliding/flat/curved questions are
naturally quantity-free, and the chapter is fresh - no earlier sheet used it.

Built against the template downloaded today, resolved through its DEFINED NAMES
rather than fixed column numbers: the new template is 238 columns wide against
the old 220, so every hard-coded index has moved.

All 10 pairs are the same question reworded with the same answer, so all 10
must be flagged as duplicates.
"""
import json
import re
from pathlib import Path

from openpyxl import load_workbook

from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")
TEMPLATE = Path("data/upload_templates/sme_sheet_science.xlsx")

CURRICULUM = {
    "grade": "Grade 1", "subject": "Mathematics", "book": "Book 1", "unit": None,
    "chapter": "CH-2: What is Long? What is Round? (Shapes)",
}
BLOOM_EXP = "The learner observes and describes how a shape behaves and what its surface is like."

NUMBER = (r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
          r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
          r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|first|second|third)\b")


def _shapes_curriculum():
    """Grade 1 Mathematics shapes competency + its LOs, via defined names."""
    wb = load_workbook(TEMPLATE)
    ws = wb["Items"]

    def vals(name):
        ref = wb.defined_names[name].value.split("!")[1].replace("$", "")
        return [c.value for r in ws[ref] for c in r if c.value is not None]

    grades = vals("Grades")
    gi = grades.index(CURRICULUM["grade"]) + 1
    subjects = vals(f"G{gi}_Subjects")
    si = subjects.index(CURRICULUM["subject"]) + 1
    comps = vals(f"G{gi}_S{si}_Competencies")
    ci = next(i for i, c in enumerate(comps, start=1)
              if c.startswith("Recognises basic geometric"))
    los = vals(f"G{gi}_S{si}_C{ci}_LOs")
    chapters = vals(f"G{gi}_S{si}_B1_Chapters")
    wb.close()
    if CURRICULUM["chapter"] not in chapters:
        raise SystemExit(f"{CURRICULUM['chapter']!r} not in {chapters}")
    return comps[ci - 1], los


COMP, LOS = _shapes_curriculum()
LO_DESC = next(l for l in LOS if l.startswith("Observes and describes"))
LO_SORT = next(l for l in LOS if l.startswith("Sorts, classifies"))

# typology, (lo), blooms, marks, A, B, answer, explanation, options
PAIRS = [
    ("Very Short Answer Question", LO_DESC, "Understanding", "1",
     "Which shape rolls when it is pushed along the floor?",
     "An object moves by rolling when it is pushed. What kind of shape does it have?",
     "A round shape", "Round shapes have a curved surface, so they roll.", None),
    ("Short Answer Question", LO_DESC, "Understanding", "2",
     "Why does a box not roll on the ground?",
     "Explain the reason a box stays still instead of rolling when it is pushed.",
     "Because it has flat faces instead of a curved surface.",
     "Flat faces stop an object rolling.", None),
    ("Very Short Answer Question", LO_DESC, "Analysing", "1",
     "Name the feature a ball has but a brick does not.",
     "What does a ball possess that is absent in a brick?",
     "A curved surface", "The curved surface is what separates the two.", None),
    ("Short Answer Question", LO_SORT, "Applying", "2",
     "How can you sort objects into rolling and sliding groups?",
     "Describe a way of putting things into separate sets, those that roll and those that slide.",
     "Push each object and see whether it rolls or slides, then put it in the matching group.",
     "Testing each object and grouping by the result is the expected method.", None),
    ("True or False", LO_DESC, "Understanding", "1",
     "A ball has flat faces.",
     "The surface of a ball is made up of flat sides.",
     "FALSE", "A ball is curved all over and has no flat faces.", None),
    ("Very Short Answer Question", LO_DESC, "Remembering", "1",
     "Name a shape that can slide but not roll.",
     "Which shape moves by sliding while being unable to roll?",
     "A box", "A box has flat faces, so it slides rather than rolls.", None),
    ("Fill in the Blank", LO_DESC, "Understanding", "1",
     "A ball is round all over, so we say its surface is ____.",
     "The surface of a ball, being round everywhere, is described as ____.",
     "curved", "A surface that is round all over is a curved surface.", None),
    ("Short Answer Question", LO_DESC, "Applying", "2",
     "Explain how you would tell a round object from a flat-sided object without looking.",
     "Describe how touch alone could tell you whether an object is round or has flat sides.",
     "Feel the surface; a round object feels smooth and curved all over, while a flat-sided one has edges and corners.",
     "Edges and corners can be felt, so touch distinguishes the two.", None),
    ("True or False", LO_DESC, "Analysing", "1",
     "Objects with corners can roll easily.",
     "Rolling comes easily to things that have corners.",
     "FALSE", "Corners stop an object rolling smoothly.", None),
    ("Multiple Choice Question", LO_DESC, "Applying", "1",
     "Which of these would roll down a slope?",
     "If these objects were set on a ramp, which would travel by rolling?",
     "A ball", "Only the ball has a curved surface, so only it rolls.",
     ["A ball", "A book", "A box", "A brick"]),
]


def rows_for(side):
    out = []
    for i, (typ, lo, blooms, marks, qa, qb, ans, exp, opts) in enumerate(PAIRS, start=1):
        out.append(row(str(i), typ, COMP, lo, blooms, BLOOM_EXP, marks,
                       qb if side == "B" else qa,
                       answer=ans, explanation=exp, options=opts))
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ma = build_sheet(rows_for("A"), "A", OUTPUT_DIR / "sheet_MA_numberfree.xlsx",
                     TEMPLATE, CURRICULUM, {})
    mb = build_sheet(rows_for("B"), "A", OUTPUT_DIR / "sheet_MB_numberfree.xlsx",
                     TEMPLATE, CURRICULUM, {})
    tok = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))
    spec, bad = [], []
    for i, (typ, lo, blooms, marks, qa, qb, ans, exp, opts) in enumerate(PAIRS, start=1):
        ov = len(tok(qa) & tok(qb)) / len(tok(qa) | tok(qb))
        free = not (re.search(NUMBER, qa, re.I) or re.search(NUMBER, qb, re.I))
        if not free:
            bad.append(str(i))
        spec.append({"sno": str(i), "typology": typ, "A": qa, "B": qb, "answer": ans,
                     "overlap": round(ov, 2), "number_free": free, "expect": "FLAG"})
    (OUTPUT_DIR / "spec_number_free.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"MA: {ma}\nMB: {mb}   ({len(PAIRS)} pairs)\n")
    print(f"{'#':>3} {'typology':<26} {'ovl':>5} {'num-free':>9}")
    for s in spec:
        print(f"{s['sno']:>3} {s['typology']:<26} {s['overlap']:>5.2f} {str(s['number_free']):>9}")
    print(f"\nmean overlap {sum(s['overlap'] for s in spec)/len(spec):.2f}")
    print("rows containing a number (must be none):", bad or "none")


if __name__ == "__main__":
    main()
