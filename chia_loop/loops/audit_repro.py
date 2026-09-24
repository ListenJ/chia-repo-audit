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
_STUB_DESIGNS = [
    ("lru_reference", "lru"),
    ("mru_variant", "mru"),
    ("fifo_variant", "fifo"),
    ("srrip_variant", "srrip"),
]
_STUB_SEEDS = [0, 1, 2]
_STUB_PROMPTS = ["default", "cot", "adversarial"]


def _stub_catalog() -> list[dict]:
    """Enumerate every (seed, prompt) cell the stub grid asks for, one per entry.

    generate_candidate() refuses a pair that is absent from the pool, so a fixture
    that wants a 3x3 rectangle has to declare 9 labelled candidates rather than 4
    designs the harness would be free to reinterpret. The seed and prompt spreads
    this produces are fixture arithmetic -- StubBackend adds 37 counts per seed and
    a fixed bias per prompt -- so they exercise the bookkeeping and the gate, and
    are not evidence about any generator's variance.
    """
    catalog = []
    for prompt_index, prompt in enumerate(_STUB_PROMPTS):
        for seed in _STUB_SEEDS:
            name, replacement = _STUB_DESIGNS[(prompt_index + seed) % len(_STUB_DESIGNS)]
            catalog.append({
                "candidate_id": f"{name}-{prompt}-s{seed}",
                "generator_seed": seed,
                "prompt": prompt,
                "design": {"llc_replacement": replacement,
                           "branch_predictor": "bimodal"},
            })
    return catalog


