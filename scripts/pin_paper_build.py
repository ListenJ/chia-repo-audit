#!/usr/bin/env python3
"""Pin the submitted PDF to the exact source it was rendered from.

Why this exists: the freshness gate it replaces compared mtimes (pdf > tex,
pdf > fig, render >= pdf). In a working tree those hold, so the gate looked
sound. In a fresh clone every file is written within milliseconds of the others
and the order is whatever git's checkout happens to do -- measured on a Windows
clone of the pushed branch, all four landed inside 7 ms and the PDF came out 1 ms
*older* than paper.tex, so the documented verification command returned 172/173
rc=1 for a reviewer while passing here. A gate whose verdict is decided by
sub-10ms write ordering is not a gate; it is a coin flip that happened to land
our way on the machine we wrote it on.

What it does instead: record the sha256 of the inputs the build consumed and the
outputs it produced. verify_paper_claims.py then asks only "are the bytes on disk
still that set", which is a question a checkout cannot change the answer to. Edit
paper.tex without recompiling and its hash stops matching the pin -- red, and red
for a reason the failure message states.

Run this after every recompile, before committing:

    pdflatex paper/paper.tex   (twice, or however the build is driven)
    python3 scripts/extract_pdf_text.py
    python3 scripts/pin_paper_build.py

It re-extracts the text layer itself and refuses to write the pin unless the
committed paper_text.txt is byte-identical to what the PDF actually contains, so
the pin cannot certify a render that belongs to an earlier PDF. Missing pypdf is
a hard failure: a gate that skips itself counts as a pass.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The submitted 4-page paper no longer includes the figure (it was cut to meet the page
# rule), so the figure is no longer an input of this build; listing it would make the pin
# overstate what the PDF was compiled from.
INPUTS = ("paper/paper.tex",)
OUTPUTS = ("paper/paper.pdf", "paper/paper_text.txt")


def sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def render_text_layer(pdf: Path) -> tuple[str, int]:
    """The text layer of `pdf` and its page count, read the way extract_pdf_text.py does."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "pypdf is required to pin the build: "
            "uv run --with pypdf python3 scripts/pin_paper_build.py\n"
            "Refusing to write a pin that was never checked against the PDF."
        )
    reader = PdfReader(str(pdf))
    return ("\n".join(page.extract_text() or "" for page in reader.pages),
            len(reader.pages))


def main() -> int:
    for rel in INPUTS + OUTPUTS:
        if not (REPO / rel).exists():
            print(f"missing {rel}", file=sys.stderr)
            return 1

    pdf = REPO / "paper/paper.pdf"
    extracted, pages = render_text_layer(pdf)
    committed = (REPO / "paper/paper_text.txt").read_text(encoding="utf-8")
    if extracted != committed:
        print(
            "paper/paper_text.txt is not the text layer of paper/paper.pdf.\n"
            "Run scripts/extract_pdf_text.py and retry. Not writing a pin that\n"
            f"would certify a stale render (extracted {len(extracted)} chars, "
            f"committed {len(committed)}).",
            file=sys.stderr,
        )
        return 2

    pin = {
        "pinned_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {rel: sha(rel) for rel in INPUTS},
        "outputs": {rel: sha(rel) for rel in OUTPUTS},
        "pages": pages,
        "regenerate": (
            "recompile paper/paper.tex, run scripts/extract_pdf_text.py, then "
            "scripts/pin_paper_build.py; verify_paper_claims.py compares the "
            f"{len(INPUTS) + len(OUTPUTS)} "
            "hashes below against the bytes on disk"
        ),
    }
    out = REPO / "paper/BUILD_PIN.json"
    # newline="\n" because .gitattributes pins paper/** as -text: the bytes have
    # to be the same on every checkout or the hashes this file records are not
    # the hashes a reviewer computes.
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(pin, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"pinned {len(INPUTS)} inputs + {len(OUTPUTS)} outputs -> "
          f"{out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
