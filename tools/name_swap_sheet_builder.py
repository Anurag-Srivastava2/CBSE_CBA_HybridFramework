"""Shared builder for the A/C "only the names changed" upload sheets.

Sheet C is always GENERATED from Sheet A by substitution rather than typed out
a second time, so "nothing but the names differ" holds by construction. It is
then re-verified: blank every name from either set out of both questions and
the remainders must match exactly.

Used by build_english_name_sheets.py and build_hindi_name_sheets.py. The row
shape and the 24-row / 12-typology layout are the callers' business; this
module only knows how to write one side of a row set into the template.
"""
import re
from shutil import copy2

from openpyxl import load_workbook

from utilities.item_template_columns import (
    clear_rows_from,
    copy_item_row,
    resolve_columns,
    trim_helper_columns,
    write_row_fields,
)


def row(sno, typology, comp, lo, blooms, blooms_exp, marks, question,
        answer=None, explanation=None, options=None):
    """One sheet row. Parent rows (Case/Source Based) pass answer=None."""
    return {
        "sno": sno, "typology": typology, "competency": comp, "learning_outcome": lo,
        "blooms": blooms, "blooms_explanation": blooms_exp, "marks": marks,
        "question": question, "answer": answer, "explanation": explanation,
        "options": options,
    }


def make_swapper(name_map):
    pattern = re.compile("|".join(re.escape(n) for n in sorted(name_map, key=len, reverse=True)))

    def swap(value):
        if not isinstance(value, str):
            return value
        return pattern.sub(lambda m: name_map[m.group(0)], value)
    return swap


def make_blanker(name_map):
    """Blank every name from BOTH sides, so A and C reduce to the same text."""
    every = sorted(set(name_map) | set(name_map.values()), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(n) for n in every))

    def blank(value):
        return pattern.sub("@", value) if isinstance(value, str) else value
    return blank


def build_sheet(rows, side, target, template, curriculum, name_map):
    """Write one side ("A" or "C") of the row set into a copy of the template."""
    copy2(template, target)
    workbook = load_workbook(target)
    worksheet = workbook["Items"]
    width = trim_helper_columns(worksheet)
    columns = resolve_columns(worksheet)
    if not columns:
        raise SystemExit(f"{template} has no recognisable item-data sheet.")

    swap = make_swapper(name_map)
    pick = swap if side == "C" else (lambda value: value)

    for offset, item in enumerate(rows):
        excel_row = offset + 2
        if excel_row != 2:
            # Always cloned from row 2 so a non-MCQ row cannot inherit the
            # option cells of whatever row happened to precede it.
            copy_item_row(worksheet, 2, excel_row, width)
        fields = {
            **curriculum,
            "sequence": item["sno"],
            "competency": item["competency"],
            "learning_outcome": item["learning_outcome"],
            "blooms": item["blooms"],
            "blooms_explanation": item["blooms_explanation"],
            "typology": item["typology"],
            "question": pick(item["question"]),
            "answer": pick(item["answer"]),
            "explanation": pick(item["explanation"]),
            "marks": item["marks"],
            "option_1": None, "option_2": None, "option_3": None, "option_4": None,
        }
        for index, option in enumerate(item["options"] or [], start=1):
            fields[f"option_{index}"] = pick(option)
        write_row_fields(worksheet, excel_row, columns, fields)

    clear_rows_from(worksheet, len(rows) + 2, width)
    workbook.save(target)
    workbook.close()
    return target


def verify_name_swap(rows, name_map):
    """Return the problems with the A->C swap; empty list means it is clean."""
    swap, blank = make_swapper(name_map), make_blanker(name_map)
    problems = []
    for item in rows:
        a = item["question"]
        c = swap(a)
        if blank(a) != blank(c):
            problems.append(f"{item['sno']}: more than the names changed")
        if a == c:
            problems.append(f"{item['sno']}: carries no swappable name, so A and C "
                            "would be byte-identical and the importer rejects it")
    return problems
