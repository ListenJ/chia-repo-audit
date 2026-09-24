from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "chia_loop" / "loops" / "audit_repro.py"

spec = importlib.util.spec_from_file_location("audit_repro", SCRIPT)
assert spec and spec.loader
audit_repro = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit_repro
spec.loader.exec_module(audit_repro)


class AuditMetricTests(unittest.TestCase):
    def test_cohen_kappa_for_perfect_agreement(self):
        self.assertEqual(
            audit_repro.cohen_kappa(["E0", "E1", "E2"], ["E0", "E1", "E2"]),
            1.0,
        )

    def test_metric_groups_are_separated(self):
        raw = {
            "schema_version": 2,
            "version": 4,
            "backend": "stub",
            "config_sha256": "test",
            "cells": {},
        }
        for seed in (0, 1):
            for prompt_index, prompt in enumerate(("default", "cot")):
                for trace_index, trace in enumerate(("trace-a", "trace-b")):
                    base = 1000 + seed * 100 + prompt_index * 10 + trace_index
                    key = f"{seed}/{prompt}/{trace}"
                    raw["cells"][key] = {
                        "seed": seed,
                        "prompt": prompt,
                        "trace": trace,
                        "design": {},
                        "design_sha256": "design",
                        "median": {"cycles": base},
                        "trials": [
                            {"cycles": base - 1},
                            {"cycles": base},
                            {"cycles": base + 1},
                        ],
                    }

        report = audit_repro._compute_audit(
            raw,
            {"acceptance_threshold": 0.20, "version": 4},
            {"publish_gate": "PASS"},
        )

        self.assertGreater(report["max_seed_cv"], report["max_prompt_spread"])
        self.assertGreater(report["max_repeat_cv"], 0)
        self.assertEqual(report["verdict"], "REPRODUCIBLE")

    def test_single_level_axis_cannot_pass_the_gate(self):
        # A one-seed grid reports cross-seed CV of exactly 0.0000% because there is
        # nothing to vary, which used to satisfy the <5% gate and print PUBLISHABLE.
        raw = {
            "schema_version": 2, "version": 6, "backend": "stub", "config_sha256": "t",
            "cells": {},
        }
        for prompt_index, prompt in enumerate(("aggressive_offset", "default")):
            for trace_index, trace in enumerate(("trace-a", "trace-b")):
                base = 1000 + prompt_index * 10 + trace_index
                raw["cells"][f"1/{prompt}/{trace}"] = {
                    "seed": 1, "generator_seed": 1, "prompt": prompt, "trace": trace,
                    "design": {}, "design_sha256": "d",
                    "median": {"cycles": base},
                    "trials": [{"cycles": base}, {"cycles": base}],
                }
        report = audit_repro._compute_audit(
            raw, {"acceptance_threshold": 0.05, "version": 6},
            {"publish_gate": "PASS"})
        self.assertEqual(report["max_seed_cv"], 0.0)
        self.assertEqual(report["unexercised_axes"], ["seed"])
        self.assertEqual(report["verdict"], "NON-REPRODUCIBLE")
        self.assertEqual(report["publish_gate"], "BLOCKED")
        self.assertIn("axis_not_exercised:seed", report["publish_blockers"])

    def test_error_taxonomy(self):
        result = audit_repro._audit_design_single(
            {"cache_size": "32KB", "replacement": "MRU"},
            {"cache_size": "64KB", "replacement": "LRU"},
            "A",
        )
        self.assertEqual(result["verdict"], "not_equivalent")
        self.assertEqual(result["error_classes"], ["E1", "E2"])

    def test_candidate_generation_tracks_seed_and_prompt(self):
        config = {
            "generator_mode": "catalog",
            "candidate_catalog": [
                {"candidate_id": "a", "generator_seed": 0, "prompt": "default",
                 "design": {"replacement": "LRU"}},
                {"candidate_id": "b", "generator_seed": 1, "prompt": "cot",
                 "design": {"replacement": "MRU"}},
            ],
        }

        first = audit_repro.generate_candidate(config, seed=0, prompt="default")
        second = audit_repro.generate_candidate(config, seed=1, prompt="cot")

        self.assertEqual(first["candidate_id"], "a")
        self.assertEqual(second["candidate_id"], "b")
        self.assertEqual(first["generator_seed"], 0)
        self.assertEqual(second["prompt"], "cot")
        self.assertEqual(len(first["candidate_sha256"]), 64)

    def test_missing_cell_is_refused_instead_of_substituted(self):
        """A factor level with no candidate must fail closed, not borrow one.

        The harness used to fall back to the whole pool whenever the requested
        (seed, prompt) pair was absent, then stamp the missing labels onto whatever
        it picked. One published grid reported a cross-seed CV computed partly by
        re-running a single design under four different names.
        """
        config = {
            "generator_mode": "catalog",
            "candidate_catalog": [
                {"candidate_id": "a", "generator_seed": 0, "prompt": "default",
                 "design": {"replacement": "LRU"}},
                {"candidate_id": "b", "generator_seed": 1, "prompt": "default",
                 "design": {"replacement": "MRU"}},
            ],
        }

        with self.assertRaises(ValueError) as caught:
            audit_repro.generate_candidate(config, seed=7, prompt="cot")

        message = str(caught.exception)
        self.assertIn("cot", message)
        self.assertIn("0/default", message)
        self.assertIn("1/default", message)

    def test_directory_generator_loads_agent_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "candidate.json"
            path.write_text(json.dumps({
                "candidate_id": "agent-001",
                "generator_seed": 3,
                "prompt": "cot",
                "design": {"prefetcher_source": "struct agent {};"},
            }))

            candidate = audit_repro.generate_candidate(
                {
                    "generator_mode": "directory",
                    "candidates_dir": tmpdir,
                },
                seed=3,
                prompt="cot",
            )

        self.assertEqual(candidate["candidate_id"], "agent-001")
        self.assertIn("prefetcher_source", candidate["design"])

    def test_non_reproducible_result_blocks_publish(self):
        report = {
            "version": 4,
            "backend": "champsim",
            "acceptance_threshold": 0.05,
            "max_seed_cv": 0.50,
            "max_repeat_cv": 0.0,
            "max_prompt_spread": 0.0,
            "max_trace_cv": 0.0,
            "verdict": "NON-REPRODUCIBLE",
            "cohen_kappa": 1.0,
            "publish_gate": "BLOCKED",
            "adversarial_detection": 1.0,
            "gold_calibration": "5/5",
            "error_distribution": {},
        }

        scorecard = audit_repro._format_scorecard(report, {"kappa_gate": 0.7})

        self.assertIn("BLOCKED", scorecard)
        self.assertNotIn("PUBLISHABLE", scorecard)

    def test_ranking_stability_detects_trace_rank_flip(self):
        cells = {}
        for candidate_id, trace_values in {
            "a": {"t1": 100, "t2": 400, "t3": 100},
            "b": {"t1": 150, "t2": 200, "t3": 200},
        }.items():
            for trace, cycles in trace_values.items():
                key = f"{candidate_id}/{trace}"
                cells[key] = {
                    "candidate_id": candidate_id,
                    "trace": trace,
                    "median": {"cycles": cycles},
                    "trials": [{"cycles": cycles}],
                }

        result = audit_repro._trace_ranking_stability(cells)

        self.assertEqual(result["n_candidates"], 2)
        self.assertEqual(result["full_top_candidate"], "b")
        self.assertLess(result["top1_stability"], 1.0)

    def test_single_candidate_ranking_is_unrankable_not_zero(self):
        cells = {}
        for trace, cycles in {"t1": 100, "t2": 400, "t3": 250}.items():
            cells[f"only/{trace}"] = {
                "candidate_id": "only",
                "trace": trace,
                "median": {"cycles": cycles},
                "trials": [{"cycles": cycles}],
            }

        result = audit_repro._trace_ranking_stability(cells)

        self.assertFalse(result["rankable"])
        self.assertEqual(result["unrankable_reason"], "fewer_than_two_candidates")
        self.assertEqual(result["n_traces"], 0)

        report = {
            "version": 6,
            "backend": "champsim_node",
            "acceptance_threshold": 0.05,
            "max_seed_cv": 0.0,
            "max_repeat_cv": 0.0,
            "max_prompt_spread": 0.0,
            "max_trace_cv": 0.64,
            "verdict": "NON-REPRODUCIBLE",
            "cohen_kappa": 1.0,
            "publish_gate": "BLOCKED",
            "publish_blockers": ["axis_not_exercised:prompt,seed"],
            "adversarial_detection": 1.0,
            "gold_calibration": "5/5",
            "error_distribution": {},
            "ranking_stability": result,
        }
        scorecard = audit_repro._format_scorecard(report, {"kappa_gate": 0.7})

        self.assertIn("unrankable (fewer_than_two_candidates)", scorecard)
        self.assertNotIn("Kendall tau: 0.0", scorecard)


class AuditCliTests(unittest.TestCase):
    def test_stub_cli_emits_versioned_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--version",
                    "4",
                    "--output-dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(completed.stdout)
            output_dir = Path(tmpdir)

            self.assertEqual(summary["audit"]["backend"], "stub")
            self.assertEqual(summary["audit"]["verdict"], "REPRODUCIBLE")
            self.assertEqual(summary["dblind"]["publish_gate"], "PASS")
            self.assertEqual(summary["run"]["n_cells"], 27)
            self.assertTrue((output_dir / "raw.json").is_file())
            self.assertTrue((output_dir / "audit_report.json").is_file())
            self.assertTrue((output_dir / "scorecard.txt").is_file())

            raw = json.loads((output_dir / "raw.json").read_text())
            first_cell = next(iter(raw["cells"].values()))
            self.assertEqual(len(first_cell["trials"]), 5)
            self.assertEqual(raw["config"]["version"], 4)


if __name__ == "__main__":
    unittest.main()
