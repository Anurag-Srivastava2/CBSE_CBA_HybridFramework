"""The item-upload sheet's column contract, in one place.

The importer accepts exactly the canonical columns and nothing else: a
workbook still carrying the template's helper/lookup columns past the last
canonical one is rejected outright, so every writer in the suite has to know
where the item data stops. Before Book and Unit existed that boundary was
column 24, and it was spelled as a bare `24` in nine different modules.

`Book` and `Unit` were then inserted at C and D (replacing the single
`Unit/Theme`), which shifted every column from `Chapter No._Name` rightwards by
one and moved the boundary to 25. Rather than renumber nine sets of magic
constants — and do it again at the next insertion — callers resolve columns by
*field name* through `resolve_columns()`, which reads the header row of the
sheet actually in hand. A sheet written against an older template still
resolves, because the aliases cover both spellings.

Column *order* is not asserted here on purpose. The importer keys on header
text, and templates downloaded from different environments have been seen to
disagree on order; `CANONICAL_HEADERS` records the current shape for the
template builders and for the contract test that compares it against a live
download.
"""

# The Items sheet as the app's current template ships it, in order. Index+1 of
# an entry is its column number, which is what makes `Marks` column 25.
CANONICAL_HEADERS = (
    "Grade",
    "Subject",
    "Book",
    "Unit",
    "Chapter No._Name",
    "S.No.",
    "Competency",
    "Learning Outcome",
    "Blooms Taxonomy",
    "Explanation of Blooms Taxonomy",
    "Typology",
    "Question",
    "Question Image",
    "Option 1",
    "Option 2",
    "Option 3",
    "Option 4",
    "Image 1",
    "Image 2",
    "Image 3",
    "Image 4",
    "Answer",
    "Answer Image",
    "Explanation/Remarks",
    "Marks",
)

#: How many columns the importer treats as item data. Anything beyond this is a
#: template helper column and has to be dropped before upload.
CANONICAL_COLUMN_COUNT = len(CANONICAL_HEADERS)

# Field name -> the header spellings that mean it, most specific first.
# Matching is on alphanumerics only and case-insensitive, so "Chapter No._Name",
# "chapter no name" and "Chapter" all collapse to the same key.
FIELD_ALIASES = {
    "grade": ("grade",),
    "subject": ("subject",),
    "book": ("book", "bookname", "booktitle"),
    # "Unit" must not be allowed to match the retired "Unit/Theme": that column
    # sat where Book sits now, so accepting it here would write a unit value
    # into the book position on a stale template.
    "unit": ("unit", "unitname"),
    "chapter": ("chapternoname", "chapter", "chapterno", "chaptername"),
    "sequence": ("sno", "serialnumber", "itemnumber"),
    "competency": ("competency",),
    "learning_outcome": ("learningoutcome", "learningoutcomencert"),
    "blooms": ("bloomstaxonomy", "bloomslevel", "blooms"),
    "blooms_explanation": ("explanationofbloomstaxonomy",),
    "typology": ("typology", "questiontypology", "itemtype"),
    "question": ("question", "questiontext", "itemcontent"),
    "question_image": ("questionimage",),
    "option_1": ("option1", "optiona"),
    "option_2": ("option2", "optionb"),
    "option_3": ("option3", "optionc"),
    "option_4": ("option4", "optiond"),
    "image_1": ("image1",),
    "image_2": ("image2",),
    "image_3": ("image3",),
    "image_4": ("image4",),
    "answer": ("answer", "correctanswer", "answerkey"),
    "answer_image": ("answerimage",),
    "explanation": ("explanationremarks", "explanation", "rationale"),
    "marks": ("marks", "mark"),
}

#: Without these a sheet is not an item-data sheet at all — the builders use
#: this to skip a template's Instructions and lookup sheets.
REQUIRED_FIELDS = ("sequence", "typology", "question", "answer", "explanation", "marks")


def normalize_header(value):
    """Reduce a header to the alphanumerics that identify it, casefolded."""
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def header_columns(worksheet):
    """Map every normalized header in row 1 to its column number."""
    return {
        normalize_header(cell.value): cell.column
        for cell in worksheet[1]
        if cell.value is not None
    }


