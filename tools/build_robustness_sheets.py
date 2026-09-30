"""Sheet E (input robustness / injection) and Sheet F (contract violations).

Sheet E rows are all STRUCTURALLY VALID items carrying hostile or awkward
CONTENT, so they pass upload validation and reach QAR. The question is what the
app then stores, renders and re-exports. Payloads are deliberately benign
detectors, not weapons: "=1+1" proves formula evaluation if the export shows
"2", and "<b>..</b>" proves HTML interpretation if it renders bold. Nothing
here executes anything or targets a third party - this is the team's own QA
environment.

Sheet F rows deliberately BREAK the typology contract and must be rejected at
upload. Two known-good control rows sit at the top and bottom so a wholesale
upload failure can be told apart from per-row rejection (the importer has been
seen rejecting rows individually: "PASSED 4 2 2").
"""
import json
from pathlib import Path
from shutil import copy2

from openpyxl import load_workbook

from utilities.item_template_columns import (
    clear_rows_from,
    copy_item_row,
    resolve_columns,
    trim_helper_columns,
    write_row_fields,
)

OUTPUT_DIR = Path("data/qar_semantic")
TEMPLATE = Path("data/upload_templates/sme_sheet.xlsx")
PAIRS_FILE = OUTPUT_DIR / "semantic_duplicate_pairs.json"

CURRICULUM = {
    "grade": "Grade 1", "subject": "Mathematics", "book": "Book 1", "unit": None,
    "chapter": "CH-6: Vegetable Farm (Addition and Subtraction up to 20)",
}

_pairs = {p["seq"]: p for p in json.loads(PAIRS_FILE.read_text(encoding="utf-8"))["pairs"]}
COMP = _pairs[1]["competency"]
LO_ADD = _pairs[1]["learning_outcome"]
LO_SUB = _pairs[11]["learning_outcome"]
BLOOM_EXP = "The learner applies an addition fact to an everyday situation."

ZWSP = "​"      # zero-width space
RLO = "‮"       # right-to-left override
BASE_A1 = "A basket holds 9 carrots and 6 more carrots are put into it. The basket now holds 15 carrots."


def item(sno, probe, expect, typology, question, answer, explanation,
         options=None, marks="1", blooms="Applying", lo=None,
         competency=None, overrides=None):
    return {
        "sno": sno, "probe": probe, "expect": expect, "typology": typology,
        "question": question, "answer": answer, "explanation": explanation,
        "options": options, "marks": marks, "blooms": blooms,
        "competency": competency or COMP, "learning_outcome": lo or LO_ADD,
        "overrides": overrides or {},
    }


