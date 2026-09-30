"""Paraphrase retest after the latest fix: 10 items at TIER-3/4 distance.

Deliberately harder than the last typology run, which came out at 0.55 token
overlap - tier-2 territory that Maths already handled 4/5 before the fix, so
its 14/14 proved nothing. The 10 failures we are actually chasing all sat at
~0.28 overlap, so every pair here is rewritten to land in that band:

  * numerals restated as words ("20" -> "twenty") - a known weak spot, the
    "ninety-one" item escaped entirely last time
  * the actor and framing swapped out
  * sentence structure rebuilt rather than reordered

The answer is unchanged in every pair, so all 10 are the same question and all
10 must be flagged.

Chapter CH-12 (Money) is fresh - no earlier sheet used it - and the five
typologies are the simple ones where every previous Maths failure occurred.
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
    "chapter": "CH-12: How Much Can We Spend? (Money)",
}
BLOOM_EXP = "The learner works with notes and coins in everyday money situations."


def _curriculum():
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
    money = next(c for c in comps if c and c.startswith("Performs simple transactions"))
    prob = next(c for c in comps if c and c.startswith("Formulates and solves"))
    return (money, los[money][0]), (prob, los[prob][1])


MONEY, PROB = _curriculum()

# sno, typology, (comp, lo), blooms, marks, A-question, B-paraphrase, answer, explanation, options
PAIRS = [
    ("1", "True or False", MONEY, "Applying", "1",
     "Sanya has one 10-rupee note and one 5-rupee coin, so she has 15 rupees in all.",
     "A ten-rupee note together with a five-rupee coin comes to fifteen rupees.",
     "TRUE", "10 rupees and 5 rupees make 15 rupees.", None),
    ("2", "Multiple Choice Question", MONEY, "Applying", "1",
     "Devan buys a pencil for 7 rupees and an eraser for 5 rupees. How much does he spend?",
     "The total bill for two items priced at seven and five rupees comes to what amount?",
     "12", "7 rupees and 5 rupees make 12 rupees.", ["10", "11", "12", "13"]),
    ("3", "Fill in the Blank", PROB, "Applying", "1",
     "Ira pays 20 rupees for a book that costs 14 rupees. She gets ____ rupees back.",
     "Change handed back from a twenty-rupee note after paying fourteen rupees is ____ rupees.",
     "6", "20 take away 14 leaves 6 rupees.", None),
    ("4", "Very Short Answer Question", MONEY, "Understanding", "1",
     "How many 2-rupee coins make 10 rupees?",
     "Ten rupees is built entirely from coins worth two rupees each. Count them.",
     "5", "Five coins of 2 rupees make 10 rupees.", None),
    ("5", "Short Answer Question", PROB, "Applying", "2",
     "Manav has 18 rupees. Explain how he can pay for a toy costing 12 rupees and say what is left.",
     "A child holding eighteen rupees wants a toy priced at twelve. Describe the payment and the remainder.",
     "He gives 12 rupees and keeps 6, because 18 take away 12 leaves 6.",
     "Paying the price and subtracting it from the amount held is the expected method.", None),
    ("6", "True or False", MONEY, "Evaluating", "1",
     "Rhea has three 5-rupee coins, so she has 20 rupees.",
     "Holding a trio of five-rupee coins gives a total of twenty rupees.",
     "FALSE", "Three coins of 5 rupees make 15 rupees, not 20.", None),
    ("7", "Multiple Choice Question", MONEY, "Analysing", "1",
     "Which of these makes exactly 20 rupees?",
     "Choose the set of money that adds up to precisely twenty rupees.",
     "Two 10-rupee notes", "Two notes of 10 rupees make 20 rupees.",
     ["Two 10-rupee notes", "Three 5-rupee coins",
      "One 10-rupee note and one 5-rupee coin", "Four 2-rupee coins"]),
    ("8", "Fill in the Blank", MONEY, "Understanding", "1",
     "A 50-rupee note is worth the same as ____ 10-rupee notes.",
     "The count of ten-rupee notes needed to match one fifty-rupee note is ____.",
     "5", "Five notes of 10 rupees make 50 rupees.", None),
    ("9", "Very Short Answer Question", PROB, "Applying", "1",
     "Sanya spends 9 rupees from 25 rupees. How much is left?",
     "Starting with twenty-five rupees and parting with nine, what remains?",
     "16", "25 take away 9 leaves 16 rupees.", None),
    ("10", "Short Answer Question", PROB, "Applying", "2",
     "Devan wants to buy a ball for 35 rupees but has 20 rupees. Explain how much more he needs.",
     "A ball is priced at thirty-five rupees and a child holds twenty. Work out the shortfall and explain it.",
     "He needs 15 rupees more, because 35 take away 20 leaves 15.",
     "Subtracting what is held from the price gives the shortfall.", None),
]


def rows_for(side):
    out = []
    for sno, typ, (comp, lo), blooms, marks, qa, qb, ans, exp, opts in PAIRS:
        out.append(row(sno, typ, comp, lo, blooms, BLOOM_EXP, marks,
                       qb if side == "B" else qa,
                       answer=ans, explanation=exp, options=opts))
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ka = build_sheet(rows_for("A"), "A", OUTPUT_DIR / "sheet_KA_baseline.xlsx",
                     TEMPLATE, CURRICULUM, {})
    kb = build_sheet(rows_for("B"), "A", OUTPUT_DIR / "sheet_KB_paraphrase.xlsx",
                     TEMPLATE, CURRICULUM, {})
    tok = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))
    spec = []
    for sno, typ, _, _, _, qa, qb, ans, _, _ in PAIRS:
        ov = len(tok(qa) & tok(qb)) / len(tok(qa) | tok(qb))
        spec.append({"sno": sno, "typology": typ, "A": qa, "B": qb,
                     "answer": ans, "overlap": round(ov, 2), "expect": "FLAG"})
    (OUTPUT_DIR / "spec_paraphrase_retest.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    mean = sum(s["overlap"] for s in spec) / len(spec)
    print(f"KA: {ka}\nKB: {kb}   ({len(PAIRS)} items)\n")
    print(f"{'#':>3} {'typology':<26} {'overlap':>7}  band")
    for s in spec:
        band = "tier 3/4" if s["overlap"] < 0.35 else ("tier 2" if s["overlap"] < 0.6 else "tier 1")
        print(f"{s['sno']:>3} {s['typology']:<26} {s['overlap']:>7.2f}  {band}")
    print(f"\nmean overlap {mean:.2f}   (target <0.35; last run was 0.55)")


if __name__ == "__main__":
    main()
