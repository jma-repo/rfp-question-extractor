import pytest

from rfpx.ingest import read_document
from rfpx.textutil import is_verbatim, squash

FORMATS = ["docx", "pdf", "xlsx"]


def _text(doc) -> str:
    return " ".join(b.text for b in doc.blocks if not b.noise)


@pytest.mark.parametrize("fmt", FORMATS)
def test_every_gold_question_survives_reading(fmt, rfp_files, gold):
    """The reader may drop noise but never a question: each answer-key text must be a verbatim piece of the readable text."""
    checked = 0
    for name, path in rfp_files.items():
        if not name.endswith(fmt):
            continue
        doc = read_document(path)
        readable = squash(_text(doc))
        missing = [g["question_text"] for g in gold[name]["questions"] if not is_verbatim(g["question_text"], readable)]
        assert not missing, f"{name}: {len(missing)} gold questions lost by the reader, e.g. {missing[:2]}"
        checked += 1
    assert checked >= 3


def test_pdf_running_header_footer_and_contents_dots_are_noise(rfp_files):
    doc = read_document(rfp_files["foothills-student-information-system.pdf"])
    noise = [b.text for b in doc.blocks if b.noise]
    assert any("CONFIDENTIAL" in t for t in noise)
    assert any("Page " in t and " of " in t for t in noise)
    assert any("......" in t for t in noise)
    assert not any("CONFIDENTIAL" in b.text for b in doc.blocks if not b.noise)


def test_pdf_wrapped_lines_are_joined_into_one_paragraph(rfp_files):
    doc = read_document(rfp_files["foothills-student-information-system.pdf"])
    block = next(b for b in doc.blocks if "single point of contact" in b.text)
    assert block.text.endswith("commit your organization?")
    assert block.loc.startswith("p.") and " L" in block.loc


def test_pdf_tables_become_rows_with_header_and_cells(rfp_files):
    doc = read_document(rfp_files["westland-cloud-hosting.pdf"])
    rows = [b for b in doc.blocks if b.kind == "row" and b.header and "Service capability" in b.header]
    assert len(rows) == 16
    assert all(len(r.cells) == len(r.header) for r in rows)
    assert any(r.cells[1].startswith("The managed cloud hosting service") for r in rows)


def test_pdf_headings_are_detected_from_bold_type(rfp_files):
    doc = read_document(rfp_files["foothills-student-information-system.pdf"])
    headings = [b.text for b in doc.blocks if b.kind == "heading"]
    assert "4.2 Technical Approach" in headings
    block = next(b for b in doc.blocks if "licensing model" in b.text)
    assert block.section == "4.2 Technical Approach"


def test_docx_numbers_stay_in_the_text_and_sections_follow_headings(rfp_files, gold):
    doc = read_document(rfp_files["northfield-fleet-telematics.docx"])
    first = gold["northfield-fleet-telematics.docx"]["questions"][0]
    block = next(b for b in doc.blocks if first["question_text"] in b.text)
    assert block.text == f"{first['id']} {first['question_text']}"
    assert block.section == first["section"]
    assert block.loc.startswith("§4.1 ¶")


def test_docx_tables_become_row_blocks_and_headers_are_not_rows(rfp_files):
    doc = read_document(rfp_files["lakeshore-billing-modernization.docx"])
    rows = [b for b in doc.blocks if b.kind == "row"]
    matrix = [r for r in rows if r.header and r.header[1] == "Requirement"]
    assert len(matrix) == 16
    assert not any(r.cells == r.header for r in rows)


def test_docx_page_numbers_pasted_into_the_body_are_noise(rfp_files):
    doc = read_document(rfp_files["prairie-health-scheduling.docx"])
    noise = [b.text for b in doc.blocks if b.noise]
    assert any(t.startswith("Page ") for t in noise)
    assert any("CONFIDENTIAL" in t for t in noise)


def test_xlsx_rows_carry_header_merged_section_and_sheet_ref(rfp_files, gold):
    doc = read_document(rfp_files["bow-river-fare-questionnaire.xlsx"])
    rows = [b for b in doc.blocks if b.kind == "row" and b.header and "Question" in b.header]
    notes = [r for r in rows if not r.cells[0]]                # note rows typed into the question column, with no reference
    assert len(rows) - len(notes) == len(gold["bow-river-fare-questionnaire.xlsx"]["questions"])
    assert notes
    assert all(r.section for r in rows)                      # the Section column is merged vertically in the file
    assert all(r.loc.startswith("Questionnaire!R") for r in rows)
    assert not any("Lists" in b.loc for b in doc.blocks)     # hidden helper sheet is skipped


def test_xlsx_banner_rows_become_headings_and_section_for_the_rows_below(rfp_files):
    doc = read_document(rfp_files["northern-lights-security-assessment.xlsx"])
    assert "Encryption" in [b.text for b in doc.blocks if b.kind == "heading"]
    row = next(b for b in doc.blocks if "AES-256" in b.text)
    assert row.section == "Encryption"


def test_locations_are_unique_within_a_document(rfp_files):
    for name, path in rfp_files.items():
        locs = [b.loc for b in read_document(path).blocks if not b.noise]
        assert len(locs) == len(set(locs)), f"{name}: duplicate locations"
