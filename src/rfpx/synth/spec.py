"""A format-neutral description of an invented RFP. The three writers render it; the gold labels come from it."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Gold:
    """The answer key for one question: exactly what the extractor should return for it."""

    id: str | None
    section: str
    question_text: str
    type: str
    required: bool
    constraints: str = ""
    dup_group: str | None = None     # items that ask for the same thing (exact copies or reworded)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class H:
    level: int
    text: str                         # as printed, including any typed number


@dataclass
class P:
    text: str
    role: str = "background"          # background | procedural | note | lead | definition


@dataclass
class Item:
    gold: Gold
    number: str | None                # printed in front of the text (None: nothing printed)
    level: int = 0                    # 0 = top-level item, 1 = lettered sub-item


@dataclass
class Tbl:
    kind: str                         # matrix | pricing | evaluation | timeline | form
    header: list[str]
    rows: list[list[str]]
    golds: list[Gold | None] = field(default_factory=list)   # one per row for a matrix, else empty
    qcol: int = -1


@dataclass
class Break:
    pass


@dataclass
class Toc:
    pass


@dataclass
class Rfp:
    slug: str
    title: str
    issuer: str
    number: str
    fmt: str                          # docx | pdf | xlsx
    split: str                        # dev | test
    layout: str
    closing: str
    elements: list[Any] = field(default_factory=list)
    running_header: bool = True       # header and footer on every page (docx: header/footer parts; pdf: page frame)
    body_page_noise: bool = False     # page header text pasted into the body, as in a document converted from PDF
    sheets: dict[str, Any] = field(default_factory=dict)      # xlsx only: layout-specific extras

    @property
    def filename(self) -> str:
        return f"{self.slug}.{self.fmt}"

    def golds(self) -> list[Gold]:
        out: list[Gold] = []
        for el in self.elements:
            if isinstance(el, Item):
                out.append(el.gold)
            elif isinstance(el, Tbl):
                out.extend(g for g in el.golds if g is not None)
        return out
