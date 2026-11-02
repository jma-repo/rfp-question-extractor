import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def load_script():
    spec = importlib.util.spec_from_file_location("results_table", ROOT / "scripts" / "results_table.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_results_in_the_readme_are_the_ones_in_the_reports():
    """No number in the README tables is typed by hand: regenerate the block and compare. Run
    `uv run python scripts/results_table.py --write` after any new evaluation."""
    script = load_script()
    start, end = README.index(script.START) + len(script.START), README.index(script.END)
    assert README[start:end].strip() == script.block()


def test_the_real_file_counts_in_the_readme_are_the_ones_in_the_committed_summary():
    script = load_script()
    start, end = README.index(script.PUBLIC_START) + len(script.PUBLIC_START), README.index(script.PUBLIC_END)
    assert README[start:end].strip() == script.public_block()


def test_the_committed_summary_of_the_real_files_holds_counts_and_ids_only():
    """It may be published; the files themselves may not. No sentence from a real file belongs in it."""
    text = (ROOT / "artifacts" / "reports" / "public-files.json").read_text(encoding="utf-8")
    data = json.loads(text)
    assert set(data) == {"files", "annex_a_numbered_items"}
    assert len(data["files"]) == 6
    assert all(set(entry) == {"format", "bytes", "pages", "chunks", "runs"} for entry in data["files"].values())
    assert len(text) < 20000


def test_the_headline_numbers_quoted_in_the_prose_match_the_reports():
    rules = json.loads((ROOT / "artifacts" / "reports" / "eval_rules.json").read_text(encoding="utf-8"))
    assert rules["summary"]["gold"] == 350                                # "350 distinct questions"
    assert README.count("350 distinct questions") == 1
    hybrid = json.loads((ROOT / "artifacts" / "reports" / "eval_hybrid-qwen2.5-3b.json").read_text(encoding="utf-8"))
    assert hybrid["by_split"]["test"]["precision"] > 0.98                 # "precision above 0.98"
    assert hybrid["by_split"]["test"]["recall_with_review"] > 0.97        # "close to 0.98"


def test_every_report_the_script_reads_exists():
    script = load_script()
    for _, name in script.ROWS:
        assert (ROOT / "artifacts" / "reports" / f"{name}.json").exists(), name
