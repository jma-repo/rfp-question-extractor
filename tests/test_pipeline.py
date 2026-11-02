import json

from docx import Document

from rfpx.baseline import RulesExtractor
from rfpx.cli import main
from rfpx.ingest import read_document
from rfpx.pipeline import list_inputs, process_document
from rfpx.textutil import is_verbatim, squash


def register_text(path) -> list[str]:
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip() and not p.text.startswith("Generated ")]
    for table in doc.tables:
        parts += ["|".join(c.text for c in row.cells) for row in table.rows]
    return parts


def test_one_command_turns_the_folder_into_one_register(synth_dir, tmp_path, capsys):
    out = tmp_path / "register.docx"
    assert main(["run", str(synth_dir / "rfps"), "-o", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "10 file(s)" in printed and "register.docx" in printed
    doc = Document(str(out))
    headings = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
    assert "Summary" in headings and "Needs human review" in headings
    assert sum(name.endswith((".docx", ".pdf", ".xlsx")) for name in headings) == 10


def test_two_runs_give_the_same_register_apart_from_the_timestamp(synth_dir, tmp_path):
    a, b = tmp_path / "a.docx", tmp_path / "b.docx"
    main(["run", str(synth_dir / "rfps"), "-o", str(a)])
    main(["run", str(synth_dir / "rfps"), "-o", str(b)])
    assert register_text(a) == register_text(b)


def test_every_question_in_the_register_is_a_verbatim_piece_of_its_source(rfp_files):
    for name, path in rfp_files.items():
        doc = read_document(path)
        readable = squash(" ".join(b.text for b in doc.blocks if not b.noise))
        result = process_document(doc, RulesExtractor())
        accepted = [f for f in result.findings if f.status == "accepted"]
        assert accepted, name
        assert all(is_verbatim(f.q.question_text, readable) for f in accepted), name
        assert all(f.q.source_ref for f in accepted), name


def test_inputs_are_found_in_a_folder_or_given_as_one_file(synth_dir):
    assert len(list_inputs(synth_dir / "rfps")) == 10
    one = synth_dir / "rfps" / "northfield-fleet-telematics.docx"
    assert list_inputs(one) == [one]


def test_subfolders_are_read_only_when_asked_for_and_temporary_office_files_never(tmp_path):
    (tmp_path / "01-a").mkdir()
    (tmp_path / "01-a" / "x.docx").write_bytes(b"")
    (tmp_path / "01-a" / "~$x.docx").write_bytes(b"")
    (tmp_path / "02-b").mkdir()
    (tmp_path / "02-b" / "y.pdf").write_bytes(b"")
    (tmp_path / "top.xlsx").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    assert [p.name for p in list_inputs(tmp_path)] == ["top.xlsx"]
    assert [p.name for p in list_inputs(tmp_path, recursive=True)] == ["x.docx", "y.pdf", "top.xlsx"]


def test_a_missing_model_server_does_not_stop_the_run_and_everything_found_is_flagged(synth_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RFPX_NO_LLM", "1")
    out = tmp_path / "offline.docx"
    assert main(["run", str(synth_dir / "rfps" / "northfield-fleet-telematics.docx"), "-o", str(out), "--extractor", "llm"]) == 0
    printed = capsys.readouterr().out
    assert "model unavailable" in printed
    text = "\n".join(register_text(out))
    assert "found by rules only" in text and "No questions were detected" in text


def test_eval_writes_a_report_with_splits_and_formats(synth_dir, tmp_path, capsys):
    report_path = tmp_path / "report.json"
    assert main(["eval", "--extractor", "rules", "--split", "all", "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(report["by_split"]) == {"dev", "test"} and set(report["by_format"]) == {"docx", "pdf", "xlsx"}
    assert report["summary"]["gold"] == 350 and report["settings"]["extractor"] == "rules"
    assert 0.9 < report["summary"]["precision"] <= 1.0
    assert "precision" in capsys.readouterr().out


def test_unsupported_files_are_refused_clearly(tmp_path):
    import pytest

    bad = tmp_path / "notes.txt"
    bad.write_text("Describe your plan.", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        read_document(bad)
