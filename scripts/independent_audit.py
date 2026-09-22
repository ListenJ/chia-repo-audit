#!/usr/bin/env python3
"""Label the hidden audit set with two independent models and report real agreement.

The checked-in cases carry the answer in several fields, so the annotator payload is
built from an allowlist (id/design/reference) and the script refuses to run if any
forbidden key survives. Cohen's kappa here is inter-annotator agreement between two
models; the deterministic in-loop self-test stays separate and is never merged in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from real_candidate_generate import vertex_access_token

REPO = Path(__file__).resolve().parents[1]
VERTEX_BASE = "https://us-central1-aiplatform.googleapis.com/v1"
PROJECT_DEFAULT = "a3-chia-hack26ath-7744"

# Anything outside this allowlist leaks the expected label.
VISIBLE_KEYS = ("id", "design", "reference")
FORBIDDEN_KEYS = ("expected_verdict", "expected_errors", "category", "variant",
                  "rationale", "planting")

RUBRIC = """\
You are auditing whether a candidate microarchitecture specification is equivalent
to a reference specification. Judge only what is written below.

Error classes:
  E0 equivalent          - no behavioural difference
  E1 parameter_mislink   - a shared parameter holds a different value
  E2 direction_error     - a change moves the wrong way or inverts a relation
  E3 missing_component   - the candidate omits something the reference has
  E4 added_component     - the candidate adds something the reference lacks,
                           or asserts a result it did not derive

Reply with ONE JSON object and nothing else:
{"id": "<case id>", "verdict": "equivalent"|"not_equivalent",
 "errors": [<zero or more of E1,E2,E3,E4>], "rationale": "<one sentence>"}

E0 is implied by an empty errors list together with verdict "equivalent".
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_cases(paths: list[Path]) -> list[dict]:
    cases = []
    for path in paths:
        for entry in sorted(Path(path).resolve().glob("*.json")):
            if entry.name == "answer-key.json":
                continue
            record = json.loads(entry.read_text(encoding="utf-8"))
            record["_source"] = str(entry.relative_to(REPO))
            cases.append(record)
    return cases


def annotator_payload(case: dict) -> dict:
    payload = {key: case[key] for key in VISIBLE_KEYS if key in case}
    leaked = [key for key in FORBIDDEN_KEYS if key in payload]
    if leaked:
        raise SystemExit(f"{case.get('id')}: annotator payload leaks {leaked}")
    return payload


def access_token() -> str:
    return vertex_access_token()


def call_model(model: str, prompt: str, token: str, retries: int = 3) -> tuple[str, dict]:
    url = (f"{VERTEX_BASE}/projects/{os.environ.get('GCP_PROJECT', PROJECT_DEFAULT)}"
           f"/locations/us-central1/publishers/google/models/{model}:generateContent")
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2048},
    }).encode()
    last = ""
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last = f"transport: {exc}"
            time.sleep(2 ** attempt)
            continue
        candidates = data.get("candidates") or []
        if not candidates:
            last = f"no candidates: {str(data.get('promptFeedback'))[:120]}"
            time.sleep(1)
            continue
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if text.strip():
            return text, data.get("usageMetadata", {})
        last = f"empty text, finishReason={candidates[0].get('finishReason')}"
        time.sleep(1)
    raise SystemExit(f"{model} produced no answer after {retries} tries: {last}")


JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_verdict(text: str) -> dict:
    match = JSON_RE.search(text)
    if not match:
        raise ValueError(f"no JSON object in reply: {text[:120]}")
    obj = json.loads(match.group(0))
    verdict = obj.get("verdict")
    if verdict not in ("equivalent", "not_equivalent"):
        raise ValueError(f"bad verdict {verdict!r}")
    errors = [e for e in obj.get("errors", []) if re.fullmatch(r"E[1-4]", e)]
    if verdict == "equivalent":
        errors = []
    return {"verdict": verdict, "errors": sorted(set(errors)),
            "rationale": str(obj.get("rationale", ""))[:400]}


