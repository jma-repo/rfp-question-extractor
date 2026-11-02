"""Run an extractor over downloaded public files and keep everything: a Word register and a JSON dump of every finding.

    uv run python -I -X utf8 scripts/run_public.py --extractor rules|llm|hybrid --out-prefix out/public-rules FILE [FILE ...]

The files are untrusted data: pass their paths as arguments, never run anything from inside their folder, and start Python with -I.
The dumps hold the real files' text, so they go to out/ (git-ignored); `summarize_public.py` turns them into counts that can be committed.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from rfpx.baseline import RulesExtractor
from rfpx.config import settings
from rfpx.ingest import read_document
from rfpx.llm import LocalLLM
from rfpx.llm_extract import HybridExtractor, LlmExtractor
from rfpx.pipeline import process_document
from rfpx.render import build_context, render_register


def main(argv: list[str]) -> int:
    kind = argv[argv.index("--extractor") + 1]
    prefix = Path(argv[argv.index("--out-prefix") + 1])
    files = [Path(a) for a in argv if a.lower().endswith((".pdf", ".docx", ".xlsx"))]
    s = settings()
    options = s.llm
    if kind == "rules":
        extractor = RulesExtractor()
    else:
        model = LlmExtractor(LocalLLM(options["base_url"], timeout=float(options["timeout_s"]), reasoning_effort=options["reasoning_effort"]),
                             **{k: options[k] for k in ("temperature", "max_tokens", "retries", "recheck", "json_schema")})
        extractor = HybridExtractor(model) if kind == "hybrid" else model
    results, dump = [], []
    started = time.time()
    for path in files:
        result = process_document(read_document(path), extractor, s.max_chars, s.near_duplicate)
        results.append(result)
        accepted = sum(f.status == "accepted" for f in result.findings)
        print(f"{path.name}: chunks={result.chunks} accepted={accepted} review={len(result.findings) - accepted} "
              f"merged={result.stats['merged_duplicates']} {result.seconds}s notes={sorted(set(result.notes))}", flush=True)
        dump += [{"file": path.name, "status": f.status, "reason": f.reason, "origin": f.origin, "id": f.q.id, "section": f.q.section,
                  "type": f.q.type, "required": f.q.required, "constraints": f.q.constraints, "ref": f.q.source_ref,
                  "also": f.also, "similar_to": f.similar_to, "text": f.q.question_text} for f in result.findings]
    prefix.parent.mkdir(parents=True, exist_ok=True)
    render_register(build_context(results, extractor.label), s.path("template"), prefix.with_suffix(".docx"))
    prefix.with_suffix(".json").write_text(
        json.dumps({"extractor": extractor.label, "seconds": round(time.time() - started, 1), "files": [p.name for p in files],
                    "findings": dump}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("done", prefix, f"{time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
