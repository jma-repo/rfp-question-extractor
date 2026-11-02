"""The offline baseline: regular expressions over the blocks, no model. Used for tests, for comparison, and as the fallback
when the local model is down or returns something that fails validation."""

from __future__ import annotations

import re
from collections.abc import Iterable

from rfpx.ingest import Block, Document
from rfpx.models import Finding, Question
from rfpx.textutil import split_number

RESPONSE_VERBS = (r"describe|provide|state|list|identify|attach|upload|submit|complete|confirm|explain|disclose|detail|outline|"
                  r"indicate|specify|demonstrate|include|propose|supply|clarify|summari[sz]e|enclose|append|name|give")
_IMPERATIVE = re.compile(rf"^(\((optional|desirable)\)\s*)?(please\s+)?({RESPONSE_VERBS})\b", re.I)
_PROPONENT_MODAL = re.compile(
    rf"^(the\s+)?(proponent|vendor|bidder|respondent|contractor|supplier)s?\s+(shall|must|should|will|to|is to|are to)\s+({RESPONSE_VERBS})\b", re.I)
_QUESTION_MARK = re.compile(r"\?\s*(\(\s*yes\s*/\s*no\s*\)\s*)?$|\?\s+(if so|if yes|if not)\b", re.I)
_SOLUTION_YESNO = re.compile(r"\(\s*yes\s*/\s*no\s*\)", re.I)
_BULLET = re.compile(r"^[•●▪*–-]\s+")
_EXCLUDED_SECTION = re.compile(
    r"(?i)\b(introduction|background|definitions?|glossary|instructions?|submission|evaluation|timeline|schedule of events|"
    r"terms and conditions|scope of services|general information|about this request|table of contents|purpose)\b")
_QUESTION_HEADER = re.compile(r"(?i)question|requirement|query|^description$|^item description$")
_NOT_A_QUESTION_TABLE = re.compile(r"(?i)price|qty|quantity|unit|total|amount|weight|date|event|rate\b|hours")
_ID_HEADER = re.compile(r"(?i)^(ref|id|req ?(#|id|no\.?)?|no\.?|#|item|question (no|number|#))$")
_TYPE_HEADER = re.compile(r"(?i)response type|answer type|^type$|format")
_REQUIRED_HEADER = re.compile(r"(?i)^(mandatory|m/d|mandatory\s*/\s*desirable|required|req\?|m/o)$")
_TYPE_WORDS = (("yes_no", r"yes\s*/\s*no|boolean|^y/n$"), ("upload", r"attach|upload|file|document"), ("pricing", r"pric|cost|fee|rate|currency"),
               ("table", r"table|matrix|grid|list"), ("narrative", r"text|narrative|free|essay|describe"))
_CONSTRAINTS = (
    re.compile(r"\(([^()]*\b(?:pages?|words?|MB|PDF|maximum|not exceeding|no more than)\b[^()]*)\)", re.I),
    re.compile(r"\b(not exceeding (?:\d\.\d|[^,.;?])+|no more than (?:\d\.\d|[^,.;?])+|maximum (?:of )?(?:\d\.\d|[^,.;?])+|"
               r"not less than (?:\d\.\d|[^.;?])+|of at least (?:\d\.\d|[^.;?])+)", re.I),
    re.compile(r"\b(Appendix [A-Z])\b"),
)


def infer_type(text: str) -> str:
    t = re.sub(r"^\((optional|desirable)\)\s*", "", text.strip(), flags=re.I)
    if _SOLUTION_YESNO.search(t):
        return "yes_no"
    if re.match(r"(?i)^(do|does|did|is|are|was|were|will|would|can|could|has|have)\b", t) and t.endswith("?"):
        return "yes_no"
    if re.search(r"(?i)\b(attach|attachment|upload|enclose|copy of|proof of)\b", t):
        return "upload"
    if re.search(r"(?i)\b(pric(e|es|ing)|rates?|costs?|fees?|quote[ds]?)\b", t):
        return "pricing"
    if re.search(r"(?i)\b(table|tabular|matrix)\b|\blist (all|every|each)\b|^list\b", t):
        return "table"
    return "narrative"


