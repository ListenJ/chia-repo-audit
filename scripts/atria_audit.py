#!/usr/bin/env python3
"""Label the registered audit sets with a cross-provider model and score it honestly.

Why this exists. The paper's own description of the annotation layer is that it is
"scored by same-provider models": both raters behind every published kappa are Google
models, and on the shared cases they agree perfectly
(`llm_vs_llm_kappa_on_laya_shared` = 1.0 in results/substrate_probe_laya.json). A
kappa between two raters from one provider cannot separate "the task is easy" from
"the two raters fail alike". This script puts a second, unrelated provider behind the
same contract, so the agreement statistic has a witness that does not share its
training lineage.

What this deliberately does NOT do. It does not merge into the published kappa. The
existing numbers are a two-rater statistic over a specific pair; a three-rater or
cross-provider number is a different quantity and is written to its own file. Pooling
them silently is how a metric stops denoting the thing its name claims.

Token handling: read from ~/.config/atria/token at run time. Never embedded in this
file, never echoed, never written into the result artifact. The artifact records the
model string the service returned, not just the name we asked for, because provider
aliases move and a pinned alias is not a pinned model.

Every case is scored three ways, and all three are reported:
  accuracy vs the measurement-derived expected label  -- the number that matters
  kappa vs each Gemini rater                          -- the independence question
  the escape cases specifically                       -- where the shared blind spot was
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from independent_audit import (annotator_payload, cohen_kappa,  # noqa: E402
                               combined_label, RUBRIC)

BASE = "https://api.atria-asi.ai"
MODEL = "Atria-Dawn-Preview"
TOKEN_FILE = Path.home() / ".config" / "atria" / "token"
PROXY = "http://127.0.0.1:7897"


def declared(mapping: str) -> dict:
    """Read SETS or LLM_RESULTS out of substrate_probe.py without importing it.

    That module imports torch at module scope, so importing it here would make this
    script unrunnable on any host without the checkpoint. Parsing its AST keeps one
    owner for "which files are which case set" while still allowing a runtime
    cross-check; a silently diverging copy would let the human and the model answer
    different sets and the scorer compare them anyway.
    """
    src = (REPO / "scripts/substrate_probe.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == mapping for t in node.targets):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(v, ast.List):
                    out[k.value] = [ast.literal_eval(getattr(e, "right", e))
                                    for e in v.elts]
                else:
                    out[k.value] = ast.literal_eval(getattr(v, "right", v))
            return out
    raise SystemExit(f"{mapping} not found in substrate_probe.py; refusing to guess")


def load_cases(dirs: list[str]) -> list[dict]:
    out = []
    for d in dirs:
        for p in sorted((REPO / d).glob("*.json")):
            if p.name == "answer-key.json":
                continue
            rec = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(rec, dict) and "id" in rec:
                out.append(rec)
    return out


def call(prompt: str, key: str, retries: int = 3, pause: float = 3.0) -> tuple[str, dict]:
    handler = urllib.request.ProxyHandler({}) if _direct() else \
        urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
    opener = urllib.request.build_opener(handler)
    body = json.dumps({"model": MODEL,
                       "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0, "max_tokens": 4096}).encode()
    last = ""
    for attempt in range(retries):
        req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
        try:
            with opener.open(req, timeout=240) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:160]}"
        except Exception as e:  # noqa: BLE001 - a transport failure is a result, not a crash
            last = f"{type(e).__name__}: {e}"
        else:
            ch = data.get("choices") or []
            if ch:
                return ((ch[0].get("message") or {}).get("content") or ""), data
            last = f"no choices: {str(data)[:160]}"
        time.sleep(pause * (attempt + 1))
    raise RuntimeError(last)


def _direct() -> bool:
    return Path("/root/.no-proxy").exists()


def parse(text: str) -> dict:
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:  # noqa: BLE001
        return {}


def gemini_labels(path: Path) -> dict[str, dict[str, str]]:
    """Rater -> case id -> combined label, from one of the published Gemini result files.

    Shape is one row per case: {id, source, expected_verdict, expected_errors,
    labels:[{model, prompt_sha256, verdict, errors, ...}]}. The rater key is *inside* the
    case, not at the top level, so a single flat pass over the file silently yields zero
    shared cases and reports no kappa at all -- which reads like "not computed", not like
    "wrong code". Shared with the rollup gate so the two cannot drift apart.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit(f"{path}: expected a list of case rows")
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        rid = row.get("id")
        for lab in row.get("labels") or []:
            if rid and isinstance(lab, dict) and lab.get("model"):
                out.setdefault(lab["model"], {})[rid] = combined_label(lab)
    return out