# --------------------------------------------------------------------------
# SHEET E - hostile content, structurally valid
# --------------------------------------------------------------------------
SHEET_E = [
    item("1", "Excel formula injection: leading '='", "accepted, exported inert",
         "Very Short Answer Question", "=9+4 is a number sentence. What is its total?",
         "13", "9 and 4 make 13."),
    item("2", "Formula injection: leading '+'", "accepted, exported inert",
         "Very Short Answer Question", "+8+6 is a number sentence. What is its total?",
         "14", "8 and 6 make 14."),
    item("3", "Formula injection: leading '@'", "accepted, exported inert",
         "Very Short Answer Question", "@ Find the total of 7 + 5.",
         "12", "7 and 5 make 12."),
    item("4", "Formula injection: leading '-'", "accepted, exported inert",
         "Very Short Answer Question", "-  Write the total of 8 + 6.",
         "14", "8 and 6 make 14."),
    item("5", "HTML tags in question", "rendered as literal text",
         "Very Short Answer Question",
         "A basket has <b>9</b> carrots and 4 more are added. How many carrots are there?",
         "13", "9 and 4 make 13."),
    item("6", "Script tag in question", "rendered as literal text, never executed",
         "Very Short Answer Question",
         "A basket has 9 carrots <script>QAPROBE</script> and 4 more are added. How many carrots?",
         "13", "9 and 4 make 13."),
    item("7", "Apostrophes and quotes", "accepted, correctly escaped",
         "Very Short Answer Question",
         "O'Brien's basket has 9 carrots and 4 more are added. How many carrots does O'Brien have?",
         "13", "9 and 4 make 13."),
    item("8", "Special characters & % # _ backslash", "accepted, correctly escaped",
         "Very Short Answer Question",
         "A sign reads & % # _ \\ and \" marks. Rani counts 9 pencils and 4 more. How many pencils?",
         "13", "9 and 4 make 13."),
    item("9", "Zero-width spaces inside a known duplicate", "FLAGGED as duplicate of IS1277-i1",
         "True or False", ZWSP.join(BASE_A1), "TRUE",
         "9 carrots and 6 more carrots make 15 carrots."),
    item("10", "Devanagari digits inside a known duplicate", "FLAGGED as duplicate of IS1277-i1",
         "True or False",
         "A basket holds ९ carrots and ६ more carrots are put into it. The basket now holds १५ carrots.",
         "TRUE", "9 carrots and 6 more carrots make 15 carrots."),
    item("11", "Very long question (~1200 chars)", "accepted or cleanly rejected, not truncated silently",
         "Very Short Answer Question",
         ("A farmer walks through the vegetable garden every morning and counts what has grown. "
          * 12) + "She counts 9 carrots and then 4 more. How many carrots did she count?",
         "13", "9 and 4 make 13."),
    item("12", "Emoji in question", "accepted, stored intact",
         "Very Short Answer Question",
         "A basket holds 9 carrots and 4 more are added. How many carrots are there?",
         "13", "9 and 4 make 13."),
    item("13", "Right-to-left override character", "accepted, no display corruption",
         "Very Short Answer Question",
         f"A basket holds 9 carrots{RLO} and 4 more are added. How many carrots are there?",
         "13", "9 and 4 make 13."),
    item("14", "Newline inside the question cell", "accepted, line break preserved or normalised",
         "Very Short Answer Question",
         "A basket holds 9 carrots.\nIf 4 more are added, how many carrots are there?",
         "13", "9 and 4 make 13."),
    item("15", "Leading and trailing whitespace", "trimmed, then duplicate-matched",
         "True or False", "      " + BASE_A1 + "      ", "TRUE",
         "9 carrots and 6 more carrots make 15 carrots."),
    item("16", "Very long answer (~600 chars)", "accepted or cleanly rejected",
         "Short Answer Question",
         "Explain in your own words how you would add 9 carrots and 4 carrots.",
         "You start at nine and count on four more. " * 15,
         "Counting on from the larger number is the expected strategy.", marks="2"),
    item("17", "Single-character question", "REJECTED by Hard Validation",
         "Very Short Answer Question", "?", "13", "9 and 4 make 13."),
    item("18", "Numeric-only question", "accepted or cleanly rejected",
         "Very Short Answer Question", "9 + 4 = ?", "13", "9 and 4 make 13."),
    item("19", "Mixed script English + Devanagari", "accepted, stored intact",
         "Very Short Answer Question",
         "A basket holds 9 गाजर and 4 more are added. How many गाजर are there?",
         "13", "9 and 4 make 13."),
    item("20", "Punctuation-only question", "REJECTED by Hard Validation",
         "Very Short Answer Question", "... ??? !!!", "13", "9 and 4 make 13."),
]
# Emoji kept out of the source literal above so the file stays ASCII-safe; add here.
SHEET_E[11]["question"] = "\U0001F955 A basket holds 9 carrots \U0001F955 and 4 more are added. How many carrots are there?"