def infer_required(text: str) -> bool:
    t = text.strip()
    if re.match(r"(?i)^\((optional|desirable)\)", t):
        return False
    if re.search(r"(?i)\b(shall|must|is required to|are required to|mandatory)\b", t):
        return True
    if re.search(r"(?i)\b(should|may wish to|desirable|optional|preferred)\b", t):
        return False
    return True


def infer_constraints(text: str) -> str:
    found: list[str] = []
    for pattern in _CONSTRAINTS:
        for match in pattern.finditer(text):
            piece = match.group(1).strip()
            if piece and piece not in found:
                found.append(piece)
    return "; ".join(found)


def _looks_like_question(body: str) -> bool:
    if _QUESTION_MARK.search(body.rstrip()):
        return True
    return bool(_IMPERATIVE.match(body) or _PROPONENT_MODAL.match(body) or
                (_SOLUTION_YESNO.search(body) and re.search(r"\b(shall|must|should)\b", body)))


def extract_document(doc: Document) -> list[Finding]:
    return extract_blocks([b for b in doc.blocks if not b.noise], doc.name)


class RulesExtractor:
    """Same interface as the model extractor: one chunk in, the questions found in it out."""

    name = "rules"
    label = "Rules baseline (regular expressions, no model)"

    def extract(self, chunk) -> tuple[list[Question], list[Finding], list[str]]:
        return [f.q for f in extract_blocks(chunk.blocks, chunk.doc.name)], [], []


def extract_blocks(blocks: Iterable[Block], doc_name: str = "") -> list[Finding]:
    found: list[Finding] = []
    for b in blocks:
        if b.noise or b.kind == "heading":
            continue
        if b.kind == "row":
            question = _from_row(b)
        elif _EXCLUDED_SECTION.search(b.section):
            continue
        else:
            question = _from_paragraph(b)
        if question is not None:
            found.append(Finding(question, doc_name, origin="rules"))
    return found


def _from_paragraph(b: Block) -> Question | None:
    number, body = split_number(_BULLET.sub("", b.text))
    if len(body) < 8 or not _looks_like_question(body):
        return None
    return Question(id=number, section=b.section, question_text=body, type=infer_type(body), required=infer_required(body),
                    constraints=infer_constraints(body), source_ref=b.loc)


def _from_row(b: Block) -> Question | None:
    header = b.header
    if not header or any(_NOT_A_QUESTION_TABLE.search(h) for h in header):
        return None
    col = next((i for i, h in enumerate(header) if _QUESTION_HEADER.search(h.strip())), None)
    if col is None or col >= len(b.cells):
        return None
    text = b.cells[col].strip()
    if len(text) < 8 or text.lower().startswith("total"):
        return None
    number = next((b.cells[i] for i, h in enumerate(header) if i < len(b.cells) and i != col and _ID_HEADER.match(h.strip()) and b.cells[i]), None)
    if number is None:
        number, text = split_number(text)
    return Question(id=number or None, section=b.section, question_text=text, type=_row_type(b, text), required=_row_required(b, text),
                    constraints=infer_constraints(text), source_ref=b.loc)


def _cell(b: Block, pattern: re.Pattern) -> str | None:
    for i, h in enumerate(b.header):
        if i < len(b.cells) and pattern.search(h.strip()) and b.cells[i].strip():
            return b.cells[i].strip()
    return None


def _row_type(b: Block, text: str) -> str:
    label = _cell(b, _TYPE_HEADER)
    if label:
        for kind, pattern in _TYPE_WORDS:
            if re.search(pattern, label, re.I):
                return kind
    if b.header and any(re.search(r"(?i)comply|compliance|yes/no", h) for h in b.header):
        return "yes_no"
    return infer_type(text)


def _row_required(b: Block, text: str) -> bool:
    label = _cell(b, _REQUIRED_HEADER)
    if label:
        word = label.lower()
        if word in {"yes", "y", "m", "mandatory", "required", "true"}:
            return True
        if word in {"no", "n", "d", "o", "desirable", "optional", "false"}:
            return False
    return infer_required(text)
