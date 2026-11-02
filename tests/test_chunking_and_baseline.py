import pytest

from rfpx.baseline import extract_blocks, infer_constraints, infer_required, infer_type
from rfpx.chunking import chunk_document
from rfpx.ingest import read_document
from rfpx.textutil import match_key

# --- chunking ---------------------------------------------------------------------------------------

def test_chunks_respect_the_size_limit_and_cover_every_readable_block(rfp_files):
    for name, path in rfp_files.items():
        doc = read_document(path)
        chunks = chunk_document(doc, max_chars=1800)
        covered = [b.idx for c in chunks for b in c.blocks]
        readable = [b.idx for b in doc.blocks if not b.noise]
        assert covered == readable, name
        assert all(c.size <= 1800 + 700 for c in chunks), name        # a single long block may overshoot, nothing else


def test_chunk_prompt_text_has_section_line_headings_and_table_header_once(rfp_files):
    doc = read_document(rfp_files["lakeshore-billing-modernization.docx"])
    chunk = next(c for c in chunk_document(doc, max_chars=1800) if any(b.kind == "row" and b.header and "Requirement" in b.header for b in c.blocks))
    lines = chunk.prompt.splitlines()
    assert lines[0].startswith("Section: ")
    assert sum(1 for line in lines if line.startswith("| Req #")) == 1
    assert any(line.startswith("| R-") for line in lines)


def test_pdf_chunks_start_on_a_page_boundary_once_they_are_well_filled(rfp_files):
    doc = read_document(rfp_files["capital-library-digital-content.pdf"])
    chunks = chunk_document(doc, max_chars=2400)
    for earlier, later in zip(chunks, chunks[1:], strict=False):
        if earlier.blocks[-1].page != later.blocks[0].page:
            assert earlier.size >= 0.4 * 2400 or earlier.size + len(later.blocks[0].text) > 2400


# --- type and required ---------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Does the platform support SAML 2.0? (Yes/No)", "yes_no"),
    ("Confirm that all data will be stored in Canada. (Yes/No)", "yes_no"),
    ("Attach a certificate of insurance showing coverage of not less than $5,000,000.", "upload"),
    ("Upload resumes (PDF, not exceeding two pages per person) for all key personnel.", "upload"),
    ("Complete the Pricing Schedule in Appendix C, showing all prices in Canadian dollars.", "pricing"),
    ("Provide hourly rates by role for change requests and additional services.", "pricing"),
    ("List all subcontractors you intend to use and the portion of the work each will perform.", "table"),
    ("Provide a work plan in tabular form showing milestones, deliverables, responsibilities and dates.", "table"),
    ("Describe your support model, including hours of coverage.", "narrative"),
    ("What are your standard support hours?", "narrative"),
])
def test_infer_type(text, expected):
    assert infer_type(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("The Proponent shall describe its support model.", True),
    ("The Proponent must describe its support model.", True),
    ("The Proponent should describe its support model.", False),
    ("(Optional) Describe your support model.", False),
    ("(Desirable) Describe your support model.", False),
    ("Describe your support model.", True),
])
def test_infer_required(text, expected):
    assert infer_required(text) is expected


def test_infer_constraints_keeps_decimals_limits_and_appendix_references():
    assert infer_constraints("Confirm monthly availability of at least 99.9 percent. (Yes/No)") == "of at least 99.9 percent"
    assert "not exceeding two pages per person" in infer_constraints("Attach a resume for each member, not exceeding two pages per person.")
    assert infer_constraints("Complete the Pricing Schedule in Appendix C.") == "Appendix C"
    assert infer_constraints("Describe your support model.") == ""


# --- extraction on real synthetic files ------------------------------------------------------------------

def test_baseline_reads_table_requirements_with_their_mandatory_column(rfp_files):
    doc = read_document(rfp_files["lakeshore-billing-modernization.docx"])
    found = extract_blocks(doc.blocks)
    matrix = [f for f in found if f.q.question_text.startswith("The customer billing and payment system")]
    assert len(matrix) == 16
    assert {f.q.type for f in matrix} == {"yes_no"}
    assert {f.q.required for f in matrix} == {True, False}


def test_baseline_ignores_pricing_tables_evaluation_tables_and_definitions(rfp_files):
    doc = read_document(rfp_files["northfield-fleet-telematics.docx"])
    texts = " ".join(f.q.question_text for f in extract_blocks(doc.blocks))
    assert "Technical approach" not in texts           # evaluation criteria table
    assert "Software licences (annual)" not in texts   # pricing table row
    assert "means" not in texts                        # definitions


def test_baseline_splits_numbers_off_and_keeps_text_verbatim(rfp_files, gold):
    doc = read_document(rfp_files["northfield-fleet-telematics.docx"])
    found = extract_blocks(doc.blocks)
    keys = {match_key(g["question_text"]): g for g in gold["northfield-fleet-telematics.docx"]["questions"]}
    hit = [f for f in found if match_key(f.q.question_text) in keys]
    assert len(hit) >= 35
    sample = hit[0]
    assert sample.q.id == keys[match_key(sample.q.question_text)]["id"]
    assert sample.q.source_ref.startswith("§")
