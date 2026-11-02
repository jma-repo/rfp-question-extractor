import json
from pathlib import Path

import pytest

from rfpx.chunking import chunk_document
from rfpx.ingest import Block, Document
from rfpx.llm import LLMUnavailable, SchemaUnsupported
from rfpx.llm_extract import LlmExtractor, parse_reply
from rfpx.models import Extraction
from rfpx.prompts import FEW_SHOT, build_messages, build_recheck_messages
from rfpx.textutil import is_verbatim


def one_chunk(*texts: str):
    blocks = [Block(i, "para", t, f"§1 ¶{i + 1}", "4.1 Experience") for i, t in enumerate(texts)]
    return chunk_document(Document(Path("x.docx"), "x.docx", "docx", blocks))[0]


def item(text, **kw):
    return {"id": None, "section": "4.1 Experience", "question_text": text, "type": "narrative", "required": True, "constraints": "", **kw}


class FakeLLM:
    """Plays back scripted replies (strings, or exceptions to raise) and records every call."""

    model_name = "fake-model"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def model(self):
        return self.model_name

    def chat(self, messages, max_tokens=0, temperature=0.0, schema=None):
        self.calls.append({"messages": messages, "schema": schema})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)


Q1 = "Describe your support model."
Q2 = "Attach the product roadmap."


def extractor(llm, **kw):
    return LlmExtractor(llm, **{"retries": 1, "recheck": False, "json_schema": "off", **kw})


# --- the prompt ---------------------------------------------------------------------------------------

def test_the_few_shot_examples_are_valid_verbatim_and_not_taken_from_the_test_set(gold):
    assert len(FEW_SHOT) == 3
    answers = {g["question_text"] for k in gold.values() for g in k["questions"]}
    for excerpt, questions in FEW_SHOT:
        assert questions
        parsed = Extraction.model_validate({"questions": questions})
        for q in parsed.questions:
            assert is_verbatim(q.question_text, excerpt), q.question_text
            assert q.question_text not in answers
        listed = " ".join(q["question_text"] for q in questions)
        assert any(not is_verbatim(line, listed) for line in excerpt.splitlines())   # every example also has text to ignore


def test_messages_are_system_then_three_worked_examples_then_the_chunk():
    chunk = one_chunk("4.1.1 " + Q1)
    messages = build_messages(chunk.prompt)
    assert [m["role"] for m in messages] == ["system"] + ["user", "assistant"] * 3 + ["user"]
    assert chunk.prompt in messages[-1]["content"]
    assert all(json.loads(m["content"]) for m in messages if m["role"] == "assistant")
    recheck = build_recheck_messages(chunk.prompt, [Q1])
    assert Q1 in recheck[-1]["content"] and "missing" in recheck[-1]["content"].lower()


# --- parsing --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("reply", [
    '{"questions": []}', '```json\n{"questions": []}\n```', 'Here you go:\n{"questions": []}\nDone.', "[]",
])
def test_parse_reply_accepts_fences_chatter_and_bare_lists(reply):
    assert parse_reply(reply) == {"questions": []}


def test_parse_reply_rejects_non_json():
    with pytest.raises(ValueError, match="JSON"):
        parse_reply("I could not find any questions.")


# --- extraction -------------------------------------------------------------------------------------------

def test_a_valid_reply_becomes_questions():
    llm = FakeLLM({"questions": [item(Q1)]})
    questions, rejected, notes = extractor(llm).extract(one_chunk("4.1.1 " + Q1))
    assert [q.question_text for q in questions] == [Q1] and not rejected and not notes
    assert llm.calls[0]["schema"] is None


def test_an_invalid_reply_is_retried_once_with_the_error_in_the_prompt():
    llm = FakeLLM("not json at all", {"questions": [item(Q1)]})
    ex = extractor(llm)
    questions, rejected, notes = ex.extract(one_chunk("4.1.1 " + Q1))
    assert len(questions) == 1 and len(llm.calls) == 2
    retry = llm.calls[1]["messages"]
    assert retry[-2] == {"role": "assistant", "content": "not json at all"}
    assert "valid JSON" in retry[-1]["content"] or "JSON" in retry[-1]["content"]
    assert ex.stats["retries"] == 1


def test_schema_errors_name_the_field_in_the_retry_message():
    llm = FakeLLM({"questions": [item(Q1, type="essay")]}, {"questions": [item(Q1)]})
    extractor(llm).extract(one_chunk(Q1))
    assert "type" in llm.calls[1]["messages"][-1]["content"]


def test_after_the_retry_valid_items_are_kept_and_bad_ones_go_to_review():
    bad = {"questions": [item(Q1), item(Q2, type="essay")]}
    llm = FakeLLM(bad, bad)
    questions, rejected, notes = extractor(llm).extract(one_chunk(Q1, Q2))
    assert [q.question_text for q in questions] == [Q1]
    assert len(rejected) == 1 and rejected[0].status == "review" and rejected[0].q.question_text == Q2 and "type" in rejected[0].reason


