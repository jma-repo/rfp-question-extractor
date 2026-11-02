from rfpx.chunking import chunk_document
from rfpx.dedupe import merge_duplicates
from rfpx.ingest import Block, Document, read_document
from rfpx.models import Finding, Question
from rfpx.validate import check_question, strip_leading_number


def make_chunk(*blocks: Block):
    from pathlib import Path

    doc = Document(Path("x.docx"), "x.docx", "docx", list(blocks))
    return chunk_document(doc)[0]


def para(idx, text, loc="§4.1 ¶1", section="4.1 Corporate Experience", page=None):
    return Block(idx, "para", text, loc, section, page=page)


def q(text, **kw):
    return Question(question_text=text, **kw)


def fnd(text, ref="p.1 L1", id=None, **kw):
    return Finding(Question(id=id, question_text=text, source_ref=ref), "a.pdf", **kw)


# --- verification against the source ---------------------------------------------------------------------

def test_a_verbatim_question_is_accepted_and_gets_its_location_from_the_source():
    chunk = make_chunk(para(0, "Intro text."), para(1, "4.1.2 The Proponent shall describe its support model.", "§4.1 ¶2"))
    out = check_question(q("The Proponent shall describe its support model.", id="9.9", section="made up"), chunk)
    assert out.status == "accepted" and out.reason == ""
    assert out.q.source_ref == "§4.1 ¶2"
    assert out.q.id == "4.1.2"                           # the printed number wins over what the model said
    assert out.q.section == "4.1 Corporate Experience"   # so does the heading


def test_a_reworded_question_goes_to_review_with_a_reason():
    chunk = make_chunk(para(0, "4.1.2 The Proponent shall describe its support model."))
    out = check_question(q("The Proponent must explain its support model."), chunk)
    assert out.status == "review" and "verbatim" in out.reason


def test_layout_and_a_dropped_full_stop_do_not_count_as_rewording():
    chunk = make_chunk(para(0, "Describe your   support\nmodel, including hours of coverage."))
    assert check_question(q("Describe your support model, including hours of coverage"), chunk).status == "accepted"


def test_leading_numbers_are_stripped_from_the_text_and_kept_as_the_id():
    assert strip_leading_number(q("4.2.1 Describe your plan.")).question_text == "Describe your plan."
    assert strip_leading_number(q("4.2.1 Describe your plan.")).id == "4.2.1"
    assert strip_leading_number(q("Describe your plan.", id="3")).id == "3"


def test_table_cell_questions_are_found_inside_the_row_text():
    row = Block(0, "row", "R-001 | The system shall support SAML 2.0. | Mandatory", "T1 r1", "3 Functional",
                cells=("R-001", "The system shall support SAML 2.0.", "Mandatory"), header=("Req #", "Requirement", "M/D"))
    out = check_question(q("The system shall support SAML 2.0."), make_chunk(row))
    assert out.status == "accepted" and out.q.source_ref == "T1 r1"


def test_a_question_that_appears_twice_in_a_chunk_is_located_at_its_first_occurrence():
    chunk = make_chunk(para(0, "Describe your plan.", "§1 ¶1"), para(1, "Describe your plan.", "§1 ¶2"))
    assert check_question(q("Describe your plan."), chunk).q.source_ref == "§1 ¶1"


# --- duplicates -----------------------------------------------------------------------------------------

def test_exact_duplicates_are_merged_and_their_locations_kept():
    out = merge_duplicates([fnd("Describe your support model.", "p.3 L4", "4.1"), fnd("Describe your support model", "p.9 L2", "6.1.2"),
                            fnd("Attach the roadmap.", "p.4 L1")])
    assert [f.q.question_text for f in out] == ["Describe your support model.", "Attach the roadmap."]
    assert out[0].also == ["p.9 L2"]


def test_a_reworded_repeat_is_kept_but_flagged_with_the_earlier_item():
    out = merge_duplicates([
        fnd("The Proponent shall describe its disaster recovery plan, including recovery time and recovery point objectives.", "p.3 L4", "4.4.2"),
        fnd("Describe your disaster recovery plan, including recovery time and recovery point objectives.", "p.8 L7", "6.1.1")])
    assert len(out) == 2 and out[0].similar_to == "" and out[1].similar_to == "4.4.2"


def test_different_questions_on_nearby_topics_are_not_flagged():
    out = merge_duplicates([fnd("Describe your training plan for administrators.", "p.1 L1"), fnd("Describe your hosting plan for administrators.", "p.1 L2")])
    assert [f.similar_to for f in out] == ["", ""]


def test_items_in_review_are_never_merged_or_dropped():
    out = merge_duplicates([fnd("Describe your support model.", "p.1 L1"), fnd("Describe your support model.", "p.2 L1", status="review", reason="x")])
    assert len(out) == 2 and out[0].also == []


def test_rules_findings_on_a_real_file_round_trip_through_verification(rfp_files):
    from rfpx.baseline import extract_document

    doc = read_document(rfp_files["northfield-fleet-telematics.docx"])
    chunks = chunk_document(doc)
    findings = extract_document(doc)
    for finding in findings[:20]:
        chunk = next(c for c in chunks if any(b.loc == finding.q.source_ref for b in c.blocks))
        assert check_question(finding.q, chunk).status == "accepted"