# --------------------------------------------------------------------------
# SHEET F - contract violations, must be rejected
# --------------------------------------------------------------------------
SHEET_F = [
    item("1", "CONTROL - valid True or False", "ACCEPTED",
         "True or False", "A crate holds 7 beans and 5 more beans are added. The crate now holds 12 beans.",
         "TRUE", "7 beans and 5 more make 12 beans."),
    item("2", "MCQ with only 3 options", "REJECTED",
         "Multiple Choice Question", "A tray has 7 peas and 5 more are added. How many peas?",
         "12", "7 and 5 make 12.", options=["10", "11", "12"]),
    item("3", "MCQ answer not among the options", "REJECTED",
         "Multiple Choice Question", "A tray has 8 peas and 5 more are added. How many peas?",
         "99", "8 and 5 make 13.", options=["11", "12", "13", "14"]),
    item("4", "MCQ with two identical options", "REJECTED",
         "Multiple Choice Question", "A tray has 6 peas and 5 more are added. How many peas?",
         "11", "6 and 5 make 11.", options=["11", "11", "12", "13"]),
    item("5", "True or False answer is 'MAYBE'", "REJECTED",
         "True or False", "A crate holds 9 beans and 5 more beans are added. The crate now holds 14 beans.",
         "MAYBE", "9 beans and 5 more make 14 beans."),
    item("6", "Fill in the Blank with no ____ marker", "REJECTED",
         "Fill in the Blank", "There were 12 onions in a sack and 5 were taken out. Onions are left.",
         "7", "12 take away 5 leaves 7 onions.", lo=LO_SUB),
    item("7", "Assertion and Reasoning answer 'E'", "REJECTED",
         "Assertion and Reasoning",
         "Assertion (A): 8 and 5 make 13. Reason (R): Adding joins two quantities.",
         "E", "Both statements are true and R explains A."),
    item("8", "Match the Following with one item in column A", "REJECTED",
         "Match the Following", "Match the vegetable to its count.",
         "1-A", "Only one pair is given, which is below the minimum of two.",
         options=["Carrot", "Nine"]),
    item("9", "Match the Following with column B missing", "REJECTED",
         "Match the Following", "Match each vegetable to its count.",
         "1-A, 2-B", "Column B is missing entirely.",
         options=["Carrot|Bean", None]),
    item("10", "Marks outside the 1-5 range", "REJECTED",
         "Very Short Answer Question", "A basket holds 7 beans and 6 more are added. How many beans?",
         "13", "7 and 6 make 13.", marks="99"),
    item("11", "Invalid Bloom's level", "REJECTED",
         "Very Short Answer Question", "A basket holds 5 beans and 6 more are added. How many beans?",
         "11", "5 and 6 make 11.", blooms="Inventing"),
    item("12", "Invalid typology", "REJECTED",
         "Puzzle", "A basket holds 4 beans and 6 more are added. How many beans?",
         "10", "4 and 6 make 10."),
    item("13", "Case Based parent with no sub-rows", "REJECTED",
         "Case Based Question", "Read the case: Rani grows beans and carrots in her garden.",
         None, "A parent with no sub-rows is incomplete.", marks="3"),
    item("14", "CONTROL - valid Very Short Answer", "ACCEPTED",
         "Very Short Answer Question", "A crate holds 6 beans and 7 more beans are added. How many beans?",
         "13", "6 beans and 7 more make 13 beans."),
]


def build(rows, target):
    copy2(TEMPLATE, target)
    workbook = load_workbook(target)
    worksheet = workbook["Items"]
    width = trim_helper_columns(worksheet)
    columns = resolve_columns(worksheet)

    for offset, entry in enumerate(rows):
        excel_row = offset + 2
        if excel_row != 2:
            copy_item_row(worksheet, 2, excel_row, width)
        fields = {
            **CURRICULUM,
            "sequence": entry["sno"],
            "competency": entry["competency"],
            "learning_outcome": entry["learning_outcome"],
            "blooms": entry["blooms"],
            "blooms_explanation": BLOOM_EXP,
            "typology": entry["typology"],
            "question": entry["question"],
            "answer": entry["answer"],
            "explanation": entry["explanation"],
            "marks": entry["marks"],
            "option_1": None, "option_2": None, "option_3": None, "option_4": None,
        }
        for index, option in enumerate(entry["options"] or [], start=1):
            fields[f"option_{index}"] = option
        fields.update(entry["overrides"])
        write_row_fields(worksheet, excel_row, columns, fields)

        # Force every text cell to be a STRING. openpyxl turns a value starting
        # with "=" into a live formula, which would mean Excel - not the app -
        # evaluated the payload and the upload would carry "2" instead of the
        # text we meant to test.
        for field in ("question", "answer", "explanation"):
            cell = worksheet.cell(row=excel_row, column=columns[field])
            if isinstance(cell.value, str):
                cell.data_type = "s"

    clear_rows_from(worksheet, len(rows) + 2, width)
    workbook.save(target)
    workbook.close()
    return target


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for rows, name, key in ((SHEET_E, "sheet_E_robustness.xlsx", "E"),
                            (SHEET_F, "sheet_F_contract.xlsx", "F")):
        target = build(rows, OUTPUT_DIR / name)
        spec = [{k: r[k] for k in ("sno", "probe", "expect", "typology")} for r in rows]
        (OUTPUT_DIR / f"spec_sheet_{key}.json").write_text(
            json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Sheet {key}: {target}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
