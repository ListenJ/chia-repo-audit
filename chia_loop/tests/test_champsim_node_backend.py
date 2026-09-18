from __future__ import annotations

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
            return SimpleNamespace(success=True, cycles=1234, ipc=0.42)

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
        self.assertTrue(math.isnan(result.l1_miss_rate))


if __name__ == "__main__":
    unittest.main()
