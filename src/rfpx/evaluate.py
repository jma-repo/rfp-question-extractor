"""Precision and recall against the answer keys, by verbatim match.

A prediction is a hit only when its words are the gold words (layout, typographic quotes and a final full stop aside).
A reworded or truncated answer is both a miss and a false positive; it is also counted as a near miss so the report can
say how much of the error is paraphrase rather than absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from rfpx.models import Finding
from rfpx.textutil import match_key, verbatim_key


@dataclass
class DocScore:
    file: str = ""
    format: str = ""
    split: str = ""
    gold: int = 0
    pred: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    review: int = 0
    tp_with_review: int = 0
    near_misses: int = 0
    type_ok: int = 0
    required_ok: int = 0
    id_ok: int = 0
    false_positives: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        return self.tp / self.pred if self.pred else 0.0

    @property
    def recall(self) -> float:
        return self.tp / self.gold if self.gold else 0.0

    @property
    def recall_with_review(self) -> float:
        return self.tp_with_review / self.gold if self.gold else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def _id(value: Any) -> str:
    return "" if value in (None, "") else str(value).strip().rstrip(".")


def _near(a: str, b: str) -> bool:
    """One text inside the other (a dropped lead-in, a truncation) or all but a character or two the same."""
    ka, kb = match_key(a), match_key(b)
    if not ka or not kb:
        return False
    short, long_ = sorted((ka, kb), key=len)
    return (short in long_ and len(short) >= 20) or SequenceMatcher(None, ka, kb).ratio() >= 0.9


def score_document(found: list[Finding], gold: list[dict]) -> DocScore:
    gold_by_key: dict[str, dict] = {}
    for g in gold:
        gold_by_key.setdefault(verbatim_key(g["question_text"]), g)
    accepted: dict[str, Finding] = {}
    review: dict[str, Finding] = {}
    for f in found:
        bucket = accepted if f.status == "accepted" else review
        bucket.setdefault(verbatim_key(f.q.question_text), f)

    score = DocScore(gold=len(gold_by_key), pred=len(accepted), review=len(review))
    hits = set(gold_by_key) & set(accepted)
    score.tp, score.fp, score.fn = len(hits), len(set(accepted) - set(gold_by_key)), len(set(gold_by_key) - hits)
    score.tp_with_review = len(set(gold_by_key) & (set(accepted) | set(review)))
    for key in hits:
        g, f = gold_by_key[key], accepted[key].q
        score.type_ok += f.type == g["type"]
        score.required_ok += f.required == g["required"]
        score.id_ok += _id(f.id) == _id(g["id"])
    score.false_positives = [accepted[k].q.question_text for k in accepted if k not in gold_by_key]
    score.misses = [gold_by_key[k]["question_text"] for k in gold_by_key if k not in hits]
    predicted_texts = [f.q.question_text for f in accepted.values()]
    score.near_misses = sum(any(_near(m, p) for p in predicted_texts) for m in score.misses)
    return score


def evaluate_extractor(extractor, data_dir: Path, split: str = "test", max_chars: int = 2400, near: float = 0.75,
                       only: list[str] | None = None, progress=None) -> dict[str, Any]:
    """Run an extractor over the synthetic RFPs and score it against their answer keys."""
    from rfpx.ingest import read_document
    from rfpx.pipeline import process_document
    from rfpx.synth.generate import load_gold

    scores: list[DocScore] = []
    seconds: dict[str, float] = {}
    notes: dict[str, list[str]] = {}
    for name, key in load_gold(Path(data_dir) / "gold").items():
        if (split != "all" and key["split"] != split) or (only and name not in only):
            continue
        doc = read_document(Path(data_dir) / "rfps" / name)
        result = process_document(doc, extractor, max_chars, near)
        score = score_document(result.findings, key["questions"])
        score.file, score.format, score.split = name, doc.fmt, key["split"]
        scores.append(score)
        seconds[name], notes[name] = result.seconds, sorted(set(result.notes))
        if progress:
            progress(f"  {name:46s} P={score.precision:.2f} R={score.recall:.2f} (gold {score.gold}, accepted {score.pred}, "
                     f"review {score.review}) {result.seconds:.1f}s")
    report = aggregate(scores)
    for entry in report["documents"]:
        entry["seconds"], entry["notes"] = seconds[entry["file"]], notes[entry["file"]]
    report["summary"]["seconds"] = round(sum(seconds.values()), 1)
    return report


def format_report(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [f"precision {s['precision']:.3f}  recall {s['recall']:.3f}  F1 {s['f1']:.3f}   "
             f"(gold {s['gold']}, accepted {s['pred']}, correct {s['tp']}, in review {s['review_items']})",
             f"recall counting the review list {s['recall_with_review']:.3f};  near misses {s['near_misses']};  "
             f"type {s['type_accuracy']:.3f}  required {s['required_accuracy']:.3f}  id {s['id_accuracy']:.3f}"]
    for fmt, r in report["by_format"].items():
        lines.append(f"  {fmt:5s} precision {r['precision']:.3f}  recall {r['recall']:.3f}  (gold {r['gold']}, documents {r['documents']})")
    return "\n".join(lines)


def _ratio(num: float, den: float) -> float:
    return round(num / den, 4) if den else 0.0


def _roll(scores: list[DocScore]) -> dict[str, Any]:
    tp, pred, gold = sum(s.tp for s in scores), sum(s.pred for s in scores), sum(s.gold for s in scores)
    precision, recall = _ratio(tp, pred), _ratio(tp, gold)
    macro_p = sum(s.precision for s in scores) / len(scores) if scores else 0.0
    macro_r = sum(s.recall for s in scores) / len(scores) if scores else 0.0
    return {
        "documents": len(scores), "gold": gold, "pred": pred, "tp": tp, "fp": sum(s.fp for s in scores), "fn": sum(s.fn for s in scores),
        "precision": precision, "recall": recall, "f1": _ratio(2 * precision * recall, precision + recall),
        "macro_precision": round(macro_p, 4), "macro_recall": round(macro_r, 4),
        "recall_with_review": _ratio(sum(s.tp_with_review for s in scores), gold), "review_items": sum(s.review for s in scores),
        "near_misses": sum(s.near_misses for s in scores),
        "type_accuracy": _ratio(sum(s.type_ok for s in scores), tp), "required_accuracy": _ratio(sum(s.required_ok for s in scores), tp),
        "id_accuracy": _ratio(sum(s.id_ok for s in scores), tp),
    }


def aggregate(scores: list[DocScore]) -> dict[str, Any]:
    formats = sorted({s.format for s in scores})
    return {
        "summary": _roll(scores),
        "by_format": {fmt: _roll([s for s in scores if s.format == fmt]) for fmt in formats},
        "documents": [{
            "file": s.file, "format": s.format, "split": s.split, "gold": s.gold, "pred": s.pred, "tp": s.tp,
            "precision": round(s.precision, 4), "recall": round(s.recall, 4), "review": s.review, "near_misses": s.near_misses,
            "false_positives": s.false_positives[:6], "misses": s.misses[:6],
        } for s in scores],
    }
