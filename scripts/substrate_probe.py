"""把 Laya 当作**第三个、架构上不同**的标注substrate，跑在已隐藏的审计用例上。

动机：论文目前的 Limitations 承认两个标注者同属一家供应商，只能声称 model-model
而非跨家族独立。Laya 是 421M ModernBERT **判别式**头，非自回归、不生成文本，
与前两个生成式 LLM 在架构上真正不同 —— 这是唯一能拿到的跨架构一致性数据。

预设的失败：本包实测它不做数值推理、不处理否定、措辞敏感。审计任务三样都用得上。
所以这个 probe 无论结果好坏都是证据：高一致说明判别头也能当标注者，
低一致说明**换架构买不到独立性**，因为独立性的对手是共同盲点，不是共同模型族。

用法：wsl -d Arch /root/.venvs/laya/bin/python /mnt/d/.../scripts/substrate_probe.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import torch  # noqa: E402
from laya import RLAgent  # noqa: E402

from independent_audit import (  # noqa: E402
    annotator_payload, cohen_kappa, combined_label, load_cases)

CKPT = "/root/models/laya"
SETS = {
    "spec10": [REPO / "chia_loop/gold", REPO / "chia_loop/adversarial"],
    "semantic4": [REPO / "chia_loop/semantic"],
    "fact36": [REPO / "chia_loop/semantic_fact"],
}
# 已落盘的生成式标注者结果，用来配对比分
LLM_RESULTS = {
    "spec10": REPO / "results/audit_independent_v1/raw.json",
    "semantic4": REPO / "results/audit_independent_semantic/raw.json",
    "fact36": REPO / "results/audit_independent_fact36/raw.json",
}


def laya_label(agent, case: dict) -> dict:
    payload = annotator_payload(case)
    # 判别头读不进嵌套 dict，序列化成它训练时见过的自然语言状态
    state = json.dumps(payload, ensure_ascii=False, sort_keys=True)[:6000]
    out = agent.predict(state, {
        "verdict": {
            "type": "choice",
            "instructions": "Two microarchitecture design specifications are being audited "
                            "against each other. Decide whether the candidate design is "
                            "functionally equivalent to the reference design.",
            "criteria": {
                "equivalent": "the candidate behaves the same as the reference",
                "not_equivalent": "the candidate behaves differently from the reference",
            },
        }
    })["answers"]["verdict"]
    p = out["probabilities"]
    top = sorted(p.items(), key=lambda kv: -kv[1])
    margin = top[0][1] - top[1][1]
    return {"model": "laya-421m-discriminative",
            "verdict": top[0][0],
            "errors": [],
            "parse_ok": True,
            "margin": margin,
            "probabilities": p}


def main() -> int:
    agent = RLAgent(model_id_or_path=CKPT, device="cuda")
    for m in vars(agent).values():
        if isinstance(m, torch.nn.Module):
            m.to(torch.bfloat16)

    report = {}
    for name, dirs in SETS.items():
        cases = load_cases([Path(d) for d in dirs])
        labels = [laya_label(agent, c) for c in cases]
        by_id = {c["id"]: l for c, l in zip(cases, labels)}

        # gold：用例自带的期望标签
        expected = {}
        for c in cases:
            expected[c["id"]] = c["expected_verdict"] + "|" + \
                ",".join(sorted(c.get("expected_errors", [])))
        laya_v = {cid: by_id[cid]["verdict"] for cid in by_id}
        gold_v = {cid: expected[cid].split("|")[0] for cid in expected}
        # A pair the labeler withdrew has no ground truth to score the substrate against.
        scored = [cid for cid in laya_v if gold_v[cid] != "unlabellable"]

        n = len(scored)
        acc_v = sum(1 for cid in scored if laya_v[cid] == gold_v[cid]) / n if n else 0.0
        margins = [by_id[cid]["margin"] for cid in by_id]
        tally = Counter(laya_v.values())

        entry = {
            "n_cases": len(cases),
            "n_labellable": n,
            "n_unlabellable": len(cases) - n,
            "laya_verdict_tally": dict(tally),
            "laya_per_case": {cid: {"laya": laya_v[cid], "expected": gold_v[cid],
                                    "margin": round(by_id[cid]["margin"], 4)}
                              for cid in sorted(laya_v)},
            "laya_verdict_accuracy_vs_expected": round(acc_v, 4),
            "mean_margin": round(sum(margins) / n, 4) if n else None,
            "low_margin_cases": sum(1 for m in margins if m < 0.15),
        }

        llm_path = LLM_RESULTS.get(name)
        if llm_path and llm_path.exists():
            raw = json.loads(llm_path.read_text(encoding="utf-8"))
            records = raw if isinstance(raw, list) else (
                raw.get("records") or raw.get("cases") or [])
            per_model = {}
            for rec in records:
                cid = rec.get("id") or rec.get("case_id")
                if cid not in by_id:
                    continue
                for lab in rec.get("labels", []):
                    if lab.get("parse_ok"):
                        per_model.setdefault(lab["model"], {})[cid] = lab
            for model, labs in sorted(per_model.items()):
                shared = sorted(set(labs) & set(by_id))
                if not shared:
                    continue
                entry[f"kappa_vs_{model}"] = round(
                    cohen_kappa([(labs[c]["verdict"], laya_v[c]) for c in shared]), 4)
                entry[f"agreement_vs_{model}"] = round(
                    sum(1 for c in shared if labs[c]["verdict"] == laya_v[c]) / len(shared), 4)
                entry[f"llm_verdicts_{model}"] = {c: labs[c]["verdict"] for c in shared}
            both = sorted(per_model)
            if len(both) >= 2:
                a, b = per_model[both[0]], per_model[both[1]]
                shared = sorted(set(a) & set(b) & set(by_id))
                entry["llm_vs_llm_kappa_on_laya_shared"] = round(
                    cohen_kappa([(a[c]["verdict"], b[c]["verdict"]) for c in shared]), 4)
        else:
            entry["llm_baseline"] = "no committed LLM result for this set"

        report[name] = entry
        print(f"[{name}] n={n} acc={entry['laya_verdict_accuracy_vs_expected']} "
              + " ".join(f"{k}={v}" for k, v in entry.items()
                         if k.startswith("kappa") or k.startswith("agreement")), flush=True)

    out = REPO / "results/substrate_probe_laya.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
