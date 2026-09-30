"""Duplicate-evasion probe: 5 questions for each of four routes, one sheet.

All rows sit in CH-8 (numbers 21-99) so they can share a single upload, and
all four routes are measured against the same bank baseline IS1335 (A2).

  rows  1-5      SOURCES - fresh questions, should come back clean. They exist
                 so route 1 has something inside this sheet to duplicate.
  rows  6-10     ROUTE 1  intra-sheet duplicate: each duplicates a row above it
                 IN THIS SAME FILE. Never tested - we have only ever compared
                 against the bank, so a sheet that repeats itself may sail through.
  rows 11-15     ROUTE 2  cross-typology: a bank question re-asked under a
                 different typology. The commonest way a bank gets padded.
  rows 16-20     ROUTE 3  inverse phrasing: the same fact stated the other way
                 round ("1 less than 70" -> "70 is 1 more than which number?").
                 Same answer, so the same item.
  row  21 + 21.1-21.5
                 ROUTE 4  sub-question duplication: Case Based sub-questions
                 that duplicate bank items. Tests whether the checker looks
                 inside CABA/SBQ children at all.

Every row from 6 onwards is a duplicate of something and MUST be flagged.
Rows 1-5 must not be.
"""
import json
from pathlib import Path

from tools.build_maths_regression_v2 import ARR, BLOOM_EXP, CURRICULUM, FB, TEMPLATE, TENS
from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")

