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

    def test_error_taxonomy(self):
        result = audit_repro._audit_design_single(
            {"cache_size": "32KB", "replacement": "MRU"},
            {"cache_size": "64KB", "replacement": "LRU"},
            "A",
        )
        self.assertEqual(result["verdict"], "not_equivalent")
        self.assertEqual(result["error_classes"], ["E1", "E2"])


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
