"""Builds templates/question_register.docx, the Word file the register is rendered from.

The file is ordinary Word: change a style (Heading 1, RFP Table Text, ...), a column width, the header or the wording of any
fixed text and the next run follows. The only parts to leave alone are the {{ ... }} and {%p ... %} / {%tr ... %} tags, which
docxtpl replaces and repeats. `rfpx template` rewrites the file from this script if it is ever damaged.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

NAVY = "1F2A44"
HEADER_TEXT = RGBColor(0xFF, 0xFF, 0xFF)
SUMMARY_WIDTHS = [2.5, 0.6, 0.8, 0.8, 0.8, 0.8, 0.7, 0.6, 0.7, 0.7, 0.8]        # inches, 9.8 in total
QUESTION_WIDTHS = [0.55, 3.0, 0.7, 0.75, 1.1, 1.9, 0.9, 0.75]
REVIEW_WIDTHS = [1.6, 1.4, 3.4, 2.1, 1.3]


def _styles(doc: Document) -> None:
    styles = doc.styles
    styles["Normal"].font.name, styles["Normal"].font.size = "Calibri", Pt(10)
    styles["Normal"].paragraph_format.space_after = Pt(4)
    styles["Title"].font.name, styles["Title"].font.size = "Calibri", Pt(24)
    styles["Title"].font.color.rgb = RGBColor(0x1F, 0x2A, 0x44)
    for name, size, before, after in (("Heading 1", 16, 14, 6), ("Heading 2", 12, 10, 4)):
        style = styles[name]
        style.font.name, style.font.size = "Calibri", Pt(size)
        style.font.color.rgb = RGBColor(0x1F, 0x2A, 0x44)
        style.paragraph_format.space_before, style.paragraph_format.space_after = Pt(before), Pt(after)
        style.paragraph_format.keep_with_next = True
    text = styles.add_style("RFP Table Text", WD_STYLE_TYPE.PARAGRAPH)
    text.base_style, text.font.size = styles["Normal"], Pt(8.5)
    text.paragraph_format.space_after, text.paragraph_format.space_before = Pt(1), Pt(1)
    head = styles.add_style("RFP Table Header", WD_STYLE_TYPE.PARAGRAPH)
    head.base_style, head.font.size, head.font.bold = styles["RFP Table Text"], Pt(8.5), True
    head.font.color.rgb = HEADER_TEXT
    small = styles.add_style("RFP Meta", WD_STYLE_TYPE.PARAGRAPH)
    small.base_style, small.font.size = styles["Normal"], Pt(9)
    small.font.color.rgb = RGBColor(0x59, 0x59, 0x59)


def _shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shade = OxmlElement("w:shd")
    for key, value in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", fill)):
        shade.set(qn(key), value)
    props.append(shade)


def _row_flags(row, header: bool = False) -> None:
    props = row._tr.get_or_add_trPr()
    props.append(OxmlElement("w:cantSplit"))
    if header:
        props.append(OxmlElement("w:tblHeader"))


def _field(paragraph, instruction: str) -> None:
    for kind in ("begin", None, "end"):
        run = paragraph.add_run()
        if kind:
            mark = OxmlElement("w:fldChar")
            mark.set(qn("w:fldCharType"), kind)
            run._r.append(mark)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = instruction
            run._r.append(instr)


def _cell(cell, text: str, style: str = "RFP Table Text", width: float | None = None) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.style = style
    paragraph.add_run(text)
    if width is not None:
        cell.width = Inches(width)


def _table(doc: Document, header: list[str], widths: list[float], body_row: list[str], loop: str, shade_last: str | None = None):
    """A header row, then the three rows docxtpl turns into a loop: {%tr for %}, the repeated row, {%tr endfor %}."""
    table = doc.add_table(rows=4, cols=len(header))
    table.style, table.alignment, table.autofit = "Table Grid", WD_TABLE_ALIGNMENT.CENTER, False
    for i, text in enumerate(header):
        _cell(table.rows[0].cells[i], text, "RFP Table Header", widths[i])
        _shade(table.rows[0].cells[i], NAVY)
    for r, content in ((1, [f"{{%tr for {loop} %}}"] + [""] * (len(header) - 1)), (2, body_row),
                       (3, ["{%tr endfor %}"] + [""] * (len(header) - 1))):
        for i, text in enumerate(content):
            _cell(table.rows[r].cells[i], text, "RFP Table Text", widths[i])
    if shade_last:
        _shade(table.rows[2].cells[len(header) - 2], shade_last)
    _row_flags(table.rows[0], header=True)
    _row_flags(table.rows[2])
    return table


def build_template(path: Path) -> None:
    doc = Document()
    _styles(doc)
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Inches(11), Inches(8.5)
    section.left_margin = section.right_margin = Inches(0.6)
    section.top_margin, section.bottom_margin = Inches(0.7), Inches(0.7)
    head = section.header.paragraphs[0]
    head.text = "RFP Question Register"
    head.style = "RFP Meta"
    foot = section.footer.paragraphs[0]
    foot.style, foot.alignment = "RFP Meta", WD_ALIGN_PARAGRAPH.CENTER
    foot.add_run("Page ")
    _field(foot, "PAGE")
    foot.add_run(" of ")
    _field(foot, "NUMPAGES")

    doc.add_paragraph("{{ title }}", style="Title")
    doc.add_paragraph("Generated {{ generated }}  |  Extractor: {{ extractor }}  |  {{ totals.rfps }} RFP(s), "
                      "{{ totals.questions }} questions, {{ totals.review }} to review", style="RFP Meta")

    doc.add_paragraph("Summary", style="Heading 1")
    summary_header = ["RFP", "Format", "Questions", "Required", "Optional", "Narrative", "Yes / No", "Table", "Upload", "Pricing", "To review"]
    table = _table(doc, summary_header, SUMMARY_WIDTHS,
                   ["{{ s.rfp }}", "{{ s.format }}", "{{ s.questions }}", "{{ s.required }}", "{{ s.optional }}", "{{ s.narrative }}",
                    "{{ s.yes_no }}", "{{ s.table }}", "{{ s.upload }}", "{{ s.pricing }}", "{{ s.review }}"], "s in summary")
    total = table.add_row()
    for i, text in enumerate(["Total", "", "{{ totals.questions }}", "{{ totals.required }}", "{{ totals.optional }}",
                              "{{ totals.narrative }}", "{{ totals.yes_no }}", "{{ totals.table }}", "{{ totals.upload }}",
                              "{{ totals.pricing }}", "{{ totals.review }}"]):
        _cell(total.cells[i], text, "RFP Table Header", SUMMARY_WIDTHS[i])
        _shade(total.cells[i], "44546A")
    doc.add_paragraph("{{ summary_note }}", style="RFP Meta")

    doc.add_paragraph("{%p for rfp in rfps %}")
    doc.add_paragraph("{{ rfp.name }}", style="Heading 1")
    doc.add_paragraph("{{ rfp.meta }}", style="RFP Meta")
    doc.add_paragraph("{%p if rfp.empty %}")
    doc.add_paragraph("No questions were detected in this file. Check the source file and the review list below.")
    doc.add_paragraph("{%p endif %}")
    doc.add_paragraph("{%p for sec in rfp.sections %}")
    doc.add_paragraph("{{ sec.title }}", style="Heading 2")
    _table(doc, ["No.", "Question (as written in the RFP)", "Type", "Required", "Constraints", "Source", "Owner", "Status"], QUESTION_WIDTHS,
           ["{{ q.no }}", "{{ q.text }}", "{{ q.type }}", "{{ q.required }}", "{{ q.constraints }}", "{{ q.source }}", "", ""], "q in sec.rows")
    doc.add_paragraph("{%p endfor %}")
    doc.add_paragraph("{%p endfor %}")

    doc.add_paragraph("Needs human review", style="Heading 1")
    doc.add_paragraph("{{ review_intro }}", style="RFP Meta")
    doc.add_paragraph("{%p if review %}")
    _table(doc, ["RFP", "Section", "Text as extracted", "Why it is here", "Source"], REVIEW_WIDTHS,
           ["{{ r.rfp }}", "{{ r.section }}", "{{ r.text }}", "{{ r.reason }}", "{{ r.source }}"], "r in review", shade_last="FFF2CC")
    doc.add_paragraph("{%p else %}")
    doc.add_paragraph("Nothing to review: every extracted question passed the checks.")
    doc.add_paragraph("{%p endif %}")

    doc.core_properties.title, doc.core_properties.author = "RFP Question Register (template)", "rfpx"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
