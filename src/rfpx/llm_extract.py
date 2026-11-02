"""Extraction with a local model: one call per chunk, reply validated with pydantic, one retry that sends the error back,
and a fallback to the rules (flagged for review) when the model is down or keeps returning something unusable.

The model only decides what is a question and how to label it. Location, printed number and section are filled in from the
source by `validate.check_question`, and the verbatim test runs on everything the model returns.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from rfpx.baseline import extract_blocks
from rfpx.chunking import Chunk
from rfpx.llm import LLMUnavailable, LocalLLM, SchemaUnsupported
from rfpx.models import Extraction, Finding, Question, llm_schema
from rfpx.prompts import build_messages, build_recheck_messages, retry_message
from rfpx.textutil import verbatim_key

RULES_ONLY = "found by rules only: the model reply for this part of the file could not be used"


def parse_reply(text: str) -> dict[str, Any]:
    """The first JSON object (or list) in the reply, tolerating code fences and chatter around it."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("reply contains no JSON")
    closer = "}" if text[start] == "{" else "]"
    end = text.rfind(closer)
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise ValueError(f"reply is not valid JSON ({error.msg} at position {error.pos})") from error
    return {"questions": data} if isinstance(data, list) else data


def _error_text(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()[:4])
    return str(error)


class HybridExtractor:
    """Run the model and the rules on every chunk. What both find is accepted; what only one finds goes to the review list.

    Two methods that fail in different ways (the rules miss unusual wording, the model drifts and invents) rarely agree on a
    mistake, so agreement is a cheap confidence signal, and the person only looks at the disagreements.
    """

    name = "hybrid"

    def __init__(self, model: LlmExtractor):
        self.model = model
        self.stats = model.stats

    @property
    def model_name(self) -> str:
        return self.model.model_name

    @property
    def recheck(self) -> bool:
        return self.model.recheck

    @property
    def label(self) -> str:
        return f"Hybrid: {self.model.label} + rules, disagreements held for review"

    def extract(self, chunk: Chunk) -> tuple[list[Question], list[Finding], list[str]]:
        from rfpx.validate import check_question, strip_leading_number

        model_questions, rejected, notes = self.model.extract(chunk)
        rule_questions = [f.q for f in extract_blocks(chunk.blocks, chunk.doc.name)]
        rule_keys = {verbatim_key(strip_leading_number(q).question_text) for q in rule_questions}
        model_keys = {verbatim_key(strip_leading_number(q).question_text) for q in model_questions}
        agreed = [q for q in model_questions if verbatim_key(strip_leading_number(q).question_text) in rule_keys]
        held: list[Finding] = []
        for q in model_questions:
            if q not in agreed:
                held.append(self._hold(check_question(q, chunk, origin="llm"), "found by the model only, not by the rules"))
        for q in rule_questions:
            if verbatim_key(strip_leading_number(q).question_text) not in model_keys:
                held.append(self._hold(check_question(q, chunk, origin="rules"), "found by the rules only, not by the model"))
        # a model reply that failed outright already put the rules' items in `rejected`; do not list them twice
        known = {verbatim_key(f.q.question_text) for f in held}
        return agreed, held + [f for f in rejected if verbatim_key(f.q.question_text) not in known], notes

    @staticmethod
    def _hold(finding: Finding, reason: str) -> Finding:
        if finding.status == "accepted":
            finding.status, finding.reason = "review", reason
        return finding