def test_unparseable_replies_fall_back_to_the_rules_and_flag_everything_for_review():
    llm = FakeLLM("nonsense", "still nonsense")
    questions, rejected, notes = extractor(llm).extract(one_chunk("4.1.1 " + Q1, "Proposals shall be submitted by email."))
    assert questions == []
    assert [r.q.question_text for r in rejected] == [Q1] and rejected[0].origin == "rules" and rejected[0].status == "review"
    assert "model reply" in rejected[0].reason and notes


def test_a_server_that_is_down_falls_back_to_the_rules_without_retrying():
    llm = FakeLLM(LLMUnavailable("Local model server not reachable"))
    ex = extractor(llm)
    questions, rejected, notes = ex.extract(one_chunk("4.1.1 " + Q1))
    assert questions == [] and len(rejected) == 1 and len(llm.calls) == 1
    assert any("unavailable" in n for n in notes)


def test_a_server_without_schema_support_is_asked_again_without_the_schema_and_remembered():
    llm = FakeLLM(SchemaUnsupported("no"), {"questions": [item(Q1)]}, {"questions": [item(Q1)]})
    ex = extractor(llm, json_schema="auto")
    ex.extract(one_chunk(Q1))
    assert llm.calls[0]["schema"] is not None and llm.calls[1]["schema"] is None
    ex.extract(one_chunk(Q1))
    assert llm.calls[2]["schema"] is None and ex.stats["schema_used"] is False


def test_recheck_asks_what_was_missed_and_adds_only_new_items():
    llm = FakeLLM({"questions": [item(Q1)]}, {"questions": [item(Q2, type="upload"), item(Q1)]})
    ex = extractor(llm, recheck=True)
    questions, _, _ = ex.extract(one_chunk(Q1, Q2))
    assert [q.question_text for q in questions] == [Q1, Q2]
    assert Q1 in llm.calls[1]["messages"][-1]["content"]
    assert ex.stats["recheck_added"] == 1


def test_a_failed_recheck_never_loses_the_first_pass():
    llm = FakeLLM({"questions": [item(Q1)]}, "garbage", "garbage")
    questions, _, _ = extractor(llm, recheck=True).extract(one_chunk(Q1))
    assert [q.question_text for q in questions] == [Q1]


def test_label_names_the_model_or_says_it_was_not_reachable():
    assert "fake-model" in extractor(FakeLLM()).label

    class Down(FakeLLM):
        def model(self):
            raise LLMUnavailable("not reachable")

    assert "not reachable" in extractor(Down()).label


# --- hybrid: accept what the model and the rules both found, hand everything else to a person -------------------

def test_hybrid_accepts_agreement_and_reviews_every_disagreement():
    from rfpx.llm_extract import HybridExtractor
    from rfpx.pipeline import process_document

    q_both, q_model_only, q_rules_only = Q1, "Details of the exit plan are to be provided with the Proposal.", "Describe your hosting plan."
    llm = FakeLLM({"questions": [item(q_both), item(q_model_only)]})
    blocks = [Block(i, "para", t, f"§1 ¶{i + 1}", "4.1 Experience") for i, t in enumerate([f"4.1.1 {q_both}", q_model_only, f"4.1.3 {q_rules_only}"])]
    doc = Document(Path("x.docx"), "x.docx", "docx", blocks)
    result = process_document(doc, HybridExtractor(extractor(llm)), max_chars=5000, gate=False)
    by_text = {f.q.question_text: f for f in result.findings}
    assert by_text[q_both].status == "accepted"
    assert by_text[q_model_only].status == "review" and "model only" in by_text[q_model_only].reason
    assert by_text[q_rules_only].status == "review" and "rules only" in by_text[q_rules_only].reason
    assert by_text[q_both].q.source_ref == "§1 ¶1" and by_text[q_model_only].q.source_ref == "§1 ¶2"


def test_hybrid_keeps_the_models_verbatim_failures_in_review_with_their_own_reason():
    from rfpx.llm_extract import HybridExtractor
    from rfpx.pipeline import process_document

    llm = FakeLLM({"questions": [item("Describe your support model in a reworded way.")]})
    doc = Document(Path("x.docx"), "x.docx", "docx", [Block(0, "para", Q1, "§1 ¶1", "4.1 Experience")])
    result = process_document(doc, HybridExtractor(extractor(llm)), max_chars=5000, gate=False)
    reasons = sorted(f.reason for f in result.findings)
    assert any("verbatim" in r for r in reasons) and any("rules only" in r for r in reasons)
    assert all(f.status == "review" for f in result.findings)
