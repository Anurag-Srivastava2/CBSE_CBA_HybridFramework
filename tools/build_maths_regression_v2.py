"""Post-fix Maths regression: fresh content, identical experimental structure.

The QA bank already holds all 124 items from the pre-fix run, so re-uploading
the original sheets proves nothing - every question would match its own prior
copy, and the exact-text gate would reject most of them at upload anyway.

This rebuilds the same experiment on content the bank has never seen:
chapter CH-8 (numbers 21-99) instead of CH-6 (add/sub under 20), counting and
place-value instead of vegetables, and names that appear in none of the earlier
sheets. Every relationship the experiment depends on is preserved - the four
paraphrase tiers, the numbers-only C side, and the adversarial transformations.

Sheets produced:
  A2 baseline      - 20 mutually distinct originals; MUST come back clean
  B2 paraphrases   - 4 tiers x 5; tiers 3-4 were the false negatives
  C2 numbers-only  - genuinely new items; were the false positives
  D2 adversarial   - 10 must-flag (incl. typo + zero-width bypasses)
                     10 must-not-flag (incl. operation flip, negation)
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
    "chapter": "CH-8: Fun with Numbers (Numbers 21 to 99)",
}


def _maths_curriculum():
    """Competency/LO strings read from the template, never retyped."""
    wb = load_workbook(TEMPLATE)
    ws = wb["Items"]
    comps = [ws.cell(row=r, column=111).value for r in range(2, 17)]
    los = {}
    for i, c in enumerate(comps):
        if c:
            los[c] = [ws.cell(row=rr, column=114 + i).value
                      for rr in range(2, ws.max_row + 1)
                      if ws.cell(row=rr, column=114 + i).value]
    wb.close()
    count = next(c for c in comps if c and c.startswith("Counts up to 99"))
    arrange = next(c for c in comps if c and c.startswith("Arranges numbers up to 99"))
    return count, los[count], arrange, los[arrange]


C_COUNT, LO_COUNT, C_ARR, LO_ARR = _maths_curriculum()
LO_FB = next(l for l in LO_COUNT if l.startswith("Counts forward and backward"))
LO_TENS = next(l for l in LO_COUNT if l.startswith("Counts objects up to 99"))
LO_ARRANGE = LO_ARR[0]

FB, TENS, ARR = (C_COUNT, LO_FB), (C_COUNT, LO_TENS), (C_ARR, LO_ARRANGE)

# seq, tier, typology, (competency, LO), blooms, marks, A, B, C
# Each of A/B/C is (question, answer, explanation, options-or-None).
PAIRS = [
    (1, 1, "True or False", FB, "Understanding", "1",
     ("Anaya counts forward from 34 and says 35 next.", "TRUE", "Counting forward from 34 gives 35.", None),
     ("Anaya says 35 next when she counts forward from 34.", "TRUE", "Counting forward from 34 gives 35.", None),
     ("Anaya counts forward from 61 and says 62 next.", "TRUE", "Counting forward from 61 gives 62.", None)),
    (2, 1, "Multiple Choice Question", FB, "Remembering", "1",
     ("Which number comes just after 57?", "58", "Counting order runs 57, 58, so 58 comes just after 57.", ["56", "57", "58", "59"]),
     ("Just after 57, which number comes next?", "58", "Counting order runs 57, 58, so 58 comes just after 57.", ["56", "57", "58", "59"]),
     ("Which number comes just after 83?", "84", "Counting order runs 83, 84, so 84 comes just after 83.", ["82", "83", "84", "85"])),
    (3, 1, "Fill in the Blank", FB, "Understanding", "1",
     ("Counting backward from 72, the next number is ____.", "71", "Counting back from 72 gives 71.", None),
     ("____ is the next number when counting backward from 72.", "71", "Counting back from 72 gives 71.", None),
     ("Counting backward from 49, the next number is ____.", "48", "Counting back from 49 gives 48.", None)),
    (4, 1, "Very Short Answer Question", FB, "Understanding", "1",
     ("Write the number that comes between 45 and 47.", "46", "46 sits between 45 and 47 in counting order.", None),
     ("Write the number that lies between 45 and 47.", "46", "46 sits between 45 and 47 in counting order.", None),
     ("Write the number that comes between 88 and 90.", "89", "89 sits between 88 and 90 in counting order.", None)),
    (5, 1, "Short Answer Question", FB, "Applying", "2",
     ("Explain how you would count aloud from 61 to 65.", "Say 61, 62, 63, 64, 65, moving on by one each time.", "Counting on by ones is the expected strategy.", None),
     ("Explain how you would say the count aloud from 61 to 65.", "Say 61, 62, 63, 64, 65, moving on by one each time.", "Counting on by ones is the expected strategy.", None),
     ("Explain how you would count aloud from 27 to 31.", "Say 27, 28, 29, 30, 31, moving on by one each time.", "Counting on by ones is the expected strategy.", None)),

    (6, 2, "True or False", ARR, "Analysing", "1",
     ("Dev arranges 28, 82 and 45 from smallest to largest as 28, 45, 82.", "TRUE", "28 is smallest, then 45, then 82.", None),
     ("Dev puts 28, 82 and 45 in order from the smallest to the biggest and gets 28, 45, 82.", "TRUE", "28 is smallest, then 45, then 82.", None),
     ("Dev arranges 36, 63 and 51 from smallest to largest as 36, 51, 63.", "TRUE", "36 is smallest, then 51, then 63.", None)),
    (7, 2, "Multiple Choice Question", ARR, "Analysing", "1",
     ("Which of these numbers is the largest?", "94", "94 has 9 tens and 4 ones, which is the greatest of the four.", ["39", "93", "49", "94"]),
     ("Out of these numbers, which one has the greatest value?", "94", "94 has 9 tens and 4 ones, which is the greatest of the four.", ["39", "93", "49", "94"]),
     ("Which of these numbers is the largest?", "76", "76 has 7 tens and 6 ones, which is the greatest of the four.", ["27", "72", "37", "76"])),
    (8, 2, "Fill in the Blank", TENS, "Understanding", "1",
     ("In the number 76, the digit 7 stands for ____ tens.", "7", "The tens place of 76 holds 7, so it stands for 7 tens.", None),
     ("In 76, the digit 7 represents ____ tens.", "7", "The tens place of 76 holds 7, so it stands for 7 tens.", None),
     ("In the number 58, the digit 5 stands for ____ tens.", "5", "The tens place of 58 holds 5, so it stands for 5 tens.", None)),
    (9, 2, "Very Short Answer Question", TENS, "Understanding", "1",
     ("How many tens are there in 50?", "5", "50 is five groups of ten.", None),
     ("The number 50 is made up of how many tens?", "5", "50 is five groups of ten.", None),
     ("How many tens are there in 80?", "8", "80 is eight groups of ten.", None)),
    (10, 2, "Short Answer Question", ARR, "Analysing", "2",
     ("Describe how you can tell that 63 is greater than 36.", "63 has 6 tens and 36 has 3 tens, and more tens means the greater number.", "Comparing the tens place first is the expected method.", None),
     ("Describe how you know that 63 is bigger than 36.", "63 has 6 tens and 36 has 3 tens, and more tens means the greater number.", "Comparing the tens place first is the expected method.", None),
     ("Describe how you can tell that 74 is greater than 47.", "74 has 7 tens and 47 has 4 tens, and more tens means the greater number.", "Comparing the tens place first is the expected method.", None)),

    (11, 3, "True or False", TENS, "Understanding", "1",
     ("Counting in tens from 20, Ishita says 20, 30, 40, 50.", "TRUE", "Each jump of ten adds one to the tens digit.", None),
     ("Skip counting by tens starting at 20 gives 20, 30, 40, 50.", "TRUE", "Each jump of ten adds one to the tens digit.", None),
     ("Counting in tens from 40, Ishita says 40, 50, 60, 70.", "TRUE", "Each jump of ten adds one to the tens digit.", None)),
    (12, 3, "Multiple Choice Question", FB, "Applying", "1",
     ("Start at 90 and count back by tens. Which number comes third?", "60", "Counting back by tens gives 80, 70, 60, so the third is 60.", ["80", "70", "60", "50"]),
     ("Ishita begins at 90 and jumps back ten each time. What is her third number?", "60", "Counting back by tens gives 80, 70, 60, so the third is 60.", ["80", "70", "60", "50"]),
     ("Start at 70 and count back by tens. Which number comes third?", "40", "Counting back by tens gives 60, 50, 40, so the third is 40.", ["60", "50", "40", "30"])),
    (13, 3, "Fill in the Blank", FB, "Understanding", "1",
     ("The number just before 40 is ____.", "39", "Counting order runs 39, 40, so 39 comes just before 40.", None),
     ("Which number comes immediately before 40? It is ____.", "39", "Counting order runs 39, 40, so 39 comes just before 40.", None),
     ("The number just before 60 is ____.", "59", "Counting order runs 59, 60, so 59 comes just before 60.", None)),
    (14, 3, "Very Short Answer Question", TENS, "Applying", "1",
     ("Which number is 10 more than 47?", "57", "Adding ten raises the tens digit by one, so 47 becomes 57.", None),
     ("A shelf has 47 books and ten more are added. How many books are there now?", "57", "Adding ten raises the tens digit by one, so 47 becomes 57.", None),
     ("Which number is 10 more than 62?", "72", "Adding ten raises the tens digit by one, so 62 becomes 72.", None)),
    (15, 3, "Short Answer Question", TENS, "Applying", "2",
     ("Explain how counting in tens from 30 helps you reach 80 quickly.", "Say 30, 40, 50, 60, 70, 80, which is five jumps of ten instead of counting one by one.", "Counting in tens is faster than counting in ones.", None),
     ("A child wants to get from 30 to 80 without counting one by one. Explain a quicker way.", "Say 30, 40, 50, 60, 70, 80, which is five jumps of ten instead of counting one by one.", "Counting in tens is faster than counting in ones.", None),
     ("Explain how counting in tens from 20 helps you reach 70 quickly.", "Say 20, 30, 40, 50, 60, 70, which is five jumps of ten instead of counting one by one.", "Counting in tens is faster than counting in ones.", None)),

    (16, 4, "True or False", ARR, "Analysing", "1",
     ("The number 29 has more tens than the number 92.", "FALSE", "29 has 2 tens and 92 has 9 tens, so 92 has more.", None),
     ("The tens digit of 29 is larger than the tens digit of 92.", "FALSE", "29 has 2 tens and 92 has 9 tens, so 92 has more.", None),
     ("The number 38 has more tens than the number 83.", "FALSE", "38 has 3 tens and 83 has 8 tens, so 83 has more.", None)),
    (17, 4, "Multiple Choice Question", TENS, "Understanding", "1",
     ("Which number sentence shows 58 split into tens and ones?", "50 + 8", "58 is five tens and eight ones, which is 50 + 8.", ["50 + 8", "5 + 8", "58 + 10", "40 + 8"]),
     ("Fifty-eight is made of five tens and eight ones. Which sentence shows that?", "50 + 8", "58 is five tens and eight ones, which is 50 + 8.", ["50 + 8", "5 + 8", "58 + 10", "40 + 8"]),
     ("Which number sentence shows 74 split into tens and ones?", "70 + 4", "74 is seven tens and four ones, which is 70 + 4.", ["70 + 4", "7 + 4", "74 + 10", "60 + 4"])),
    (18, 4, "Fill in the Blank", TENS, "Remembering", "1",
     ("Rohan writes the number ninety-one in figures as ____.", "91", "Ninety-one written in figures is 91.", None),
     ("Rohan writes ninety-one using digits instead of words: ____.", "91", "Ninety-one written in figures is 91.", None),
     ("Rohan writes the number sixty-three in figures as ____.", "63", "Sixty-three written in figures is 63.", None)),
    (19, 4, "Very Short Answer Question", FB, "Understanding", "1",
     ("Which number is 1 less than 70?", "69", "Counting back one from 70 gives 69.", None),
     ("Take one away from seventy. What do you get?", "69", "Counting back one from 70 gives 69.", None),
     ("Which number is 1 less than 50?", "49", "Counting back one from 50 gives 49.", None)),
    (20, 4, "Short Answer Question", ARR, "Evaluating", "2",
     ("Tara says 47 comes before 38 when counting up. Explain why she is wrong.", "Counting up reaches 38 first, because 38 has 3 tens and 47 has 4 tens, so 38 is the smaller number.", "Comparing the tens place shows which number is reached first.", None),
     ("Tara believes 47 is reached before 38 when counting upwards. Say why that cannot be right.", "Counting up reaches 38 first, because 38 has 3 tens and 47 has 4 tens, so 38 is the smaller number.", "Comparing the tens place shows which number is reached first.", None),
     ("Tara says 65 comes before 56 when counting up. Explain why she is wrong.", "Counting up reaches 56 first, because 56 has 5 tens and 65 has 6 tens, so 56 is the smaller number.", "Comparing the tens place shows which number is reached first.", None)),
]

BLOOM_EXP = "The learner works with two-digit numbers in the 21 to 99 range."
ZWSP = "​"


def side_rows(index):
    """index 0/1/2 -> the A / B / C side of every pair, as builder rows."""
    out = []
    for seq, tier, typ, (comp, lo), blooms, marks, *sides in PAIRS:
        q, a, e, opts = sides[index]
        out.append(row(str(seq), typ, comp, lo, blooms, BLOOM_EXP, marks, q,
                       answer=a, explanation=e, options=opts))
    return out


def adversarial_rows():
    """10 probes that MUST flag, 10 that must NOT, derived from the A2 side."""
    A = {seq: sides[0] for seq, _, _, _, _, _, *sides in PAIRS}
    meta = {seq: (typ, cl, bl, mk) for seq, _, typ, cl, bl, mk, *_ in PAIRS}

    def make(sno, base_seq, question, answer, probe, expect, options=None, typ=None):
        t, (comp, lo), bl, mk = meta[base_seq]
        return row(sno, typ or t, comp, lo, bl, BLOOM_EXP, mk, question,
                   answer=answer, explanation=A[base_seq][2],
                   options=options if options is not None else A[base_seq][3]), \
               {"sno": sno, "base": f"A2-{base_seq}", "probe": probe, "expect": expect}

    specs = [
        # ---- must be FLAGGED: same question, cosmetic change only ----
        make("1", 1, A[1][0].replace(" ", "  "), "TRUE", "whitespace only", "FLAG"),
        make("2", 6, A[6][0].replace(".", ";").replace(",", " ,"), "TRUE", "punctuation only", "FLAG"),
        make("3", 4, A[4][0].upper(), "46", "letter case only", "FLAG"),
        make("4", 2, "Read carefully: " + A[2][0], "58", "trivial prefix", "FLAG"),
        make("5", 7, A[7][0] + " Choose the correct option.", "94", "trivial suffix", "FLAG"),
        make("6", 9, A[9][0].replace("How many", "What number of"), "5", "one synonym swapped", "FLAG"),
        make("7", 13, "The number just before forty is ____.", "39", "digits written as words", "FLAG"),
        make("8", 14, "Which number is obtained when 10 is added to 47?", "57", "active turned passive", "FLAG"),
        make("9", 1, A[1][0].replace("counts", "connts"), "TRUE", "TYPO introduced (was a bypass)", "FLAG"),
        # Zero-width joined everywhere EXCEPT inside the "____" marker: joining
        # through it produces "_<zw>_<zw>_<zw>_", which is no longer the blank
        # the Fill in the Blank contract requires and gets the row rejected at
        # upload before the duplicate check ever sees it.
        make("10", 3, "____".join(ZWSP.join(part) for part in A[3][0].split("____")),
             "71", "ZERO-WIDTH chars (was a bypass)", "FLAG"),
        # ---- must NOT be flagged: different question, different answer ----
        make("11", 1, "Anaya counts backward from 34 and says 35 next.", "FALSE", "direction flipped", "NO_FLAG"),
        make("12", 6, "Dev arranges 28, 82 and 45 from smallest to largest as 28, 45, 82, which is not correct.", "FALSE", "negation inserted", "NO_FLAG"),
        make("13", 9, "How many ones are there in 50?", "0", "tens changed to ones", "NO_FLAG"),
        make("14", 2, "Which number comes just before 57?", "56", "after changed to before", "NO_FLAG"),
        make("15", 10, "Describe how you can tell that 36 is smaller than 63.", "36 has 3 tens and 63 has 6 tens, and fewer tens means the smaller number.", "comparison flipped", "NO_FLAG"),
        make("16", 19, "Which number is 1 more than 70?", "71", "less changed to more", "NO_FLAG"),
        make("17", 8, "In the number 76, the digit 6 stands for ____ ones.", "6", "tens place changed to ones", "NO_FLAG"),
        make("18", 14, "Which number is 10 less than 47?", "37", "more changed to less", "NO_FLAG"),
        # Counting forward from 90 would reach 120, outside this chapter's
        # 21-99 range and outside the inherited options - so the probe starts
        # at 30 instead. Still the same transformation: backward -> forward.
        make("19", 12, "Start at 30 and count forward by tens. Which number comes third?", "60",
             "back changed to forward", "NO_FLAG", options=["40", "50", "60", "70"]),
        make("20", 16, "The number 92 has more tens than the number 29.", "TRUE", "operands swapped, answer flips", "NO_FLAG"),
    ]
    return [r for r, _ in specs], [s for _, s in specs]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    built = []
    for index, (key, name) in enumerate([("A2", "sheet_A2_maths.xlsx"),
                                         ("B2", "sheet_B2_maths.xlsx"),
                                         ("C2", "sheet_C2_maths.xlsx")]):
        target = build_sheet(side_rows(index), "A", OUTPUT_DIR / name, TEMPLATE, CURRICULUM, {})
        built.append((key, target))

    rows, spec = adversarial_rows()
    target = build_sheet(rows, "A", OUTPUT_DIR / "sheet_D2_maths.xlsx", TEMPLATE, CURRICULUM, {})
    built.append(("D2", target))
    (OUTPUT_DIR / "spec_D2_maths.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUTPUT_DIR / "pairs_v2_maths.json").write_text(json.dumps(
        {"curriculum": CURRICULUM,
         "pairs": [{"seq": s, "tier": t, "typology": ty,
                    "A": a[0], "B": b[0], "C": c[0]}
                   for s, t, ty, _, _, _, a, b, c in PAIRS]},
        indent=2, ensure_ascii=False), encoding="utf-8")

    for key, path in built:
        print(f"{key}: {path}")
    print(f"\nchapter: {CURRICULUM['chapter']}")


if __name__ == "__main__":
    main()
