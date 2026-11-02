import runpy
from pathlib import Path

from docx import Document

SNIPPETS = Path(__file__).resolve().parents[1] / "docs" / "copilot_snippets.py"


def load():
    return runpy.run_path(str(SNIPPETS))


def test_verify_flags_only_text_that_is_not_in_the_source():
    ns = load()
    source = "4.1.2 The Proponent shall describe its\nsupport model, including hours of coverage."
    rows = [{"text": "The Proponent shall describe its support model, including hours of coverage."},
            {"text": "The Proponent must describe its support model."},
            {"text": "The Proponent shall describe its support model, including hours of coverage"}]
    assert [r["text"] for r in ns["verify"](rows, source)] == ["The Proponent must describe its support model."]


def test_build_register_writes_one_table_per_section_with_fixed_columns(tmp_path):
    ns = load()
    rows = [{"rfp": "a.pdf", "section": "4.1 Experience", "ref": "4.1.1", "text": 'Describe "AT&T" <b>x</b>.', "type": "Narrative",
             "required": True, "constraints": "", "source": "p.3 L4"},
            {"rfp": "a.pdf", "section": "4.2 Security", "ref": None, "text": "Does it support SAML? (Yes/No)", "type": "Yes / No",
             "required": False, "constraints": "", "source": "p.4 L1"},
            {"rfp": "b.docx", "section": "1 Intro", "ref": "1", "text": "Attach the roadmap.", "type": "Upload", "required": True,
             "constraints": "", "source": "§1 ¶2"}]
    path = ns["build_register"](rows, str(tmp_path / "out.docx"))
    doc = Document(path)
    assert len(doc.tables) == 3
    assert all([c.text for c in t.rows[0].cells] == [name for name, _ in ns["COLUMNS"]] for t in doc.tables)
    assert doc.tables[0].rows[1].cells[1].text == 'Describe "AT&T" <b>x</b>.'
    assert doc.tables[1].rows[1].cells[3].text == "Optional" and doc.tables[1].rows[1].cells[0].text == "-"
