#!/usr/bin/env python3
"""Roll up the cross-provider rater and gate the artifact it published.

Two jobs, deliberately in one file. The first is the table the paper cites: per set, the
rater's accuracy against the recorded expectation on *both* axes (verdict, and verdict
plus error codes), plus agreement and Cohen's kappa against each published Gemini rater.
The second is the reason to trust that table.

Every number in the rollup is re-derived from the per-case records, and the stored score
block is compared against the re-derivation. That check exists because the first resumed
run published `combined_accuracy_vs_expected = 0.0` over 16 cases: the records had been
written before the field existed, so a missing field was read as a measured mismatch. 0.0
on a two-level axis has been the signature of a dead axis in this repository twice
already, and a rollup that only prints what the artifact says cannot tell "the rater
scored zero" from "no one scored".

Exit is non-zero if any check fails, including a probe artifact that is only half
answered, so a stalled run can never be reported as a completed one.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from atria_audit import (MODEL, backfill, declared,  # noqa: E402
                         gemini_labels)
from independent_audit import cohen_kappa               # noqa: E402

CHECKS: list[tuple[str, object, object]] = []


def check(what: str, want: object, got: object) -> bool:
    ok = want == got
    CHECKS.append((what, want, got))
    print(f"[{'ok ' if ok else 'BAD'}] {what}: {want!r}" + ("" if ok else f" != {got!r}"))
    return ok


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", default="results/audit_independent_atria/raw.json")
    ap.add_argument("--probe", default="results/rubric_precedence_probe/raw.json")
    ap.add_argument("--out", default="results/audit_independent_atria/rollup.json")
    opts = ap.parse_args(argv)

    art_path = REPO / opts.artifact
    if not art_path.exists():
        print(f"no rater artifact at {opts.artifact}: not run, not zero", file=sys.stderr)
        return 1
    art = json.loads(art_path.read_text(encoding="utf-8"))
    llm = declared("LLM_RESULTS")
    rows: dict[str, dict] = {}

    for name, blk in sorted((art.get("sets") or {}).items()):
        cases = blk.get("cases") or {}
        stored = blk.get("scores") or {}
        if not check(f"{name}: every record carries a 64-hex prompt digest",
                     0, sum(1 for v in cases.values()
                            if not re.fullmatch(r"[0-9a-f]{64}", str(v.get("prompt_sha256"))))):
            print(f"     {name}: a case without prompt_sha256 cannot be traced to a question")
        digests = [v.get("prompt_sha256") for v in cases.values()]
        check(f"{name}: no two cases share a prompt digest",
              len(digests), len(set(digests)))

        # The presence check reads the artifact as written, so an older record shape is
        # reported as missing data. Only then is the field re-derived, which is what makes
        # the accuracy re-derivation below meaningful.
        check(f"{name}: every record carries both labels to score from", 0,
              sum(1 for v in cases.values() if not all(
                  v.get(k) is not None for k in
                  ("verdict", "expected_verdict", "combined", "expected_combined"))))
        fixed = backfill(cases)
        if fixed:
            print(f"     {name}: re-derived {fixed} records' expected labels in memory "
                  "(the artifact on disk still needs the reconcile run)")
        n = len(cases)
        # Re-derive from the label strings, never from the stored booleans. The first
        # version of this file summed `matches_combined`, which is exactly the field the
        # resumed run had not written -- so it recomputed 0.0, agreed with the 0.0 it was
        # checking, and reported a passing gate over a number that measured nothing.
        # Labels are what the raters actually said; agreement is a function of them.
        v_ok = [i for i, v in sorted(cases.items())
                if v.get("verdict") and v["verdict"] == v.get("expected_verdict")]
        c_ok = [i for i, v in sorted(cases.items())
                if v.get("combined") and v["combined"] == v.get("expected_combined")]
        v_acc = round(len(v_ok) / n, 4) if n else None
        c_acc = round(len(c_ok) / n, 4) if n else None
        check(f"{name}: stored verdict accuracy equals the re-derivation",
              stored.get("verdict_accuracy_vs_expected"), v_acc)
        check(f"{name}: stored combined accuracy equals the re-derivation",
              stored.get("combined_accuracy_vs_expected"), c_acc)

        ours = {i: v.get("combined", "") for i, v in cases.items()}
        gem = gemini_labels(REPO / llm[name]) if name in llm else {}
        kappas: dict[str, float] = {}
        for gmodel, gl in sorted(gem.items()):
            shared = [i for i in ours if i in gl]
            if len(shared) < 2:
                check(f"{name}: >=2 cases shared with {gmodel}", ">=2", len(shared))
                continue
            pairs = [(ours[i], gl[i]) for i in shared]
            k = round(cohen_kappa(pairs), 4)
            a = round(sum(x == y for x, y in pairs) / len(pairs), 4)
            kappas[gmodel] = k
            check(f"{name}: stored kappa vs {gmodel} equals the re-derivation",
                  stored.get(f"kappa_vs_{gmodel}"), k)
            check(f"{name}: stored agreement vs {gmodel} equals the re-derivation",
                  stored.get(f"agreement_vs_{gmodel}"), a)
        rows[name] = {"n_cases": n, "verdict_accuracy": v_acc,
                      "combined_accuracy": c_acc, "kappa_vs_gemini": kappas,
                      "mismatched_cases": sorted(i for i in cases if i not in c_ok)}

    models = sorted({str(v.get("returned_model")) for b in (art.get("sets") or {}).values()
                     for v in (b.get("cases") or {}).values()})
    check("one model string answers every case", [MODEL], models)
    unparsed = sorted(f"{n}/{i}" for n, b in (art.get("sets") or {}).items()
                      for i, v in (b.get("cases") or {}).items() if not v.get("verdict"))
    check("contract_failures lists exactly the cases with no verdict",
          sorted(art.get("contract_failures") or []), unparsed)

    probe_path = REPO / opts.probe
    probe: dict = {}
    if probe_path.exists():
        pr = json.loads(probe_path.read_text(encoding="utf-8"))
        conds = pr.get("conditions") or {}
        # An empty artifact passes a "no case left unanswered" test written as a product
        # of ids x conditions, because 0 x 3 == 0. Assert the shape from both ends.
        check("probe: all three conditions started", 3, len(conds))
        check("probe: no condition is empty", 0, sum(1 for c in conds.values() if not c))
        check("probe: the same cases appear in every condition", 1,
              len({tuple(sorted(c or {})) for c in conds.values()}))
        ids = sorted({i for c in conds.values() for i in (c or {})})
        check("probe: the three escapes are present in condition A",
              ["sem-esc-01", "sem-esc-02", "sem-esc-03"],
              sorted(i for i in (conds.get("A") or {}) if i.startswith("sem-esc")))
        check("probe: no case left unanswered in any condition",
              len(ids) * 3, sum(len(c or {}) for c in conds.values()))
        check("probe: condition A reproduces the published escape labels",
              ["not_equivalent|E4"] * 3,
              [((conds.get("A") or {}).get(i) or {}).get("combined")
               for i in sorted(ids) if i.startswith("sem-esc")])
        esc = [i for i in ids if i.startswith("sem-esc")]
        ctl = [i for i in ids if not i.startswith("sem-esc")]

        def moved(cond):
            return sorted(i for i in ids
                          if ((conds.get(cond) or {}).get(i) or {}).get("combined")
                          != ((conds.get("A") or {}).get(i) or {}).get("combined"))

        strong = bool(esc) and (set(esc) <= set(moved("C"))) and not (set(ctl) & set(moved("C")))
        check("probe: stored strong_confirmation equals the re-derivation",
              (pr.get("verdict") or {}).get("strong_confirmation"), strong)
        probe = {"ids": ids, "moved_B": moved("B"), "moved_C": moved("C"),
                 "strong_confirmation": strong,
                 "labels": {c: {i: ((conds.get(c) or {}).get(i) or {}).get("combined")
                                for i in ids} for c in ("A", "B", "C")}}
    else:
        print(f"probe: {opts.probe} absent -- reported as not run, not as no effect")

    print("\n--- rollup ---")
    for name, r in rows.items():
        print(f"{name:10s} n={r['n_cases']:3d} verdict_acc={r['verdict_accuracy']} "
              f"combined_acc={r['combined_accuracy']} kappa={r['kappa_vs_gemini']}")
    bad = [c for c in CHECKS if c[1] != c[2]]
    out = {"checks": len(CHECKS), "failed": [b[0] for b in bad], "sets": rows,
           "probe": probe, "unparsed_cases": unparsed}
    (REPO / opts.out).write_bytes(
        (json.dumps(out, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"\n{len(CHECKS) - len(bad)}/{len(CHECKS)} checks ok; wrote {opts.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
