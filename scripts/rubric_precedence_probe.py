#!/usr/bin/env python3
"""Causal test of the rubric finding, not another correlation.

Section 38.3 established by inspection that E0 ("no behavioural difference") and E4
("the candidate adds something the reference lacks") are both literally true for a
nullity escape, and that the rubric states no precedence. Three raters from two providers
resolved it the same way. That is still consistent with "the models are simply bad at
this", because the payload they were shown contains no measurement at all: the visible
keys are id/design/reference, and `evidence` -- which holds the cycle counts -- is
excluded. The raters were asked a behavioural question and given only source, so answering
from source is the only move available to them.

This script turns that into a testable prediction by changing exactly one thing at a
time and re-asking:

  A  original contract                         -- baseline, must reproduce section 38.2
  B  + the two cycle counts, same rubric       -- does the rater use measurement when
                                                  it is merely present?
  C  + cycle counts + an explicit precedence   -- does an unspecified tie-break explain
     rule ("behaviour governs E0/E4")             the three identical answers?

Prediction if the rubric/visibility account is right: A stays not_equivalent|E4 on all
three escapes, B moves some, C moves all three to equivalent with empty errors -- and the
three NON-escape cases stay put in every condition, which is what makes this a test
rather than a nudge. If C flips the controls too, the rule is under-constrained and the
finding is weaker than section 38.3 claims.

The artifact records its own prompt digest and a protocol_deviation note, because a
payload with extra keys is not comparable to the published labels and must not be pooled
with them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from independent_audit import (RUBRIC, annotator_payload, combined_label,  # noqa: E402
                               VISIBLE_KEYS)

BASE = "https://api.atria-asi.ai"
MODEL = "Atria-Dawn-Preview"
PROXY = "http://127.0.0.1:7897"

PRECEDENCE = """
PRECEDENCE (new in this probe): the verdict is decided on the BEHAVIOURAL axis. If the
two runs are reported to take the same number of cycles, the pair is equivalent and
errors must be empty, even when the candidate's source adds or removes code. Source-level
additions license E3/E4 only when the reported behaviour also differs.
"""


def payload(case: dict, cond: str) -> dict:
    vis = {k: case[k] for k in VISIBLE_KEYS if k in case}
    if cond == "A":
        return vis
    ev = case.get("evidence") or {}
    vis = dict(vis)
    vis["reported_cycles"] = {"candidate": ev.get("design_cycles"),
                              "reference": ev.get("reference_cycles")}
    return vis


def ask(prompt: str, key: str) -> tuple[str, dict]:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"https": PROXY, "http": PROXY}))
    body = json.dumps({"model": MODEL,
                       "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0, "max_tokens": 4096}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with opener.open(req, timeout=300) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    ch = data.get("choices") or []
    if not ch:
        raise RuntimeError(f"no choices: {str(data)[:200]}")
    return (ch[0].get("message") or {}).get("content") or "", data


def parse(text: str) -> dict:
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:  # noqa: BLE001
        return {}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results/rubric_precedence_probe")
    args = ap.parse_args(argv)
    key = (Path.home() / ".config/atria/token").read_text(encoding="utf-8").strip()

    ids = ["sem-esc-01", "sem-esc-02", "sem-esc-03",   # predicted to move under C
           "sem-01", "sem-02", "sem-03"]               # predicted to stay put
    cases = {c["id"]: c for c in
             (json.loads(p.read_text(encoding="utf-8"))
              for p in sorted((REPO / "chia_loop/semantic").glob("*.json")))}
    out: dict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_deviation": "conditions B and C show the rater reported cycle counts, "
                              "which the published protocol never exposes; these labels "
                              "are NOT comparable with the published kappa and are not "
                              "merged into it",
        "requested_model": MODEL, "temperature": 0.0, "conditions": {},
    }
    (REPO / args.out).mkdir(parents=True, exist_ok=True)
    art = REPO / args.out / "raw.json"

    for cond, rub in (("A", RUBRIC), ("B", RUBRIC), ("C", RUBRIC + PRECEDENCE)):
        res = {}
        for cid in ids:
            case = cases[cid]
            prompt = rub + "\nCase to audit:\n" + json.dumps(
                payload(case, cond), indent=2)
            try:
                text, data = ask(prompt, key)
            except Exception as e:  # noqa: BLE001
                res[cid] = {"error": f"{type(e).__name__}: {e}"}
                art.write_bytes((json.dumps(out, indent=2) + "\n").encode("utf-8"))
                continue
            p = parse(text)
            res[cid] = {"combined": combined_label(p) if p else "",
                        "verdict": p.get("verdict"), "errors": p.get("errors"),
                        "raw_reply": text[:1200],
                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                        "returned_model": data.get("model"),
                        "expected": combined_label({
                            "verdict": case.get("expected_verdict"),
                            "errors": case.get("expected_errors") or []})}
            print(f"{cond} {cid:11s} {res[cid]['combined']:22s} "
                  f"expected={res[cid]['expected']:22s}", flush=True)
            art.write_bytes((json.dumps(out, indent=2) + "\n").encode("utf-8"))
        out["conditions"][cond] = res

    esc = [c for c in ids if c.startswith("sem-esc")]
    ctl = [c for c in ids if not c.startswith("sem-esc")]
    def moved(cond, group):
        return [c for c in group
                if (out["conditions"][cond].get(c) or {}).get("combined")
                != (out["conditions"]["A"].get(c) or {}).get("combined")]
    print("\n--- prediction check ---")
    for cond in ("B", "C"):
        print(f"cond {cond}: escapes moved {moved(cond, esc)}  "
              f"controls moved {moved(cond, ctl)}")
    c_esc_moved = set(moved("C", esc))
    c_ctl_moved = set(moved("C", ctl))
    verdict_strong = (set(esc) <= c_esc_moved) and not c_ctl_moved
    print(f"\nC moves all three escapes and no control: {verdict_strong}")
    out["verdict"] = {"C_moved_all_escapes": sorted(c_esc_moved),
                      "C_moved_controls": sorted(c_ctl_moved),
                      "strong_confirmation": verdict_strong}
    art.write_bytes((json.dumps(out, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {args.out}/raw.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
