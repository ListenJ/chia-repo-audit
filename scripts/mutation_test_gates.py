#!/usr/bin/env python3
"""Mutation-test the gates that read the delivery and rater evidence files.

Why this is a tracked script and not a scratch file: docs/operations-log.md §32.8
publishes a table saying "six mutations, all six bite". A claim is only worth
what its evidence is, and evidence under .tmp/ is excluded from both the
referenced-path gate and the coverage census -- a reviewer could neither re-run
it nor see that it existed. So the harness lives here. Run it with
`python3 scripts/mutation_test_gates.py`; exit 0 means every mutation bit.

Scope, stated plainly: the first six mutations cover the three checks over the fresh-clone
record, added in the 187-claim round; the last four cover the cross-provider rater layer
added in the 212-claim round. The ~10 mutations logged in §32.6 were run ad-hoc against the
build pin, the retained-PDF block and the README current-state block and are not reproduced
here.

Two things this harness insists on, both learned the hard way:

1. Every mutation must actually change the bytes. The first pass reported
   "eol claim downgraded to crlf -> rc=0", which read as "that arm of the check
   does not bite". It did bite; the replacement string simply never matched, so
   the mutation was a no-op. Without `mutated != original` asserted, a broken
   test is indistinguishable from a broken gate.
2. rc=1 with zero named FAILs is a harness failure, not a success. A crash still
   refuses to pass, but it hands the reviewer a traceback instead of the name of
   the claim that was wrong. Both real defects this harness found were of that
   shape: JSONDecodeError when `cloned_head` named a commit that does not exist
   (`git show` emits nothing), and KeyError when an eol row was missing.

Deleting the record file entirely is deliberately not one of the mutations. It
also exits 1 with no FAIL line, but the resulting FileNotFoundError names the
missing file, which is the one piece of information a reviewer would need; that
is a different situation from a bare JSONDecodeError, and `load_json` is shared
by every evidence file in the verifier, so changing it is not this harness's
call to make.

Exit code: 0 only if every mutation applied AND produced at least one named FAIL
AND produced no traceback AND the file was restored byte-for-byte.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CLONE = "results/fresh_clone_verification_2026-09-24.json"
RATER = "results/audit_independent_atria/raw.json"

# (label, artifact mutated, mutation). Two artifacts because the checks grew into a second
# evidence file: the clone record covers the delivery chain, the rater record covers the
# annotation layer. A harness pinned to one file cannot show that the *other* layer's
# gates can fail, which is the whole point of running it.
MUTATIONS = [
    ("cloned_head invented", CLONE, lambda d: d.__setitem__("cloned_head", "0" * 40)),
    ("pin_at_clone tex digest retyped", CLONE,
     lambda d: d["pin_at_clone"]["inputs"].__setitem__("paper/paper.tex", "a" * 64)),
    ("core_autocrlf claimed false", CLONE, lambda d: d.__setitem__("core_autocrlf", "false")),
    ("eol rows claim crlf", CLONE, lambda d: d.__setitem__("eol_table_paper", [
        ln.replace("w/lf", "w/crlf") for ln in d["eol_table_paper"]])),
    ("one eol row dropped", CLONE,
     lambda d: d.__setitem__("eol_table_paper", d["eol_table_paper"][:-1])),
    ("attr/-text downgraded to text=auto", CLONE, lambda d: d.__setitem__("eol_table_paper", [
        ln.replace("attr/-text", "attr/text=auto") for ln in d["eol_table_paper"]])),
    # ---- the cross-provider rater layer -------------------------------
    ("escape label rewritten as if the rater had not made the shared error", RATER,
     lambda d: d["sets"]["measured6"]["cases"]["sem-esc-01"].update(
         {"verdict": "equivalent", "errors": [], "combined": "equivalent|"})),
    ("one case's prompt digest blanked", RATER,
     lambda d: d["sets"]["spec10"]["cases"]["av-001"].__setitem__("prompt_sha256", "")),
    ("a second model string appears in the records", RATER,
     lambda d: d["sets"]["spec10"]["cases"]["av-002"].__setitem__(
         "returned_model", "Some-Other-Model")),
    ("stored accuracy retyped back to the false zero", RATER,
     lambda d: d["sets"]["spec10"]["scores"].__setitem__(
         "combined_accuracy_vs_expected", 0.0)),
]


def run_verifier() -> tuple[int, list[str], list[str]]:
    proc = subprocess.run([sys.executable, str(REPO / "scripts/verify_paper_claims.py")],
                          cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = out.splitlines()
    fails = [ln[5:].strip() for ln in lines if ln.startswith("FAIL")]
    crashes = [ln.strip() for ln in lines if ln.startswith("Traceback") or "Error:" in ln]
    return proc.returncode, fails, crashes


def main() -> int:
    targets = sorted({rel for _, rel, _ in MUTATIONS})
    originals = {rel: (REPO / rel).read_text(encoding="utf-8") for rel in targets}
    problems: list[str] = []
    try:
        rc, _, _ = run_verifier()
        print(f"baseline: rc={rc}")
        if rc != 0:
            problems.append("baseline is already red; fix that before mutation testing")
        for name, rel, mutate in MUTATIONS:
            doc = json.loads(originals[rel])
            mutate(doc)
            mutated = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
            if mutated == originals[rel]:
                problems.append(f"{name}: mutation DID NOT APPLY (no-op test)")
                print(f"[{name}] NO-OP")
                continue
            (REPO / rel).write_text(mutated, encoding="utf-8", newline="\n")
            rc, fails, crashes = run_verifier()
            print(f"[{name}] rc={rc} nfail={len(fails)} crashes={len(crashes)}")
            for f in fails:
                print(f"      FAIL  {f[:110]}")
            if rc == 0:
                problems.append(f"{name}: gate did not bite (rc=0)")
            if not fails:
                problems.append(f"{name}: rc={rc} but no named FAIL -- verifier crashed")
            if crashes:
                problems.append(f"{name}: traceback in output: {crashes[-1][:90]}")
    finally:
        for rel, text in originals.items():
            (REPO / rel).write_text(text, encoding="utf-8", newline="\n")

    rc, fails, _ = run_verifier()
    print(f"restored: rc={rc} nfail={len(fails)}")
    # Byte comparison only. A red baseline is already reported as its own problem;
    # folding "verifier is red" in here made the restore check fire for reasons
    # that had nothing to do with restoration, which is how a harness starts
    # crying wolf and gets ignored.
    for rel, text in originals.items():
        if (REPO / rel).read_text(encoding="utf-8") != text:
            problems.append(f"{rel} was not restored byte-for-byte")
    for p in problems:
        print(f"PROBLEM  {p}")
    print(f"{len(MUTATIONS)} mutations, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
