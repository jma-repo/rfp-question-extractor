"""Cut a document into prompt-sized chunks along its own structure (sections, pages, table rows)."""

from __future__ import annotations

from dataclasses import dataclass

from rfpx.ingest import Block, Document


@dataclass
class Chunk:
    index: int
    doc: Document
    blocks: list[Block]
    prompt: str                     # exactly what the model reads (and what the verbatim check compares against)
    size: int

    @property
    def section(self) -> str:
        return self.blocks[0].section if self.blocks else ""


def render_lines(blocks: list[Block]) -> list[str]:
    """One line per block. Table rows are pipe-separated and each table's header row is printed once before its first row."""
    lines, current_table = [], None
    for b in blocks:
        if b.kind == "row":
            if b.table != current_table and b.header:
                lines.append("| " + " | ".join(b.header) + " |")
            current_table = b.table
            lines.append("| " + " | ".join(b.cells) + " |")
        else:
            current_table = None
            lines.append(f"## {b.text}" if b.kind == "heading" else b.text)
    return lines


def chunk_document(doc: Document, max_chars: int = 2400) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: list[Block] = []
    size = 0
    for b in (b for b in doc.blocks if not b.noise):
        cost = len(b.text) + 8
        page_turn = bool(current) and b.page is not None and current[-1].page != b.page and size >= 0.4 * max_chars
        if current and (size + cost > max_chars or page_turn):
            chunks.append(_make(doc, len(chunks), current, size))
            current, size = [], 0
        current.append(b)
        size += cost
    if current:
        chunks.append(_make(doc, len(chunks), current, size))
    return chunks


def _make(doc: Document, index: int, blocks: list[Block], size: int) -> Chunk:
    prompt = "\n".join([f"Section: {blocks[0].section or '(start of document)'}", *render_lines(blocks)])
    return Chunk(index, doc, blocks, prompt, size)
