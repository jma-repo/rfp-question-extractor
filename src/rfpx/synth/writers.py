"""Render a neutral Rfp spec as Word, PDF or Excel, with the mess real files have: running headers, page numbers
pasted into the body, tables of contents with dot leaders, merged category cells, hidden helper sheets."""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable

from rfpx.synth.spec import Break, H, Item, P, Rfp, Tbl, Toc

BANNER = "Synthetic test document - not a real solicitation"
TYPE_LABEL = {"narrative": "Free text", "yes_no": "Yes/No", "table": "Table", "upload": "Attachment", "pricing": "Pricing"}


def _headings(rfp: Rfp) -> list[H]:
    return [e for e in rfp.elements if isinstance(e, H) and e.level <= 2]


def _col_widths(kind: str, total: float, n: int) -> list[float]:
    if kind == "matrix":
        shares = [0.11, 0.47, 0.14, 0.14, 0.14]
    elif kind == "pricing":
        shares = [0.07, 0.43, 0.08, 0.21, 0.21]
    elif kind == "form":
        shares = [0.12, 0.28, 0.2, 0.14, 0.26]
    else:
        shares = [1 / n] * n if n != 2 else [0.7, 0.3]
    shares = shares[:n] if len(shares) >= n else shares + [1 / n] * (n - len(shares))
    scale = total / sum(shares)
    return [s * scale for s in shares]


# --- Word ---------------------------------------------------------------------------------------------

def _field(paragraph, instruction: str) -> None:
    for kind, text in (("begin", None), (None, instruction), ("end", None)):
        run = paragraph.add_run()
        if kind:
            mark = OxmlElement("w:fldChar")
            mark.set(qn("w:fldCharType"), kind)
            run._r.append(mark)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = text
            run._r.append(instr)


def _shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shade = OxmlElement("w:shd")
    shade.set(qn("w:val"), "clear")
    shade.set(qn("w:color"), "auto")
    shade.set(qn("w:fill"), fill)
    props.append(shade)


