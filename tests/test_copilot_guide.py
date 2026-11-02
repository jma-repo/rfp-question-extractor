import re
from pathlib import Path

from rfpx.textutil import is_verbatim

GUIDE = (Path(__file__).resolve().parents[1] / "docs" / "copilot-guide.md").read_text(encoding="utf-8")


def instructions() -> str:
    block = re.search(r"<!-- agent-instructions:start -->\s*```text\n(.*?)\n```\s*<!-- agent-instructions:end -->", GUIDE, re.S)
    assert block, "the Instructions block is missing or its markers were removed"
    return block.group(1)


def test_instructions_fit_agent_builders_limit_with_room_to_spare():
    assert len(instructions()) <= 7000                 # Agent Builder accepts 8,000 characters


def test_instructions_name_every_rule_the_guide_depends_on():
    text = instructions()
    for phrase in ("COPY WORD FOR WORD", "Never invent an item", "UNKNOWN", "Starts with / Ends with", "Last item in chunk",
                   "CONTEXT ONLY", "REVIEW", "MISSING"):
        assert phrase in text, phrase


def test_the_worked_example_copies_its_chunk_and_counts_words_correctly():
    text = instructions()
    chunk = text.split("Chunk:\n", 1)[1].split("\nReply:\n", 1)[0]
    reply = text.split("\nReply:\n", 1)[1]
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in reply.splitlines()
            if line.startswith("|") and not line.startswith("| Ref") and "---" not in line]
    assert len(rows) == 3
    for row in rows:
        body, kind, required, starts, ends = row[2], row[3], row[4], row[7], row[8]      # Ref | Section | Text | Type | Required | ...
        assert is_verbatim(body, chunk), body
        words = body.split()
        assert starts == " ".join(words[:6]), (starts, words[:6])
        assert ends == " ".join(words[-6:]), (ends, words[-6:])
        assert kind in {"yes_no", "upload", "pricing", "table", "narrative"} and required in {"Yes", "No"}
    assert "Items: 3 | Review: 0 | Last item in chunk: " + " ".join(rows[-1][2].split()[:6]) in reply


def test_the_example_leaves_out_what_the_rules_say_to_leave_out():
    text = instructions()
    reply = text.split("\nReply:\n", 1)[1]
    assert "Proposals shall be submitted" not in reply
    assert "The Proponent shall address each of the following" not in reply


def test_the_json_example_is_valid_and_has_the_keys_the_snippet_needs():
    import json

    block = re.search(r"<!-- json-example:start -->\s*```text\n(.*?)\n```\s*<!-- json-example:end -->", GUIDE, re.S)
    assert block
    line = next(ln for ln in block.group(1).splitlines() if ln.startswith("Example JSON:"))
    rows = json.loads(line.split("Example JSON:", 1)[1])
    assert set(rows[0]) == {"rfp", "section", "ref", "text", "type", "required", "constraints", "source"}
    assert rows[0]["required"] is False and rows[0]["type"] == "yes_no"


def test_every_prompt_the_guide_promises_is_present():
    for heading in ("### P1", "### P2", "### P3", "### P4", "### P5", "### P6"):
        assert heading in GUIDE
    for link in ("copilot_snippets.py",):
        assert link in GUIDE
