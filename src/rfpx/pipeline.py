"""read -> chunk -> extract -> verify -> merge duplicates, for one file or a folder of them."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rfpx.chunking import Chunk, chunk_document
from rfpx.dedupe import merge_duplicates
from rfpx.ingest import SUPPORTED, Document, read_document
from rfpx.models import Finding, Question
from rfpx.validate import check_question, gate_sections


class Extractor(Protocol):
    name: str
    label: str

    def extract(self, chunk: Chunk) -> tuple[list[Question], list[Finding], list[str]]:
        """Questions found in the chunk, items already known to be unusable (for the review list), and notes."""


@dataclass
class DocResult:
    name: str
    fmt: str
    findings: list[Finding]
    notes: list[str]
    chunks: int
    seconds: float = 0.0
    stats: dict = field(default_factory=dict)


def list_inputs(path: Path, recursive: bool = False) -> list[Path]:
    path = Path(path)
    if path.is_file():
        return [path]
    found = path.rglob("*") if recursive else path.iterdir()
    return sorted(p for p in found if p.is_file() and p.suffix.lower() in SUPPORTED and not p.name.startswith("~$"))


def process_document(doc: Document, extractor: Extractor, max_chars: int = 2400, near: float = 0.75, gate: bool = True) -> DocResult:
    started = time.time()
    findings: list[Finding] = []
    notes: list[str] = []
    chunks = chunk_document(doc, max_chars)
    for chunk in chunks:
        questions, rejected, chunk_notes = extractor.extract(chunk)
        findings += [check_question(q, chunk, origin=extractor.name) for q in questions]
        findings += rejected
        notes += chunk_notes
    merged = merge_duplicates(gate_sections(findings) if gate else findings, near)
    stats = {"readable_blocks": sum(not b.noise for b in doc.blocks), "noise_blocks": sum(b.noise for b in doc.blocks),
             "merged_duplicates": len(findings) - len(merged)}
    return DocResult(doc.name, doc.fmt, merged, notes, len(chunks), round(time.time() - started, 2), stats)


def run_directory(path: Path, extractor: Extractor, max_chars: int = 2400, near: float = 0.75, gate: bool = True,
                  recursive: bool = False) -> list[DocResult]:
    return [process_document(read_document(p), extractor, max_chars, near, gate) for p in list_inputs(path, recursive)]