def write_docx(rfp: Rfp, path: Path) -> None:
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10.5)
    for name, size in (("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11)):
        doc.styles[name].font.size, doc.styles[name].font.name = Pt(size), "Calibri"
        doc.styles[name].font.color.rgb = RGBColor(0x1F, 0x2A, 0x44)
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Inches(1)
    if rfp.running_header:
        head = section.header.paragraphs[0]
        head.text = f"{rfp.number}  |  {rfp.title}\tCONFIDENTIAL"
        head.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT)
        foot = section.footer.paragraphs[0]
        foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        foot.add_run("Page ")
        _field(foot, "PAGE")
        foot.add_run(" of ")
        _field(foot, "NUMPAGES")
    title = doc.add_paragraph(style="Title")
    title.add_run(f"Request for Proposals\n{rfp.title}")
    for line in (rfp.issuer, f"RFP No. {rfp.number}", f"Closing Time: {rfp.closing}", BANNER):
        doc.add_paragraph(line)
    page_no = 1
    new_page = _page_break_with_noise if rfp.body_page_noise else _page_break

    for el in rfp.elements:
        if isinstance(el, Toc):
            new_page(doc, rfp, page_no)
            page_no += 1
            doc.add_paragraph("Table of Contents").runs[0].bold = True
            for n, h in enumerate(_headings(rfp)):
                line = doc.add_paragraph()
                line.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
                line.paragraph_format.left_indent = Inches(0.25 * (h.level - 1))
                line.add_run(f"{h.text}\t{3 + n // 2}")
            new_page(doc, rfp, page_no)
            page_no += 1
        elif isinstance(el, H):
            if el.level == 1 and rfp.body_page_noise and page_no > 2:
                new_page(doc, rfp, page_no)
                page_no += 1
            doc.add_heading(el.text, level=el.level)
        elif isinstance(el, P):
            para = doc.add_paragraph(el.text)
            if el.role == "note":
                para.runs[0].italic = True
        elif isinstance(el, Item):
            para = doc.add_paragraph()
            fmt = para.paragraph_format
            fmt.left_indent, fmt.first_line_indent = Inches(0.7 + 0.4 * el.level), Inches(-0.7)
            fmt.tab_stops.add_tab_stop(Inches(0.7 + 0.4 * el.level))
            fmt.space_after = Pt(6)
            para.add_run(f"{el.number}\t{el.gold.question_text}" if el.number else el.gold.question_text)
        elif isinstance(el, Tbl):
            _docx_table(doc, el)
        elif isinstance(el, Break):
            new_page(doc, rfp, page_no)
            page_no += 1
    doc.core_properties.title = f"{rfp.title} (synthetic)"
    doc.core_properties.author = "rfpx synthetic data"
    doc.save(path)


def _page_break(doc, rfp: Rfp, page_no: int) -> None:
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def _page_break_with_noise(doc, rfp: Rfp, page_no: int) -> None:
    """What a Word file converted from PDF looks like: the old page footer and header sit in the body."""
    foot = doc.add_paragraph(f"Page {page_no}")
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot.add_run().add_break(WD_BREAK.PAGE)
    head = doc.add_paragraph(f"{rfp.number}  |  {rfp.title}  |  CONFIDENTIAL")
    head.runs[0].font.size = Pt(8)


def _docx_table(doc, tbl: Tbl) -> None:
    table = doc.add_table(rows=1, cols=len(tbl.header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = _col_widths(tbl.kind, 6.5, len(tbl.header))
    for i, text in enumerate(tbl.header):
        cell = table.rows[0].cells[i]
        cell.text = text
        cell.paragraphs[0].runs[0].bold = True
        _shade(cell, "D9E2F3")
    for row in tbl.rows:
        cells = table.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = text
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            cell.width = Inches(widths[i])
    doc.add_paragraph()


# --- PDF ----------------------------------------------------------------------------------------------

class _Doc(BaseDocTemplate):
    def __init__(self, target, marks: dict[str, int], **kw):
        super().__init__(target, **kw)
        self.marks = marks

    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, Paragraph) and flowable.style.name in ("H1", "H2"):
            self.marks[flowable.getPlainText()] = self.page


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    body = ParagraphStyle("Body", parent=base, fontName="Helvetica", fontSize=9.5, leading=12.5, spaceAfter=6)
    return {
        "body": body,
        "note": ParagraphStyle("Note", parent=body, fontName="Helvetica-Oblique"),
        "H1": ParagraphStyle("H1", parent=body, fontName="Helvetica-Bold", fontSize=14, leading=18, spaceBefore=14, spaceAfter=8),
        "H2": ParagraphStyle("H2", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=6),
        "H3": ParagraphStyle("H3", parent=body, fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=4),
        "title": ParagraphStyle("Title", parent=body, fontName="Helvetica-Bold", fontSize=22, leading=28, alignment=TA_CENTER,
                                spaceBefore=120, spaceAfter=18),
        "center": ParagraphStyle("Center", parent=body, alignment=TA_CENTER, fontSize=11, leading=16),
        "cell": ParagraphStyle("Cell", parent=body, fontSize=8.5, leading=10.5, spaceAfter=0),
        "cellb": ParagraphStyle("CellB", parent=body, fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, spaceAfter=0),
    }


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pdf_story(rfp: Rfp, marks: dict[str, int]) -> list:
    st = _pdf_styles()
    story: list = [Paragraph(f"Request for Proposals<br/>{_esc(rfp.title)}", st["title"])]
    for line in (rfp.issuer, f"RFP No. {rfp.number}", f"Closing Time: {rfp.closing}", BANNER):
        story.append(Paragraph(_esc(line), st["center"]))
    story.append(PageBreak())
    width = letter[0] - 2 * inch
    for el in rfp.elements:
        if isinstance(el, Toc):
            story.append(Paragraph("Table of Contents", st["H1"]))
            for h in _headings(rfp):
                page = marks.get(h.text, "")
                dots = "." * max(4, 92 - len(h.text) - 2 * (h.level - 1))
                indent = "&nbsp;" * 4 * (h.level - 1)
                story.append(Paragraph(f"{indent}{_esc(h.text)} {dots} {page}", st["body"]))
            story.append(PageBreak())
        elif isinstance(el, H):
            story.append(Paragraph(_esc(el.text), st[f"H{min(el.level, 3)}"]))
        elif isinstance(el, P):
            story.append(Paragraph(_esc(el.text), st["note" if el.role == "note" else "body"]))
        elif isinstance(el, Item):
            indent = 0.4 * inch * el.level
            number = Paragraph(_esc(el.number or ""), st["body"])
            text = Paragraph(_esc(el.gold.question_text), st["body"])
            row = Table([[number, text]], colWidths=[0.75 * inch, width - 0.75 * inch - indent], hAlign="RIGHT")
            row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            story += [row, Spacer(1, 5)]
        elif isinstance(el, Tbl):
            data = [[Paragraph(_esc(c), st["cellb"]) for c in el.header]]
            data += [[Paragraph(_esc(c), st["cell"]) for c in row] for row in el.rows]
            table = Table(data, colWidths=_col_widths(el.kind, width, len(el.header)), repeatRows=1)
            table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [Spacer(1, 4), table, Spacer(1, 10)]
        elif isinstance(el, Break):
            story.append(PageBreak())
    return story


def write_pdf(rfp: Rfp, path: Path) -> None:
    def build(target, total: int, marks: dict[str, int]) -> int:
        def frame(canvas, doc):
            if rfp.running_header:
                canvas.saveState()
                canvas.setFont("Helvetica", 8)
                canvas.drawString(inch, letter[1] - 0.6 * inch, f"{rfp.number}  |  {rfp.title}")
                canvas.drawRightString(letter[0] - inch, letter[1] - 0.6 * inch, "CONFIDENTIAL")
                canvas.line(inch, letter[1] - 0.68 * inch, letter[0] - inch, letter[1] - 0.68 * inch)
                canvas.drawCentredString(letter[0] / 2, 0.55 * inch, f"Page {doc.page} of {total}")
                canvas.drawString(inch, 0.55 * inch, "Issued by " + rfp.issuer)
                canvas.restoreState()

        doc = _Doc(target, marks, pagesize=letter, leftMargin=inch, rightMargin=inch, topMargin=1.1 * inch, bottomMargin=inch,
                   title=f"{rfp.title} (synthetic)", author="rfpx synthetic data", invariant=1)
        body = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
        doc.addPageTemplates([PageTemplate(id="main", frames=[body], onPage=frame)])
        doc.build(_pdf_story(rfp, marks))
        return doc.page

    marks: dict[str, int] = {}
    total = build(io.BytesIO(), 0, marks)            # first pass: page numbers for the contents list and the footer
    build(str(path), total, dict(marks))


# --- Excel --------------------------------------------------------------------------------------------

_HEAD = PatternFill("solid", fgColor="1F2A44")
_BANNER = PatternFill("solid", fgColor="D9E2F3")
_INPUT = PatternFill("solid", fgColor="FFF2CC")
_WRAP = Alignment(wrap_text=True, vertical="top")


def _sheet_header(ws, values: list[str], row: int) -> None:
    for col, text in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font, cell.fill, cell.alignment = Font(bold=True, color="FFFFFF"), _HEAD, _WRAP


def _widths(ws, widths: list[float]) -> None:
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width


def _instructions(wb: Workbook, rfp: Rfp) -> None:
    ws = wb.active
    ws.title = "Instructions"
    ws["A1"] = rfp.title
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"{rfp.issuer}  |  {rfp.number}  |  Closing Time: {rfp.closing}"
    ws["A3"] = BANNER
    row = 5
    for el in rfp.elements:
        if isinstance(el, P) and el.role in ("background", "procedural", "note", "lead", "definition"):
            ws.cell(row=row, column=1, value=el.text).alignment = _WRAP
            row += 1
    ws.cell(row=row + 1, column=1, value="Complete the highlighted cells only. Do not change the question text or insert rows.")
    ws.column_dimensions["A"].width = 120


def _pricing_sheet(wb: Workbook, rfp: Rfp) -> None:
    table = next((e for e in rfp.elements if isinstance(e, Tbl) and e.kind == "pricing"), None)
    if table is None:
        return
    ws = wb.create_sheet("Pricing")
    ws["A1"] = "Pricing Schedule (CAD, excluding GST)"
    ws["A1"].font = Font(bold=True, size=12)
    _sheet_header(ws, table.header, 3)
    for r, row in enumerate(table.rows, start=4):
        for c, text in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=text)
            cell.alignment = _WRAP
            if c >= 4:
                cell.fill = _INPUT
    _widths(ws, [8, 44, 8, 20, 20])


def _lists_sheet(wb: Workbook, values: list[str]) -> str:
    ws = wb.create_sheet("Lists")
    for r, value in enumerate(values, start=1):
        ws.cell(row=r, column=1, value=value)
    ws.sheet_state = "hidden"
    return f"Lists!$A$1:$A${len(values)}"


def write_xlsx(rfp: Rfp, path: Path) -> None:
    wb = Workbook()
    _instructions(wb, rfp)
    {"flat": _xlsx_flat, "security": _xlsx_security, "xmatrix": _xlsx_matrix}[rfp.layout](wb, rfp)
    _pricing_sheet(wb, rfp)
    wb.properties.title, wb.properties.creator = f"{rfp.title} (synthetic)", "rfpx synthetic data"
    wb.save(path)


def _xlsx_flat(wb: Workbook, rfp: Rfp) -> None:
    ws = wb.create_sheet("Questionnaire")
    ws["A1"] = f"{rfp.title} - Vendor Questionnaire"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "CONFIDENTIAL - for vendor use only"
    header = ["Ref", "Section", "Question", "Response type", "Mandatory", "Vendor response", "Comments"]
    _sheet_header(ws, header, 4)
    row, section, start, last_item = 5, "", 5, 4
    spans: list[tuple[int, int]] = []
    for el in rfp.elements:
        if isinstance(el, H):
            if last_item >= start and section:
                spans.append((start, last_item))
            section, start = el.text, row
        elif isinstance(el, Item):
            g = el.gold
            values = [el.number, "", g.question_text, TYPE_LABEL[g.type], "Yes" if g.required else "No", "", ""]
            for col, value in enumerate(values, start=1):
                cell = ws.cell(row=row, column=col, value=value)
                cell.alignment = _WRAP
                if col in (6, 7):
                    cell.fill = _INPUT
            ws.cell(row=row, column=2, value=section).alignment = _WRAP
            last_item = row
            row += 1
        elif isinstance(el, P) and last_item >= start and section:     # a note row after a section's questions
            note = ws.cell(row=row, column=3, value=el.text)
            note.alignment, note.font = _WRAP, Font(italic=True)
            row += 1
    spans.append((start, last_item))
    for first, last in spans:
        if last > first:
            ws.merge_cells(start_row=first, start_column=2, end_row=last, end_column=2)
    options = _lists_sheet(wb, list(TYPE_LABEL.values()))
    dv = DataValidation(type="list", formula1=options, allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"D5:D{row}")
    ws.freeze_panes = "A5"
    _widths(ws, [8, 24, 70, 14, 11, 40, 30])


def _xlsx_security(wb: Workbook, rfp: Rfp) -> None:
    ws = wb.create_sheet("Security Questionnaire")
    ws["A1"] = f"{rfp.title}"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "Answer Yes, No or N/A in column C and give evidence in column D. Attach documents as separate files named by ID."
    _sheet_header(ws, ["ID", "Question", "Response", "Evidence / comments"], 4)
    row = 5
    for el in rfp.elements:
        if isinstance(el, H):
            ws.cell(row=row, column=1, value=el.text).font = Font(bold=True)
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            for col in range(1, 5):
                ws.cell(row=row, column=col).fill = _BANNER
            row += 1
        elif isinstance(el, Item):
            ws.cell(row=row, column=1, value=el.number)
            ws.cell(row=row, column=2, value=el.gold.question_text).alignment = _WRAP
            ws.cell(row=row, column=3).fill = _INPUT
            ws.cell(row=row, column=4).fill = _INPUT
            row += 1
    options = _lists_sheet(wb, ["Yes", "No", "N/A"])
    dv = DataValidation(type="list", formula1=options, allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"C5:C{row}")
    ws.freeze_panes = "A5"
    _widths(ws, [8, 90, 14, 40])


def _xlsx_matrix(wb: Workbook, rfp: Rfp) -> None:
    req = wb.create_sheet("Requirements")
    req["A1"] = "Functional and technical requirements"
    req["A1"].font = Font(bold=True, size=13)
    req["A2"] = "M = mandatory, D = desirable. Compliance: Y = fully, P = partially, N = not met."
    first = next(e for e in rfp.elements if isinstance(e, Tbl) and e.kind == "matrix")
    _sheet_header(req, first.header, 4)
    vq = wb.create_sheet("Vendor Questions")
    vq["A1"] = "Vendor questions"
    vq["A1"].font = Font(bold=True, size=13)
    _sheet_header(vq, ["Ref", "Question", "Response"], 3)
    r_row, v_row, section = 5, 4, ""
    for el in rfp.elements:
        if isinstance(el, H):
            section = el.text
            if section != "Vendor questions":
                req.cell(row=r_row, column=1, value=section).font = Font(bold=True)
                req.merge_cells(start_row=r_row, start_column=1, end_row=r_row, end_column=5)
                req.cell(row=r_row, column=1).fill = _BANNER
                r_row += 1
        elif isinstance(el, Tbl) and el.kind == "matrix":
            for values in el.rows:
                for col, value in enumerate(values, start=1):
                    req.cell(row=r_row, column=col, value=value).alignment = _WRAP
                r_row += 1
        elif isinstance(el, Item):
            vq.cell(row=v_row, column=1, value=el.number)
            vq.cell(row=v_row, column=2, value=el.gold.question_text).alignment = _WRAP
            vq.cell(row=v_row, column=3).fill = _INPUT
            v_row += 1
    _widths(req, [10, 80, 8, 18, 30])
    _widths(vq, [9, 90, 40])


WRITERS = {"docx": write_docx, "pdf": write_pdf, "xlsx": write_xlsx}
