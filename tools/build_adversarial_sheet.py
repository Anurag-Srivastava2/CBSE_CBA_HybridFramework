"""Adversarial duplicate-check probe: 20 items built to break the checker.

Every item is derived from a known Sheet A item already in the bank (IS1277)
by ONE named transformation, and carries the verdict it MUST get:

  FLAG    - the transformation does not change the question, so this is the
            same item and the duplicate check has to catch it.
  NO_FLAG - the transformation changes what is being asked or what the answer
            is, so this is a genuinely NEW item and flagging it is a false
            positive that blocks an SME from doing ordinary work.

The two groups are deliberately built to look alike on the surface: several
NO_FLAG items differ from their source by a single character (a "+" becoming
a "-", an inserted "not"), while several FLAG items differ by a whole clause.
A checker keying on surface distance rather than meaning gets both groups
backwards, which is exactly what this sheet is for.
"""
import json
from pathlib import Path

from tools.name_swap_sheet_builder import build_sheet, row

OUTPUT_DIR = Path("data/qar_semantic")
TEMPLATE = Path("data/upload_templates/sme_sheet.xlsx")
PAIRS_FILE = OUTPUT_DIR / "semantic_duplicate_pairs.json"

CURRICULUM = {
    "grade": "Grade 1", "subject": "Mathematics", "book": "Book 1", "unit": None,
    "chapter": "CH-6: Vegetable Farm (Addition and Subtraction up to 20)",
}

# Reuse the exact competency/LO strings that already passed validation, read
# from the file rather than retyped - a single stray space gets a row rejected.
_pairs = json.loads(PAIRS_FILE.read_text(encoding="utf-8"))["pairs"]
_by_seq = {p["seq"]: p for p in _pairs}
COMP_ADDSUB = _by_seq[1]["competency"]
LO_ADD = _by_seq[1]["learning_outcome"]
LO_SUB = _by_seq[11]["learning_outcome"]
LO_SYM = _by_seq[13]["learning_outcome"]
COMP_NUM = _by_seq[9]["competency"]
LO_CMP = _by_seq[9]["learning_outcome"]

#: (attack, base item in IS1277, expected verdict)
PROBES = [
    # ---------- GROUP 1: same question, must be FLAGGED ----------
    ("whitespace only", "A-i1", "FLAG"),
    ("punctuation only", "A-i11", "FLAG"),
    ("letter case only", "A-i4", "FLAG"),
    ("trivial prefix added", "A-i7", "FLAG"),
    ("trivial suffix added", "A-i2", "FLAG"),
    ("one synonym swapped", "A-i3", "FLAG"),
    ("digits written as words", "A-i9", "FLAG"),
    ("active turned passive", "A-i4", "FLAG"),
    ("typo introduced", "A-i1", "FLAG"),
    ("spacing around punctuation", "A-i13", "FLAG"),
    # ---------- GROUP 2: different question, must NOT be flagged ----------
    ("operation flipped + to -", "A-i1", "NO_FLAG"),
    ("negation inserted", "A-i11", "NO_FLAG"),
    ("different quantity asked", "A-i9", "NO_FLAG"),
    ("asks for the part, not the rest", "A-i7", "NO_FLAG"),
    ("asks for difference, not total", "A-i2", "NO_FLAG"),
    ("numbers changed", "A-i3", "NO_FLAG"),
    ("equation restructured", "A-i13", "NO_FLAG"),
    ("operation flipped, entity kept", "A-i4", "NO_FLAG"),
    ("stated total changed, answer flips", "A-i1", "NO_FLAG"),
    ("answer form changed to a sentence", "A-i7", "NO_FLAG"),
]

