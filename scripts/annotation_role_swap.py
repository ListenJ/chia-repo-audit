"""角色互换一致性探针：同一个设计对，把 candidate 与 reference 对调再问一次。

动机：论文 Limitations 里刚写下"标注污染我们没测"。对调测试是同一类威胁里
**能测的那一半** —— 审计问的是"这两个设计等价吗"，而等价是对称关系。
如果同一个模型在同一对上因为谁被摆在 candidate 位置而改变 verdict，
那么它的判断读的是**方向性的叙述**（"加了 X"、"少了 Y"），不是行为等价性。
这直接动摇以 κ 报告的可靠性：κ 高可能只是两个模型共享同一种呈现偏置。

不重跑仿真、不下结论式断言：只报告翻转率与翻转发生在哪些对上。
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from independent_audit import (  # noqa: E402
    RUBRIC, annotator_payload, call_model, load_cases, parse_verdict)
from real_candidate_generate import vertex_access_token  # noqa: E402


def label_swapped(model: str, case: dict, token: str) -> dict:
    """Same payload, candidate and reference exchanged; the answer is read back swapped."""
    payload = annotator_payload(case)
    payload["design"], payload["reference"] = payload["reference"], payload["design"]
    prompt = RUBRIC + "\nCase to audit:\n" + json.dumps(payload, indent=2)
    text, usage = call_model(model, prompt, token)
    try:
        parsed = parse_verdict(text)
        parsed["parse_ok"] = True
    except (ValueError, json.JSONDecodeError) as exc:
        parsed = {"verdict": None, "errors": [], "rationale": f"parse failure: {exc}",
                  "parse_ok": False}
    return {"model": model, "raw_reply": text, "usage": usage, **parsed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-dirs", nargs="+",
                    default=[str(REPO / "chia_loop/semantic")])
    ap.add_argument("--models", nargs="+", default=["gemini-2.5-flash", "gemini-2.5-pro"])
    ap.add_argument("--output-dir", type=Path,
                    default=REPO / "results/annotation_role_swap")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    token = vertex_access_token()
    cases = load_cases([Path(p) for p in args.case_dirs])
    baseline_path = REPO / "results/audit_independent_semantic_v2/raw.json"
    if not baseline_path.is_file():
        raise SystemExit(f"need the forward-direction baseline at {baseline_path}")
    forward = {r["id"]: {l["model"]: l for l in r["labels"]}
               for r in json.loads(baseline_path.read_text(encoding="utf-8"))}

    rows, flips = [], []
    for case in cases:
        rec = {"id": case["id"], "expected_verdict": case["expected_verdict"], "labels": []}
        for model in args.models:
            fwd = forward.get(case["id"], {}).get(model)
            if fwd is None:
                print(f"skip {case['id']}/{model}: no forward answer")
                continue
            rev = label_swapped(model, case, token)
            rec["labels"].append({"model": model, "direction": "swapped", **rev})
            agree_fwd = fwd["verdict"] == case["expected_verdict"]
            agree_rev = rev["verdict"] == case["expected_verdict"]
            flipped = bool(fwd.get("parse_ok") and rev.get("parse_ok")
                           and fwd["verdict"] != rev["verdict"])
            if flipped:
                flips.append((case["id"], model, fwd["verdict"], rev["verdict"]))
            print(f"[{case['id']}] {model:<18} fwd={fwd['verdict']:<15} "
                  f"swap={rev['verdict']:<15} gold={case['expected_verdict']:<15} "
                  f"{'FLIP' if flipped else 'stable'}", flush=True)
        rows.append(rec)

    n_cmp = sum(len(r["labels"]) for r in rows)
    report = {
        "n_cases": len(cases),
        "n_comparisons": n_cmp,
        "n_flips": len(flips),
        "flip_rate": round(len(flips) / n_cmp, 4) if n_cmp else None,
        "flips": [{"case": c, "model": m, "forward": f, "swapped": s}
                  for c, m, f, s in flips],
        "note": ("equivalence is symmetric, so a verdict that changes when candidate and "
                 "reference exchange places is reading the direction of the narrative, "
                 "not the behaviour"),
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "raw.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nflips {report['n_flips']}/{report['n_comparisons']} "
          f"(rate {report['flip_rate']}) -> {args.output_dir/'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
