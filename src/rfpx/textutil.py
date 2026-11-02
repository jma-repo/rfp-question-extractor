"""Text helpers shared by every step. Matching is whitespace- and quote-insensitive, never wording-insensitive."""

from __future__ import annotations

import re
import unicodedata

_FOLD = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
    "­": None, "​": None, "‌": None, "‍": None, "﻿": None,
})
_SPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAILING = " .;:,"

# A printed number at the start of an item: 3.2.1 | 3.2.1. | (a) | a) | (iv) | Q12. | R-014 | A.3 | 7)
_NUMBER = re.compile(
    r"^(?P<num>"
    r"\((?:[a-zA-Z]|[ivxlc]{1,5}|\d{1,3})\)"            # (a) (iv) (3)
    r"|(?:[QRSB]|Req|REQ|Q-|R-|RQ-|REQ-)\d{1,4}[.:)]?"   # Q12. R-014 REQ-7
    r"|[A-Z]\.\d{1,3}(?:\.\d{1,3})*\.?"                  # A.3 B.2.1
    r"|\d{1,2}(?:\.\d{1,3})+\.?"                         # 3.2 3.2.1 3.2.1.
    r"|\d{1,2}[.)]"                                      # 7. 7)
    r"|[a-z][.)]"                                        # a. a)
    r")\s+(?=\S)")


def squash(text: str) -> str:
    """Whitespace-collapsed text with ligatures expanded and typographic quotes and dashes folded to ASCII."""
    return _SPACE.sub(" ", unicodedata.normalize("NFKC", text).translate(_FOLD)).strip()


def _edges(text: str) -> str:
    return squash(text).rstrip(_TRAILING)


def verbatim_key(text: str) -> str:
    """The form in which two texts must be identical to count as the same words: layout, quotes and a final full stop ignored."""
    return _edges(text)


def is_verbatim(candidate: str, source: str) -> bool:
    """True when the candidate is a contiguous piece of the source (only layout, quotes and a final full stop may differ)."""
    core = _edges(candidate)
    return bool(core) and core in squash(source)


def locate(candidate: str, source: str) -> int:
    """Offset of the candidate inside squash(source), or -1."""
    core = _edges(candidate)
    return squash(source).find(core) if core else -1


def split_number(text: str) -> tuple[str | None, str]:
    """Split a printed item number off the front of a line: '3.2.1 Describe x' -> ('3.2.1', 'Describe x')."""
    stripped = text.strip()
    match = _NUMBER.match(stripped)
    if not match:
        return None, stripped
    return match.group("num"), stripped[match.end():].strip()


def match_key(text: str) -> str:
    """Key under which two renderings of the same question collide (case, punctuation and spacing ignored)."""
    return re.sub(r"[^0-9a-z]+", " ", squash(text).casefold()).strip()


def clean_cell(value: object) -> str:
    """Cell or paragraph text made safe for XML: no control characters, numbers without a trailing '.0'."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _CONTROL.sub("", str(value))