def backfill(prev: dict) -> int:
    """Re-derive stored per-case fields that a later scoring change introduced.

    ``--resume`` loads records written by an earlier version of this file, which stored
    ``matches_expected`` but neither ``expected_combined`` nor ``matches_combined``.
    Reading an absent field as false turns *missing data* into a *measured mismatch*: the
    first resumed run published ``combined_accuracy_vs_expected = 0.0`` over 16 cases for
    exactly that reason, and 0.0 on a two-level axis is the shape this repository has
    already been burned by twice. The expected label is a pure function of fields that
    were always stored, so it is recomputed here rather than guessed at.
    """
    n = 0
    for rec in prev.values():
        if not isinstance(rec, dict):
            continue
        exp_c = combined_label({"verdict": rec.get("expected_verdict"),
                                "errors": rec.get("expected_errors") or []})
        if rec.get("expected_combined") != exp_c:
            rec["expected_combined"] = exp_c
            n += 1
        rec["matches_expected"] = (bool(rec.get("verdict"))
                                   and rec["verdict"] == rec.get("expected_verdict"))
        rec["matches_combined"] = (bool(rec.get("combined"))
                                   and rec["combined"] == exp_c)
    return n


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sets", nargs="*", default=["measured6", "spec10", "fact36"])
    ap.add_argument("--out", default="results/audit_independent_atria")
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N cases")
    ap.add_argument("--resume", action="store_true",
                    help="keep already-answered cases in the artifact and ask only the rest")
    ap.add_argument("--reask-unparsed", action="store_true",
                    help="with --resume, drop records whose reply could not be parsed "
                         "and ask those cases again (the only way to get their raw text)")
    opts = ap.parse_args(argv)

    if not TOKEN_FILE.exists():
        raise SystemExit(f"no token at {TOKEN_FILE}; refusing to run without a rater")
    key = TOKEN_FILE.read_text(encoding="utf-8").strip()

    sets = declared("SETS")
    llm = declared("LLM_RESULTS")
    want = sorted(sets) if opts.sets == ["all"] else opts.sets
    out_dir = REPO / opts.out
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / "raw.json"
    report: dict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "requested_model": MODEL, "endpoint": BASE,
        "temperature": 0.0,
        "note": "cross-provider rater; NOT merged into the published same-provider kappa",
        "sets": {},
    }
    done_before = 0
    if artifact.exists() and opts.resume:
        # Reconcile against what already landed rather than restarting: a 52-call run
        # over a reasoning model is long enough that the second attempt should be able
        # to pick up the first, and re-asking is not free.
        report = json.loads(artifact.read_text(encoding="utf-8"))
        done_before = sum(len(b.get("cases") or {}) for b in report["sets"].values())
        fixed = sum(backfill(b.get("cases") or {}) for b in report["sets"].values())
        print(f"resuming: {done_before} cases already answered, "
              f"{fixed} stored fields re-derived")
        if opts.reask_unparsed:
            kept = out_dir / "unparsed_replies.json"
            archive = (json.loads(kept.read_text(encoding="utf-8"))
                       if kept.exists() else {})
            for name, blk in report["sets"].items():
                cs = blk.get("cases") or {}
                bad = [i for i, rec in cs.items()
                       if isinstance(rec, dict) and not rec.get("verdict")]
                for i in bad:
                    # The dropped record is evidence: same prompt digest, and whether the
                    # retry parses is the temperature-0 stability measurement. Deleting it
                    # would replace one data point with another and lose the pair.
                    archive[f"{name}/{i}"] = cs[i]
                    del cs[i]
                if bad:
                    print(f"re-asking {name}: {bad}")
            if archive:
                kept.write_bytes((json.dumps(archive, indent=2, ensure_ascii=False)
                                  + "\n").encode("utf-8"))
                print(f"archived {len(archive)} dropped records to "
                      f"{kept.name}, keyed set/id with their prompt digests")

    def save() -> None:
        artifact.write_bytes(
            (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    def save_set(name: str, per_case: dict, scores: dict | None = None) -> None:
        # Publish the in-flight set into `report` before writing. Without this the
        # per-case save() inside the loop writes a report whose sets[name] is still
        # absent -- i.e. it persists nothing new, and a crash still costs the whole
        # set. The first version of this file had exactly that bug: it claimed
        # incremental persistence on a path that only flushed at set boundaries.
        blk = report["sets"].setdefault(name, {})
        blk["cases"] = per_case
        if scores is not None:
            blk["scores"] = scores
        save()

    returned_models: set[str] = set()
    contract_failures: list[str] = []

    for name in want:
        cases = load_cases(sets[name])
        if opts.limit:
            cases = cases[: opts.limit]
        gemini: dict[str, dict[str, str]] = {}
        gpath = REPO / llm[name]
        if gpath.exists():
            gemini = gemini_labels(gpath)
        prev = (report["sets"].get(name) or {}).get("cases") or {}
        ours: dict[str, str] = {k: v.get("combined", "") for k, v in prev.items()}
        per_case: dict[str, dict] = dict(prev)
        right = sum(1 for v in per_case.values() if v.get("matches_expected"))
        right_c = sum(1 for v in per_case.values() if v.get("matches_combined"))
        for case in cases:
            if opts.resume and case["id"] in per_case:
                continue
            prompt = RUBRIC + "\nCase to audit:\n" + json.dumps(
                annotator_payload(case), indent=2)
            sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            try:
                text, data = call(prompt, key)
            except RuntimeError as e:
                contract_failures.append(f"{name}/{case['id']}: {e}")
                print(f"!! {name}/{case['id']} transport: {e}", flush=True)
                save_set(name, per_case)
                continue
            parsed = parse(text)
            if not parsed.get("verdict"):
                # "no verdict in reply" is only actionable if the reply survives. The
                # first version dropped the text, so gold-01's single miss could not be
                # re-examined without spending the call again -- and the distinction
                # between truncation, prose-wrapped JSON, and a refusal is the finding.
                contract_failures.append(f"{name}/{case['id']}: no verdict in reply")
                print(f"!! {name}/{case['id']} unparseable, reply kept verbatim",
                      flush=True)
            label = combined_label(parsed) if parsed else ""
            ours[case["id"]] = label
            returned_models.add(str(data.get("model")))
            exp = case.get("expected_verdict")
            ok = bool(parsed) and parsed.get("verdict") == exp
            right += ok
            # Combined is a different quantity from verdict. The published finding is
            # on this axis (verdict kappa 1.0, combined kappa 0.455), and measuring only
            # verdict would call sem-03 correct when its error set is wrong -- so both
            # are recorded and neither is allowed to stand in for the other.
            ok_c = bool(parsed) and label == combined_label({
                "verdict": exp, "errors": case.get("expected_errors") or []})
            right_c += ok_c
            per_case[case["id"]] = {
                "combined": label, "verdict": parsed.get("verdict"),
                "errors": parsed.get("errors"), "expected_verdict": exp,
                "expected_errors": case.get("expected_errors"),
                "matches_expected": ok, "matches_combined": ok_c,
                "expected_combined": combined_label({
                    "verdict": exp, "errors": case.get("expected_errors") or []}),
                "prompt_sha256": sha,
                "returned_model": data.get("model"),
                "usage": data.get("usage"),
                **({} if parsed.get("verdict") else
                   {"raw_reply_unparsed": text[:4000]}),
            }
            # Persist per case, not per set. The first version of this script wrote the
            # artifact only at the end of a 52-call run; a `timeout` killed it at call
            # six and there was nothing on disk to reconcile against, so the whole run
            # was worth zero. A crash should cost one case, not an evening.
            save_set(name, per_case)
            print(f"{case['id']:12s} {label:28s} expected={exp} "
                  f"{'OK' if ok else 'DIFF'}" if ok_c == ok else
                  f"verdict-ok/combined-DIFF", flush=True)
        scores: dict = {
            "n_cases": len(cases), "n_answered": len(ours),
            "verdict_accuracy_vs_expected": round(right / len(ours), 4) if ours else None,
            "combined_accuracy_vs_expected": (
                round(right_c / len(ours), 4) if ours else None),
        }
        for gmodel, gl in gemini.items():
            shared = [i for i in ours if i in gl]
            if len(shared) >= 2:
                pairs = [(ours[i], gl[i]) for i in shared]
                scores[f"kappa_vs_{gmodel}"] = round(cohen_kappa(pairs), 4)
                scores[f"agreement_vs_{gmodel}"] = round(
                    sum(a == b for a, b in pairs) / len(pairs), 4)
        if not gemini:
            # Silence here would turn a missing cross-reference into a missing number,
            # which is the difference between "we measured no agreement" and "we never
            # looked". Refuse rather than publish the former reading.
            raise SystemExit(f"{name}: no Gemini raters found in {llm[name]}; "
                             "cannot compute cross-provider kappa")
        report["sets"][name] = {"raters_compared": sorted(gemini)}
        save_set(name, per_case, scores)
        print(f"== {name}: {scores}")

    # Both of these describe the artifact, not just this invocation. A zero-call
    # reconciliation re-run under --resume answers nothing, so rebuilding them from this
    # run's memory alone would publish "no contract failures" and an empty model set --
    # a gate that clears because the checker stopped looking. Re-derive from the records
    # and union in what only this run could know.
    answered_nothing = [f"{n}/{i}" for n, b in report["sets"].items()
                        for i, rec in (b.get("cases") or {}).items()
                        if isinstance(rec, dict) and not rec.get("verdict")]
    models_seen = {str(rec.get("returned_model"))
                   for b in report["sets"].values()
                   for rec in (b.get("cases") or {}).values()
                   if isinstance(rec, dict) and rec.get("returned_model")}
    report["returned_model_strings"] = sorted(models_seen | returned_models)
    report["contract_failures"] = sorted(set(answered_nothing) | set(contract_failures))
    (out_dir / "raw.json").write_bytes(
        (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"\nwrote {out_dir.relative_to(REPO)}/raw.json")
    print(f"returned model strings: {sorted(returned_models)}")
    if contract_failures:
        print(f"CONTRACT FAILURES: {len(contract_failures)}")
        for f in contract_failures[:8]:
            print("   ", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
