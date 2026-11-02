"""Paste this whole file into Microsoft Copilot (code interpreter) and ask it to run it. Two helpers, no other dependency than python-docx.

  verify(rows, source)  -> the rows whose text is NOT a verbatim piece of the source (the check the pipeline does with code)
  build_register(rows)  -> one Word file with the same layout every time (landscape, one table, fixed columns and fonts)

`rows` is a list of dicts with the keys rfp, section, ref, text, type, required, constraints, source.
"""
import re
import unicodedata

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

COLUMNS = [("No.", 0.6), ("Question (as written in the RFP)", 3.7), ("Type", 0.8), ("Required", 0.8),
           ("Constraints", 1.3), ("Source", 1.1), ("Owner", 0.8), ("Status", 0.7)]


def squash(text):
    """Whitespace folded, typographic quotes and dashes made plain, so layout never counts as a difference."""
    text = unicodedata.normalize("NFKC", str(text))
    for old, new in {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def verify(rows, source):
    """Rows whose text is not found word for word in `source` (one trailing full stop may differ)."""
    haystack = squash(source)
    return [r for r in rows if squash(r["text"]).rstrip(" .;:,") not in haystack]


def _shade(cell, fill):
    shade = OxmlElement("w:shd")
    for key, value in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", fill)):
        shade.set(qn(key), value)
    cell._tc.get_or_add_tcPr().append(shade)


def _write(cell, text, bold=False, white=False):
    cell.text = ""
    run = cell.paragraphs[0].add_run(str(text))
    run.font.size, run.bold = Pt(8.5), bold
    if white:
        run.font.color.rgb = RGBColor(255, 255, 255)


def build_register(rows, path="rfp_register.docx", title="RFP Question Register"):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Inches(11), Inches(8.5)
    section.left_margin = section.right_margin = Inches(0.6)
    doc.add_heading(title, level=0)
    for rfp in dict.fromkeys(r["rfp"] for r in rows):
        doc.add_heading(rfp, level=1)
        for sec in dict.fromkeys(r["section"] for r in rows if r["rfp"] == rfp):
            doc.add_heading(sec or "(no section)", level=2)
            table = doc.add_table(rows=1, cols=len(COLUMNS))
            table.style, table.autofit = "Table Grid", False
            for i, (name, width) in enumerate(COLUMNS):
                _write(table.rows[0].cells[i], name, bold=True, white=True)
                _shade(table.rows[0].cells[i], "1F2A44")
                table.rows[0].cells[i].width = Inches(width)
            for r in (r for r in rows if r["rfp"] == rfp and r["section"] == sec):
                cells = table.add_row().cells
                values = [r.get("ref") or "-", r["text"], r.get("type", ""), "Required" if r.get("required", True) else "Optional",
                          r.get("constraints", ""), r.get("source", ""), "", ""]
                for i, value in enumerate(values):
                    _write(cells[i], value)
                    cells[i].width = Inches(COLUMNS[i][1])
    doc.save(path)
    return path
