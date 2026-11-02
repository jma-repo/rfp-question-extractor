"""Turn the run dumps on the downloaded public files into counts that can be committed (no text from the files).

    uv run python -I -X utf8 scripts/summarize_public.py

Reads out/public-rules.json, out/public-hybrid-3b.json and out/public-llm-27b-annex-a.json (written by run_public.py) and the files in
data/public/, writes artifacts/reports/public-files.json. Besides counts per file, it gives one rough yardstick for the one real file that is
a list of numbered questions (CITT Annex A): how many of the numbered items (1.1, 1.2, ...) each run accepted, or accepted or held for review.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from rfpx.chunking import chunk_document
from rfpx.config import settings
from rfpx.ingest import read_document
from rfpx.textutil import split_number

ROOT = Path(__file__).resolve().parents[1]
RUNS = {"rules": "public-rules", "hybrid_3b": "public-hybrid-3b", "llm_27b": "public-llm-27b-annex-a"}
ANNEX = "citt-annex-a-questions-to-industry.pdf"


def numbered_items(path: Path) -> list[str]:
    found: dict[str, str] = {}
    for b in read_document(path).blocks:
        if b.noise or b.kind != "para":
            continue
        number, body = split_number(b.text)
        if number and re.fullmatch(r"\d{1,2}\.\d{1,2}", number) and len(body) > 25:
            found.setdefault(number, body)
    return sorted(found, key=lambda s: tuple(map(int, s.split("."))))


def main() -> int:
    files = sorted((ROOT / "data" / "public").rglob("*.*"))
    files = [p for p in files if p.suffix.lower() in (".pdf", ".docx", ".xlsx")]
    if not files:
        print("no files in data/public", file=sys.stderr)
        return 2
    max_chars = settings().max_chars
    summary: dict = {"files": {}, "annex_a_numbered_items": {}}
    for path in files:
        doc = read_document(path)
        summary["files"][path.name] = {"format": doc.fmt, "bytes": path.stat().st_size, "pages": doc.pages,
                                       "chunks": len(chunk_document(doc, max_chars)), "runs": {}}
    for label, stem in RUNS.items():
        dump = ROOT / "out" / f"{stem}.json"
        if not dump.exists():
            continue
        data = json.loads(dump.read_text(encoding="utf-8"))
        processed = data.get("files") or sorted({f["file"] for f in data["findings"]})     # a file with no findings is still a file the run read
        for name, entry in summary["files"].items():
            if name not in processed:
                continue
            rows = [f for f in data["findings"] if f["file"] == name]
            accepted = [f for f in rows if f["status"] == "accepted"]
            entry["runs"][label] = {"accepted": len(accepted), "review": len(rows) - len(accepted),
                                    "review_reasons": dict(Counter(f["reason"] for f in rows if f["status"] != "accepted")),
                                    "extractor": data["extractor"], "seconds_all_files_in_run": data["seconds"]}
    annex = next(p for p in files if p.name == ANNEX)
    numbered = numbered_items(annex)
    key = {"total": len(numbered), "ids": numbered}
    for label, stem in RUNS.items():
        dump = ROOT / "out" / f"{stem}.json"
        if not dump.exists():
            continue
        rows = [f for f in json.loads(dump.read_text(encoding="utf-8"))["findings"] if f["file"] == ANNEX]
        accepted = {f["id"] for f in rows if f["status"] == "accepted" and f["id"]}
        anywhere = {f["id"] for f in rows if f["id"]}
        key[label] = {"accepted": len(set(numbered) & accepted), "accepted_or_review": len(set(numbered) & anywhere),
                      "not_found_at_all": sorted(set(numbered) - anywhere, key=lambda s: tuple(map(int, s.split("."))))}
    summary["annex_a_numbered_items"] = key
    target = ROOT / "artifacts" / "reports" / "public-files.json"
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("written", target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
