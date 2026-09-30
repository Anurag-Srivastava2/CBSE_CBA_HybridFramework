"""50-pair duplicate probe: same design as the numeric/number-free retests,
scaled up. 5 typologies x 10 pairs each (5 numeric-anchored, 5 number-free per
typology), spanning multiple Grade 1 Mathematics skills for content variety.

Filed under CH-10 (Time) - a chapter no earlier sheet in this session has
used - purely for the one-chapter-per-upload rule; competencies are drawn from
across the Grade 1 Mathematics catalogue since Metadata Alignment validates
chapter-vs-grade/subject and learning-outcome-vs-competency, not
competency-vs-chapter.

Every pair keeps the same answer, so every one of the 50 is a genuine
duplicate and all 50 must be flagged.
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
    "chapter": "CH-10: How do I Spend my Day? (Time)",
}
BLOOM_EXP = "The learner applies a Grade 1 Mathematics skill to an everyday situation."
NUMBER = (r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
          r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
          r"thirty|forty|fifty|half|first|second|third|fourth)\b")


def _lo(all_comps, all_los, prefix, index=0):
    comp = next(c for c in all_comps if c.startswith(prefix))
    return comp, all_los[comp][index]


def _load_curriculum():
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
    los = {c: vals(f"G{gi}_S{si}_C{i}_LOs") for i, c in enumerate(comps, start=1)}
    chapters = vals(f"G{gi}_S{si}_B1_Chapters")
    wb.close()
    if CURRICULUM["chapter"] not in chapters:
        raise SystemExit(f"{CURRICULUM['chapter']!r} not in {chapters}")
    return comps, los


COMPS, LOS = _load_curriculum()
ADD = _lo(COMPS, LOS, "Performs addition and subtraction", 2)
SUB = _lo(COMPS, LOS, "Performs addition and subtraction", 3)
COUNT = _lo(COMPS, LOS, "Counts up to 99", 0)
NUM_CMP = _lo(COMPS, LOS, "Recognises and uses numerals", 0)
NUM_WRITE = _lo(COMPS, LOS, "Recognises and uses numerals", 1)
PATTERN = _lo(COMPS, LOS, "Identifies and extends simple patterns")
TIME_EARLY = _lo(COMPS, LOS, "Performs simple measurements of time", 1)
TIME_SEQ = _lo(COMPS, LOS, "Performs simple measurements of time", 4)
MONEY = _lo(COMPS, LOS, "Performs simple transactions")
MULT = _lo(COMPS, LOS, "Recognises multiplication", 0)
SHAPE = _lo(COMPS, LOS, "Recognises basic geometric shapes", 3)
SORT = _lo(COMPS, LOS, "Sorts objects into groups")
MEASURE = _lo(COMPS, LOS, "Performs simple measurements of length", 1)

# (kind, typology, comp_lo, blooms, marks, A, B, answer, explanation, options)
PAIRS = []

def add(kind, typ, comp_lo, blooms, marks, qa, qb, ans, exp, opts=None):
    PAIRS.append((kind, typ, comp_lo, blooms, marks, qa, qb, ans, exp, opts))


# ---------------- True or False: 5 numeric + 5 number-free ----------------
add("numeric", "True or False", ADD, "Applying", "1",
    "A basket has 7 mangoes and 6 more are added, so it has 13 mangoes.",
    "Seven mangoes in a basket, with six more put in, comes to thirteen mangoes.",
    "TRUE", "7 and 6 make 13.")
add("numeric", "True or False", SUB, "Applying", "1",
    "A tank had 15 fish and 9 swam away, leaving 6 fish.",
    "Fifteen fish in a tank, with nine swimming away, leaves six fish.",
    "TRUE", "15 take away 9 leaves 6.")
add("numeric", "True or False", COUNT, "Understanding", "1",
    "Counting forward from 68, the next number said is 69.",
    "The number that follows when counting forward from sixty-eight is sixty-nine.",
    "TRUE", "68 followed by 69 in the counting order.")
add("numeric", "True or False", MONEY, "Applying", "1",
    "Two 5-rupee coins and one 2-rupee coin make 12 rupees.",
    "Twelve rupees is made from a pair of five-rupee coins plus a two-rupee coin.",
    "TRUE", "5+5+2 = 12.")
add("numeric", "True or False", MULT, "Applying", "1",
    "4 groups of 3 marbles each give 12 marbles in total.",
    "Four equal groups holding three marbles apiece add up to twelve marbles.",
    "TRUE", "4 groups of 3 make 12.")
add("number-free", "True or False", TIME_SEQ, "Understanding", "1",
    "We eat breakfast before we eat dinner.",
    "Dinner is eaten only after breakfast has already been had.",
    "TRUE", "Breakfast comes earlier in the day than dinner.")
add("number-free", "True or False", SHAPE, "Understanding", "1",
    "A ball can roll but a book cannot.",
    "Rolling is something a ball can do, which a book is unable to do.",
    "TRUE", "A ball is round and rolls; a book has flat sides and does not.")
add("number-free", "True or False", SORT, "Analysing", "1",
    "Keeping red toys and blue toys in separate boxes sorts them by colour.",
    "Placing red toys together and blue toys separately in their own group is sorting by colour.",
    "TRUE", "Colour is the property being used to separate the groups.")
add("number-free", "True or False", MEASURE, "Understanding", "1",
    "A giraffe is taller than a cat.",
    "Compared with a cat, a giraffe stands taller.",
    "TRUE", "A giraffe is much taller than a cat.")
add("number-free", "True or False", TIME_EARLY, "Understanding", "1",
    "Holidays feel longer than a single school day.",
    "A single school day feels shorter than the holidays do.",
    "TRUE", "Holidays stretch on for longer than one school day.")

# ---------------- Multiple Choice Question: 5 numeric + 5 number-free ----------------
add("numeric", "Multiple Choice Question", ADD, "Applying", "1",
    "Rohit has 8 stamps and gets 5 more. How many stamps does he have now?",
    "Starting with eight stamps and receiving five more, what total does Rohit reach?",
    "13", "8 and 5 make 13.", ["11", "12", "13", "14"])
add("numeric", "Multiple Choice Question", SUB, "Applying", "1",
    "A shelf holds 16 books and 7 are removed. How many books remain?",
    "Out of sixteen books on a shelf, seven are taken away — how many are left?",
    "9", "16 take away 7 leaves 9.", ["7", "8", "9", "10"])
add("numeric", "Multiple Choice Question", NUM_CMP, "Understanding", "1",
    "Which number is bigger, 34 or 43?",
    "Comparing thirty-four with forty-three, which one has the greater value?",
    "43", "43 has more tens than 34.", ["34", "43", "Equal", "Cannot say"])
add("numeric", "Multiple Choice Question", MULT, "Applying", "1",
    "3 rows of 4 chairs each. How many chairs in total?",
    "With three rows holding four chairs apiece, what is the total chair count?",
    "12", "3 groups of 4 make 12.", ["10", "11", "12", "13"])
add("numeric", "Multiple Choice Question", MONEY, "Applying", "1",
    "A pencil costs 6 rupees. How much do 2 pencils cost?",
    "If one pencil is priced at six rupees, what would two of them together cost?",
    "12", "6 rupees times 2 pencils is 12 rupees.", ["10", "11", "12", "13"])
add("number-free", "Multiple Choice Question", SHAPE, "Understanding", "1",
    "Which of these has corners?",
    "Out of these, which shape has corners?",
    "A square", "A square has four corners; the others are curved.",
    ["A ball", "A square", "An orange", "A wheel"])
add("number-free", "Multiple Choice Question", SORT, "Analysing", "1",
    "Which pair of objects could be sorted into the same group?",
    "Which pair of objects listed here would naturally belong in the same group?",
    "Apple and orange", "Both are fruits.",
    ["Apple and orange", "Apple and chair", "Orange and table", "Chair and table"])
add("number-free", "Multiple Choice Question", TIME_SEQ, "Understanding", "1",
    "Which of these happens earliest in a normal day?",
    "Out of these daily events, which takes place earliest?",
    "Waking up", "Waking up starts the day before the other events.",
    ["Waking up", "Going to sleep", "Eating dinner", "Watching the sunset"])
add("number-free", "Multiple Choice Question", MEASURE, "Understanding", "1",
    "Which of these is the heaviest?",
    "Among these choices, which weighs the most?",
    "An elephant", "An elephant is far heavier than the others.",
    ["A feather", "A pencil", "A balloon", "An elephant"])
add("number-free", "Multiple Choice Question", PATTERN, "Applying", "1",
    "Which shape continues the pattern square, circle, square, circle, ____?",
    "Looking at how square and circle keep alternating, which shape should come next?",
    "Square", "The pattern alternates square and circle.",
    ["Square", "Circle", "Triangle", "Star"])

# ---------------- Fill in the Blank: 5 numeric + 5 number-free ----------------
add("numeric", "Fill in the Blank", ADD, "Applying", "1",
    "A farmer has 9 hens and buys 6 more. He now has ____ hens.",
    "Starting with nine hens and buying six more, the farmer now has ____ hens.",
    "15", "9 and 6 make 15.")
add("numeric", "Fill in the Blank", SUB, "Applying", "1",
    "A box had 14 crayons and 5 were used up. ____ crayons are left.",
    "Out of fourteen crayons in a box, five have been used, leaving ____ crayons.",
    "9", "14 take away 5 leaves 9.")
add("numeric", "Fill in the Blank", NUM_WRITE, "Remembering", "1",
    "The numeral 14 is written in words as ____.",
    "In words rather than digits, fourteen is written as ____.",
    "fourteen", "14 in words is fourteen.")
add("numeric", "Fill in the Blank", COUNT, "Understanding", "1",
    "Counting back from 52, the next number is ____.",
    "The number that comes next when counting backward from fifty-two is ____.",
    "51", "52 counting back gives 51.")
add("numeric", "Fill in the Blank", MULT, "Applying", "1",
    "5 groups of 2 apples each make ____ apples.",
    "Five equal groups holding two apples each give a total of ____ apples.",
    "10", "5 groups of 2 make 10.")
add("number-free", "Fill in the Blank", TIME_SEQ, "Understanding", "1",
    "The meal we eat right after waking up is called ____.",
    "____ is the name given to the meal eaten right after waking up.",
    "breakfast", "Breakfast is the first meal of the day.")
add("number-free", "Fill in the Blank", TIME_EARLY, "Understanding", "1",
    "The rainy season is also called the ____ season.",
    "____ is the other name for the rainy season.",
    "monsoon", "The rainy season is also known as the monsoon season.")
add("number-free", "Fill in the Blank", SORT, "Understanding", "1",
    "Grouping objects by what they are used for is sorting by ____.",
    "____ is the property being used when objects are grouped by their use.",
    "use", "Function or use is a valid sorting property.")
add("number-free", "Fill in the Blank", MEASURE, "Understanding", "1",
    "An object that is not heavy is described as ____.",
    "____ describes an object that does not weigh very much.",
    "light", "The opposite of heavy is light.")
add("number-free", "Fill in the Blank", PATTERN, "Applying", "1",
    "In the pattern up, down, up, down, the next direction is ____.",
    "Following the sequence up, down, up, down, the direction that comes next is ____.",
    "up", "The pattern alternates up and down.")

# ---------------- Very Short Answer Question: 5 numeric + 5 number-free ----------------
add("numeric", "Very Short Answer Question", ADD, "Applying", "1",
    "A tray has 6 eggs and 7 more are added. How many eggs in all?",
    "Six eggs on a tray, with seven more placed on it, gives how many eggs altogether?",
    "13", "6 and 7 make 13.")
add("numeric", "Very Short Answer Question", SUB, "Applying", "1",
    "There were 18 balloons and 9 burst. How many balloons are left?",
    "Of eighteen balloons, nine have burst — how many balloons remain?",
    "9", "18 take away 9 leaves 9.")
add("numeric", "Very Short Answer Question", NUM_CMP, "Analysing", "1",
    "How much bigger is 27 than 19?",
    "By how much does twenty-seven exceed nineteen?",
    "8", "27 take away 19 leaves 8.")
add("numeric", "Very Short Answer Question", MONEY, "Applying", "1",
    "How many 2-rupee coins make 8 rupees?",
    "To reach a total of eight rupees using only two-rupee coins, how many coins are needed?",
    "4", "4 coins of 2 rupees make 8 rupees.")
add("numeric", "Very Short Answer Question", MULT, "Applying", "1",
    "How many wheels are there on 3 bicycles?",
    "If each bicycle has two wheels, how many wheels do three bicycles have altogether?",
    "6", "3 bicycles with 2 wheels each make 6 wheels.")
add("number-free", "Very Short Answer Question", SHAPE, "Remembering", "1",
    "Name a shape that has no corners.",
    "Which shape can you name that has no corners at all?",
    "Circle", "A circle is a curved shape with no corners.")
add("number-free", "Very Short Answer Question", SORT, "Understanding", "1",
    "Name a way you could sort a pile of buttons.",
    "Give a property you could use to sort a pile of buttons.",
    "By colour", "Colour, size or shape are all valid sorting rules.")
add("number-free", "Very Short Answer Question", TIME_SEQ, "Remembering", "1",
    "Name the part of the day when the sun sets.",
    "What is the part of the day called during which the sun sets?",
    "Evening", "Sunset happens in the evening.")
add("number-free", "Very Short Answer Question", MEASURE, "Understanding", "1",
    "Which is longer, a pencil or a pen, usually?",
    "Between a pencil and a pen, which is usually the longer?",
    "A pencil", "A pencil is usually longer than a pen.")
add("number-free", "Very Short Answer Question", PATTERN, "Understanding", "1",
    "In the pattern loud, soft, loud, soft, what comes after loud?",
    "Following the sequence loud, soft, loud, soft, what should come right after loud?",
    "Soft", "The pattern alternates loud and soft.")

# ---------------- Short Answer Question: 5 numeric + 5 number-free ----------------
add("numeric", "Short Answer Question", ADD, "Applying", "2",
    "A vendor sells 12 balloons and has 9 more. Explain how many balloons he has now.",
    "A vendor already sold twelve balloons and has nine more in hand. Describe how many balloons he holds now.",
    "He has 21 balloons, because 12 and 9 make 21.",
    "Adding the two amounts gives the total.")
add("numeric", "Short Answer Question", SUB, "Applying", "2",
    "A jar had 20 sweets and 8 were eaten. Explain how many sweets are left.",
    "Out of twenty sweets in a jar, eight have been eaten. Describe how many sweets remain.",
    "12 sweets are left, because 20 take away 8 leaves 12.",
    "Subtracting the eaten sweets from the total gives what remains.")
add("numeric", "Short Answer Question", COUNT, "Understanding", "2",
    "Explain how you would count from 40 to 50 in groups of 10.",
    "Describe the way you would move from forty to fifty by counting in groups of ten.",
    "Say 40, then jump by 10 to reach 50 in a single step.",
    "Counting in tens is faster than counting one by one.")
add("numeric", "Short Answer Question", MONEY, "Applying", "2",
    "Explain how you would pay exactly 17 rupees using notes and coins.",
    "Describe a way of making up exactly seventeen rupees using notes and coins.",
    "Use one 10-rupee note, one 5-rupee coin and one 2-rupee coin, which add up to 17.",
    "Any combination that totals 17 rupees is acceptable.")
add("numeric", "Short Answer Question", MULT, "Applying", "2",
    "Explain how you would find the total number of legs on 4 chairs, if each chair has 4 legs.",
    "Describe how you would work out the total legs across four chairs, given four legs on each chair.",
    "Multiply 4 chairs by 4 legs each to get 16 legs in total.",
    "Repeated addition or multiplication gives the total.")
add("number-free", "Short Answer Question", SHAPE, "Analysing", "2",
    "Explain why a ball rolls but a cube does not.",
    "Describe the reason a ball is able to roll while a cube cannot.",
    "A ball has a curved surface all over, while a cube has flat faces that stop it rolling.",
    "The curved surface is what allows rolling.")
add("number-free", "Short Answer Question", SORT, "Analysing", "2",
    "Explain how you would sort a mixed pile of fruits and vegetables.",
    "Describe a method for separating a mixed pile of fruits and vegetables.",
    "Look at each item and place it in the fruit group or the vegetable group based on what it is.",
    "Sorting by category is the expected method.")
add("number-free", "Short Answer Question", TIME_SEQ, "Understanding", "2",
    "Explain the order of events from waking up to going to school.",
    "Describe the sequence of events that happens between waking up and reaching school.",
    "First you wake up, then you get ready, eat breakfast, and finally leave for school.",
    "The events should be given in their correct order.")
add("number-free", "Short Answer Question", MEASURE, "Applying", "2",
    "Explain how you would find out which of a pair of bags is heavier without a weighing machine.",
    "Describe a way to tell which bag in a pair weighs more, without using a weighing machine.",
    "Hold one bag in each hand and feel which one pulls down more.",
    "Comparing by feel is an acceptable non-standard method.")
add("number-free", "Short Answer Question", PATTERN, "Analysing", "2",
    "Explain the rule followed by the pattern clap, stomp, clap, stomp.",
    "Describe what rule the sequence clap, stomp, clap, stomp is following.",
    "The pattern repeats clap and stomp turn by turn.",
    "Identifying the repeating unit is the expected answer.")


def rows_for(side):
    out = []
    for i, (kind, typ, comp_lo, blooms, marks, qa, qb, ans, exp, opts) in enumerate(PAIRS, start=1):
        comp, lo = comp_lo
        out.append(row(str(i), typ, comp, lo, blooms, BLOOM_EXP, marks,
                       qb if side == "B" else qa, answer=ans, explanation=exp, options=opts))
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ra = build_sheet(rows_for("A"), "A", OUTPUT_DIR / "sheet_RA_fifty.xlsx", TEMPLATE, CURRICULUM, {})
    rb = build_sheet(rows_for("B"), "A", OUTPUT_DIR / "sheet_RB_fifty.xlsx", TEMPLATE, CURRICULUM, {})

    tok = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))
    spec, wrong = [], []
    for i, (kind, typ, comp_lo, blooms, marks, qa, qb, ans, exp, opts) in enumerate(PAIRS, start=1):
        ov = len(tok(qa) & tok(qb)) / len(tok(qa) | tok(qb))
        free = not (re.search(NUMBER, qa, re.I) or re.search(NUMBER, qb, re.I))
        if (kind == "number-free") != free:
            wrong.append(f"{i} tagged {kind} but number_free={free}")
        spec.append({"sno": str(i), "kind": kind, "typology": typ, "A": qa, "B": qb,
                     "answer": ans, "overlap": round(ov, 2), "number_free": free, "expect": "FLAG"})
    (OUTPUT_DIR / "spec_fifty.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"RA: {ra}\nRB: {rb}   ({len(PAIRS)} pairs)\n")
    from collections import Counter
    print("typology counts:", dict(Counter(s["typology"] for s in spec)))
    print("kind counts    :", dict(Counter(s["kind"] for s in spec)))
    print(f"mean overlap: {sum(s['overlap'] for s in spec)/len(spec):.2f}")
    print("tag mismatches:", wrong or "none")
    dupq = [s["A"] for s in spec]
    print("duplicate A questions within sheet:", len(dupq) - len(set(dupq)))


if __name__ == "__main__":
    main()
