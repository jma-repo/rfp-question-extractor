"""Prompts for the local model. Short rules plus three worked examples: for a 3B model the examples do more than longer
instructions. The examples use invented subject matter that appears nowhere in the synthetic test set."""

from __future__ import annotations

import json

SYSTEM = """You read one excerpt of a request for proposals (RFP) and list every question or requirement the vendor has to answer in its response.

Rules
1. Copy each item word for word from the excerpt. Never rewrite, shorten, merge or translate. Do not copy the printed number into question_text; put it in id.
2. One entry per question or requirement that asks the vendor to describe, state, provide, confirm, list, attach or price something. Include items inside table rows. Keep a printed "(Optional)" or "(Desirable)" marker and a printed "(Yes/No)" as part of the text.
3. Leave out: background, definitions, dates and submission instructions, evaluation criteria and weights, contact details, headings, table header rows, blank form rows, line items of a pricing table, notes about page limits, and a sentence that only introduces a list. Every lettered or numbered item under such a sentence is still an item. The instruction to complete a pricing table IS an item.
4. id: the number printed in front of the item, exactly as printed, or null.
5. section: the heading the item sits under.
6. type: yes_no (the answer is yes or no), upload (a document must be attached), pricing (prices, rates, costs), table (the answer is a table or a list in fixed columns), narrative (anything else).
7. required: true when the text says shall, must, is required or says nothing; false when it says optional, desirable, should or may, or the table marks the item desirable or optional.
8. constraints: page, word or file limits, formats, amounts, appendix references; "" if there are none.
9. Go through the whole excerpt to its last line, in order. Do not stop early.
Reply with JSON only, in the form {"questions": [...]}. If the excerpt has no questions, reply {"questions": []}."""


def _q(id_, section, text, type_="narrative", required=True, constraints=""):
    return {"id": id_, "section": section, "question_text": text, "type": type_, "required": required, "constraints": constraints}


FEW_SHOT: list[tuple[str, list[dict]]] = [
    (
        "Section: 3.2 Network Design\n"
        "## 3.2 Network Design\n"
        "3.2.1 The Proponent shall describe how access points are managed centrally, including firmware updates.\n"
        "Proposals shall be submitted through the City portal before the Closing Time.\n"
        "3.2.2 Please state the maximum number of simultaneous users that each access point supports.\n"
        "3.2.3 (Optional) Does the solution support captive portals with branded landing pages? (Yes/No)\n"
        "3.2.4 The Proponent should describe how outages are reported to the City.",
        [_q("3.2.1", "3.2 Network Design", "The Proponent shall describe how access points are managed centrally, including firmware updates."),
         _q("3.2.2", "3.2 Network Design", "Please state the maximum number of simultaneous users that each access point supports."),
         _q("3.2.3", "3.2 Network Design", "(Optional) Does the solution support captive portals with branded landing pages? (Yes/No)",
            "yes_no", False),
         _q("3.2.4", "3.2 Network Design", "The Proponent should describe how outages are reported to the City.", "narrative", False)],
    ),
    (
        "Section: Appendix B Requirements\n"
        "## Appendix B Requirements\n"
        "| Ref | Requirement | M/D | Response |\n"
        "| B-01 | The system shall export any report to Excel and PDF. | Mandatory |  |\n"
        "| B-02 | The system should provide a mobile application for field crews. | Desirable |  |\n"
        "| Item | Description | Qty | Unit price (CAD) |\n"
        "| 1 | Annual licence | 1 |  |\n"
        "| 2 | Training day | 5 |  |\n"
        "Complete the price table above for each year of the contract term.",
        [_q("B-01", "Appendix B Requirements", "The system shall export any report to Excel and PDF.", "yes_no"),
         _q("B-02", "Appendix B Requirements", "The system should provide a mobile application for field crews.", "yes_no", False),
         _q(None, "Appendix B Requirements", "Complete the price table above for each year of the contract term.", "pricing")],
    ),
    (
        "Section: 5 Required Documents\n"
        "## 5 Required Documents\n"
        "A copy of the Proponent's business licence must be attached to the Proposal.\n"
        "Note: responses to this section should not exceed 10 pages.\n"
        "Proponents shall address each of the following in their response:\n"
        "(a) Describe how operators are certified before they run the equipment.\n"
        "(b) Attach a sample maintenance schedule (PDF, maximum two pages).\n"
        "Unit rates for each class of equipment are required.",
        [_q(None, "5 Required Documents", "A copy of the Proponent's business licence must be attached to the Proposal.", "upload"),
         _q("(a)", "5 Required Documents", "Describe how operators are certified before they run the equipment."),
         _q("(b)", "5 Required Documents", "Attach a sample maintenance schedule (PDF, maximum two pages).", "upload", True, "PDF, maximum two pages"),
         _q(None, "5 Required Documents", "Unit rates for each class of equipment are required.", "pricing")],
    ),
]


def _excerpt(chunk_prompt: str) -> str:
    return f"Excerpt:\n{chunk_prompt}"


def build_messages(chunk_prompt: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM}]
    for excerpt, questions in FEW_SHOT:
        messages.append({"role": "user", "content": _excerpt(excerpt)})
        messages.append({"role": "assistant", "content": json.dumps({"questions": questions}, ensure_ascii=False)})
    messages.append({"role": "user", "content": _excerpt(chunk_prompt)})
    return messages


def build_recheck_messages(chunk_prompt: str, listed: list[str]) -> list[dict[str, str]]:
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(listed, start=1)) or "(none)"
    ask = (f"{_excerpt(chunk_prompt)}\n\nQuestions already listed:\n{numbered}\n\n"
           "Is any question or requirement in the excerpt missing from that list? Reply with JSON only, in the same form, containing "
           'only the missing items, each copied word for word. If nothing is missing reply {"questions": []}.')
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": ask}]


def retry_message(error: str) -> dict[str, str]:
    return {"role": "user", "content": f"That reply was not usable: {error}. Reply again with valid JSON only, in the form "
                                       '{"questions": [...]} with every field present.'}
