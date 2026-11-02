"""Deterministic checks on what an extractor returned. Nothing here is extracted, only verified.

The rule that matters: `question_text` must be a contiguous piece of the chunk the model was shown (layout, quotes and a
final full stop aside). Whatever the model says about location, number and section is replaced by what the source says.
"""

from __future__ import annotations

import re

from rfpx.baseline import _EXCLUDED_SECTION, _ID_HEADER
from rfpx.chunking import Chunk
from rfpx.ingest import Block
from rfpx.models import Finding, Question
from rfpx.textutil import split_number, squash, verbatim_key

NOT_VERBATIM = "text is not a verbatim piece of the source"
SPANS_BLOCKS = "text runs across more than one paragraph or table cell"
BACKGROUND_SECTION = "found under a heading that normally holds background or instructions, not questions"


def gate_sections(findings: list[Finding]) -> list[Finding]:
    """Items under headings like Background, Definitions or Instructions to Proponents are held for review instead of accepted."""
    for f in findings:
        if f.status == "accepted" and _EXCLUDED_SECTION.search(f.q.section):
            f.status, f.reason = "review", BACKGROUND_SECTION
    return findings


def strip_leading_number(q: Question) -> Question:
    """Models often copy the printed number into the text; it belongs in `id`."""
    number, body = split_number(q.question_text)
    if number and len(body) >= 8:
        return q.model_copy(update={"question_text": body, "id": q.id or number})
    return q


def source_id(block: Block, question_start: int) -> str | None:
    """The number printed with the item: in front of a paragraph, or in the id column of a table row."""
    if block.kind == "row":
        for h, cell in zip(block.header, block.cells, strict=False):
            if _ID_HEADER.match(h.strip()) and cell:
                return cell
        return None
    number, _ = split_number(block.text)
    return number if number and question_start <= len(squash(number)) + 1 else None


def check_question(q: Question, chunk: Chunk, origin: str = "llm") -> Finding:
    q = strip_leading_number(q)
    texts = [squash(b.text) for b in chunk.blocks]
    starts, pos = [], 0
    for t in texts:
        starts.append(pos)
        pos += len(t) + 1
    joined = " ".join(texts)
    core = verbatim_key(q.question_text)
    at = joined.find(core) if core else -1
    if at < 0:
        return Finding(q, chunk.doc.name, status="review", reason=NOT_VERBATIM, origin=origin)
    k = max(i for i, s in enumerate(starts) if s <= at)
    block = chunk.blocks[k]
    end_of_block = starts[k] + len(texts[k])
    if at + len(core) > end_of_block or (block.kind == "row" and re.search(r" \| ", core)):
        return Finding(q, chunk.doc.name, status="review", reason=SPANS_BLOCKS, origin=origin)
    fixed = q.model_copy(update={"source_ref": block.loc, "section": block.section, "id": source_id(block, at - starts[k])})
    return Finding(fixed, chunk.doc.name, origin=origin)
