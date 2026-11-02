"""Write the synthetic RFPs and their answer keys: data/synthetic/rfps/*, gold/*.json and manifest.json."""

from __future__ import annotations

import json
from pathlib import Path

from rfpx.synth.compose import PLANS, compose
from rfpx.synth.writers import WRITERS


def run(out: Path) -> list[dict]:
    rfp_dir, gold_dir = out / "rfps", out / "gold"
    rfp_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for plan in PLANS:
        rfp = compose(plan)
        WRITERS[rfp.fmt](rfp, rfp_dir / rfp.filename)
        golds = rfp.golds()
        (gold_dir / f"{rfp.slug}.json").write_text(
            json.dumps({"file": rfp.filename, "title": rfp.title, "issuer": rfp.issuer, "split": rfp.split,
                        "questions": [g.as_dict() for g in golds]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        manifest.append({"file": rfp.filename, "format": rfp.fmt, "split": rfp.split, "layout": rfp.layout, "questions": len(golds),
                         "required": sum(g.required for g in golds)})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def load_gold(gold_dir: Path) -> dict[str, dict]:
    """Answer keys by file name."""
    out = {}
    for path in sorted(gold_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["file"]] = data
    return out
