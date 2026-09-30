"""Focused probe: changing ONLY the numbers must not be called a duplicate.

Sheet C3 is the A2 baseline with a third, distinct set of numbers. Every other
word is held identical, so the numbers are the only variable. These are
legitimately NEW practice items - an item bank is meant to hold 34->35 and
47->48 as separate questions - so ANY duplicate verdict here is a false
positive.

Two things are fixed relative to the earlier C2 sheet:
  * Item 7's stem now carries its numbers ("...largest: 28, 82, 38 or 85?").
    In C2 the numbers lived only in the options, so a numbers-only change left
    the question text byte-identical and scored 100% - which said nothing
    about number sensitivity.
  * Every number is distinct from BOTH A2 and C2, so a match cannot be
    explained by collision with the earlier variant.
"""
import json
from pathlib import Path

from openpyxl import load_workbook

from tools.build_maths_regression_v2 import CURRICULUM, TEMPLATE, PAIRS, BLOOM_EXP
from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")

# seq -> (question, answer, explanation, options) with a THIRD number set.
C3 = {
    1: ("Anaya counts forward from 47 and says 48 next.", "TRUE", "Counting forward from 47 gives 48.", None),
    2: ("Which number comes just after 25?", "26", "Counting order runs 25, 26, so 26 comes just after 25.", ["24", "25", "26", "27"]),
    3: ("Counting backward from 66, the next number is ____.", "65", "Counting back from 66 gives 65.", None),
    4: ("Write the number that comes between 31 and 33.", "32", "32 sits between 31 and 33 in counting order.", None),
    5: ("Explain how you would count aloud from 74 to 78.", "Say 74, 75, 76, 77, 78, moving on by one each time.", "Counting on by ones is the expected strategy.", None),
    6: ("Dev arranges 24, 42 and 37 from smallest to largest as 24, 37, 42.", "TRUE", "24 is smallest, then 37, then 42.", None),
    7: ("Which of these numbers is the largest: 28, 82, 38 or 85?", "85", "85 has 8 tens and 5 ones, which is the greatest of the four.", ["28", "82", "38", "85"]),
    8: ("In the number 94, the digit 9 stands for ____ tens.", "9", "The tens place of 94 holds 9, so it stands for 9 tens.", None),
    9: ("How many tens are there in 30?", "3", "30 is three groups of ten.", None),
    10: ("Describe how you can tell that 85 is greater than 58.", "85 has 8 tens and 58 has 5 tens, and more tens means the greater number.", "Comparing the tens place first is the expected method.", None),
    11: ("Counting in tens from 50, Ishita says 50, 60, 70, 80.", "TRUE", "Each jump of ten adds one to the tens digit.", None),
    12: ("Start at 80 and count back by tens. Which number comes third?", "50", "Counting back by tens gives 70, 60, 50, so the third is 50.", ["70", "60", "50", "40"]),
    13: ("The number just before 90 is ____.", "89", "Counting order runs 89, 90, so 89 comes just before 90.", None),
    14: ("Which number is 10 more than 35?", "45", "Adding ten raises the tens digit by one, so 35 becomes 45.", None),
    15: ("Explain how counting in tens from 40 helps you reach 90 quickly.", "Say 40, 50, 60, 70, 80, 90, which is five jumps of ten instead of counting one by one.", "Counting in tens is faster than counting in ones.", None),
    16: ("The number 46 has more tens than the number 64.", "FALSE", "46 has 4 tens and 64 has 6 tens, so 64 has more.", None),
    17: ("Which number sentence shows 36 split into tens and ones?", "30 + 6", "36 is three tens and six ones, which is 30 + 6.", ["30 + 6", "3 + 6", "36 + 10", "20 + 6"]),
    18: ("Rohan writes the number forty-seven in figures as ____.", "47", "Forty-seven written in figures is 47.", None),
    19: ("Which number is 1 less than 80?", "79", "Counting back one from 80 gives 79.", None),
    20: ("Tara says 83 comes before 72 when counting up. Explain why she is wrong.", "Counting up reaches 72 first, because 72 has 7 tens and 83 has 8 tens, so 72 is the smaller number.", "Comparing the tens place shows which number is reached first.", None),
}


def main():
    meta = {seq: (typ, cl, bl, mk, sides) for seq, _, typ, cl, bl, mk, *sides in
            [(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8]) for p in PAIRS]}
    rows, spec = [], []
    for seq in sorted(C3):
        typ, (comp, lo), bl, mk, sides = meta[seq]
        q, a, e, opts = C3[seq]
        a2_q = sides[0][0]
        # Item 7's stem was rewritten to carry its numbers; every other stem is
        # the A2 stem with different digits.
        rows.append(row(str(seq), typ, comp, lo, bl, BLOOM_EXP, mk, q,
                        answer=a, explanation=e, options=opts))
        spec.append({"seq": seq, "typology": typ, "A2": a2_q, "C3": q,
                     "expect": "NO_FLAG"})
    target = build_sheet(rows, "A", OUTPUT_DIR / "sheet_C3_numbers.xlsx",
                         TEMPLATE, CURRICULUM, {})
    (OUTPUT_DIR / "spec_C3_numbers.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"C3: {target} (20 rows, numbers-only change, all expect NO_FLAG)")


if __name__ == "__main__":
    main()
