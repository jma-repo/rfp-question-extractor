import pytest
from pydantic import ValidationError

from rfpx.models import Extraction, Question, llm_schema


def test_question_defaults_and_trimming():
    q = Question(question_text="  Describe your support model.  ")
    assert q.question_text == "Describe your support model."
    assert (q.id, q.type, q.required, q.constraints, q.section, q.source_ref) == (None, "narrative", True, "", "", "")


@pytest.mark.parametrize("raw", [None, "", "null", "None", "n/a", "N/A", "  "])
def test_blank_ids_become_none(raw):
    assert Question(id=raw, question_text="Describe your support model.").id is None


def test_numeric_ids_become_strings():
    assert Question(id=12, question_text="Describe your support model.").id == "12"
    assert Question(id="4.2.1", question_text="Describe your support model.").id == "4.2.1"


def test_null_text_fields_become_empty_strings():
    q = Question(question_text="Describe your support model.", constraints=None, section=None)
    assert q.constraints == "" and q.section == ""


@pytest.mark.parametrize("raw,expected", [("mandatory", True), ("Required", True), ("shall", True), ("true", True),
                                          ("optional", False), ("Desirable", False), ("should", False), ("false", False)])
def test_required_accepts_the_words_models_actually_return(raw, expected):
    assert Question(question_text="Describe your support model.", required=raw).required is expected


def test_unknown_type_is_rejected_so_the_retry_message_can_name_it():
    with pytest.raises(ValidationError) as err:
        Question(question_text="Describe your support model.", type="essay")
    assert "type" in str(err.value)


def test_too_short_text_is_rejected():
    with pytest.raises(ValidationError):
        Question(question_text="Yes")


def test_extraction_wraps_a_list_and_ignores_extra_keys():
    out = Extraction.model_validate({"questions": [{"question_text": "Describe your support model.", "confidence": 0.9}]})
    assert len(out.questions) == 1


def test_llm_schema_is_flat_and_omits_source_ref():
    schema = llm_schema()
    item = schema["properties"]["questions"]["items"]
    assert set(item["properties"]) == {"id", "section", "question_text", "type", "required", "constraints"}
    assert item["properties"]["type"]["enum"] == ["narrative", "yes_no", "table", "upload", "pricing"]
    assert item["required"] == ["id", "section", "question_text", "type", "required", "constraints"]
    assert schema["required"] == ["questions"]
