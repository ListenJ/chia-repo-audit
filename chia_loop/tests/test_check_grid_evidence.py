import importlib.util
import json
import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "check_grid_evidence.py"
spec = importlib.util.spec_from_file_location("check_grid_evidence", MODULE)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

REFERENCE = [{"design": "noop", "runs": [{"trace": "/traces/t1.xz", "cycles": 1000.0}]},
             {"design": "next_line", "runs": [{"trace": "/traces/t1.xz", "cycles": 940.0}]}]


def raw_for(digest="a" * 16, cycles=980.0, backend="champsim_node", prompt="default",
            module="gen_default_s0", trial_cycles=None, instructions=5_000_001):
    trial = {"cycles": cycles, "ipc": 1.7, "instructions": instructions,
             "binary_sha256": digest}
    trials = [trial, dict(trial, cycles=cycles if trial_cycles is None else trial_cycles)]
    return {
        "schema_version": 2, "backend": backend, "git_sha": "abc",
        "config_sha256": "def",
        "cells": {f"0/{prompt}/t1.xz": {
            "seed": 0, "prompt": prompt, "trace": "t1.xz", "candidate_id": "c",
            "candidate_sha256": "x", "generator_seed": 0,
            "design": {"module_name": module, "prefetcher_source": "struct s {};"},
            "design_sha256": "y", "median": trial, "trials": trials}},
    }


class CheckGridEvidenceTest(unittest.TestCase):
    def test_a_real_distinct_binary_beating_the_reference_passes(self):
        out = check.verdicts(raw_for(), REFERENCE)
        self.assertEqual(out["failures"], {})
        self.assertTrue(out["passed"])
        self.assertEqual(out["n_distinct_binaries"], 1)

    def test_the_stub_backend_cannot_pass(self):
        out = check.verdicts(raw_for(backend="stub"), REFERENCE)
        self.assertIn("backend_is_real", out["failures"])
        self.assertFalse(out["passed"])

    def test_a_design_measured_with_the_image_default_binary_is_rejected(self):
        out = check.verdicts(raw_for(digest=check.IMAGE_DEFAULT_BINARY), REFERENCE)
        self.assertIn("not_the_image_default_binary", out["failures"])

    def test_a_candidate_that_equals_the_noop_cycle_count_does_not_count(self):
        out = check.verdicts(raw_for(cycles=1000.0), REFERENCE)
        self.assertIn("moves_cycles_vs_reference", out["failures"])

    def test_two_designs_sharing_one_binary_are_reported(self):
        raw = raw_for()
        raw["cells"].update(raw_for(digest="a" * 16, prompt="cot",
                                    module="gen_cot_s0")["cells"])
        out = check.verdicts(raw, REFERENCE)
        self.assertIn("one_design_per_binary", out["failures"])

    def test_a_missing_reference_is_an_explicit_failure_not_a_pass(self):
        out = check.verdicts(raw_for(), None)
        self.assertIn("reference_available", out["failures"])

    def test_an_unparsed_instruction_count_cannot_clear_the_smoke_floor(self):
        # NaN comparisons are always False, so a NaN must not slip through.
        out = check.verdicts(raw_for(instructions=float("nan")), REFERENCE)
        self.assertIn("above_smoke_floor", out["failures"])


if __name__ == "__main__":
    unittest.main()