CONFIG = {
    "version": 5,
    "backend": "stub",
    "generator_mode": "catalog",
    "candidate_catalog": _stub_catalog(),
    "seeds": _STUB_SEEDS,
    "prompts": _STUB_PROMPTS,
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


def _load_candidate_directory(directory: Path) -> list[dict]:
    candidates = []
    for path in sorted(directory.glob("*.json")):
        if path.name == "answer-key.json":
            continue
        candidate = json.loads(path.read_text())
        candidate.setdefault("candidate_id", candidate.get("id", path.stem))
        if "design" not in candidate:
            raise ValueError(f"Candidate {path} is missing 'design'")
        candidates.append(candidate)
    if not candidates:
        raise ValueError(f"No candidate JSON files found in {directory}")
    return candidates


def generate_candidate(config: dict, *, seed: int, prompt: str) -> dict:
    """Select or load the candidate artifact for one generation cell.

    The catalog mode is an offline fixture generator. ``directory`` mode is
    the pre-compute integration point for candidates emitted by Gemini or
    another LLM agent.
    """
    mode = config.get("generator_mode", "catalog")
    if mode == "catalog":
        candidates = config.get("candidate_catalog", [])
    elif mode == "directory":
        candidates_dir = config.get("candidates_dir")
        if not candidates_dir:
            raise ValueError("directory generator requires candidates_dir")
        candidates = _load_candidate_directory(Path(candidates_dir))
    else:
        raise ValueError(f"Unknown generator_mode: {mode}")

    if not candidates:
        raise ValueError("Candidate pool is empty")

    matching = [
        candidate
        for candidate in candidates
        if candidate.get("generator_seed") == seed
        and candidate.get("prompt") == prompt
    ]
    if not matching:
        # This used to fall back to the whole pool and pick one by a hash of the prompt,
        # then stamp the missing seed/prompt labels onto it. The cell looked like a real
        # factor level, the recomputed candidate_sha256 looked like provenance, and a
        # grid reported a cross-seed CV measured partly by re-running one design under
        # several names. A missing candidate is a missing cell, not a free choice.
        raise ValueError(
            f"no candidate in the pool for seed={seed} prompt={prompt!r}; pool offers "
            + ", ".join(sorted({f"{c.get('generator_seed')}/{c.get('prompt')}"
                                for c in candidates})))
    prompt_offset = int(
        hashlib.sha256(prompt.encode()).hexdigest()[:8],
        16,
    )
    candidate = copy.deepcopy(matching[(seed + prompt_offset) % len(matching)])
    candidate.setdefault("candidate_id", f"candidate-{seed}-{prompt}")
    candidate.setdefault("generator_seed", seed)
    candidate.setdefault("prompt", prompt)
    candidate["candidate_sha256"] = _canonical_digest({
        key: value
        for key, value in candidate.items()
        if key != "candidate_sha256"
    })
    return candidate


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
    cells = {}

    for seed in config["seeds"]:
        for prompt in config["prompts"]:
            candidate = generate_candidate(config, seed=seed, prompt=prompt)
            design = candidate["design"]
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
                    "candidate_id": candidate["candidate_id"],
                    "candidate_sha256": candidate["candidate_sha256"],
                    "generator_seed": candidate["generator_seed"],
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
        "n_candidates": len({
            cell["candidate_id"] for cell in cells.values()
        }),
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


def _rank_scores(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda candidate_id: (
        scores[candidate_id],
        candidate_id,
    ))


def _kendall_tau(left: list[str], right: list[str]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 1.0
    right_position = {candidate_id: index for index, candidate_id in enumerate(right)}
    concordant = 0
    discordant = 0
    for left_index, left_id in enumerate(left):
        for right_id in left[left_index + 1:]:
            delta = right_position[left_id] - right_position[right_id]
            if delta < 0:
                concordant += 1
            elif delta > 0:
                discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total else 1.0


def _trace_ranking_stability(cells: dict) -> dict:
    """Compare full-trace rankings with leave-one-trace-out rankings."""
    observations = {}
    for cell_id, cell in cells.items():
        candidate_id = cell.get("candidate_id") or cell.get("design_sha256") or cell_id
        trace = cell.get("trace")
        if not trace:
            continue
        cycles = cell.get("median", {}).get("cycles")
        if cycles is None or not math.isfinite(float(cycles)):
            continue
        observations.setdefault(candidate_id, {}).setdefault(trace, []).append(
            float(cycles)
        )

    by_candidate_trace = {
        candidate_id: {
            trace: statistics.mean(values)
            for trace, values in trace_map.items()
        }
        for candidate_id, trace_map in observations.items()
    }

    if len(by_candidate_trace) < 2:
        return {
            "n_candidates": len(by_candidate_trace),
            "n_traces": 0,
            "full_top_candidate": None,
            # tau=0.0 here is a fill value: one candidate has nothing to rank.
            "rankable": False,
            "unrankable_reason": "fewer_than_two_candidates",
            "top1_stability": 0.0,
            "mean_kendall_tau": 0.0,
            "leave_one_out": [],
        }

    common_traces = set.intersection(*[
        set(trace_map) for trace_map in by_candidate_trace.values()
    ])
    eligible = {
        candidate_id: trace_map
        for candidate_id, trace_map in by_candidate_trace.items()
        if set(trace_map) == common_traces
    }
    if len(common_traces) < 2 or len(eligible) < 2:
        return {
            "n_candidates": len(eligible),
            "n_traces": len(common_traces),
            "full_top_candidate": None,
            "rankable": False,
            "unrankable_reason": "fewer_than_two_rankable",
            "top1_stability": 0.0,
            "mean_kendall_tau": 0.0,
            "leave_one_out": [],
        }

    full_scores = {
        candidate_id: statistics.mean(trace_map.values())
        for candidate_id, trace_map in eligible.items()
    }
    full_order = _rank_scores(full_scores)
    leave_one_out = []
    for held_out_trace in sorted(common_traces):
        remaining_traces = sorted(common_traces - {held_out_trace})
        subset_scores = {
            candidate_id: statistics.mean(
                trace_map[trace] for trace in remaining_traces
            )
            for candidate_id, trace_map in eligible.items()
        }
        subset_order = _rank_scores(subset_scores)
        leave_one_out.append({
            "held_out_trace": held_out_trace,
            "ranking": subset_order,
            "top_candidate": subset_order[0],
            "top1_matches_full": subset_order[0] == full_order[0],
            "kendall_tau": round(_kendall_tau(full_order, subset_order), 6),
        })

    return {
        "n_candidates": len(eligible),
        "n_traces": len(common_traces),
        "rankable": True,
        "full_ranking": full_order,
        "full_top_candidate": full_order[0],
        "full_scores": _rounded_map(full_scores),
        "top1_stability": round(
            sum(item["top1_matches_full"] for item in leave_one_out)
            / len(leave_one_out),
            6,
        ),
        "mean_kendall_tau": round(
            statistics.mean(item["kendall_tau"] for item in leave_one_out),
            6,
        ),
        "leave_one_out": leave_one_out,
    }


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

    # _cv and _relative_spread both return 0.0 when an axis has a single level, so a
    # one-seed grid used to "pass" the seed gate at 0.0000% without ever varying the
    # seed. An unexercised axis is not a passing axis.
    # Real cells carry both keys; fixtures may carry only "seed".
    n_seeds = len({c.get("generator_seed", c.get("seed")) for c in cells.values()})
    n_prompts = len({c.get("prompt") for c in cells.values()})
    n_traces = len({c.get("trace") for c in cells.values()})
    n_repeat = min((len(c.get("trials", [])) for c in cells.values()), default=0)
    axes = {
        "seed": n_seeds >= 2,
        "prompt": n_prompts >= 2,
        "trace": n_traces >= 2,
        "repeat": n_repeat >= 2,
    }
    unexercised = sorted(name for name, ok in axes.items() if not ok)

    reproducible = (axes["seed"] and max_seed_cv < threshold
                    and axes["repeat"] and max_repeat_cv < threshold)
    audit_passed = dblind.get("publish_gate") == "PASS"
    publish_blockers = []
    if unexercised:
        publish_blockers.append("axis_not_exercised:" + ",".join(unexercised))
    if not reproducible:
        publish_blockers.append("reproducibility_threshold")
    if not audit_passed:
        publish_blockers.append("audit_gate")
    publish_gate = "PASS" if not publish_blockers else "BLOCKED"
    ranking_stability = _trace_ranking_stability(cells)

    return {
        "version": raw.get("version", config["version"]),
        "backend": raw.get("backend", config.get("backend", "unknown")),
        "config_sha256": raw.get("config_sha256", _canonical_digest(config)),
        "acceptance_threshold": threshold,
        "axis_levels": {"seed": n_seeds, "prompt": n_prompts, "trace": n_traces,
                        "repeat_min": n_repeat},
        "axes_measured": axes,
        "unexercised_axes": unexercised,
        "max_seed_cv": round(max_seed_cv, 6),
        "max_repeat_cv": round(max_repeat_cv, 6),
        "max_prompt_spread": round(max_prompt_spread, 6),
        "max_trace_cv": round(max_trace_cv, 6),
        "seed_cv": _rounded_map(seed_cv),
        "repeatability_cv": _rounded_map(repeatability),
        "prompt_spread": _rounded_map(prompt_spread),
        "trace_cv": _rounded_map(trace_cv),
        "ranking_stability": ranking_stability,
        "verdict": "REPRODUCIBLE" if reproducible else "NON-REPRODUCIBLE",
        "cohen_kappa": dblind.get("cohen_kappa", "N/A"),
        "publish_gate": publish_gate,
        "publish_blockers": publish_blockers,
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
    gate = (
        "PASS"
        if report.get("publish_gate") == "PASS"
        and report.get("verdict") == "REPRODUCIBLE"
        else "BLOCKED"
    )
    threshold = report["acceptance_threshold"]
    ranking_stability = report.get("ranking_stability", {})
    if ranking_stability.get("rankable", True):
        top1_line = (f"Trace top-1 stability: "
                     f"{ranking_stability.get('top1_stability', 'N/A')}")
        tau_line = (f"Trace ranking Kendall tau: "
                    f"{ranking_stability.get('mean_kendall_tau', 'N/A')}")
    else:
        why = ranking_stability.get("unrankable_reason", "unknown")
        top1_line = f"Trace top-1 stability: unrankable ({why})"
        tau_line = f"Trace ranking Kendall tau: unrankable ({why})"
    lines = [
        f"CHIA reproducibility audit (config v{report['version']})",
        "=" * 56,
        f"Backend: {report.get('backend', 'unknown')}",
        f"Verdict: {report['verdict']}",
        f"Max cross-seed CV: {report['max_seed_cv']:.4%} (gate < {threshold:.0%})",
        f"Max repeated-run CV: {report['max_repeat_cv']:.4%}",
        f"Max prompt spread: {report['max_prompt_spread']:.4%} (max-min)/mean",
        f"Max trace CV: {report['max_trace_cv']:.4%}",
        f"Axis levels: seed={report.get('axis_levels', {}).get('seed')} "
        f"prompt={report.get('axis_levels', {}).get('prompt')} "
        f"trace={report.get('axis_levels', {}).get('trace')} "
        f"repeat>={report.get('axis_levels', {}).get('repeat_min')}",
        f"Unexercised axes: "
        f"{','.join(report.get('unexercised_axes', [])) or 'none'}",
        top1_line,
        tau_line,
        "=" * 56,
        "Double-blind protocol self-test:",
        f"  Cohen's kappa: {report.get('cohen_kappa', 'N/A')} "
        f"(gate {config['kappa_gate']})",
        f"  Adversarial detection: {report.get('adversarial_detection', 'N/A')}",
        f"  Gold calibration: {report.get('gold_calibration', 'N/A')}",
        f"  Error distribution: {report.get('error_distribution', {})}",
        f"  Publish gate: {gate}",
        f"  Publish blockers: {report.get('publish_blockers', [])}",
        "=" * 56,
        "PUBLISHABLE" if gate == "PASS" else "BLOCKED",
    ]
    return "\n".join(lines)


@ChiaFunction()
def stage_act(*, version: int, report: dict, config: dict) -> str:
    scorecard = _format_scorecard(report, config)
    (RESULTS_DIR / "scorecard.txt").write_text(scorecard + "\n")
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
    parser.add_argument(
        "--backend",
        choices=["stub", "champsim", "champsim_node"],
    )
    parser.add_argument(
        "--generator-mode",
        choices=["catalog", "directory"],
    )
    parser.add_argument("--candidates-dir")
    parser.add_argument("--chia-root")
    parser.add_argument("--traces-dir")
    parser.add_argument("--warmup-instructions", type=int)
    parser.add_argument("--simulation-instructions", type=int)
    return parser.parse_args(argv)


def _apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    config["version"] = args.version
    if args.backend:
        config["backend"] = args.backend
    if args.generator_mode:
        config["generator_mode"] = args.generator_mode
    if args.candidates_dir:
        config["candidates_dir"] = args.candidates_dir

    champsim = config.setdefault("champsim", {})
    champsim_node = config.setdefault("champsim_node", {})
    if args.chia_root:
        champsim["chia_root"] = args.chia_root
    if args.traces_dir:
        champsim["traces_dir"] = args.traces_dir
    if args.warmup_instructions is not None:
        champsim["warmup_instructions"] = args.warmup_instructions
    if args.simulation_instructions is not None:
        champsim["simulation_instructions"] = args.simulation_instructions
        champsim_node["simulation_instructions"] = args.simulation_instructions
    if args.chia_root:
        champsim_node["champsim_root"] = args.chia_root
    if args.traces_dir:
        champsim_node["traces_dir"] = args.traces_dir
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
            "n_candidates": raw["n_candidates"],
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
