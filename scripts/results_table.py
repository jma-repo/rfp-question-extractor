"""Print the results tables of the README from artifacts/reports/*.json, so no number in the README is typed by hand.

    uv run python scripts/results_table.py            # print
    uv run python scripts/results_table.py --write    # replace the block between the markers in README.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "artifacts" / "reports"
README = ROOT / "README.md"
START, END = "<!-- results:start -->", "<!-- results:end -->"

ROWS = [
    ("Rules (regular expressions, no model)", "eval_rules"),
    ("qwen2.5-3b-instruct", "eval_qwen2.5-3b"),
    ("&nbsp;&nbsp;+ second pass for missed items", "eval_qwen2.5-3b_recheck"),
    ("&nbsp;&nbsp;without the section gate", "eval_qwen2.5-3b_nogate"),
    ("&nbsp;&nbsp;without JSON-schema decoding", "eval_qwen2.5-3b_noschema"),
    ("Hybrid: qwen2.5-3b + rules, disagreements to review", "eval_hybrid-qwen2.5-3b"),
    ("&nbsp;&nbsp;+ second pass for missed items", "eval_hybrid-qwen2.5-3b_recheck"),
    ("qwen3.8-27b, reasoning off", "eval_qwen3.8-27b"),
]


def load(name: str) -> dict | None:
    path = REPORTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def roll(report: dict, files: list[str] | None = None) -> dict:
    docs = [d for d in report["documents"] if files is None or d["file"] in files]
    gold, pred, tp = sum(d["gold"] for d in docs), sum(d["pred"] for d in docs), sum(d["tp"] for d in docs)
    precision, recall = tp / pred if pred else 0.0, tp / gold if gold else 0.0
    return {"p": precision, "r": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "gold": gold, "pred": pred, "review": sum(d["review"] for d in docs), "seconds": sum(d.get("seconds", 0) for d in docs)}


def fmt(x: float) -> str:
    return f"{x:.3f}"


def main_table() -> list[str]:
    lines = ["| Extractor | Test precision | Test recall | Test F1 | Test recall incl. review list | Items in review (test) | Dev F1 |",
             "|---|---|---|---|---|---|---|"]
    for label, name in ROWS:
        report = load(name)
        if report is None:
            continue
        test, dev = report["by_split"]["test"], report["by_split"]["dev"]
        lines.append(f"| {label} | {fmt(test['precision'])} | {fmt(test['recall'])} | {fmt(test['f1'])} | {fmt(test['recall_with_review'])} | "
                     f"{test['review_items']} | {fmt(dev['f1'])} |")
    return lines


def by_format_table() -> list[str]:
    lines = ["| Test split | Word (3 files) | PDF (2 files) | Excel (2 files) |", "|---|---|---|---|"]
    for label, name in (("Rules", "eval_rules"), ("qwen2.5-3b", "eval_qwen2.5-3b"), ("Hybrid", "eval_hybrid-qwen2.5-3b"),
                        ("qwen3.8-27b", "eval_qwen3.8-27b")):
        report = load(name)
        if report is None:
            continue
        cells = []
        for fmt_name in ("docx", "pdf", "xlsx"):
            files = [d["file"] for d in report["documents"] if d["format"] == fmt_name and d["split"] == "test"]
            r = roll(report, files)
            cells.append(f"P {fmt(r['p'])} / R {fmt(r['r'])}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


def labels_table() -> list[str]:
    lines = ["| Test split, matched questions | Type correct | Required correct | Number correct |", "|---|---|---|---|"]
    for label, name in (("Rules", "eval_rules"), ("qwen2.5-3b", "eval_qwen2.5-3b"), ("Hybrid", "eval_hybrid-qwen2.5-3b"),
                        ("qwen3.8-27b", "eval_qwen3.8-27b")):
        report = load(name)
        if report is None:
            continue
        s = report["by_split"]["test"]
        lines.append(f"| {label} | {fmt(s['type_accuracy'])} | {fmt(s['required_accuracy'])} | {fmt(s['id_accuracy'])} |")
    return lines


def review_reasons() -> list[str]:
    columns = [("qwen2.5-3b", load("eval_qwen2.5-3b")), ("Hybrid", load("eval_hybrid-qwen2.5-3b")), ("qwen3.8-27b", load("eval_qwen3.8-27b"))]
    columns = [(label, report["summary"]) for label, report in columns if report is not None]
    if not columns:
        return []
    reasons = list(dict.fromkeys(r for _, s in columns for r in s.get("review_reasons", {})))
    lines = ["| Why an item is in the review list (all 10 files) | " + " | ".join(label for label, _ in columns) + " |",
             "|---|" + "---|" * len(columns)]
    lines += [f"| {reason} | " + " | ".join(str(s.get("review_reasons", {}).get(reason, 0)) for _, s in columns) + " |" for reason in reasons]
    lines.append("| **Items in the review list** | " + " | ".join(f"**{s['review_items']}**" for _, s in columns) + " |")
    lines.append("| of which are real questions from the answer key | " + " | ".join(str(s["review_real_questions"]) for _, s in columns) + " |")
    return lines


def block() -> str:
    parts = [main_table(), [""], by_format_table(), [""], labels_table(), [""], review_reasons()]
    return "\n".join(line for part in parts for line in part).strip()


def main() -> int:
    text = block()
    if "--write" not in sys.argv:
        print(text)
        return 0
    readme = README.read_text(encoding="utf-8")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(f"{head}{START}\n{text}\n{END}{tail}", encoding="utf-8", newline="\n")
    print(f"updated {README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
