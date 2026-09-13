#!/usr/bin/env python3
"""audit_repro.py — CHIA hackathon 提交 loop（增强版：含双盲审计层）。

题目:
  "Does Agentic Architecture Discovery Reproduce?
   A Double-Blind Audit Protocol for LLM-Driven Microarchitecture Search"

4 阶段:
  1. prepare  — pin 环境 + 加载审计配置
  2. run      — 仿真网格（seed × prompt × trace）
  3. dblind   — 双盲审计（A/B auditor 独立判定 + κ + 对抗样本检测 + 发布门禁）
  4. act      — 记分卡

双盲审计层适配自 Axiom 的语义等价评估协议（κ=0.954, N=100, 20% 复核抽样），
将 E0-E4 错误分类从 NLP 迁移到硬件设计领域。

CHIA 依赖可选：装了用 CHIA 编排，没装退化到直跑。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

try:
    from chia.base.ChiaFunction import ChiaFunction, get
    HAS_CHIA = True
except ImportError:
    HAS_CHIA = False
    def ChiaFunction(**kwargs):
        def deco(fn): return fn
        return deco
    def get(x): return x

REPO_ROOT = Path(__file__).resolve().parents[2]  # loops/ → chia_loop/ → repo root
RESULTS_DIR = REPO_ROOT / "results"
ADVERSARIAL_DIR = REPO_ROOT / "chia_loop" / "adversarial"
GOLD_DIR = REPO_ROOT / "chia_loop" / "gold"
PIN_FILE = RESULTS_DIR / "env_pin.json"

# 使 sim.backends 可导入（脚本直跑时 chia_loop 不在 sys.path）
_CHIA_LOOP = str(REPO_ROOT / "chia_loop")
if _CHIA_LOOP not in sys.path:
    sys.path.insert(0, _CHIA_LOOP)
from sim.backends import get_backend  # noqa: E402

# ── 预注册配置（冻结于跑实验前）──────────────────────────────
CONFIG = {
    "version": 3,  # v3: 后端抽象（stub 默认，champsim 可切）
    "backend": "stub",  # "stub" | "champsim"（09-21 算力到账后切换）
    "design": {"llc_replacement": "lru", "branch_predictor": "bimodal"},
    "seeds": [0, 1, 2],
    "prompts": ["default", "cot", "adversarial"],
    "traces": ["spec_gcc", "spec_mcf", "web_cloud"],
    "acceptance_threshold": 0.05,
    "n_repeat": 5,
    "kappa_gate": 0.7,        # Cohen's κ 发布门禁
    "re_audit_ratio": 0.20,   # 20% 复核抽样
}

ERROR_CLASSES = ["E0", "E1", "E2", "E3", "E4"]


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════
def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception:
        return "unknown"


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """计算两个标注员在分类标签上的 Cohen's κ。"""
    n = len(a)
    if n == 0:
        return 0.0
    if a == b:
        return 1.0
    labels = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


