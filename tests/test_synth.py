import json
from collections import Counter

from rfpx.synth.compose import PLANS
from rfpx.synth.generate import run
from rfpx.textutil import verbatim_key


def test_the_committed_answer_keys_are_what_the_generator_produces(synth_dir, tmp_path):
    """Stale data (generator changed, files not regenerated) fails here."""
    run(tmp_path)
    for path in sorted((tmp_path / "gold").glob("*.json")):
        assert path.read_text(encoding="utf-8") == (synth_dir / "gold" / path.name).read_text(encoding="utf-8"), path.name
    for name in ("manifest.json", "gold_all.csv"):
        assert (tmp_path / name).read_bytes() == (synth_dir / name).read_bytes(), name


def test_the_set_has_three_formats_and_a_dev_test_split(synth_dir):
    manifest = json.loads((synth_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == len(PLANS) == 10
    assert Counter(m["format"] for m in manifest) == {"docx": 4, "pdf": 3, "xlsx": 3}
    assert Counter(m["split"] for m in manifest) == {"dev": 3, "test": 7}
    assert {m["format"] for m in manifest if m["split"] == "dev"} == {"docx", "pdf", "xlsx"}


def test_answer_keys_are_well_formed_and_cover_the_cases_the_set_is_meant_to_cover(gold):
    types, required, repeated, indirect = Counter(), Counter(), 0, 0
    for name, key in gold.items():
        texts = Counter(verbatim_key(g["question_text"]) for g in key["questions"])
        for g in key["questions"]:
            assert g["type"] in {"narrative", "yes_no", "table", "upload", "pricing"}, name
            assert len(g["question_text"]) >= 8 and g["section"], name
            types[g["type"]] += 1
            required[g["required"]] += 1
            repeated += g["dup_group"] is not None
            indirect += g["question_text"].startswith(("Please ", "Proponent to ")) or " are to be " in g["question_text"] or " is to be " in g["question_text"]
        assert all(count == 1 for k, count in texts.items() if not any(
            g["dup_group"] for g in key["questions"] if verbatim_key(g["question_text"]) == k)), name
    assert set(types) == {"narrative", "yes_no", "table", "upload", "pricing"} and min(types.values()) >= 10
    assert required[False] >= 25 and required[True] >= 250
    assert repeated >= 20 and indirect >= 25


def test_every_document_carries_the_synthetic_banner(rfp_files):
    from rfpx.ingest import read_document

    for name, path in rfp_files.items():
        text = " ".join(b.text for b in read_document(path).blocks)
        assert "Synthetic test document - not a real solicitation" in text, name
