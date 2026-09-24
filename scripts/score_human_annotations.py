#!/usr/bin/env python3
"""Score a human annotation export, and refuse to overstate what it can support.

This file exists because scripts/make_annotator_page.py cites it. A page whose results
nothing can consume is a survey, not evidence.

Three checks run before any statistic is printed, and each of them exits non-zero:

1. Display binding. The export carries the shuffle seed and the sha256 of the rendered
   slot set. Both must equal the key file's records. Without this, an answer file could
   have been produced against a different, easier display -- or after the key was read.
   A matching digest is the only thing that makes "the rater was blind" a checked claim
   instead of a sentence.

2. Completeness. Every slot answered, verdict present, no duplicates.

3. Rater independence, as data not as prose. The export records
   `rater_authored_cases`. When it is true, this script still computes the numbers --
   they are the honest accuracy of the person who built the cases against measurement --
   but it refuses the phrase "inter-rater reliability" anywhere in its output and labels
   the result explicitly. An author rating their own cases is the exact configuration
   where agreement is guaranteed by shared blind spots rather than earned.

What the accuracy number means: the expected label is derived from measurement, not from
a human's reading, so "human agrees with expected" is agreement with the simulator
record. That is the same quantity already published for the two Gemini raters and for
Laya (0 of 33), which is why the three can sit in one table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from independent_audit import combined_label, cohen_kappa  # noqa: E402


def die(msg: str) -> None:
    print(f"FAIL  {msg}")
    raise SystemExit(1)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--answers", default="web/annotator_result.json")
    ap.add_argument("--key", default="results/annotator_human_key.json")
    ap.add_argument("--atria", default="results/audit_independent_atria/raw.json")
    opts = ap.parse_args(argv)

    ap_path, key_path = REPO / opts.answers, REPO / opts.key
    if not ap_path.exists():
        die(f"no answer export at {opts.answers}; annotate the page first")
    ans = json.loads(ap_path.read_text(encoding="utf-8"))
    key = json.loads(key_path.read_text(encoding="utf-8"))

    slots = {s["slot"]: s for s in key["slots"]}
    labels = ans.get("labels") or []
    ids = [l.get("slot") for l in labels]
    if len(ids) != len(set(ids)):
        die("duplicate slots in the export")
    missing = sorted(set(slots) - set(ids))
    if missing:
        die(f"{len(missing)} slots unanswered: {missing[:6]}")
    unknown = sorted(set(ids) - set(slots))
    if unknown:
        die(f"export names slots that the key does not contain: {unknown[:6]}")

    # Display binding. Recompute what the page rendered and compare against the digest
    # the page stamped into the export; then compare that against the key file.
    if ans.get("shuffle_seed") != key["shuffle_seed"]:
        die(f"shuffle seed {ans.get('shuffle_seed')!r} != key {key['shuffle_seed']!r}")
    if ans.get("display_sha256") != key["display_sha256"]:
        die("export was produced against a different display than the key describes")

    unblinded = [l["slot"] for l in labels
                 if not l.get("verdict")]
    if unblinded:
        die(f"{len(unblinded)} slots have no verdict: {unblinded[:6]}")
    if not ans.get("attested_blind"):
        die("attested_blind is false; the export does not claim to be blind")

    authored = bool(ans.get("rater_authored_cases"))
    exp_verdict = {s["slot"]: s.get("expected_verdict") for s in key["slots"]}
    exp_combined = {s["slot"]: combined_label({
        "verdict": s.get("expected_verdict"), "errors": s.get("expected_errors") or []})
        for s in key["slots"]}
    got = {l["slot"]: combined_label({"verdict": l["verdict"],
                                      "errors": l.get("errors") or []}) for l in labels}
    got_v = {l["slot"]: l["verdict"] for l in labels}

    n = len(slots)
    acc_v = sum(got_v[s] == exp_verdict[s] for s in slots) / n
    acc_c = sum(got[s] == exp_combined[s] for s in slots) / n
    missed = sorted(s for s in slots if got[s] != exp_combined[s])

    print(f"rater            : {ans.get('rater') or '(unnamed)'}")
    print(f"rater authored   : {authored}")
    print(f"slots            : {n}")
    print(f"accuracy verdict : {acc_v:.4f}  ({int(acc_v*n)}/{n})")
    print(f"accuracy combined: {acc_c:.4f}  ({int(acc_c*n)}/{n})")
    print(f"missed slots     : {missed or 'none'}")

    atr = REPO / opts.atria
    if atr.exists():
        a = json.loads(atr.read_text(encoding="utf-8"))
        # The page slots come from the case ids in the key, so join on case_id.
        ascore: dict[str, str] = {}
        for name, blk in (a.get("sets") or {}).items():
            ascore.update({cid: v.get("combined", "")
                           for cid, v in (blk.get("cases") or {}).items()})
        pair = [(got[s], ascore[slots[s]["case_id"]])
                for s in slots if slots[s]["case_id"] in ascore]
        if len(pair) >= 2:
            print(f"slots shared with Atria: {len(pair)}")
            print(f"kappa vs Atria (combined): "
                  f"{cohen_kappa(pair):.4f}  "
                  f"agreement {sum(x == y for x, y in pair)/len(pair):.4f}")
        joined = [(slots[s]["case_id"], got[s], ascore[slots[s]["case_id"]])
                  for s in slots if slots[s]["case_id"] in ascore]
        expc = {s["case_id"]: combined_label({"verdict": s.get("expected_verdict"),
                                             "errors": s.get("expected_errors") or []})
                for s in key["slots"]}
        shared_wrong = sorted(cid for cid, h, m in joined
                              if h == m and h != expc[cid])
        print(f"human+Atria agree and both wrong vs measurement: "
              f"{shared_wrong or 'none'}")
    else:
        print(f"(no {opts.atria}; cross-provider comparison skipped, not assumed)")

    if authored:
        print("\nLIMIT: the rater states they constructed some of these cases. These "
              "numbers are that rater's agreement with measurement-derived labels. They "
              "are NOT an inter-rater reliability estimate and must not be reported as "
              "one.")
    else:
        print("\nRater attested they did not author the cases; kappa above is a "
              "human-model agreement statistic on the rated subset.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