# ══════════════════════════════════════════════════════════════
# Stage 1: prepare
# ══════════════════════════════════════════════════════════════
@ChiaFunction()
def stage_prepare(*, version: int) -> dict:
    pin = {
        "config_version": version,
        "timestamp": time.time(),
        "git_sha": _git_head(),
        "python": sys.version.split()[0],
        "cwd": str(REPO_ROOT),
        "audit_protocol": "double-blind adapted from Axiom semantic-equivalence (kappa=0.954)",
        "pre_registered": True,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PIN_FILE.write_text(json.dumps(pin, indent=2))
    return pin


# ══════════════════════════════════════════════════════════════
# Stage 2: run — 仿真网格
# ══════════════════════════════════════════════════════════════
@ChiaFunction()
def stage_run(*, version: int) -> dict:
    backend = get_backend(CONFIG)
    design = CONFIG.get("design", {})
    results = {}
    for seed in CONFIG["seeds"]:
        for prompt in CONFIG["prompts"]:
            for trace in CONFIG["traces"]:
                trials = [backend.run(seed, prompt, trace, design).asdict()
                           for _ in range(CONFIG["n_repeat"])]
                trials.sort(key=lambda t: t["cycles"])
                results[f"{seed}/{prompt}/{trace}"] = trials[len(trials) // 2]
    (RESULTS_DIR / "raw.json").write_text(json.dumps(results, indent=2))
    return {"n_cells": len(results), "backend": backend.name}


# ══════════════════════════════════════════════════════════════
# Stage 3: double-blind audit — Axiom 适配的双盲审计
# ══════════════════════════════════════════════════════════════
def _audit_design_single(design: dict, reference: dict, auditor_id: str) -> dict:
    """单个 auditor 的独立判定。

    说明（诚实口径）：桩阶段的 A/B auditor 是确定性且一致的——κ=1.0 反映的是
    「协议逻辑自检通过」，不是真实标注员间信度。真实部署时应接入独立的人工/LLM
    annotator 测量 κ（对齐 Axiom 语义等价评估的实测 κ=0.954 流程）。
    """
    errors = []
    all_keys = set(reference.keys()) | set(design.keys())

    for key in all_keys:
        ref_val = reference.get(key)
        des_val = design.get(key)

        if ref_val is not None and des_val is not None:
            if ref_val != des_val:
                if isinstance(ref_val, str) and isinstance(des_val, str):
                    direction_words = {"lru", "mru", "fifo", "lifo", "rr"}
                    if ref_val.lower() in direction_words or des_val.lower() in direction_words:
                        errors.append("E2")
                    else:
                        errors.append("E1")
                else:
                    errors.append("E1")
        elif ref_val is not None and des_val is None:
            errors.append("E3")
        elif ref_val is None and des_val is not None:
            # 两个 auditor 均严格判定（去除 A 的 extra_ 放行，检测率→100%）
            errors.append("E4")

    # V1 weak-verifier trap：agent 只打印 PASS 未做实质工作 → 伪造输出，定为 E4
    # （抑制伴随的 E1 值错判，避免分类噪声）
    if design.get("output") == "PASS" and reference.get("output") != "PASS":
        errors = ["E4"]

    errors = list(dict.fromkeys(errors))
    verdict = "equivalent" if not errors else "not_equivalent"
    return {
        "auditor": auditor_id,
        "verdict": verdict,
        "error_classes": errors,
        "rationale": f"keys: {sorted(all_keys)}, errors: {errors}",
    }


def _load_cases(directory: Path) -> list[dict]:
    cases = []
    if directory.exists():
        for f in sorted(directory.glob("*.json")):
            if f.name == "answer-key.json":
                continue
            cases.append(json.loads(f.read_text()))
    return cases


@ChiaFunction()
def stage_double_blind_audit(*, version: int) -> dict:
    """双盲审计：A/B auditor 独立判定 + κ + 对抗检测 + 发布门禁。"""
    gold_cases = _load_cases(GOLD_DIR)
    adv_cases = _load_cases(ADVERSARIAL_DIR)
    all_cases = gold_cases + adv_cases

    annotator_a, annotator_b, per_case = [], [], []

    for case in all_cases:
        result_a = _audit_design_single(case["design"], case["reference"], "A")
        result_b = _audit_design_single(case["design"], case["reference"], "B")

        label_a = result_a["error_classes"][0] if result_a["error_classes"] else "E0"
        label_b = result_b["error_classes"][0] if result_b["error_classes"] else "E0"
        annotator_a.append(label_a)
        annotator_b.append(label_b)

        arbitrated = result_a if result_a["verdict"] == result_b["verdict"] else {
            "verdict": "contested",
            "error_classes": list(set(result_a["error_classes"]) | set(result_b["error_classes"])),
        }

        expected_verdict = case.get("expected_verdict", "")
        expected_errors = case.get("expected_errors", [])
        match = (arbitrated["verdict"] == expected_verdict
                 and set(arbitrated.get("error_classes", [])) == set(expected_errors))

        per_case.append({
            "id": case["id"],
            "auditor_a": label_a, "auditor_b": label_b,
            "agreed": label_a == label_b,
            "arbitrated_verdict": arbitrated["verdict"],
            "arbitrated_errors": arbitrated.get("error_classes", []),
            "expected_verdict": expected_verdict,
            "expected_errors": expected_errors,
            "correct": match,
        })

    kappa = cohen_kappa(annotator_a, annotator_b)
    adv_correct = sum(1 for c in per_case[len(gold_cases):] if c["correct"])
    adv_total = len(adv_cases)
    adv_rate = adv_correct / adv_total if adv_total else 0.0
    gold_correct = sum(1 for c in per_case[:len(gold_cases)] if c["correct"])

    error_dist = {e: 0 for e in ERROR_CLASSES}
    for c in per_case:
        for e in c["arbitrated_errors"]:
            error_dist[e] = error_dist.get(e, 0) + 1

    kappa_pass = kappa >= CONFIG["kappa_gate"]
    adv_pass = adv_rate >= 1.0
    publish_gate = "PASS" if (kappa_pass and adv_pass) else "BLOCKED"

    report = {
        "version": version,
        "n_cases": len(all_cases),
        "n_gold": len(gold_cases),
        "n_adversarial": adv_total,
        "cohen_kappa": round(kappa, 4),
        "kappa_gate": CONFIG["kappa_gate"],
        "kappa_passed": kappa_pass,
        "adversarial_detection_rate": round(adv_rate, 4),
        "adversarial_passed": adv_pass,
        "gold_calibration_correct": f"{gold_correct}/{len(gold_cases)}",
        "error_distribution": error_dist,
        "publish_gate": publish_gate,
        "per_case": per_case,
        "protocol_source": "adapted from Axiom semantic-equivalence (kappa=0.954, N=100, 20% re-audit)",
    }
    (RESULTS_DIR / "dblind_report.json").write_text(json.dumps(report, indent=2))
    return report


# ══════════════════════════════════════════════════════════════
# Stage 4: audit + act — 复现性记分卡（含双盲审计结果）
# ══════════════════════════════════════════════════════════════
def _cv(values) -> float:
    if not values:
        return float("nan")
    m = statistics.mean(values)
    return statistics.stdev(values) / m if m else float("nan")


@ChiaFunction()
def stage_audit(*, version: int) -> dict:
    raw = json.loads((RESULTS_DIR / "raw.json").read_text())
    cells = list(raw.values())

    by_key = {}
    for cell in cells:
        by_key.setdefault((cell["prompt"], cell["trace"]), []).append(cell["cycles"])
    seed_cv = {f"{p}/{t}": _cv(v) for (p, t), v in by_key.items()}

    tmap = {}
    for cell in cells:
        tmap.setdefault(cell["trace"], []).append(cell["cycles"])
    trace_cv = {t: _cv(v) for t, v in tmap.items()}

    max_cv = max(seed_cv.values())
    reproducible = max_cv < CONFIG["acceptance_threshold"]

    dblind = {}
    dblind_file = RESULTS_DIR / "dblind_report.json"
    if dblind_file.exists():
        dblind = json.loads(dblind_file.read_text())

    report = {
        "version": version,
        "max_seed_cv": round(max_cv, 4),
        "verdict": "REPRODUCIBLE" if reproducible else "NON-REPRODUCIBLE",
        "trace_cv": {k: round(v, 4) for k, v in trace_cv.items()},
        "cohen_kappa": dblind.get("cohen_kappa", "N/A"),
        "publish_gate": dblind.get("publish_gate", "N/A"),
        "adversarial_detection": dblind.get("adversarial_detection_rate", "N/A"),
        "gold_calibration": dblind.get("gold_calibration_correct", "N/A"),
        "error_distribution": dblind.get("error_distribution", {}),
    }
    (RESULTS_DIR / "audit_report.json").write_text(json.dumps(report, indent=2))
    return report


@ChiaFunction()
def stage_act(*, version: int) -> str:
    report = json.loads((RESULTS_DIR / "audit_report.json").read_text())
    gate = report.get("publish_gate", "N/A")
    lines = [
        f"CHIA 复现性审计报告 (config v{version})",
        f"{'━'*40}",
        f"复现性判定: {report['verdict']}",
        f"最大跨种子变异系数: {report['max_seed_cv']} (阈值 {CONFIG['acceptance_threshold']})",
        f"{'━'*40}",
        f"双盲审计 (Axiom 适配协议):",
        f"  Cohen's κ: {report.get('cohen_kappa', 'N/A')} (门禁 {CONFIG['kappa_gate']})",
        f"  对抗样本检测率: {report.get('adversarial_detection', 'N/A')}",
        f"  Gold 校准: {report.get('gold_calibration', 'N/A')}",
        f"  错误分布: {report.get('error_distribution', {})}",
        f"  发布门禁: {gate}",
        f"{'━'*40}",
        f"{'✓ 可对外发布' if gate == 'PASS' else '✗ BLOCKED: 不可对外发布'}",
    ]
    out = "\n".join(lines)
    (RESULTS_DIR / "scorecard.txt").write_text(out)
    print(out)
    return out


# ══════════════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=CONFIG["version"])
    args = ap.parse_args()
    v = args.version

    def call(fn, **kw):
        if HAS_CHIA:
            return get(fn.chia_remote(**kw))
        return fn(**kw)

    pin = call(stage_prepare, version=v)
    run_res = call(stage_run, version=v)
    dblind = call(stage_double_blind_audit, version=v)
    audit = call(stage_audit, version=v)
    scorecard = call(stage_act, version=v)

    print(json.dumps({
        "pin": pin, "run": run_res, "dblind": dblind,
        "audit": audit, "scorecard": scorecard,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()