class LlmExtractor:
    name = "llm"

    def __init__(self, llm: LocalLLM, temperature: float = 0.0, max_tokens: int = 1800, retries: int = 1, recheck: bool = False,
                 json_schema: str = "auto"):
        self.llm, self.temperature, self.max_tokens, self.retries, self.recheck = llm, temperature, max_tokens, retries, recheck
        self.schema = llm_schema() if json_schema in ("auto", "on") else None
        self.stats = {"calls": 0, "retries": 0, "fallback_chunks": 0, "recheck_added": 0, "schema_used": self.schema is not None}

    @property
    def model_name(self) -> str:
        try:
            return self.llm.model()
        except LLMUnavailable:
            return "unavailable"

    @property
    def label(self) -> str:
        name = self.model_name
        if name == "unavailable":
            return "local model (not reachable: the rules were used and everything found is held for review)"
        return f"{name} (local model server)" + (", second pass on" if self.recheck else "")

    def _ask(self, messages: list[dict[str, str]]) -> str:
        self.stats["calls"] += 1
        try:
            return self.llm.chat(messages, max_tokens=self.max_tokens, temperature=self.temperature, schema=self.schema)
        except SchemaUnsupported:
            self.schema, self.stats["schema_used"] = None, False
            return self.llm.chat(messages, max_tokens=self.max_tokens, temperature=self.temperature, schema=None)

    def _valid(self, messages: list[dict[str, str]]) -> tuple[Extraction | None, str, dict[str, Any] | None]:
        """Ask, validate, and on a failure send the error back once (or `retries` times). Returns (result, last error, last raw data)."""
        error, raw = "", None
        for attempt in range(self.retries + 1):
            reply = self._ask(messages)
            try:
                raw = parse_reply(reply)
                return Extraction.model_validate(raw), "", raw
            except (ValueError, ValidationError) as problem:
                error = _error_text(problem)
                if attempt < self.retries:
                    self.stats["retries"] += 1
                    messages = [*messages, {"role": "assistant", "content": reply}, retry_message(error)]
        return None, error, raw

    def extract(self, chunk: Chunk) -> tuple[list[Question], list[Finding], list[str]]:
        try:
            result, error, raw = self._valid(build_messages(chunk.prompt))
        except LLMUnavailable as problem:
            return self._fallback(chunk, f"model unavailable ({problem})", f"model unavailable for part of the file ({problem})")
        if result is not None:
            questions = result.questions
            rejected: list[Finding] = []
        elif isinstance(raw, dict) and isinstance(raw.get("questions"), list):
            questions, rejected = self._salvage(raw["questions"], chunk, error)
        else:
            return self._fallback(chunk, error, "the model reply could not be read for some parts of the file")
        if self.recheck and questions:
            questions += self._second_pass(chunk, questions)
        return questions, rejected, []

    def _salvage(self, items: list[Any], chunk: Chunk, error: str) -> tuple[list[Question], list[Finding]]:
        good: list[Question] = []
        bad: list[Finding] = []
        for item in items:
            try:
                good.append(Question.model_validate(item))
            except ValidationError as problem:
                text = item.get("question_text") if isinstance(item, dict) else None
                if isinstance(text, str) and len(text.strip()) >= 8:
                    stub = Question(question_text=text.strip(), section=str(item.get("section") or ""))
                    bad.append(Finding(stub, chunk.doc.name, status="review", reason=f"model output failed validation: {_error_text(problem)}",
                                       origin="llm"))
        return good, bad

    def _fallback(self, chunk: Chunk, error: str, note: str) -> tuple[list[Question], list[Finding], list[str]]:
        self.stats["fallback_chunks"] += 1
        found = extract_blocks(chunk.blocks, chunk.doc.name)
        for f in found:
            f.status, f.reason = "review", RULES_ONLY
        return [], found, [note]

    def _second_pass(self, chunk: Chunk, found: list[Question]) -> list[Question]:
        try:
            result, _, _ = self._valid(build_recheck_messages(chunk.prompt, [q.question_text for q in found]))
        except LLMUnavailable:
            return []
        known = {verbatim_key(q.question_text) for q in found}
        extra = []
        for q in (result.questions if result else []):
            key = verbatim_key(q.question_text)
            if key not in known:
                known.add(key)
                extra.append(q)
        self.stats["recheck_added"] += len(extra)
        return extra
