from __future__ import annotations

import hashlib
import math
import unittest
from pathlib import Path
from types import SimpleNamespace

from chia_loop.sim.backends import ChampSimNodeBackend


class ChampSimNodeBackendTests(unittest.TestCase):
    def test_uses_official_contract_without_requiring_ray(self):
        calls = {}

        def build_runner(champsim_root, source, module, **kwargs):
            calls["build"] = {
                "champsim_root": champsim_root,
                "source": source,
                "module": module,
                "kwargs": kwargs,
            }
            return SimpleNamespace(binary=b"compiled", success=True)

        def run_runner(binary, trace, **kwargs):
            calls["run"] = {"binary": binary, "trace": trace, "kwargs": kwargs}
            return SimpleNamespace(success=True, cycles=1234, ipc=0.42,
                                   instructions=5_000_001)

        backend = ChampSimNodeBackend(
            champsim_root="/tmp/champsim",
            traces_dir="/tmp/traces",
            build_runner=build_runner,
            run_runner=run_runner,
        )
        result = backend.run(
            seed=7,
            prompt="cot",
            trace="trace-a",
            design={
                "prefetcher_source": "struct candidate {};",
                "module_name": "candidate",
            },
        )

        self.assertEqual(calls["build"]["module"], "candidate")
        self.assertEqual(calls["run"]["binary"], b"compiled")
        self.assertEqual(calls["run"]["trace"], Path("/tmp/traces/trace-a"))
        self.assertEqual(result.cycles, 1234)
        self.assertEqual(result.ipc, 0.42)
        self.assertEqual(result.instructions, 5_000_001)
        self.assertTrue(math.isnan(result.l1_miss_rate))

    def test_builds_once_per_design_and_never_requests_a_cached_binary(self):
        builds, runs = [], []

        def build_runner(champsim_root, source, module, **kwargs):
            builds.append({"module": module, "incremental": kwargs["incremental"]})
            return SimpleNamespace(binary=module.encode(), success=True)

        def run_runner(binary, trace, **kwargs):
            runs.append((binary, str(trace)))
            return SimpleNamespace(success=True, cycles=1, ipc=0.5)

        backend = ChampSimNodeBackend(
            champsim_root="/tmp/champsim",
            traces_dir="/tmp/traces",
            build_runner=build_runner,
            run_runner=run_runner,
        )
        design_a = {"prefetcher_source": "struct a {};", "module_name": "a"}
        design_b = {"prefetcher_source": "struct b {};", "module_name": "b"}
        results = []
        for trace in ("t1", "t2"):
            results.append(
                backend.run(seed=0, prompt="default", trace=trace, design=design_a))
        results.append(
            backend.run(seed=0, prompt="default", trace="t1", design=design_b))

        self.assertEqual([b["module"] for b in builds], ["a", "b"])
        self.assertEqual([b["incremental"] for b in builds], [False, False])
        self.assertEqual([binary for binary, _ in runs], [b"a", b"a", b"b"])
        # Gate 2 is checked from the artifact itself, so every measurement has to
        # name the binary it was taken with.
        self.assertEqual(
            [result.binary_sha256 for result in results],
            [hashlib.sha256(b"a").hexdigest()[:16]] * 2
            + [hashlib.sha256(b"b").hexdigest()[:16]],
        )


if __name__ == "__main__":
    unittest.main()