# (sno, route, duplicate-of, typology, (comp, lo), blooms, marks,
#  question, answer, explanation, options)
SPEC = [
    # ---------------- SOURCES (must stay clean) ----------------
    ("1", "source", "-", "True or False", TENS, "Understanding", "1",
     "There are 9 ones in the number 39.", "TRUE",
     "39 is three tens and nine ones, so it has 9 ones.", None),
    ("2", "source", "-", "Multiple Choice Question", FB, "Applying", "1",
     "How many numbers come between 61 and 65?", "3",
     "62, 63 and 64 lie between 61 and 65, which is 3 numbers.", ["2", "3", "4", "5"]),
    ("3", "source", "-", "Fill in the Blank", TENS, "Applying", "1",
     "The number that is 20 more than 45 is ____.", "65",
     "Adding two tens to 45 gives 65.", None),
    ("4", "source", "-", "Very Short Answer Question", TENS, "Understanding", "1",
     "Write the smallest number that has 7 tens.", "70",
     "Seven tens and no ones is 70.", None),
    ("5", "source", "-", "Short Answer Question", TENS, "Understanding", "2",
     "Explain how you would show the number 47 using tens and ones.",
     "Four tens and seven ones make 47.",
     "Splitting into tens and ones is the expected method.", None),

    # ---------------- ROUTE 1: intra-sheet duplicate ----------------
    ("6", "1 intra-sheet", "row 1", "True or False", TENS, "Understanding", "1",
     "The number 39 contains 9 ones.", "TRUE",
     "39 is three tens and nine ones, so it has 9 ones.", None),
    ("7", "1 intra-sheet", "row 2", "Multiple Choice Question", FB, "Applying", "1",
     "Between 61 and 65, how many numbers lie?", "3",
     "62, 63 and 64 lie between 61 and 65, which is 3 numbers.", ["2", "3", "4", "5"]),
    ("8", "1 intra-sheet", "row 3", "Fill in the Blank", TENS, "Applying", "1",
     "20 more than 45 gives ____.", "65",
     "Adding two tens to 45 gives 65.", None),
    ("9", "1 intra-sheet", "row 4", "Very Short Answer Question", TENS, "Understanding", "1",
     "What is the smallest number having 7 tens?", "70",
     "Seven tens and no ones is 70.", None),
    ("10", "1 intra-sheet", "row 5", "Short Answer Question", TENS, "Understanding", "2",
     "Explain how the number 47 can be shown as tens and ones.",
     "Four tens and seven ones make 47.",
     "Splitting into tens and ones is the expected method.", None),

    # ---------------- ROUTE 2: cross-typology ----------------
    ("11", "2 cross-typology", "A2-i4 (was VSAQ)", "Multiple Choice Question", FB, "Understanding", "1",
     "Which number comes between 45 and 47?", "46",
     "46 sits between 45 and 47 in counting order.", ["44", "45", "46", "47"]),
    ("12", "2 cross-typology", "A2-i2 (was MCQ)", "Fill in the Blank", FB, "Remembering", "1",
     "The number that comes just after 57 is ____.", "58",
     "Counting order runs 57, 58, so 58 comes just after 57.", None),
    ("13", "2 cross-typology", "A2-i3 (was FITB)", "Very Short Answer Question", FB, "Understanding", "1",
     "When counting backward from 72, which number comes next?", "71",
     "Counting back from 72 gives 71.", None),
    ("14", "2 cross-typology", "A2-i9 (was VSAQ)", "True or False", TENS, "Understanding", "1",
     "There are 5 tens in the number 50.", "TRUE",
     "50 is five groups of ten.", None),
    ("15", "2 cross-typology", "A2-i8 (was FITB)", "Multiple Choice Question", TENS, "Understanding", "1",
     "In the number 76, what does the digit 7 stand for?", "7 tens",
     "The tens place of 76 holds 7, so it stands for 7 tens.",
     ["7 ones", "7 tens", "6 tens", "70 tens"]),

    # ---------------- ROUTE 3: inverse phrasing ----------------
    ("16", "3 inverse", "A2-i19", "Very Short Answer Question", FB, "Understanding", "1",
     "70 is 1 more than which number?", "69",
     "Counting back one from 70 gives 69.", None),
    ("17", "3 inverse", "A2-i14", "Very Short Answer Question", TENS, "Applying", "1",
     "47 is 10 less than which number?", "57",
     "Adding ten to 47 gives 57.", None),
    ("18", "3 inverse", "A2-i16", "True or False", ARR, "Analysing", "1",
     "92 has fewer tens than 29.", "FALSE",
     "92 has 9 tens and 29 has 2 tens, so 92 has more.", None),
    ("19", "3 inverse", "A2-i13", "Fill in the Blank", FB, "Understanding", "1",
     "40 comes just after ____.", "39",
     "Counting order runs 39, 40, so 39 comes just before 40.", None),
    ("20", "3 inverse", "A2-i12", "Multiple Choice Question", FB, "Applying", "1",
     "Counting back by tens from 90, 60 is which number in the count?", "third",
     "Counting back by tens gives 80, 70, 60, so 60 is the third.",
     ["first", "second", "third", "fourth"]),

    # ---------------- ROUTE 4: sub-questions duplicating bank items ----------------
    ("21", "4 sub-question", "-", "Case Based Question", FB, "Understanding", "5",
     "Ishita is practising with two-digit numbers in her workbook.", None,
     "The case sets up five practice questions.", None),
    ("21.1", "4 sub-question", "A2-i2", "Multiple Choice Question", FB, "Remembering", "1",
     "Which number follows straight after 57?", "58",
     "Counting order runs 57, 58, so 58 comes just after 57.", ["56", "57", "58", "59"]),
    ("21.2", "4 sub-question", "A2-i3", "Fill in the Blank", FB, "Understanding", "1",
     "Counting back from 72, the next number is ____.", "71",
     "Counting back from 72 gives 71.", None),
    ("21.3", "4 sub-question", "A2-i9", "Very Short Answer Question", TENS, "Understanding", "1",
     "How many tens does 50 contain?", "5",
     "50 is five groups of ten.", None),
    ("21.4", "4 sub-question", "A2-i1", "True or False", FB, "Understanding", "1",
     "Anaya counts forward from 34 and the next number she says is 35.", "TRUE",
     "Counting forward from 34 gives 35.", None),
    ("21.5", "4 sub-question", "A2-i10", "Short Answer Question", ARR, "Analysing", "1",
     "Describe how you know 63 is larger than 36.",
     "63 has 6 tens and 36 has 3 tens, and more tens means the greater number.",
     "Comparing the tens place first is the expected method.", None),
]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, spec = [], []
    for sno, route, dup_of, typ, (comp, lo), blooms, marks, q, a, e, opts in SPEC:
        rows.append(row(sno, typ, comp, lo, blooms, BLOOM_EXP, marks, q,
                        answer=a, explanation=e, options=opts))
        spec.append({"sno": sno, "route": route, "duplicate_of": dup_of,
                     "typology": typ, "question": q, "answer": a,
                     "expect": "CLEAN" if route == "source" else
                               ("n/a (parent)" if typ == "Case Based Question" else "FLAG")})
    target = build_sheet(rows, "A", OUTPUT_DIR / "sheet_G_evasion.xlsx",
                         TEMPLATE, CURRICULUM, {})
    (OUTPUT_DIR / "spec_G_evasion.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(f"Sheet G: {target}  ({len(rows)} rows)")
    for route, n in sorted(Counter(s["route"] for s in spec).items()):
        print(f"   {route:<20} {n}")


if __name__ == "__main__":
    main()
