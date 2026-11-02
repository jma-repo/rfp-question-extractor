"""The record every extractor produces, and the small JSON schema the model is held to."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

QuestionType = Literal["narrative", "yes_no", "table", "upload", "pricing"]
TYPES: tuple[str, ...] = get_args(QuestionType)

_NO_ID = {"", "null", "none", "n/a", "na", "-"}
_REQUIRED = {"mandatory", "required", "must", "shall", "true", "yes", "y", "m"}
_OPTIONAL = {"optional", "desirable", "should", "may", "preferred", "false", "no", "n", "o", "d"}


class Question(BaseModel):
    """One thing the vendor has to answer, copied word for word from the RFP."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str | None = None
    section: str = ""
    question_text: str = Field(min_length=8, max_length=2000)
    type: QuestionType = "narrative"
    required: bool = True
    constraints: str = ""
    source_ref: str = ""

    @field_validator("id", mode="before")
    @classmethod
    def _id(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return None if text.lower() in _NO_ID else text

    @field_validator("section", "constraints", "source_ref", mode="before")
    @classmethod
    def _blank(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("required", mode="before")
    @classmethod
    def _required(cls, value: Any) -> Any:
        if isinstance(value, str):
            word = value.strip().lower()
            if word in _REQUIRED:
                return True
            if word in _OPTIONAL:
                return False
        return value


class Extraction(BaseModel):
    """What the model returns for one chunk."""

    model_config = ConfigDict(extra="ignore")

    questions: list[Question]


def llm_schema() -> dict[str, Any]:
    """The schema sent as `response_format`: small, flat, no source_ref (code finds the location itself)."""
    item = {
        "type": "object",
        "properties": {
            "id": {"type": ["string", "null"], "description": "Item number exactly as printed, or null"},
            "section": {"type": "string", "description": "Heading of the section the item sits under"},
            "question_text": {"type": "string", "description": "The question or requirement, copied word for word"},
            "type": {"type": "string", "enum": list(TYPES)},
            "required": {"type": "boolean"},
            "constraints": {"type": "string", "description": "Page or word limits, file formats, attachments; empty if none"},
        },
        "required": ["id", "section", "question_text", "type", "required", "constraints"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {"questions": {"type": "array", "items": item}},
            "required": ["questions"], "additionalProperties": False}


@dataclass
class Finding:
    """A Question plus where it came from and what the checks decided about it."""

    q: Question
    doc: str
    status: str = "accepted"          # accepted | review
    reason: str = ""                  # why it is in review
    origin: str = "rules"             # rules | llm | llm-recheck
    also: list[str] = field(default_factory=list)   # source refs of exact duplicates merged into this one
    similar_to: str = ""              # label of an earlier, near-identical question
