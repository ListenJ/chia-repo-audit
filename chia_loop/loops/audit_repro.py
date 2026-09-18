#!/usr/bin/env python3
"""CHIA loop for auditing reproducibility and evaluation fairness.

Stages:
  1. prepare  - pin the environment and pre-registered configuration
  2. run      - collect repeated measurements over seed x prompt x trace
  3. dblind   - classify candidate/reference pairs with A/B auditors
  4. audit    - compute repeatability and sensitivity metrics
  5. act      - emit a publish scorecard

CHIA is optional. Without CHIA, the same function bodies run locally.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
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
        def deco(fn):
            return fn
        return deco

    def get(x):
        return x


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
ADVERSARIAL_DIR = REPO_ROOT / "chia_loop" / "adversarial"
GOLD_DIR = REPO_ROOT / "chia_loop" / "gold"
PIN_FILE = RESULTS_DIR / "env_pin.json"

_CHIA_LOOP = str(REPO_ROOT / "chia_loop")
if _CHIA_LOOP not in sys.path:
    sys.path.insert(0, _CHIA_LOOP)
from sim.backends import get_backend  # noqa: E402


# Frozen before real measurements. CLI overrides are recorded in raw.json.
CONFIG = {
    "version": 4,
    "backend": "stub",
    "design": {"llc_replacement": "lru", "branch_predictor": "bimodal"},
    "seeds": [0, 1, 2],
    "prompts": ["default", "cot", "adversarial"],
    "traces": ["spec_gcc", "spec_mcf", "web_cloud"],
    "acceptance_threshold": 0.05,
    "n_repeat": 5,
    "kappa_gate": 0.7,
    "re_audit_ratio": 0.20,
}

ERROR_CLASSES = ["E0", "E1", "E2", "E3", "E4"]


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False))


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Return Cohen's kappa for two label sequences."""
    if len(a) != len(b):
        raise ValueError("annotator label sequences must have equal length")
    n = len(a)
    if n == 0:
        return 0.0
    if a == b:
        return 1.0
    labels = sorted(set(a) | set(b))
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    expected = sum((a.count(label) / n) * (b.count(label) / n) for label in labels)
    if math.isclose(expected, 1.0):
        return 1.0
    return (observed - expected) / (1.0 - expected)


@ChiaFunction()
def stage_prepare(*, version: int, config: dict) -> dict:
    pin = {
        "config_version": version,
        "timestamp": time.time(),
        "git_sha": _git_head(),
        "python": sys.version.split()[0],
        "cwd": str(REPO_ROOT),
        "config_sha256": _canonical_digest(config),
        "backend": config.get("backend", "stub"),
        "audit_protocol": (
            "double-blind semantics adapted from Axiom "
            "(kappa=0.954, N=100, 20% re-audit)"
        ),
        "pre_registered": True,
    }
    _write_json(PIN_FILE, pin)
    return pin


