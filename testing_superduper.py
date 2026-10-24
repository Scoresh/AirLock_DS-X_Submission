"""testing_superduper.py — interactive one-file test for the rubric_parsing pipeline.

Opens a native Windows file dialog, lets you pick one (or more) rubric files,
runs each through rubric_parsing (pandoc -> LLM -> validated JSON), prints the
resulting rubric JSON, and writes it next to the source as <name>.rubric.json.

Run from the repo root so `rubric_parsing` is importable:

    python testing_superduper.py

Requires the LLM settings in the environment (same as the package):
    LLM_BASE_URL   e.g. http://localhost:11434/v1
    LLM_MODEL      e.g. llama3.1
    LLM_API_KEY    bearer token (may be empty for local Ollama)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# make sure the repo root (this file's folder) is on sys.path for the import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rubric_parsing import parse_rubric_file  # noqa: E402
from rubric_parsing.llm import LLMConfigError, LLMRequestError  # noqa: E402
from rubric_parsing.pandoc import PandocError, to_markdown  # noqa: E402

# Windows consoles default to cp1252 and crash on characters like the bullet
# "▪" found in many rubrics. Switch stdout/stderr to UTF-8 where supported.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass


def safe_print(text: str = "", **kwargs) -> None:
    """print() that never raises on un-encodable characters."""
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(enc, "replace").decode(enc), **kwargs)


def pick_files() -> list[str]:
    """Open a Windows file-open dialog and return the chosen paths."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()          # hide the empty root window
    root.attributes("-topmost", True)  # bring the dialog to the front
    paths = filedialog.askopenfilenames(
        title="Select rubric file(s) to parse",
        filetypes=[
            ("Documents", "*.pdf *.docx *.doc *.odt *.rtf *.html *.htm *.md *.markdown *.txt *.tex *.epub"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return list(paths)


def process(path: str) -> int:
    """Parse one rubric file; print extracted text + JSON, write <name>.rubric.json."""
    safe_print(f"\n=== {path} ===")

    # Stage 1: extract raw text (pandoc / PyMuPDF). Print it so you can see
    # exactly what will be sent to the LLM.
    try:
        extracted = to_markdown(path)
    except FileNotFoundError as exc:
        safe_print(f"  file error: {exc}", file=sys.stderr)
        return 1
    except PandocError as exc:
        safe_print(f"  pandoc error: {exc}", file=sys.stderr)
        return 1

    safe_print("--- extracted text (sent to LLM) ---")
    safe_print(extracted)
    safe_print("--- end extracted text ---")

    # Stage 2: LLM extraction into structured JSON.
    try:
        rubric = parse_rubric_file(path)
    except LLMConfigError as exc:
        safe_print(f"  LLM config error: {exc}", file=sys.stderr)
        safe_print("  set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY and retry.", file=sys.stderr)
        return 1
    except (LLMRequestError, ValueError) as exc:
        safe_print(f"  parse error: {exc}", file=sys.stderr)
        return 1

    payload = rubric.to_dict()
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    safe_print("--- parsed rubric JSON ---")
    safe_print(text)

    out_path = Path(path).with_suffix(Path(path).suffix + ".rubric.json")
    out_path.write_text(text, encoding="utf-8")
    safe_print(f"  -> wrote {out_path}")
    safe_print(f"  -> {len(payload['rubric'])} criteria extracted")
    return 0


def main() -> int:
    files = pick_files()
    if not files:
        safe_print("no file selected; exiting.")
        return 0

    # Quick heads-up if the LLM env isn't configured (parsing needs it).
    if not os.getenv("LLM_BASE_URL") or not os.getenv("LLM_MODEL"):
        safe_print(
            "warning: LLM_BASE_URL / LLM_MODEL not set — parsing will fail.\n"
            "         configure them, e.g. for local Ollama:\n"
            "           set LLM_BASE_URL=http://localhost:11434/v1\n"
            "           set LLM_MODEL=llama3.1\n",
            file=sys.stderr,
        )

    failures = 0
    for path in files:
        failures += process(path)

    safe_print(f"\ndone: {len(files) - failures}/{len(files)} parsed successfully.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
