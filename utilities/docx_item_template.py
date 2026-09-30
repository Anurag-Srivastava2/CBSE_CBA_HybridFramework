"""Read and rewrite the Word item-upload template.

The Word template is the .docx counterpart of the Excel sheet
`utilities/item_template_columns.py` handles: same canonical fields, laid out
down a two-column table instead of across a header row. One block per question
-- a "Question N" heading followed by a 25-row table whose left cell is the
field label and whose right cell is the value.

Everything here works on the raw WordprocessingML inside the .docx zip. No
python-docx: the framework does not ship it, and the edits needed are narrow
(read a field, set a field, rename a label), so a dependency would buy little.

Values are written into the *first* run of the target cell and the remaining
runs are emptied, which keeps the cell's formatting and leaves the document
openable in Word. Word splits a single visible string across several runs
whenever it tracks spelling or revision state, so reading concatenates runs and
writing collapses them.
"""

import copy
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree

W_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{W_NAMESPACE}}}"

DOCUMENT_PART = "word/document.xml"

# The 25 field labels every sample document carries, in the order they appear.
# Kept as a tuple so a template that grows or reorders fields is caught by
# `assert_canonical_labels` rather than silently changing what a test uploads.
FIELD_LABELS = (
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

# Fields whose value is an image filename that must also be present in the
# companion images .zip. Used to check a document and its zip agree before an
# upload blames the app for a packaging mistake.
IMAGE_FIELDS = (
    "Question Image",
    "Image 1",
    "Image 2",
    "Image 3",
    "Image 4",
    "Answer Image",
)


def _register_namespace():
    """Keep the w: prefix on round-trip so Word still opens what we write."""
    ElementTree.register_namespace("w", W_NAMESPACE)


def _cell_text(cell):
    """The visible string of a table cell, runs concatenated."""
    return "".join(node.text or "" for node in cell.iter(f"{_W}t"))


def _set_cell_text(cell, value):
    """Replace a cell's visible string, preserving its first run's formatting."""
    text_nodes = list(cell.iter(f"{_W}t"))
    if text_nodes:
        text_nodes[0].text = value
        # `xml:space="preserve"` keeps leading/trailing spaces from being eaten.
        text_nodes[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        for extra in text_nodes[1:]:
            extra.text = ""
        return

    # An empty cell has a paragraph but no run to write into, so build one.
    paragraph = cell.find(f"{_W}p")
    if paragraph is None:
        paragraph = ElementTree.SubElement(cell, f"{_W}p")
    run = ElementTree.SubElement(paragraph, f"{_W}r")
    text_node = ElementTree.SubElement(run, f"{_W}t")
    text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_node.text = value


def _label_value_rows(root):
    """Every two-column table row in the document, as (row, label, value cells).

    Rows with fewer than two cells are skipped: the heading tables in some
    documents carry a single merged cell.
    """
    rows = []
    for row in root.iter(f"{_W}tr"):
        cells = row.findall(f"{_W}tc")
        if len(cells) >= 2:
            rows.append((row, cells[0], cells[1]))
    return rows


def _load_document(path):
    _register_namespace()
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read(DOCUMENT_PART)
    return ElementTree.fromstring(xml_bytes)


def _save_document(source_path, target_path, root):
    """Write `root` back into a copy of the source .docx.

    Rebuilds the archive rather than patching in place: a zip entry cannot be
    replaced with a different-length one, and rewriting keeps every other part
    (styles, media, relationships) byte-identical.
    """
    _register_namespace()
    target_path = Path(target_path)
    source_path = Path(source_path)
    if target_path != source_path:
        shutil.copy2(source_path, target_path)

    document_bytes = ElementTree.tostring(root, encoding="UTF-8", xml_declaration=True)

    with zipfile.ZipFile(source_path) as source_archive:
        entries = [
            (info, source_archive.read(info.filename))
            for info in source_archive.infolist()
        ]

    with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as target_archive:
        for info, payload in entries:
            target_archive.writestr(
                info, document_bytes if info.filename == DOCUMENT_PART else payload
            )
    return target_path


def read_fields(path):
    """Every label -> value pair in the document's first question block.

    Later blocks repeat the same labels, so a plain dict would silently keep
    only the last. Callers that need every block ask `read_blocks`.
    """
    blocks = read_blocks(path)
    return blocks[0] if blocks else {}


def read_blocks(path):
    """One dict per question block, split whenever the label order restarts."""
    root = _load_document(path)
    blocks = []
    current = {}
    for _, label_cell, value_cell in _label_value_rows(root):
        label = _cell_text(label_cell).strip()
        if not label:
            continue
        if label in current:
            blocks.append(current)
            current = {}
        current[label] = _cell_text(value_cell).strip()
    if current:
        blocks.append(current)
    return blocks


def write_fields(source_path, target_path, updates, block_index=0):
    """Copy `source_path` to `target_path` with `updates` applied.

    `updates` maps field label to new value. A label the document does not
    carry raises rather than being ignored -- a silently dropped update would
    upload a file that does not test what the caller asked for.
    """
    root = _load_document(source_path)
    rows = _label_value_rows(root)

    seen_labels = set()
    block = 0
    applied = set()
    for _, label_cell, value_cell in rows:
        label = _cell_text(label_cell).strip()
        if not label:
            continue
        if label in seen_labels:
            block += 1
            seen_labels = set()
        seen_labels.add(label)
        if block != block_index:
            continue
        if label in updates:
            _set_cell_text(value_cell, str(updates[label]))
            applied.add(label)

    missing = set(updates) - applied
    assert not missing, (
        f"{Path(source_path).name} has no field labelled {sorted(missing)} in block "
        f"{block_index}. Known labels: {sorted(seen_labels) or list(FIELD_LABELS)}"
    )
    return _save_document(source_path, target_path, root)


def _paragraph_text(paragraph):
    return "".join(node.text or "" for node in paragraph.iter(f"{_W}t"))


def add_question_blocks(source_path, target_path, blocks):
    """Copy `source_path` with extra question blocks appended after the first.

    Case Based and Source Based items are several blocks: a parent (S.No. "1",
    the passage) and one block per sub-question (S.No. "1.1", "1.2", ...), each
    with its own leaf Typology - the importer fails a parent with no sub-rows.
    Each new block clones the first block's "Question 1" heading and table, so
    it inherits Grade, Subject, Chapter, Competency and the rest, then applies
    its own `updates` dict. Every field the parent carries but a block does not
    override is kept, so pass "" to blank one (e.g. the parent's Answer).
    """
    root = _load_document(source_path)
    body = root.find(f"{_W}body")
    children = list(body)
    table_index = next(
        index for index, node in enumerate(children) if node.tag == f"{_W}tbl"
    )
    heading = next(
        (
            node
            for node in reversed(children[:table_index])
            if node.tag == f"{_W}p" and _paragraph_text(node).strip().startswith("Question")
        ),
        None,
    )
    assert heading is not None, (
        f"{Path(source_path).name} has no 'Question 1' heading before its first table."
    )
    table = children[table_index]
    # Before the section properties, which Word requires to stay last.
    insert_at = next(
        (index for index, node in enumerate(body) if node.tag == f"{_W}sectPr"),
        len(body),
    )
    for number, updates in enumerate(blocks, start=2):
        new_heading = copy.deepcopy(heading)
        text_nodes = list(new_heading.iter(f"{_W}t"))
        text_nodes[0].text = f"Question {number}"
        for extra in text_nodes[1:]:
            extra.text = ""
        new_table = copy.deepcopy(table)
        for _, label_cell, value_cell in _label_value_rows(new_table):
            label = _cell_text(label_cell).strip()
            if label in updates:
                _set_cell_text(value_cell, str(updates[label]))
        unknown = set(updates) - set(FIELD_LABELS)
        assert not unknown, f"Unknown field label(s) {sorted(unknown)} for block {number}."
        body.insert(insert_at, new_heading)
        body.insert(insert_at + 1, new_table)
        insert_at += 2
    return _save_document(source_path, target_path, root)


def rename_field_label(source_path, target_path, old_label, new_label):
    """Rename a field label, for the negative case the template warns about.

    The template's own instruction line says "do not rename the field labels",
    so a renamed label is the documented way to make a structurally valid Word
    file the importer should still refuse.
    """
    root = _load_document(source_path)
    renamed = 0
    for _, label_cell, _value_cell in _label_value_rows(root):
        if _cell_text(label_cell).strip() == old_label:
            _set_cell_text(label_cell, new_label)
            renamed += 1
    assert renamed, f"{Path(source_path).name} has no field labelled {old_label!r} to rename."
    return _save_document(source_path, target_path, root)


def uniquify_question(source_path, target_path, run_id, block_index=0):
    """Stamp a run id into the Question text so re-runs are not duplicates.

    The samples ship with a `[QA-...]` tag already. Replacing it rather than
    appending keeps the question from growing on every run and keeps the
    plagiarism/duplicate checks looking at fresh content each time.
    """
    fields = read_blocks(source_path)[block_index]
    question = re.sub(r"\s*\[QA-[^\]]*\]", "", fields.get("Question", "")).strip()
    stamped = f"{question} [QA-{run_id}]"
    write_fields(source_path, target_path, {"Question": stamped}, block_index=block_index)
    return stamped


def assert_canonical_labels(path):
    """Fail loudly when a document's field labels drift from FIELD_LABELS.

    A drifted template still uploads and still looks valid, so without this a
    changed label would surface much later as an unexplained row-validation
    failure -- the same trap `ReadConfig._carries_current_columns` guards for
    the Excel sheet.
    """
    labels = tuple(read_fields(path).keys())
    assert labels == FIELD_LABELS, (
        f"{Path(path).name} field labels have drifted from the canonical order.\n"
        f"  expected: {list(FIELD_LABELS)}\n"
        f"  actual:   {list(labels)}"
    )
    return labels


def referenced_images(path):
    """Image filenames the document points at, across every block."""
    names = []
    for block in read_blocks(path):
        for field in IMAGE_FIELDS:
            value = (block.get(field) or "").strip()
            if value:
                names.append(value)
    return names


def zip_member_names(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        return [
            Path(name).name
            for name in archive.namelist()
            if not name.endswith("/")
        ]
