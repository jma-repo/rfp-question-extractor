"""Word, PDF and Excel to one list of blocks: headings, paragraphs and table rows, each with a section and a location.

No model is involved. Page headers and footers, contents-list lines and page numbers pasted into the body are kept but
marked `noise`, so a count of what was ignored is available and nothing is dropped silently.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from docx import Document as WordDocument
from docx.oxml.ns import qn
from docx.table import Table as WordTable
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook

from rfpx.textutil import clean_cell, split_number, squash

SUPPORTED = (".docx", ".pdf", ".xlsx")
_PAGE_NO = re.compile(r"^(page\s+)?\d+\s*(of|/)\s*\d+$|^page\s+\d+$", re.I)
_LEADER = re.compile(r"\.{4,}\s*\d*\s*$")
_CUES = re.compile(r"\b(shall|must|should|describe|provide|state|attach|confirm|list|identify|explain|complete|submit|"
                   r"disclose|include|upload|specify)\b", re.I)
_HEADER_WORDS = re.compile(r"question|requirement|description|item|ref|\bid\b|response|comment|mandatory|vendor|compliance|req", re.I)
_BULLET = re.compile(r"^[•●▪\-*]\s+")


@dataclass
class Block:
    idx: int
    kind: str                       # heading | para | row
    text: str
    loc: str
    section: str = ""
    cells: tuple[str, ...] = ()
    header: tuple[str, ...] = ()
    page: int | None = None
    noise: bool = False
    table: int = 0                  # rows of one table share this number


@dataclass
class Document:
    path: Path
    name: str
    fmt: str
    blocks: list[Block] = field(default_factory=list)
    pages: int | None = None

    def add(self, kind: str, text: str, loc: str, section: str, **kw) -> Block:
        block = Block(len(self.blocks), kind, text, loc, section, **kw)
        self.blocks.append(block)
        return block


def read_document(path: Path) -> Document:
    path = Path(path)
    fmt = path.suffix.lower().lstrip(".")
    reader = {"docx": _read_docx, "pdf": _read_pdf, "xlsx": _read_xlsx}.get(fmt)
    if reader is None:
        raise ValueError(f"Unsupported file type: {path.suffix} (expected one of {', '.join(SUPPORTED)})")
    doc = Document(path, path.name, fmt)
    reader(doc)
    _mark_noise(doc)
    return doc


_CID_LEAD = re.compile(r"^(\(cid:\d+\)\s*)+")
_CID = re.compile(r"\(cid:\d+\)")


def _line(text: str) -> str:
    """One line of text: control characters gone, runs of whitespace collapsed, and unmapped glyphs from PDF fonts
    ('(cid:127)', usually a bullet) turned into a bullet at the start of a line and dropped elsewhere."""
    text = _CID.sub("", _CID_LEAD.sub("• ", clean_cell(text)))
    return re.sub(r"\s+", " ", text).strip()


def _mark_noise(doc: Document) -> None:
    for b in doc.blocks:
        if b.kind != "row" and (_PAGE_NO.match(b.text) or _LEADER.search(b.text)):
            b.noise = True
    shapes = Counter(_shape(b.text) for b in doc.blocks if b.kind == "para" and len(b.text) <= 100 and not b.noise)
    for b in doc.blocks:
        if b.kind == "para" and shapes[_shape(b.text)] >= 3 and "?" not in b.text and not _CUES.search(b.text):
            b.noise = True


def _shape(text: str) -> str:
    return re.sub(r"\d+", "#", squash(text).casefold())


def _section_label(heading: str) -> str:
    number = split_number(heading)[0]
    return (number or heading[:24]).rstrip(".") if heading else "front"


# --- Word ---------------------------------------------------------------------------------------------

def _body_items(element, parent):
    """Paragraphs and tables in order, also inside block-level content controls (cover pages, contents lists), which
    python-docx's own iterator skips."""
    for child in element.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield WordTable(child, parent)
        elif child.tag == qn("w:sdt"):
            content = child.find(qn("w:sdtContent"))
            if content is not None:
                yield from _body_items(content, parent)


def _read_docx(doc: Document) -> None:
    word = WordDocument(str(doc.path))
    section, para_no, table_no = "", 0, 0
    for item in _body_items(word.element.body, word._body):
        if isinstance(item, Paragraph):
            text = _line(item.text)
            if not text:
                continue
            style = (item.style.name if item.style is not None else "") or ""
            level = _heading_level(style)
            if level:
                section, para_no, table_no = text, 0, 0
                doc.add("heading", text, f"§{_section_label(text)}", section)
            else:
                para_no += 1
                doc.add("para", text, f"§{_section_label(section)} ¶{para_no}", section, noise=style.lower().startswith("toc"))
        elif isinstance(item, WordTable):
            table_no += 1
            rows = _docx_rows(item)
            header = tuple(rows[0]) if len(rows) > 1 else ()
            for i, cells in enumerate(rows[1:] if header else rows, start=1):
                if any(cells):
                    doc.add("row", " | ".join(cells), f"§{_section_label(section)} T{table_no} r{i}", section,
                            cells=tuple(cells), header=header, table=_table_key(doc, section, table_no))


def _table_key(doc: Document, section: str, number: int) -> int:
    return hash((section, number)) & 0x7FFFFFFF


def _heading_level(style: str) -> int:
    match = re.match(r"(?i)heading\s*(\d)", style)
    if match:
        return int(match.group(1))
    return 1 if style.lower() == "title" else 0


def _docx_rows(table: WordTable) -> list[list[str]]:
    rows = []
    for row in table.rows:
        cells, seen = [], set()
        for cell in row.cells:
            if id(cell._tc) in seen:             # a horizontally merged cell appears once per grid column
                continue
            seen.add(id(cell._tc))
            cells.append(_line(cell.text))
        rows.append(cells)
    return rows