def label_case(model: str, case: dict, token: str) -> dict:
    prompt = RUBRIC + "\nCase to audit:\n" + json.dumps(annotator_payload(case), indent=2)
    sha = hashlib.sha256(prompt.encode()).hexdigest()
    text, usage = call_model(model, prompt, token)
    try:
        parsed = parse_verdict(text)
        parsed["parse_ok"] = True
    except (ValueError, json.JSONDecodeError) as exc:
        parsed = {"verdict": None, "errors": [], "rationale": f"parse failure: {exc}",
                  "parse_ok": False}
    return {"model": model, "prompt_sha256": sha, "raw_reply": text,
            "usage": usage, **parsed}


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    """pairs are (label_a, label_b) over the same items; undefined cases score 0 agreement."""
    n = len(pairs)
    if n == 0:
        return float("nan")
    observed = sum(1 for a, b in pairs if a == b) / n
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    expected = sum((sum(1 for a, _ in pairs if a == l) / n) *
                   (sum(1 for _, b in pairs if b == l) / n) for l in labels)
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1.0 - expected)


def combined_label(result: dict) -> str:
    if result["verdict"] is None:
        return "unparseable"
    return result["verdict"] + "|" + ",".join(result["errors"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["gemini-2.5-flash", "gemini-2.5-pro"])
    parser.add_argument("--case-dirs", nargs="+",
                        default=[str(REPO / "chia_loop/gold"), str(REPO / "chia_loop/adversarial")])
    parser.add_argument("--output-dir", type=Path, default=REPO / "results/audit_independent_v1")
    parser.add_argument("--limit", type=int, default=0, help="stop after N cases (smoke runs)")
    args = parser.parse_args()

    if len(args.models) < 2:
        raise SystemExit("two or more annotators are required to measure agreement")

    cases = load_cases([Path(p) for p in args.case_dirs])
    if args.limit:
        cases = cases[:args.limit]

    token = access_token()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for case in cases:
        entry = {"id": case["id"], "source": case["_source"],
                 "expected_verdict": case["expected_verdict"],
                 "expected_errors": sorted(case["expected_errors"]),
                 "labels": []}
        for model in args.models:
            result = label_case(model, case, token)
            entry["labels"].append(result)
            print(f"{case['id']:9s} {model:18s} {combined_label(result):28s} "
                  f"{'ok' if result['parse_ok'] else 'PARSE_FAIL'}", flush=True)
        records.append(entry)

    a, b = args.models[0], args.models[1]
    by_model = {m: [r for r in records if any(l["model"] == m for l in r["labels"])] for m in args.models}

    def pick(record: dict, model: str) -> dict:
        return next(l for l in record["labels"] if l["model"] == model)

    pairs = [(combined_label(pick(r, a)), combined_label(pick(r, b))) for r in records]
    verdict_pairs = [(pick(r, a)["verdict"] or "unparseable", pick(r, b)["verdict"] or "unparseable")
                     for r in records]

    disagreements = []
    for record, (label_a, label_b) in zip(records, pairs):
        if label_a == label_b:
            continue
        disagreements.append({
            "id": record["id"],
            "expected": f"{record['expected_verdict']}|{','.join(record['expected_errors'])}",
            a: label_a,
            b: label_b,
        })

    report = {
        "generated_at": now(),
        "annotators": args.models,
        "n_cases": len(records),
        "kappa_combined_label": cohen_kappa(pairs),
        "kappa_verdict_only": cohen_kappa(verdict_pairs),
        "observed_agreement": round(sum(1 for x, y in pairs if x == y) / len(pairs), 4) if pairs else None,
        "per_model": {
            m: {
                "n": len(by_model[m]),
                "parse_ok": sum(1 for r in by_model[m] if pick(r, m)["parse_ok"]),
                "verdict_accuracy": round(
                    sum(1 for r in by_model[m] if pick(r, m)["verdict"] == r["expected_verdict"])
                    / len(by_model[m]), 4) if by_model[m] else None,
                "error_set_exact": round(
                    sum(1 for r in by_model[m] if pick(r, m)["errors"] == r["expected_errors"])
                    / len(by_model[m]), 4) if by_model[m] else None,
            } for m in args.models
        },
        "disagreements": disagreements,
        "unparseable": [r["id"] for r in records
                        for l in r["labels"] if not l["parse_ok"]],
        "caveats": [
            "Both annotators are hosted by the same provider; cross-family independence is not claimed.",
            "kappa here is model-model agreement. It is not a human reliability estimate.",
            "The deterministic in-loop double-blind self-test is reported separately and is not merged into this number.",
        ],
    }

    (args.output_dir / "raw.json").write_text(json.dumps(records, indent=1), encoding="utf-8")
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("n_cases", "kappa_combined_label", "kappa_verdict_only",
                       "observed_agreement", "per_model")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
