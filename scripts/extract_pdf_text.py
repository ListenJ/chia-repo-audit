#!/usr/bin/env python3
"""Extract the PDF's text layer to paper/paper_text.txt.

Why this is a committed artifact: the PDF is what reviewers read, but the claim
verifier works on LaTeX source. Without a text render there is no way to check that
what was *typeset* still says what the source says -- and a text layer can lose
characters (underscores in typewriter font did exactly that before this file existed),
which silently breaks searching and copy-paste for every identifier in the paper.

Fails loudly when pypdf is missing: a coverage gate that skips itself counts as a pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf is required: uv run --with pypdf python scripts/extract_pdf_text.py",
              file=sys.stderr)
        return 2
    pdf = REPO / "paper/paper.pdf"
    if not pdf.exists():
        print(f"missing {pdf}", file=sys.stderr)
        return 1
    reader = PdfReader(str(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    out = REPO / "paper/paper_text.txt"
    # newline="\n" because paper/** is pinned -text in .gitattributes and
    # BUILD_PIN.json hashes this file's bytes. Without it a Windows run writes
    # CRLF and a Linux run writes LF, and the same committed PDF pins to two
    # different hashes depending on who extracted it.
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(reader.pages)} pages, {len(text)} chars -> {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