def resolve_columns(worksheet, required=REQUIRED_FIELDS):
    """Field name -> column number for one worksheet, or None if it is not an
    item-data sheet.

    Every field in FIELD_ALIASES gets a key; one the sheet does not carry maps
    to None rather than being absent, so callers can write
    `columns["book"] is None` for "this template predates Book" without having
    to guard the lookup itself.
    """
    headers = header_columns(worksheet)
    resolved = {
        field: next(
            (headers[alias] for alias in aliases if alias in headers),
            None,
        )
        for field, aliases in FIELD_ALIASES.items()
    }
    if any(resolved[field] is None for field in required):
        return None
    return resolved


def item_data_worksheet(workbook):
    """The workbook's item-data sheet, or None.

    Not `workbook.active`: the downloaded template opens on its
    "CBSE Item Upload — Instructions" sheet, whose row 1 is a title.
    """
    return next(
        (sheet for sheet in workbook.worksheets if resolve_columns(sheet) is not None),
        None,
    )


def last_item_column(worksheet):
    """The rightmost column the importer reads as item data on this sheet.

    Derived from the sheet's own headers rather than assumed to be
    CANONICAL_COLUMN_COUNT: the typology templates are trimmed to the canonical
    columns, while a freshly downloaded template carries its lookup data far to
    the right, and both have to give the same answer here.
    """
    columns = resolve_columns(worksheet)
    if columns is None:
        return CANONICAL_COLUMN_COUNT
    return max(column for column in columns.values() if column is not None)


def trim_helper_columns(worksheet):
    """Drop the template's helper/lookup columns, which the importer rejects.

    Returns the last item-data column, so the caller can go on to use it as the
    copy/clear width.
    """
    boundary = last_item_column(worksheet)
    if worksheet.max_column > boundary:
        worksheet.delete_cols(boundary + 1, worksheet.max_column - boundary)
    return boundary


def copy_item_row(worksheet, source_row, target_row, item_column_count=None):
    """Duplicate an item row's values and styling across the item columns.

    Used to carry the template's curriculum chain — Grade, Subject, Book, Unit,
    Chapter, Competency, Learning Outcome, Bloom's — onto every row a fixture
    writes, since the importer resolves those per row and a blank one fails
    validation. The width is read from the sheet unless the caller pins it.
    """
    from copy import copy as copy_style  # local: only the writers need it

    width = item_column_count or last_item_column(worksheet)
    for column in range(1, width + 1):
        source_cell = worksheet.cell(row=source_row, column=column)
        target_cell = worksheet.cell(row=target_row, column=column)
        target_cell.value = source_cell.value
        if source_cell.has_style:
            target_cell._style = copy_style(source_cell._style)
        target_cell.alignment = copy_style(source_cell.alignment)
        target_cell.protection = copy_style(source_cell.protection)
        target_cell.number_format = source_cell.number_format
    return width


def clear_rows_from(worksheet, first_row, item_column_count=None):
    """Blank every item column from `first_row` down.

    The templates ship with sample rows below the first, and a row left behind
    under the ones a fixture wrote is uploaded as a real item.
    """
    width = item_column_count or last_item_column(worksheet)
    for row in range(first_row, worksheet.max_row + 1):
        for column in range(1, width + 1):
            worksheet.cell(row=row, column=column).value = None
    return width


def write_row_fields(worksheet, row, columns, values):
    """Write {field name: value} into one row through a resolved column map.

    A field the sheet does not carry is skipped rather than raising, so a
    fixture can set `unit` unconditionally and still build against a template
    that predates it.
    """
    for field, value in values.items():
        column = columns.get(field)
        if column is not None:
            worksheet.cell(row=row, column=column).value = value


def write_canonical_headers(worksheet):
    """Lay the canonical header row onto a blank sheet, and resolve it.

    Fixtures that hand-build a workbook rather than copying a template use this
    so they exercise the same header-driven column resolution as production
    instead of writing at bare indices that quietly rot when a column moves.
    """
    for column, header in enumerate(CANONICAL_HEADERS, start=1):
        worksheet.cell(row=1, column=column).value = header
    return resolve_columns(worksheet)
