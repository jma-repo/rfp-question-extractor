import pytest

from rfpx.evaluate import aggregate, score_document
from rfpx.models import Finding, Question


def gold(text, id=None, type="narrative", required=True):
    return {"id": id, "question_text": text, "type": type, "required": required, "section": "", "constraints": "", "dup_group": None}


def found(text, id=None, type="narrative", required=True, status="accepted"):
    return Finding(Question(id=id, question_text=text, type=type, required=required), "doc", status=status)


def test_exact_matches_count_as_true_positives_and_the_rest_as_errors():
    g = [gold("Describe your support model."), gold("Describe your training plan."), gold("Attach the roadmap.", type="upload")]
    p = [found("Describe your support model."), found("Describe your hosting plan."), found("Attach the roadmap.", type="upload")]
    s = score_document(p, g)
    assert (s.tp, s.fp, s.fn) == (2, 1, 1)
    assert s.precision == pytest.approx(2 / 3) and s.recall == pytest.approx(2 / 3)
    assert s.false_positives == ["Describe your hosting plan."] and s.misses == ["Describe your training plan."]


def test_matching_ignores_layout_and_a_final_full_stop_but_not_wording():
    s = score_document([found("Describe  your support\nmodel"), found("Describe your support models.")],
                       [gold("Describe your support model.")])
    assert (s.tp, s.fp, s.fn) == (1, 1, 0)


def test_a_slightly_reworded_answer_is_a_miss_and_a_false_positive_but_is_reported_as_a_near_miss():
    s = score_document([found("Describe your support models.")], [gold("Describe your support model.")])
    assert (s.tp, s.fp, s.fn) == (0, 1, 1)
    assert s.near_misses == 1


def test_a_different_question_about_another_topic_is_not_a_near_miss():
    s = score_document([found("Describe your hosting plan.")], [gold("Describe your training plan.")])
    assert (s.fp, s.fn, s.near_misses) == (1, 1, 0)


def test_a_truncated_answer_is_a_near_miss():
    s = score_document([found("Describe your support model")], [gold("Describe your support model, including hours of coverage.")])
    assert (s.tp, s.near_misses) == (0, 1)


def test_type_required_and_id_accuracy_are_measured_on_true_positives_only():
    g = [gold("Describe your support model.", id="4.1", type="narrative", required=True),
         gold("Does it support SAML? (Yes/No)", id="4.2", type="yes_no", required=False)]
    p = [found("Describe your support model.", id="4.1", type="narrative", required=True),
         found("Does it support SAML? (Yes/No)", id="4.9", type="narrative", required=False),
         found("Something else entirely.", type="upload")]
    s = score_document(p, g)
    assert (s.type_ok, s.required_ok, s.id_ok, s.tp) == (1, 2, 1, 2)


def test_review_items_are_not_accepted_but_count_toward_recall_with_review():
    g = [gold("Describe your support model."), gold("Describe your training plan.")]
    p = [found("Describe your support model."), found("Describe your training plan.", status="review")]
    s = score_document(p, g)
    assert (s.tp, s.fp, s.fn) == (1, 0, 1)
    assert s.recall_with_review == 1.0 and s.review == 1


def test_duplicate_gold_texts_count_once():
    g = [gold("Describe your support model."), gold("Describe your support model.")]
    s = score_document([found("Describe your support model.")], g)
    assert (s.tp, s.fn, s.gold) == (1, 0, 1)


def test_aggregate_gives_micro_macro_and_per_format_numbers():
    a = score_document([found("Describe your support model.")], [gold("Describe your support model."), gold("Describe your training plan.")])
    b = score_document([found("Describe your hosting plan.")], [gold("Describe your hosting plan.")])
    a.file, a.format, b.file, b.format = "a.docx", "docx", "b.pdf", "pdf"
    out = aggregate([a, b])
    assert out["summary"]["precision"] == 1.0
    assert out["summary"]["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert out["summary"]["macro_recall"] == pytest.approx(0.75)
    assert set(out["by_format"]) == {"docx", "pdf"}
    assert out["by_format"]["pdf"]["recall"] == 1.0
    assert [d["file"] for d in out["documents"]] == ["a.docx", "b.pdf"]