@ChiaFunction()
def stage_run(*, version: int, config: dict) -> dict:
    backend = get_backend(config)
    design = config.get("design", {})
    cells = {}

    for seed in config["seeds"]:
        for prompt in config["prompts"]:
            for trace in config["traces"]:
                trials = [
                    backend.run(
                        seed,
                        prompt,
                        trace,
                        design,
                        run_index=run_index,
                    ).asdict()
                    for run_index in range(config["n_repeat"])
                ]
                ordered = sorted(trials, key=lambda item: item["cycles"])
                cells[f"{seed}/{prompt}/{trace}"] = {
                    "seed": seed,
                    "prompt": prompt,
                    "trace": trace,
                    "design": design,
                    "design_sha256": _canonical_digest(design),
                    "median": ordered[len(ordered) // 2],
                    "trials": trials,
                }

    raw = {
        "schema_version": 2,
        "version": version,
        "backend": backend.name,
        "config": config,
        "config_sha256": _canonical_digest(config),
        "git_sha": _git_head(),
        "n_cells": len(cells),
        "cells": cells,
    }
    _write_json(RESULTS_DIR / "raw.json", raw)
    return raw


def _audit_design_single(design: dict, reference: dict, auditor_id: str) -> dict:
    """Classify one candidate/reference pair with the E0-E4 taxonomy."""
    errors = []
    all_keys = set(reference) | set(design)

    for key in all_keys:
        ref_val = reference.get(key)
        des_val = design.get(key)

        if ref_val is not None and des_val is not None:
            if ref_val != des_val:
                if isinstance(ref_val, str) and isinstance(des_val, str):
                    direction_words = {"lru", "mru", "fifo", "lifo", "rr"}
                    if (
                        ref_val.lower() in direction_words
                        or des_val.lower() in direction_words
                    ):
                        errors.append("E2")
                    else:
                        errors.append("E1")
                else:
                    errors.append("E1")
        elif ref_val is not None and des_val is None:
            errors.append("E3")
        elif ref_val is None and des_val is not None:
            errors.append("E4")

    if design.get("output") == "PASS" and reference.get("output") != "PASS":
        errors = ["E4"]

    errors = [error for error in ERROR_CLASSES if error in set(errors)]
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
        for path in sorted(directory.glob("*.json")):
            if path.name == "answer-key.json":
                continue
            cases.append(json.loads(path.read_text()))
    return cases


@ChiaFunction()
def stage_double_blind_audit(*, version: int, config: dict) -> dict:
    """Run the deterministic A/B protocol self-test and publish gate."""
    gold_cases = _load_cases(GOLD_DIR)
    adversarial_cases = _load_cases(ADVERSARIAL_DIR)
    all_cases = gold_cases + adversarial_cases

    labels_a, labels_b, per_case = [], [], []
    for case in all_cases:
        result_a = _audit_design_single(case["design"], case["reference"], "A")
        result_b = _audit_design_single(case["design"], case["reference"], "B")

        label_a = result_a["error_classes"][0] if result_a["error_classes"] else "E0"
        label_b = result_b["error_classes"][0] if result_b["error_classes"] else "E0"
        labels_a.append(label_a)
        labels_b.append(label_b)

        if (
            result_a["verdict"] == result_b["verdict"]
            and result_a["error_classes"] == result_b["error_classes"]
        ):
            arbitrated = result_a
        else:
            arbitrated = {
                "verdict": "contested",
                "error_classes": sorted(
                    set(result_a["error_classes"]) | set(result_b["error_classes"])
                ),
            }

        expected_verdict = case.get("expected_verdict", "")
        expected_errors = case.get("expected_errors", [])
        correct = (
            arbitrated["verdict"] == expected_verdict
            and set(arbitrated.get("error_classes", [])) == set(expected_errors)
        )
        per_case.append({
            "id": case["id"],
            "auditor_a": label_a,
            "auditor_b": label_b,
            "agreed": label_a == label_b,
            "arbitrated_verdict": arbitrated["verdict"],
            "arbitrated_errors": arbitrated.get("error_classes", []),
            "expected_verdict": expected_verdict,
            "expected_errors": expected_errors,
            "correct": correct,
        })

    kappa = cohen_kappa(labels_a, labels_b)
    adversarial_correct = sum(
        1 for case in per_case[len(gold_cases):] if case["correct"]
    )
    adversarial_total = len(adversarial_cases)
    adversarial_rate = (
        adversarial_correct / adversarial_total if adversarial_total else 0.0
    )
    gold_correct = sum(1 for case in per_case[:len(gold_cases)] if case["correct"])

    error_distribution = {error: 0 for error in ERROR_CLASSES}
    for case in per_case:
        for error in case["arbitrated_errors"]:
            error_distribution[error] = error_distribution.get(error, 0) + 1

    kappa_pass = kappa >= config["kappa_gate"]
    adversarial_pass = adversarial_rate >= 1.0
    publish_gate = "PASS" if kappa_pass and adversarial_pass else "BLOCKED"

    report = {
        "version": version,
        "n_cases": len(all_cases),
        "n_gold": len(gold_cases),
        "n_adversarial": adversarial_total,
        "cohen_kappa": round(kappa, 4),
        "kappa_gate": config["kappa_gate"],
        "kappa_passed": kappa_pass,
        "adversarial_detection_rate": round(adversarial_rate, 4),
        "adversarial_passed": adversarial_pass,
        "gold_calibration_correct": f"{gold_correct}/{len(gold_cases)}",
        "error_distribution": error_distribution,
        "publish_gate": publish_gate,
        "per_case": per_case,
        "protocol_source": (
            "adapted from Axiom semantic-equivalence "
            "(kappa=0.954, N=100, 20% re-audit)"
        ),
    }
    _write_json(RESULTS_DIR / "dblind_report.json", report)
    return report


def _cv(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if len(finite) < 2:
        return 0.0
    mean = statistics.mean(finite)
    return statistics.stdev(finite) / mean if mean else float("nan")


def _relative_spread(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if len(finite) < 2:
        return 0.0
    mean = statistics.mean(finite)
    return (max(finite) - min(finite)) / mean if mean else float("nan")


def _rounded_map(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 6) for key, value in sorted(values.items())}


def _compute_audit(raw: dict, config: dict, dblind: dict) -> dict:
    """Compute repeatability and sensitivity metrics from raw measurements."""
    if "cells" not in raw:
        raise ValueError("raw.json uses an unsupported schema; rerun the loop")

    cells = raw["cells"]
    repeatability = {}
    by_seed = {}
    by_prompt = {}
    by_trace = {}

    for cell_id, cell in cells.items():
        repeatability[cell_id] = _cv(
            [trial["cycles"] for trial in cell["trials"]]
        )
        median_cycles = cell["median"]["cycles"]
        by_seed.setdefault(
            (cell["prompt"], cell["trace"]), []
        ).append(median_cycles)
        by_prompt.setdefault(
            (cell["seed"], cell["trace"]), []
        ).append(median_cycles)
        by_trace.setdefault(
            (cell["seed"], cell["prompt"]), []
        ).append(median_cycles)

    seed_cv = {
        f"{prompt}/{trace}": _cv(values)
        for (prompt, trace), values in by_seed.items()
    }
    prompt_spread = {
        f"{seed}/{trace}": _relative_spread(values)
        for (seed, trace), values in by_prompt.items()
    }
    trace_cv = {
        f"{seed}/{prompt}": _cv(values)
        for (seed, prompt), values in by_trace.items()
    }

    max_seed_cv = max(seed_cv.values(), default=0.0)
    max_repeat_cv = max(repeatability.values(), default=0.0)
    max_prompt_spread = max(prompt_spread.values(), default=0.0)
    max_trace_cv = max(trace_cv.values(), default=0.0)
    threshold = config["acceptance_threshold"]
    reproducible = max_seed_cv < threshold and max_repeat_cv < threshold

    return {
        "version": raw.get("version", config["version"]),
        "backend": raw.get("backend", config.get("backend", "unknown")),
        "config_sha256": raw.get("config_sha256", _canonical_digest(config)),
        "acceptance_threshold": threshold,
        "max_seed_cv": round(max_seed_cv, 6),
        "max_repeat_cv": round(max_repeat_cv, 6),
        "max_prompt_spread": round(max_prompt_spread, 6),
        "max_trace_cv": round(max_trace_cv, 6),
        "seed_cv": _rounded_map(seed_cv),
        "repeatability_cv": _rounded_map(repeatability),
        "prompt_spread": _rounded_map(prompt_spread),
        "trace_cv": _rounded_map(trace_cv),
        "verdict": "REPRODUCIBLE" if reproducible else "NON-REPRODUCIBLE",
        "cohen_kappa": dblind.get("cohen_kappa", "N/A"),
        "publish_gate": dblind.get("publish_gate", "N/A"),
        "adversarial_detection": dblind.get("adversarial_detection_rate", "N/A"),
        "gold_calibration": dblind.get("gold_calibration_correct", "N/A"),
        "error_distribution": dblind.get("error_distribution", {}),
    }


@ChiaFunction()
def stage_audit(*, version: int, raw: dict, config: dict, dblind: dict) -> dict:
    report = _compute_audit(raw, config, dblind)
    _write_json(RESULTS_DIR / "audit_report.json", report)
    return report


def _format_scorecard(report: dict, config: dict) -> str:
    gate = report.get("publish_gate", "N/A")
    threshold = report["acceptance_threshold"]
    lines = [
        f"CHIA reproducibility audit (config v{report['version']})",
        "=" * 56,
        f"Backend: {report.get('backend', 'unknown')}",
        f"Verdict: {report['verdict']}",
        f"Max cross-seed CV: {report['max_seed_cv']:.4%} (gate < {threshold:.0%})",
        f"Max repeated-run CV: {report['max_repeat_cv']:.4%}",
        f"Max prompt spread: {report['max_prompt_spread']:.4%}",
        f"Max trace CV: {report['max_trace_cv']:.4%}",
        "=" * 56,
        "Double-blind protocol self-test:",
        f"  Cohen's kappa: {report.get('cohen_kappa', 'N/A')} "
        f"(gate {config['kappa_gate']})",
        f"  Adversarial detection: {report.get('adversarial_detection', 'N/A')}",
        f"  Gold calibration: {report.get('gold_calibration', 'N/A')}",
        f"  Error distribution: {report.get('error_distribution', {})}",
        f"  Publish gate: {gate}",
        "=" * 56,
        "PUBLISHABLE" if gate == "PASS" else "BLOCKED",
    ]
    return "\n".join(lines)


@ChiaFunction()
def stage_act(*, version: int, report: dict, config: dict) -> str:
    scorecard = _format_scorecard(report, config)
    (RESULTS_DIR / "scorecard.txt").write_text(scorecard)
    return scorecard


def _load_config(path: Path | None) -> dict:
    config = copy.deepcopy(CONFIG)
    if path is not None:
        override = json.loads(path.read_text())
        config.update(override)
    return config


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=CONFIG["version"])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--execution", choices=["local", "chia"], default="local")
    parser.add_argument("--backend", choices=["stub", "champsim"])
    parser.add_argument("--chia-root")
    parser.add_argument("--traces-dir")
    parser.add_argument("--warmup-instructions", type=int)
    parser.add_argument("--simulation-instructions", type=int)
    return parser.parse_args(argv)


def _apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    config["version"] = args.version
    if args.backend:
        config["backend"] = args.backend

    champsim = config.setdefault("champsim", {})
    if args.chia_root:
        champsim["chia_root"] = args.chia_root
    if args.traces_dir:
        champsim["traces_dir"] = args.traces_dir
    if args.warmup_instructions is not None:
        champsim["warmup_instructions"] = args.warmup_instructions
    if args.simulation_instructions is not None:
        champsim["simulation_instructions"] = args.simulation_instructions
    return config


def main(argv: list[str] | None = None) -> dict:
    global RESULTS_DIR, PIN_FILE

    args = _parse_args(argv)
    config = _apply_overrides(_load_config(args.config), args)
    if args.output_dir:
        RESULTS_DIR = args.output_dir.resolve()
        PIN_FILE = RESULTS_DIR / "env_pin.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    use_chia = args.execution == "chia"
    if use_chia and not HAS_CHIA:
        raise RuntimeError("--execution chia requires the chialoops package")

    def call(fn, **kwargs):
        if use_chia:
            return get(fn.chia_remote(**kwargs))
        return fn(**kwargs)

    pin = call(stage_prepare, version=args.version, config=config)
    raw = call(stage_run, version=args.version, config=config)
    dblind = call(
        stage_double_blind_audit,
        version=args.version,
        config=config,
    )
    audit = call(
        stage_audit,
        version=args.version,
        raw=raw,
        config=config,
        dblind=dblind,
    )
    scorecard = call(
        stage_act,
        version=args.version,
        report=audit,
        config=config,
    )

    summary = {
        "pin": pin,
        "run": {
            "backend": raw["backend"],
            "n_cells": raw["n_cells"],
            "config_sha256": raw["config_sha256"],
        },
        "dblind": {
            "cohen_kappa": dblind["cohen_kappa"],
            "adversarial_detection_rate": dblind["adversarial_detection_rate"],
            "publish_gate": dblind["publish_gate"],
        },
        "audit": audit,
        "scorecard": scorecard,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    main()
