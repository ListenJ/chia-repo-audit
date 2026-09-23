"""锁定 nullity 判据的两种情形：每个 trace 都空 vs 只在一条 trace 上空。

原缺陷：checker 把两者都记成同一个失败项 `moves_cycles_vs_reference`，
于是"这个 prefetcher 在 imagick 上没起作用"（正常性质）与
"这个设计根本不做事"（模拟器逃逸）在报告里不可区分——论文自己把这一点列为缺陷。
"""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from check_grid_evidence import verdicts  # noqa: E402

TRACES = {"a": "traceA.champsimtrace.xz", "b": "traceB.champsimtrace.xz"}
NOOP = {"a": 1000, "b": 2000}


def raw(cycles_by_trace, design="gen_x"):
    return {
        "backend": "champsim_node",
        "git_sha": "deadbeef",
        "config_sha256": "abc",
        "cells": {
            f"{seed}/p/{TRACES[t]}": {
                "seed": seed, "prompt": "p", "trace": TRACES[t],
                "candidate_id": design, "candidate_sha256": "c1",
                "design": {"module_name": design}, "design_sha256": "d1",
                "median": {"cycles": c, "ipc": 1.0, "instructions": 5_000_000},
                "trials": [{"cycles": c, "binary_sha256": "bin1"}],
            } for (seed, t), c in cycles_by_trace.items()
        },
    }


REFERENCE = [{"design": "noop", "binary_sha256": "binref", "runs": [
    {"trace": TRACES[t], "cycles": c, "instructions": 5_000_000}
    for t, c in NOOP.items()]}]


class TestNullityClassification(unittest.TestCase):
    def test_equal_on_every_trace_is_a_hard_failure(self):
        v = verdicts(raw({(1, "a"): NOOP["a"], (1, "b"): NOOP["b"]}), REFERENCE)
        self.assertFalse(v["passed"])
        self.assertIn("null_on_every_measured_trace", _names(v))
        self.assertEqual(1, v["n_designs_null_on_every_trace"])
        self.assertEqual(0, v["n_designs_null_on_some_trace"])

    def test_equal_on_one_trace_only_is_reported_not_failed(self):
        v = verdicts(raw({(1, "a"): NOOP["a"], (1, "b"): 1900}), REFERENCE)
        self.assertTrue(v["passed"], v["failures"])
        self.assertNotIn("null_on_every_measured_trace", _names(v))
        self.assertEqual(0, v["n_designs_null_on_every_trace"])
        self.assertEqual(1, v["n_designs_null_on_some_trace"])
        self.assertIn("trace-dependent", v["nullity_notes"][0])

    def test_a_design_that_differs_everywhere_is_clean(self):
        v = verdicts(raw({(1, "a"): 1100, (1, "b"): 2100}), REFERENCE)
        self.assertTrue(v["passed"], v["failures"])
        self.assertEqual([], v["nullity_notes"])

    def test_missing_reference_is_still_a_failure(self):
        v = verdicts(raw({(1, "a"): 1100, (1, "b"): 2100}), [])
        self.assertFalse(v["passed"])
        self.assertIn("reference_available", _names(v))


def _names(v):
    return set(v["failures"])


if __name__ == "__main__":
    unittest.main()