# --- PDF ----------------------------------------------------------------------------------------------

def _read_pdf(doc: Document) -> None:
    with pdfplumber.open(str(doc.path)) as pdf:
        doc.pages = len(pdf.pages)
        pages = [_pdf_page(page) for page in pdf.pages]
    margin_shapes = Counter(_shape(line["text"]) for page in pages for line in page["lines"] if line["margin"])
    section = ""
    for number, page in enumerate(pages, start=1):
        items = [(line["top"], "line", line) for line in page["lines"]] + [(t["top"], "table", t) for t in page["tables"]]
        previous = None
        for _, kind, payload in sorted(items, key=lambda x: x[0]):
            if kind == "table":
                previous = None
                header = tuple(payload["rows"][0]) if len(payload["rows"]) > 1 else ()
                for i, cells in enumerate(payload["rows"][1:] if header else payload["rows"], start=1):
                    if any(cells):
                        doc.add("row", " | ".join(cells), f"p.{number} T{payload['no']} r{i}", section, cells=tuple(cells),
                                header=header, page=number, table=number * 100 + payload["no"])
                continue
            line = payload
            text = line["text"]
            loc = f"p.{number} L{line['no']}"
            if line["margin"] and (margin_shapes[_shape(text)] >= 2 or _PAGE_NO.match(text)):
                doc.add("para", text, loc, section, page=number, noise=True)
                previous = None
            elif line["heading"]:
                section = text
                doc.add("heading", text, loc, section, page=number)
                previous = None
            elif previous is not None and _continues(previous, line):
                previous["block"].text = f"{previous['block'].text} {text}"
                previous.update(top=line["top"], size=line["size"])
            else:
                block = doc.add("para", text, loc, section, page=number)
                previous = {"block": block, "top": line["top"], "size": line["size"]}


def _continues(previous: dict, line: dict) -> bool:
    if split_number(line["text"])[0] or _BULLET.match(line["text"]):
        return False
    return line["top"] - previous["top"] <= 1.6 * line["size"]


def _pdf_page(page) -> dict:
    tables, exclude = [], []
    for n, table in enumerate(page.find_tables(), start=1):
        rows = [[_line(c) for c in row] for row in table.extract()]
        if len(rows) >= 2 and len(rows[0]) >= 2:
            tables.append({"no": n, "top": table.bbox[1], "rows": rows})
            exclude.append(table.bbox)
    body = page
    for bbox in exclude:
        body = body.outside_bbox(bbox)
    lines = []
    for n, raw in enumerate(body.extract_text_lines(return_chars=True), start=1):
        text = _line(raw["text"])
        if not text:
            continue
        chars = [c for c in raw["chars"] if c["text"].strip()]
        size = max((c["size"] for c in chars), default=10.0)
        bold = bool(chars) and all("bold" in c["fontname"].lower() for c in chars)
        lines.append({"no": n, "text": text, "top": raw["top"], "size": size, "heading": bold and size >= 10.4 and len(text) <= 110,
                      "margin": raw["top"] < 0.09 * page.height or raw["bottom"] > 0.91 * page.height})
    return {"lines": lines, "tables": tables}


# --- Excel --------------------------------------------------------------------------------------------

def _read_xlsx(doc: Document) -> None:
    book = load_workbook(str(doc.path), data_only=True)
    for sheet in book.worksheets:
        if sheet.sheet_state != "visible":
            continue
        grid = _xlsx_grid(sheet)
        header_row = _find_header(grid)
        header = tuple(grid[header_row - 1]) if header_row is not None else ()
        section_col = next((i for i, h in enumerate(header) if re.fullmatch(r"(?i)section|category|area", h.strip())), None)
        section = sheet.title
        for r, cells in enumerate(grid, start=1):
            filled = [c for c in cells if c]
            if not filled or r == header_row:
                continue
            loc = f"{sheet.title}!R{r}"
            if header_row is None or r < header_row:
                doc.add("para", " ".join(filled), loc, section)
            elif len(filled) == 1 and sheet.merged_cells and _is_banner(sheet, r):
                section = filled[0]
                doc.add("heading", filled[0], loc, section)
            else:
                own = cells[section_col] if section_col is not None and cells[section_col] else section
                doc.add("row", " | ".join(cells), loc, own, cells=tuple(cells), header=header, table=hash(sheet.title) & 0xFFFF)


def _xlsx_grid(sheet) -> list[list[str]]:
    width = sheet.max_column or 1
    grid = [[clean_cell(sheet.cell(row=r, column=c).value).strip() for c in range(1, width + 1)]
            for r in range(1, (sheet.max_row or 0) + 1)]
    for span in sheet.merged_cells.ranges:                 # a vertically merged cell holds its value in the top row only
        if span.max_row > span.min_row:
            value = grid[span.min_row - 1][span.min_col - 1]
            for r in range(span.min_row, span.max_row + 1):
                for c in range(span.min_col, span.max_col + 1):
                    grid[r - 1][c - 1] = value
    return grid


def _find_header(grid: list[list[str]]) -> int | None:
    best, best_hits = None, 1
    for r, cells in enumerate(grid[:25], start=1):
        filled = [c for c in cells if c]
        hits = sum(bool(_HEADER_WORDS.search(c)) for c in filled)
        if len(filled) >= 2 and hits > best_hits:
            best, best_hits = r, hits
    return best


def _is_banner(sheet, row: int) -> bool:
    return any(span.min_row == row == span.max_row and span.max_col > span.min_col for span in sheet.merged_cells.ranges)
