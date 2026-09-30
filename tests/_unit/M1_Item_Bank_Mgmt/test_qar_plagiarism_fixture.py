from openpyxl import load_workbook

from utilities.qar_plagiarism_fixture import (
    EXPECTED_PLAGIARISM_THRESHOLD,
    PUBLISHED_SOURCE_ITEMS,
    build_qar_plagiarism_workbook,
    source_similarity,
)
from utilities.item_template_columns import resolve_columns
from utilities.read_config import ReadConfig


def test_pdf_plagiarism_fixture_preserves_six_verbatim_sources(tmp_path, record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Build the PDF plagiarism fixture workbook.\n"
        "Check it carries six items copied word for word from their published "
        "sources, with the source evidence recorded alongside each.",
    )
    output, evidence = build_qar_plagiarism_workbook(
        ReadConfig.get_upload_item_file_path(),
        tmp_path / "pdf-plagiarism.xlsx",
        "QAR_AUTO_PDF_PLAG_UNIT",
    )
    assert len(evidence) == 6
    assert len({row["source_item_id"] for row in evidence}) == 6
    assert {row["source_pdf_page"] for row in evidence} == {1, 2, 3}
    assert all(
        row["source_similarity"] >= EXPECTED_PLAGIARISM_THRESHOLD
        for row in evidence
    )

    workbook = load_workbook(output, data_only=True)
    worksheet = workbook.active
    columns = resolve_columns(worksheet)
    assert columns, "Built workbook has no recognisable item-data sheet."
    for row, source in enumerate(PUBLISHED_SOURCE_ITEMS, start=2):
        assert worksheet.cell(row, columns["typology"]).value == "True or False"
        assert worksheet.cell(row, columns["question"]).value == source.question
        assert source_similarity(worksheet.cell(row, columns["question"]).value, source.question) == 100
        assert worksheet.cell(row, columns["answer"]).value == source.answer
    workbook.close()


def test_similarity_contract_rejects_content_below_97_percent(record_property):
    # Plain-English orientation for the report, for a reader who does
    # not know this test. One line per step, in the order they happen.
    record_property(
        "test_summary",
        "Score a passage against itself, and then against unrelated text.\n"
        "Check identical text scores 100 and unrelated text falls below the 97 "
        "percent mark the fixture relies on.",
    )
    source = PUBLISHED_SOURCE_ITEMS[0].question
    assert source_similarity(source, source) == 100
    assert source_similarity("An unrelated new question.", source) < 97
