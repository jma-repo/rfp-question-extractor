"""Merge exact repeats, flag reworded repeats. Nothing is dropped except the second copy of identical words, and its
location is kept on the first."""

from __future__ import annotations

from rfpx.models import Finding
from rfpx.textutil import match_key

_FILLER = frozenset("""the a an of to and or in for your its their our proponent proponents vendor vendors shall must should will please
is are be by with that any all this""".split())


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in match_key(text).split() if t not in _FILLER)


def merge_duplicates(findings: list[Finding], near: float = 0.75) -> list[Finding]:
    kept: list[Finding] = []
    by_key: dict[str, Finding] = {}
    for f in findings:
        if f.status != "accepted":
            kept.append(f)
            continue
        key = match_key(f.q.question_text)
        if key in by_key:
            by_key[key].also.append(f.q.source_ref)
            continue
        tokens = _tokens(f.q.question_text)
        best, best_score = None, 0.0
        for earlier in kept:
            if earlier.status != "accepted":
                continue
            other = _tokens(earlier.q.question_text)
            score = len(tokens & other) / len(tokens | other) if tokens | other else 0.0
            if score > best_score:
                best, best_score = earlier, score
        if best is not None and best_score >= near:
            f.similar_to = best.q.id or best.q.source_ref
        by_key[key] = f
        kept.append(f)
    return kept
