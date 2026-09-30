"""Pure-intent paraphrase probe: no numbers, no shared entities.

Every earlier Maths pair carried a numeric anchor (0/10 were number-free), so
we could not tell whether the Maths failures were about the subject's
configuration or about losing the digits the matcher was leaning on. These
pairs remove numbers entirely.

Two groups, deliberately:

  L1-L4  the Science pairs supplied by the user, verbatim. There is no Science
         subject in the bank (only English/Hindi/Mathematics, Grades 1-3), so
         these are filed under Grade 1 Mathematics and are WILDLY off-syllabus.
         That is a second, free test: Metadata Alignment has only ever been
         observed passing, and has never been shown content that has nothing to
         do with its chapter.

  L5-L8  on-syllabus controls in the same style - Grade 1 shapes questions that
         are naturally number-free. If the Science pairs behave differently
         from these, the difference is content validity, not paraphrasing.

All 8 pairs are the same question reworded with the same answer, so all 8 must
be flagged as duplicates.
"""
import json
import re
from pathlib import Path

from openpyxl import load_workbook

from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")
TEMPLATE = Path("data/upload_templates/sme_sheet.xlsx")

CURRICULUM = {
    "grade": "Grade 1", "subject": "Mathematics", "book": "Book 1", "unit": None,
    "chapter": "CH-2: What is Long? What is Round? (Shapes)",
}
BLOOM_EXP = "The learner recalls or explains a property of the material studied."


def _shapes_curriculum():
    wb = load_workbook(TEMPLATE)
    ws = wb["Items"]
    comps = [ws.cell(row=r, column=111).value for r in range(2, 17)]
    idx = next(i for i, c in enumerate(comps) if c and c.startswith("Recognises basic geometric"))
    los = [ws.cell(row=r, column=114 + idx).value for r in range(2, ws.max_row + 1)
           if ws.cell(row=r, column=114 + idx).value]
    wb.close()
    return comps[idx], los


COMP, LOS = _shapes_curriculum()
LO_DESC = next(l for l in LOS if l.startswith("Observes and describes"))
LO_SORT = next(l for l in LOS if l.startswith("Sorts, classifies"))

# group, typology, marks, A, B, answer, explanation
PAIRS = [
    ("science", "Very Short Answer Question", "1",
     "What happens to a solid when it is heated enough to change into a liquid?",
     "Name the process in which a solid turns into a liquid on heating.",
     "Melting", "A solid becomes a liquid on heating, and that process is melting."),
    ("science", "Very Short Answer Question", "1",
     "Which indicator turns red in an acidic solution and blue in a basic solution?",
     "What is the name of the substance that changes from blue to red when it comes into contact with an acid?",
     "Litmus", "Litmus is the indicator that turns red in acid and blue in base."),
    ("science", "Very Short Answer Question", "1",
     "How does heat travel through a metal spoon placed in hot tea?",
     "By which mode of heat transfer does a metal rod get hot at the other end when one end is heated?",
     "Conduction", "Heat passes through a solid metal by conduction."),
    ("science", "Very Short Answer Question", "1",
     "Which gas do we breathe in that our body needs to release energy from food?",
     "What is the gas taken in during breathing that is used in respiration to produce energy?",
     "Oxygen", "Oxygen is taken in during breathing and used in respiration."),

    ("control", "Very Short Answer Question", "1",
     "Which shape rolls when it is pushed along the floor?",
     "An object moves by rolling when it is pushed. What kind of shape does it have?",
     "A round shape", "Round shapes have a curved surface, so they roll."),
    ("control", "Short Answer Question", "2",
     "Why does a box not roll on the ground?",
     "Explain the reason a box stays still instead of rolling when it is pushed.",
     "Because it has flat faces instead of a curved surface.",
     "Flat faces stop an object rolling."),
    ("control", "Short Answer Question", "2",
     "Which part of a ball makes it different from a brick?",
     "Describe what a ball has that a brick does not.",
     "A ball has a curved surface all over, while a brick has flat faces.",
     "The curved surface is the difference between the two."),
    ("control", "Short Answer Question", "2",
     "How can you sort objects into rolling and sliding groups?",
     "Describe a way of putting things into two sets, those that roll and those that slide.",
     "Push each object and see whether it rolls or slides, then put it in the matching group.",
     "Testing each object and grouping by the result is the expected method."),
]


def rows_for(side):
    out = []
    for i, (group, typ, marks, qa, qb, ans, exp) in enumerate(PAIRS, start=1):
        lo = LO_SORT if group == "control" and i == 8 else LO_DESC
        out.append(row(str(i), typ, COMP, lo, "Remembering" if typ.startswith("Very") else "Understanding",
                       BLOOM_EXP, marks, qb if side == "B" else qa,
                       answer=ans, explanation=exp))
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    la = build_sheet(rows_for("A"), "A", OUTPUT_DIR / "sheet_LA_pure_intent.xlsx",
                     TEMPLATE, CURRICULUM, {})
    lb = build_sheet(rows_for("B"), "A", OUTPUT_DIR / "sheet_LB_pure_intent.xlsx",
                     TEMPLATE, CURRICULUM, {})
    tok = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))
    NUM = r"\d|one|two|three|four|five|six|seven|eight|nine|ten"
    spec = []
    for i, (group, typ, marks, qa, qb, ans, exp) in enumerate(PAIRS, start=1):
        ov = len(tok(qa) & tok(qb)) / len(tok(qa) | tok(qb))
        spec.append({"sno": str(i), "group": group, "typology": typ, "A": qa, "B": qb,
                     "answer": ans, "overlap": round(ov, 2),
                     "number_free": not (re.search(NUM, qa, re.I) or re.search(NUM, qb, re.I)),
                     "expect": "FLAG"})
    (OUTPUT_DIR / "spec_pure_intent.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"LA: {la}\nLB: {lb}   ({len(PAIRS)} pairs)\n")
    print(f"{'#':>3} {'group':<8} {'ovl':>5} {'num-free':>9}  A")
    for s in spec:
        print(f"{s['sno']:>3} {s['group']:<8} {s['overlap']:>5.2f} {str(s['number_free']):>9}  {s['A'][:62]}")
    print(f"\nmean overlap {sum(s['overlap'] for s in spec)/len(spec):.2f}")
    print(f"number-free: {sum(s['number_free'] for s in spec)}/{len(spec)}")


if __name__ == "__main__":
    main()
