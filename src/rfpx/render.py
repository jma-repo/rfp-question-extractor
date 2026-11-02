"""Fill the Word template with the results. All layout lives in the template; this file only prepares the values."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate, Listing

from rfpx.models import TYPES, Finding
from rfpx.pipeline import DocResult
from rfpx.textutil import clean_cell

TYPE_LABEL = {"narrative": "Narrative", "yes_no": "Yes / No", "table": "Table", "upload": "Upload", "pricing": "Pricing"}
NO_NUMBER = "–"
REVIEW_INTRO = ("These items did not pass an automatic check, or came from a part of the file the model could not read reliably. "
                "They are listed, not dropped. Confirm each one against the source file before it goes into a response.")


def _row(f: Finding) -> dict[str, Any]:
    q = f.q
    source = [q.source_ref, *[f"also {ref}" for ref in f.also]]
    if f.similar_to:
        source.append(f"≈ similar to {f.similar_to}")
    # A zero-width space after "!" lets a long sheet reference break at the sheet name instead of in the middle of the row number.
    return {"no": clean_cell(q.id) or NO_NUMBER, "text": clean_cell(q.question_text), "type": TYPE_LABEL[q.type],
            "required": "Required" if q.required else "Optional", "constraints": clean_cell(q.constraints),
            "source": Listing(clean_cell("\n".join(source)).replace("!", "!​"))}


def _counts(findings: list[Finding]) -> dict[str, int]:
    out = {"questions": len(findings), "required": sum(f.q.required for f in findings)}
    out["optional"] = out["questions"] - out["required"]
    for kind in TYPES:
        out[kind] = sum(f.q.type == kind for f in findings)
    return out


def build_context(results: list[DocResult], extractor: str, generated: str | None = None) -> dict[str, Any]:
    summary, rfps, review = [], [], []
    for r in results:
        accepted = [f for f in r.findings if f.status == "accepted"]
        flagged = [f for f in r.findings if f.status != "accepted"]
        counts = _counts(accepted)
        summary.append({"rfp": clean_cell(r.name), "format": r.fmt.upper(), **counts, "review": len(flagged)})
        sections: dict[str, list[dict]] = {}
        for f in accepted:
            sections.setdefault(clean_cell(f.q.section) or "(no section)", []).append(_row(f))
        meta = f"{r.fmt.upper()}  |  {counts['questions']} questions ({counts['required']} required, {counts['optional']} optional)"
        if flagged:
            meta += f"  |  {len(flagged)} to review"
        if r.notes:
            meta += "  |  " + "; ".join(dict.fromkeys(r.notes))
        rfps.append({"name": clean_cell(r.name), "meta": clean_cell(meta), "empty": not accepted,
                     "sections": [{"title": title, "rows": rows} for title, rows in sections.items()]})
        review += [{"rfp": clean_cell(r.name), "section": clean_cell(f.q.section), "text": clean_cell(f.q.question_text),
                    "reason": clean_cell(f.reason), "source": clean_cell(f.q.source_ref)} for f in flagged]
    totals = {"rfps": len(results), "review": len(review)}
    for key in ("questions", "required", "optional", *TYPES):
        totals[key] = sum(s[key] for s in summary)
    return {
        "title": "RFP Question Register",
        "generated": generated or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "extractor": clean_cell(extractor),
        "totals": totals, "summary": summary, "rfps": rfps, "review": review,
        "summary_note": "Counts cover accepted questions only; items in the review list at the end are not included.",
        "review_intro": REVIEW_INTRO,
    }


def render_register(context: dict[str, Any], template: Path, out: Path) -> Path:
    doc = DocxTemplate(str(template))
    doc.render(context, autoescape=True)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out
