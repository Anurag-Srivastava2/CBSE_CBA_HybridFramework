"""Build the two upload sheets for the QAR semantic-duplicate probe.

Sheet A holds 20 mutually-distinct originals; Sheet B holds one paraphrase of
each, graded into four tiers by how much surface wording survives. Everything
except the Question (and, where the paraphrase swaps entities, the Answer and
Explanation that have to follow it) is held identical within a pair, so the
Duplicate Check score moves for one reason only.

Both sheets are built from the environment's own template via
`resolve_columns`, not at fixed indices - the same contract every other writer
in the suite uses, so a column insertion does not silently shift the data.
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

PAIRS_FILE = Path("data/qar_semantic/semantic_duplicate_pairs.json")
OUTPUT_DIR = Path("data/qar_semantic")


def build_sheet(template, pairs, side, target, curriculum):
    """Write one side ("A" or "B") of every pair into a copy of the template.

    Grade, subject, book and chapter come from `curriculum` and are the same on
    every row by necessity, not by convenience: the importer rejects a mixed
    upload with "All items in one upload must belong to the same grade, subject
    and chapter." Competency and Learning Outcome still vary per row - those
    are validated against the grade-subject, not the chapter.
    """
    copy2(template, target)
    workbook = load_workbook(target)
    worksheet = workbook["Items"]
    max_data_column = trim_helper_columns(worksheet)
    columns = resolve_columns(worksheet)
    if not columns:
        raise SystemExit(f"{template} has no recognisable item-data sheet.")

    for offset, pair in enumerate(pairs):
        row = offset + 2
        if row != 2:
            # Always cloned from row 2, never from the row above: row 2 has the
            # option/image cells empty, so a True/False row following an MCQ
            # does not inherit that MCQ's four options.
            copy_item_row(worksheet, 2, row, max_data_column)

        item = pair[side]
        fields = {
            "grade": curriculum["grade"],
            "subject": curriculum["subject"],
            "book": curriculum["book"],
            # Mathematics is the unitless subject on this template - the
            # chapter hangs straight off the book, so Unit stays empty.
            "unit": None,
            "chapter": curriculum["chapter"],
            "sequence": pair["seq"],
            "competency": pair["competency"],
            "learning_outcome": pair["learning_outcome"],
            "blooms": pair["blooms"],
            "blooms_explanation": pair["blooms_explanation"],
            "typology": pair["typology"],
            "question": item["question"],
            "answer": item["answer"],
            "explanation": item["explanation"],
            "marks": pair["marks"],
        }
        for index, option in enumerate(item.get("options") or [], start=1):
            fields[f"option_{index}"] = option
        write_row_fields(worksheet, row, columns, fields)

    clear_rows_from(worksheet, len(pairs) + 2, max_data_column)
    workbook.save(target)
    workbook.close()
    return target


def main():
    data = json.loads(PAIRS_FILE.read_text(encoding="utf-8"))
    pairs = data["pairs"]
    # Read from the checked-in QA template rather than CBSE_UPLOAD_ITEM_FILE, so
    # building the sheets never depends on which environment .env points at.
    template = Path("data/upload_templates/sme_sheet.xlsx")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curriculum = data["curriculum"]
    sides = [("A", "sheet_A_originals.xlsx"), ("B", "sheet_B_semantic.xlsx")]
    # Sheet C only exists once the numbers-only variant has been injected.
    if all("C" in pair for pair in pairs):
        sides.append(("C", "sheet_C_numbers_only.xlsx"))
    for side, name in sides:
        target = build_sheet(template, pairs, side, OUTPUT_DIR / name, curriculum)
        print(f"Sheet {side}: {target}  ({len(pairs)} rows)")
    print(f"All rows: {curriculum['grade']} / {curriculum['subject']} / "
          f"{curriculum['book']} / {curriculum['chapter']}")


if __name__ == "__main__":
    main()
