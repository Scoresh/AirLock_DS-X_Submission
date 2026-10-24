"""CLI: python -m rubric_parsing <rubric_file> [--out out.json]

Reads LLM settings from the environment (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY).
Prints the structured rubric JSON to stdout, or writes it with --out.
"""
from __future__ import annotations

import argparse
import json
import sys

from .llm import LLMConfigError, LLMRequestError
from .pandoc import PandocError
from .parser import parse_rubric_file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rubric_parsing", description=__doc__)
    ap.add_argument("rubric_file", help="path to the rubric (docx, pdf, html, md, ...)")
    ap.add_argument("--out", help="write JSON here instead of stdout")
    ap.add_argument("--indent", type=int, default=2, help="JSON indent (default 2)")
    args = ap.parse_args(argv)

    try:
        rubric = parse_rubric_file(args.rubric_file)
    except (FileNotFoundError, PandocError, LLMConfigError, LLMRequestError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(rubric.to_dict(), indent=args.indent, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