ROWS = [
    # ---------- GROUP 1 ----------
    row("1", "True or False", COMP_ADDSUB, LO_ADD, "Applying",
        "The learner checks a stated total against the addition it reports.", "1",
        "A basket holds 9 carrots and  6 more carrots are put into it.  The basket now holds 15 carrots.",
        answer="TRUE", explanation="9 carrots and 6 more carrots make 15 carrots."),
    row("2", "True or False", COMP_ADDSUB, LO_SUB, "Applying",
        "The learner checks a stated remainder against the subtraction it reports.", "1",
        "A farmer pulls out 14 radishes and sells 6 of them; so, 8 radishes are left with the farmer",
        answer="TRUE", explanation="14 take away 6 leaves 8 radishes."),
    row("3", "Very Short Answer Question", COMP_ADDSUB, LO_ADD, "Applying",
        "The learner joins two quantities to find how many there are in all.", "1",
        "a FARMER plants 8 ROWS of spinach and THEN plants 3 more rows. how many ROWS are there now?",
        answer="11", explanation="8 rows and 3 more rows make 11 rows."),
    row("4", "Multiple Choice Question", COMP_ADDSUB, LO_SUB, "Applying",
        "The learner models a sale as a subtraction and selects what is left.", "1",
        "Read the question carefully: A vegetable seller had 18 cucumbers and sold 6 of them. How many cucumbers are left with him?",
        answer="12", explanation="18 take away 6 leaves 12 cucumbers.",
        options=["10", "11", "12", "13"]),
    row("5", "Multiple Choice Question", COMP_ADDSUB, LO_ADD, "Applying",
        "The learner models a story situation as an addition.", "1",
        "Meera picks 7 tomatoes and her brother picks 5 tomatoes. How many tomatoes do they have altogether? Choose the correct option.",
        answer="12", explanation="7 tomatoes and 5 tomatoes together make 12 tomatoes.",
        options=["10", "11", "12", "13"]),
    row("6", "Fill in the Blank", COMP_ADDSUB, LO_SUB, "Applying",
        "The learner models a take-away situation and states what is left.", "1",
        "There were 13 onions in a bag and 4 were taken out. ____ onions are left in the bag.",
        answer="9", explanation="13 take away 4 leaves 9 onions."),
    row("7", "Very Short Answer Question", COMP_NUM, LO_CMP, "Analysing",
        "The learner compares two collections and quantifies the difference.", "1",
        "There are eleven brinjals in one basket and four in another. How many more brinjals does the first basket have?",
        answer="7", explanation="11 take away 4 leaves 7."),
    row("8", "Very Short Answer Question", COMP_ADDSUB, LO_ADD, "Applying",
        "The learner joins two quantities to find how many there are in all.", "1",
        "8 rows of spinach are planted by a farmer, and then 3 more rows are planted. How many rows are there now?",
        answer="11", explanation="8 rows and 3 more rows make 11 rows."),
    row("9", "True or False", COMP_ADDSUB, LO_ADD, "Applying",
        "The learner checks a stated total against the addition it reports.", "1",
        "A basket holds 9 carrotts and 6 more carrotts are put into it. The basket now holds 15 carrotts.",
        answer="TRUE", explanation="9 carrots and 6 more carrots make 15 carrots."),
    row("10", "Fill in the Blank", COMP_ADDSUB, LO_SYM, "Understanding",
        "The learner reads a number sentence and supplies the missing addend.", "1",
        "Complete the number sentence :6 + ____ = 15",
        answer="9", explanation="6 and 9 make 15, so the missing addend is 9."),

    # ---------- GROUP 2 ----------
    row("11", "True or False", COMP_ADDSUB, LO_SUB, "Applying",
        "The learner models a take-away and judges the stated total.", "1",
        "A basket holds 9 carrots and 6 carrots are taken out of it. The basket now holds 15 carrots.",
        answer="FALSE", explanation="9 take away 6 leaves 3 carrots, not 15, so the statement is false."),
    row("12", "True or False", COMP_ADDSUB, LO_SUB, "Evaluating",
        "The learner judges a negated claim about a remainder.", "1",
        "A farmer pulls out 14 radishes and sells 6 of them, so 8 radishes are not left with the farmer.",
        answer="FALSE", explanation="14 take away 6 does leave 8 radishes, so the negative claim is false."),
    row("13", "Very Short Answer Question", COMP_ADDSUB, LO_ADD, "Applying",
        "The learner totals two collections rather than comparing them.", "1",
        "There are 11 brinjals in one basket and 4 in another. How many brinjals are there in the two baskets altogether?",
        answer="15", explanation="11 brinjals and 4 brinjals together make 15 brinjals."),
    row("14", "Multiple Choice Question", COMP_ADDSUB, LO_SUB, "Remembering",
        "The learner reads the quantity sold straight from the situation.", "1",
        "A vegetable seller had 18 cucumbers and sold 6 of them. How many cucumbers did he sell?",
        answer="6", explanation="The situation states that 6 cucumbers were sold.",
        options=["4", "5", "6", "7"]),
    row("15", "Multiple Choice Question", COMP_NUM, LO_CMP, "Analysing",
        "The learner compares the two pickers rather than totalling them.", "1",
        "Meera picks 7 tomatoes and her brother picks 5 tomatoes. How many more tomatoes does Meera have?",
        answer="2", explanation="7 take away 5 leaves 2, so Meera has 2 more.",
        options=["1", "2", "3", "4"]),
    row("16", "Fill in the Blank", COMP_ADDSUB, LO_SUB, "Applying",
        "The learner models a take-away situation and states what is left.", "1",
        "There were 19 onions in a sack and 6 were taken out. ____ onions are left in the sack.",
        answer="13", explanation="19 take away 6 leaves 13 onions."),
    row("17", "Fill in the Blank", COMP_ADDSUB, LO_SYM, "Understanding",
        "The learner reads a subtraction sentence and supplies the missing part.", "1",
        "Complete the number sentence: 15 - ____ = 6",
        answer="9", explanation="15 take away 9 leaves 6, so the missing number is 9."),
    row("18", "Very Short Answer Question", COMP_ADDSUB, LO_SUB, "Applying",
        "The learner removes a quantity rather than adding one.", "1",
        "A farmer plants 8 rows of spinach and then removes 3 rows. How many rows are there now?",
        answer="5", explanation="8 rows take away 3 rows leaves 5 rows."),
    row("19", "True or False", COMP_ADDSUB, LO_ADD, "Evaluating",
        "The learner checks a stated total and finds it wrong.", "1",
        "A basket holds 9 carrots and 6 more carrots are put into it. The basket now holds 16 carrots.",
        answer="FALSE", explanation="9 carrots and 6 more make 15 carrots, not 16, so the statement is false."),
    row("20", "Very Short Answer Question", COMP_ADDSUB, LO_SYM, "Understanding",
        "The learner writes the number sentence that models the situation.", "1",
        "A vegetable seller had 18 cucumbers and sold 6 of them. Write the subtraction sentence for this situation.",
        answer="18 - 6 = 12", explanation="Selling removes cucumbers, so the situation is modelled as 18 - 6 = 12."),
]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = build_sheet(ROWS, "A", OUTPUT_DIR / "sheet_D_adversarial.xlsx",
                         TEMPLATE, CURRICULUM, {})
    spec = [
        {"sno": r["sno"], "attack": a, "base": b, "expect": e,
         "typology": r["typology"], "question": r["question"], "answer": r["answer"]}
        for r, (a, b, e) in zip(ROWS, PROBES)
    ]
    (OUTPUT_DIR / "adversarial_spec.json").write_text(
        json.dumps({"curriculum": CURRICULUM, "probes": spec}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    flag = sum(1 for p in spec if p["expect"] == "FLAG")
    print(f"Sheet D: {target}  ({len(ROWS)} rows)")
    print(f"  must be FLAGGED    : {flag}")
    print(f"  must NOT be flagged: {len(spec) - flag}")


if __name__ == "__main__":
    main()
