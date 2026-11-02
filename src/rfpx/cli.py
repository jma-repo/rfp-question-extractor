"""Command line: `rfpx run`, `rfpx eval`, `rfpx samples`, `rfpx template`, `rfpx llm-status`."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rfpx.config import Settings, settings


def _extractor(s: Settings, args: argparse.Namespace):
    if args.extractor == "rules":
        from rfpx.baseline import RulesExtractor

        return RulesExtractor()
    from rfpx.llm import LocalLLM
    from rfpx.llm_extract import HybridExtractor, LlmExtractor

    options = s.llm
    if getattr(args, "recheck", False):
        options["recheck"] = True
    if getattr(args, "no_json_schema", False):
        options["json_schema"] = "off"
    llm = LocalLLM(args.base_url or options["base_url"], model=args.model, timeout=float(options["timeout_s"]))
    model = LlmExtractor(llm, **{k: options[k] for k in ("temperature", "max_tokens", "retries", "recheck", "json_schema")})
    return HybridExtractor(model) if args.extractor == "hybrid" else model


def _run(s: Settings, args: argparse.Namespace) -> int:
    from rfpx.pipeline import list_inputs, run_directory
    from rfpx.render import build_context, render_register

    files = list_inputs(Path(args.input))
    if not files:
        print(f"No .docx, .pdf or .xlsx files found in {args.input}", file=sys.stderr)
        return 2
    extractor = _extractor(s, args)
    started = time.time()
    results = run_directory(Path(args.input), extractor, args.max_chars or s.max_chars, s.near_duplicate, not args.no_section_gate)
    template = Path(args.template) if args.template else s.path("template")
    out = render_register(build_context(results, extractor.label), template, Path(args.output))
    questions = sum(f.status == "accepted" for r in results for f in r.findings)
    review = sum(f.status != "accepted" for r in results for f in r.findings)
    print(f"{len(results)} file(s), {questions} questions, {review} to review -> {out}  ({time.time() - started:.1f}s)")
    for r in results:
        accepted = sum(f.status == "accepted" for f in r.findings)
        print(f"  {r.name}: {accepted} questions, {sum(f.status != 'accepted' for f in r.findings)} to review, "
              f"{r.chunks} chunk(s), {r.stats['merged_duplicates']} duplicate(s) merged, {r.seconds}s")
        for note in dict.fromkeys(r.notes):
            print(f"    note: {note}")
    return 0


def _eval(s: Settings, args: argparse.Namespace) -> int:
    from rfpx.evaluate import evaluate_extractor, format_report

    extractor = _extractor(s, args)
    data = Path(args.data) if args.data else s.path("synthetic")
    report = evaluate_extractor(extractor, data, args.split, args.max_chars or s.max_chars, s.near_duplicate,
                                only=args.only, progress=lambda m: print(m, flush=True), gate=not args.no_section_gate)
    report["settings"] = {"extractor": extractor.name, "label": extractor.label, "split": args.split, "max_chars": args.max_chars or s.max_chars,
                          "section_gate": not args.no_section_gate,
                          **({"model": getattr(extractor, "model_name", None), "recheck": getattr(extractor, "recheck", None)}
                             if args.extractor != "rules" else {})}
    print(format_report(report))
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"written to {target}")
    return 0


def _samples(s: Settings, args: argparse.Namespace) -> int:
    from rfpx.synth.generate import run

    out = Path(args.out) if args.out else s.path("synthetic")
    for row in run(out):
        print(f"  {row['file']:46s} {row['split']:5s} {row['questions']:3d} questions")
    print(f"written to {out}")
    return 0


def _template(s: Settings, args: argparse.Namespace) -> int:
    from rfpx.template import build_template

    target = Path(args.out) if args.out else s.path("template")
    build_template(target)
    print(f"template written to {target}")
    return 0


def _llm_status(s: Settings, args: argparse.Namespace) -> int:
    from rfpx.llm import LocalLLM

    llm = LocalLLM(args.base_url or s.llm["base_url"], model=args.model)
    print(json.dumps(llm.status(), indent=2))
    return 0


def _add_llm_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", help="chat model id (default: LLM_CHAT_MODEL, else qwen2.5-3b-instruct if loaded)")
    p.add_argument("--base-url", help="local model server (must be on this machine)")
    p.add_argument("--recheck", action="store_true", help="second pass per chunk: ask the model what it missed")
    p.add_argument("--no-json-schema", action="store_true", help="do not send response_format; rely on the prompt and the retry")
    p.add_argument("--no-section-gate", action="store_true",
                   help="accept items found under Background / Definitions / Instructions headings instead of holding them for review")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rfpx", description="RFP question extractor")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="read a folder (or one file) of RFPs and write the Word register")
    run.add_argument("input", help="folder with .docx, .pdf and .xlsx files, or a single file")
    run.add_argument("-o", "--output", default="out/register.docx")
    run.add_argument("--extractor", choices=["rules", "llm", "hybrid"], default="rules")
    run.add_argument("--template", help="Word template (default: templates/question_register.docx)")
    run.add_argument("--max-chars", type=int, help="chunk size in characters")
    _add_llm_options(run)

    ev = sub.add_parser("eval", help="precision and recall against the answer keys of the synthetic RFPs")
    ev.add_argument("--extractor", choices=["rules", "llm", "hybrid"], default="rules")
    ev.add_argument("--split", choices=["dev", "test", "all"], default="test")
    ev.add_argument("--data", help="folder with rfps/ and gold/ (default: data/synthetic)")
    ev.add_argument("--only", nargs="*", help="file names to include")
    ev.add_argument("--out", help="write the full report as JSON")
    ev.add_argument("--max-chars", type=int)
    _add_llm_options(ev)

    samples = sub.add_parser("samples", help="regenerate the synthetic RFPs and their answer keys")
    samples.add_argument("--out")
    template = sub.add_parser("template", help="rewrite the Word template")
    template.add_argument("--out")
    status = sub.add_parser("llm-status", help="is the local model server up, and which model would be used")
    status.add_argument("--model")
    status.add_argument("--base-url")

    args = parser.parse_args(argv)
    handlers = {"run": _run, "eval": _eval, "samples": _samples, "template": _template, "llm-status": _llm_status}
    return handlers[args.command](settings(), args)


if __name__ == "__main__":
    sys.exit(main())
