import json

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

from utilities.item_bank_workbook_builder import build_item_workbook
from utilities.item_template_columns import (
    CANONICAL_HEADERS,
    resolve_columns,
    write_row_fields,
)
from utilities.question_bank_manager import content_hash


def _seed_isolated_question_bank(monkeypatch, tmp_path):
    """Point the builder at a throwaway bank/env so this offline unit test never
    consumes real per-environment usage from the shared data/question_bank file."""
    typologies = (
        "Multiple Choice Question", "Fill in the Blank", "Match the Following", "True or False",
    )
    records = []
    index = 0
    for repeat in range(2):
        for typology in typologies:
            index += 1
            question = f"Fixture question {index} for {typology}"
            records.append({
                "id": f"FIXTURE-{index:03d}",
                "typology": typology,
                "grade": "5",
                "subject": "Mathematics",
                "chapter": "Fixture Chapter",
                "competency": "Fixture Competency",
                "blooms_level": "Understanding",
                "question": question,
                "options": ["A", "B", "C", "D"] if typology == "Multiple Choice Question" else [],
                "answer": (
                    "A" if typology == "Multiple Choice Question"
                    else "True" if typology == "True or False"
                    else "Fixture answer"
                ),
                "explanation": "Fixture explanation.",
                "marks": 1,
                "content_hash": content_hash(question),
                "usage": {},
            })
    bank_path = tmp_path / "fixture_questions.json"
    bank_path.write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setenv("CBSE_QUESTION_BANK_PATH", str(bank_path))
    monkeypatch.setenv("CBSE_ENV", "offline-fixture-tests")


# The sheet is built from the shared contract rather than a second copy of
# the header list, so a column added to the template cannot leave this test
# passing against a shape the app no longer sends.
HEADERS = CANONICAL_HEADERS


def _add_item_sheet(workbook, title):
    worksheet = workbook.create_sheet(title)
    for column, header in enumerate(HEADERS, start=1):
        worksheet.cell(row=1, column=column).value = header
    columns = resolve_columns(worksheet)
    metadata = {
        "grade": "Grade 1",
        "subject": "Mathematics",
        "book": "Book 1",
        # Unit is left empty on purpose: it is optional, and the subject this
        # row names has no unit data behind it — the same shape the checked-in
        # typology templates carry.
        "unit": None,
        "chapter": "How do I Spend my Day? (Time)",
        "sequence": 1,
        "competency": "Uses time in daily life",
        "learning_outcome": "Reads time to the hour",
        "blooms": "Applying",
        "blooms_explanation": "Uses a clock to reason about time",
    }
    write_row_fields(worksheet, 2, columns, metadata)
    worksheet.cell(row=6, column=columns["question"]).value = "stale item that must be cleared"
    # Past the item columns: a helper cell the builder must leave alone.
    worksheet["CA2"] = "True or False"
    validation = DataValidation(type="list", formula1='"True or False,Fill in the Blank"')
    worksheet.add_data_validation(validation)
    validation.add(f"{worksheet.cell(row=1, column=columns['typology']).column_letter}2:"
                   f"{worksheet.cell(row=1, column=columns['typology']).column_letter}500")
    return worksheet


def _create_template(path):
    workbook = Workbook()
    workbook.remove(workbook.active)
    _add_item_sheet(workbook, "Items")
    _add_item_sheet(workbook, "Items Hindi")
    lookup = workbook.create_sheet("Lookups")
    lookup["A1"] = "must remain unchanged"
    workbook.save(path)
    workbook.close()


def test_builder_creates_four_mixed_non_image_items_per_sheet(tmp_path, monkeypatch, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Ask the workbook builder for a sheet of mixed non-image items, against "
        "an isolated question bank.\n"
        "Check it writes four items per sheet and reports a summary matching what "
        "it actually wrote.",
    )
    _seed_isolated_question_bank(monkeypatch, tmp_path)
    template = tmp_path / "template.xlsx"
    output = tmp_path / "offline-items.xlsx"
    _create_template(template)

    _, summaries = build_item_workbook(
        template,
        output,
        count=4,
        seed="offline-verification",
    )

    assert {name: len(items) for name, items in summaries.items()} == {
        "Items": 4,
        "Items Hindi": 4,
    }

    workbook = load_workbook(output, read_only=False, data_only=False)
    expected_typologies = [
        "Multiple Choice Question",
        "Fill in the Blank",
        "Match the Following",
        "True or False",
    ]
    all_questions = []
    for sheet_name in ("Items", "Items Hindi"):
        worksheet = workbook[sheet_name]
        columns = resolve_columns(worksheet)
        questions = [
            worksheet.cell(row=row, column=columns["question"]).value for row in range(2, 6)
        ]
        all_questions.extend(questions)
        assert all(questions)
        assert worksheet.cell(row=6, column=columns["question"]).value is None
        assert [
            worksheet.cell(row=row, column=columns["typology"]).value for row in range(2, 6)
        ] == expected_typologies
        # Book and Unit come from the template row and must be carried onto
        # every generated row: the importer resolves the curriculum chain per
        # row, and a row missing its Book fails validation.
        assert [
            worksheet.cell(row=row, column=columns["book"]).value for row in range(2, 6)
        ] == ["Book 1"] * 4
        assert [
            worksheet.cell(row=row, column=columns["unit"]).value for row in range(2, 6)
        ] == [None] * 4
        expected_options = [
            *summaries[sheet_name][1]["options"],
            *([None] * (4 - len(summaries[sheet_name][1]["options"]))),
        ]
        assert [
            worksheet.cell(row=3, column=columns[f"option_{index}"]).value
            for index in range(1, 5)
        ] == expected_options
        assert worksheet["CA2"].value == "True or False"
        assert len(worksheet.data_validations.dataValidation) == 1
        assert len(worksheet._images) == 0
        assert worksheet.cell(row=5, column=columns["question_image"]).value is None

    assert len(all_questions) == len(set(all_questions))
    assert workbook["Lookups"]["A1"].value == "must remain unchanged"
    workbook.close()
