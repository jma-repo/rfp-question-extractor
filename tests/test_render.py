from pathlib import Path

import pytest
from docx import Document

from rfpx.models import Finding, Question
from rfpx.pipeline import DocResult
from rfpx.render import build_context, render_register
from rfpx.template import build_template


def f(text, id=None, section="1 Intro", type="narrative", required=True, status="accepted", reason="", ref="p.1 L1", also=(), similar="",
      constraints=""):
    q = Question(id=id, section=section, question_text=text, type=type, required=required, source_ref=ref, constraints=constraints)
    return Finding(q, "a.pdf", status=status, reason=reason, also=list(also), similar_to=similar)


@pytest.fixture()
def template(tmp_path) -> Path:
    path = tmp_path / "register.docx"
    build_template(path)
    return path


def result(name, findings, fmt="pdf"):
    return DocResult(name=name, fmt=fmt, findings=findings, notes=[], chunks=1)


def all_text(path: Path) -> str:
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts += [c.text for c in row.cells]
    return "\n".join(parts)


def test_context_groups_by_rfp_then_section_and_counts_everything():
    ctx = build_context([
        result("a.pdf", [f("Describe your support model.", "4.1", "4 Tech"), f("Does it support SAML? (Yes/No)", "4.2", "4 Tech", "yes_no", False),
                         f("Attach the roadmap.", None, "5 Docs", "upload"),
                         f("Describe the thing", None, "5 Docs", status="review", reason="not a verbatim piece of the source")]),
        result("b.docx", [f("Provide references.", "1")], fmt="docx"),
    ], extractor="Rules baseline")
    assert ctx["totals"]["rfps"] == 2 and ctx["totals"]["questions"] == 4 and ctx["totals"]["review"] == 1
    assert ctx["totals"]["required"] == 3 and ctx["totals"]["optional"] == 1
    a = ctx["rfps"][0]
    assert [s["title"] for s in a["sections"]] == ["4 Tech", "5 Docs"]
    first = a["sections"][0]["rows"][0]
    assert (first["no"], first["type"], first["required"]) == ("4.1", "Narrative", "Required")
    assert a["sections"][0]["rows"][1]["required"] == "Optional" and a["sections"][0]["rows"][1]["type"] == "Yes / No"
    assert a["sections"][1]["rows"][0]["no"] == "–"
    assert ctx["review"][0]["rfp"] == "a.pdf" and "verbatim" in ctx["review"][0]["reason"]
    assert [r["rfp"] for r in ctx["summary"]] == ["a.pdf", "b.docx"]


def test_context_puts_merged_duplicates_and_near_duplicates_in_the_source_cell():
    ctx = build_context([result("a.pdf", [f("Describe your support model.", ref="p.3 L4", also=["p.9 L1"], similar="4.1")])], extractor="x")
    row = ctx["rfps"][0]["sections"][0]["rows"][0]
    source = str(row["source"])
    assert "p.3 L4" in source and "also p.9 L1" in source and "similar to 4.1" in source


def test_rendered_document_has_summary_sections_rows_and_review_list(template, tmp_path):
    ctx = build_context([result("a.pdf", [f("Describe your support model.", "4.1", "4 Tech", constraints="maximum 500 words"),
                                          f("Describe the thing", None, "4 Tech", status="review", reason="not a verbatim piece of the source")])],
                        extractor="Rules baseline")
    out = tmp_path / "out.docx"
    render_register(ctx, template, out)
    text = all_text(out)
    for expected in ("RFP Question Register", "Rules baseline", "a.pdf", "4 Tech", "Describe your support model.", "4.1", "maximum 500 words",
                     "Needs human review", "Describe the thing", "not a verbatim piece of the source", "Owner", "Status"):
        assert expected in text, expected
    assert "{{" not in text and "{%" not in text


def test_special_characters_and_control_characters_do_not_corrupt_the_file(template, tmp_path):
    nasty = 'Describe "AT&T" <b>pricing</b> & terms\x0b for 5 > 3 – “quotes” \x00end.'
    ctx = build_context([result("a&b <1>.pdf", [f(nasty, "1.1")])], extractor="x")
    out = tmp_path / "out.docx"
    render_register(ctx, template, out)
    text = all_text(out)
    assert 'Describe "AT&T" <b>pricing</b> & terms' in text and "end." in text
    assert "\x00" not in text and "\x0b" not in text
    assert "a&b <1>.pdf" in text


def test_a_file_with_no_questions_gets_a_clear_line_instead_of_an_empty_table(template, tmp_path):
    ctx = build_context([result("empty.pdf", [])], extractor="x")
    out = tmp_path / "out.docx"
    render_register(ctx, template, out)
    assert "No questions were detected in this file" in all_text(out)
    assert "Nothing to review" in all_text(out)


def test_layout_does_not_depend_on_the_data(template, tmp_path):
    """Same styles, page setup, column widths and header/footer whatever is in the register."""
    small = tmp_path / "small.docx"
    big = tmp_path / "big.docx"
    render_register(build_context([result("a.pdf", [f("Describe your support model.", "4.1")])], extractor="x"), template, small)
    many = [f(f"Describe item number {i} in some detail for the evaluation committee.", f"4.{i}", f"{i % 4} Section") for i in range(60)]
    render_register(build_context([result("a.pdf", many), result("b.xlsx", many[:5], fmt="xlsx")], extractor="x"), template, big)
    a, b = Document(str(small)), Document(str(big))
    sa, sb = a.sections[0], b.sections[0]
    assert (sa.page_width, sa.page_height, sa.left_margin, sa.orientation) == (sb.page_width, sb.page_height, sb.left_margin, sb.orientation)
    assert [s.name for s in a.styles if s.type == 1] == [s.name for s in b.styles if s.type == 1]
    widths = lambda d: [[c.width for c in t.rows[0].cells] for t in d.tables if len(t.columns) == 8]  # noqa: E731
    assert widths(a)[0] == widths(b)[0] == widths(b)[-1]
    used = lambda d: {p.style.name for p in d.paragraphs}  # noqa: E731
    assert used(a) <= used(b) | {"Normal"}


def test_restyling_the_template_in_word_restyles_the_register(template, tmp_path):
    """The promise in the README: change a style or a column width in the template and the next run follows."""
    from docx.shared import Inches, Pt

    edited = Document(str(template))
    edited.styles["RFP Table Text"].font.size = Pt(12)
    edited.styles["Heading 2"].font.name = "Georgia"
    for row in edited.tables[1].rows:                       # the first question table: widen the Question column
        row.cells[1].width = Inches(4.4)
    edited.save(str(template))
    out = tmp_path / "out.docx"
    render_register(build_context([result("a.pdf", [f("Describe your support model.", "4.1")])], extractor="x"), template, out)
    doc = Document(str(out))
    assert doc.styles["RFP Table Text"].font.size == Pt(12) and doc.styles["Heading 2"].font.name == "Georgia"
    question_table = next(t for t in doc.tables if len(t.columns) == 8)
    assert question_table.rows[1].cells[1].width == Inches(4.4)


def test_template_can_be_rebuilt_and_opened(tmp_path):
    path = tmp_path / "t.docx"
    build_template(path)
    doc = Document(str(path))
    assert {"Title", "Heading 1", "Heading 2", "RFP Table Text", "RFP Table Header"} <= {s.name for s in doc.styles}
