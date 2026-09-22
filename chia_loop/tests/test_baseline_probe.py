import contextlib
import importlib
import io
import json
import sys
import types
import unittest

RECORDER = {"builds": [], "runs": []}


class Remote:
    def __init__(self, kind):
        self.kind = kind

    def chia_remote(self, *args, **kwargs):
        if self.kind == "build":
            module = args[2]
            RECORDER["builds"].append(module)
            return types.SimpleNamespace(success=True, base_rev="abc",
                                         binary=module.encode())
        binary = kwargs["binary"]
        RECORDER["runs"].append((binary, kwargs["trace"],
                                 kwargs["simulation_instructions"]))
        return types.SimpleNamespace(success=True, instructions=5_000_001,
                                     cycles=1234, ipc=4.0)


class FakeNode:
    def __init__(self, **kwargs):
        self.build_champsim = Remote("build")
        self.run_champsim = Remote("run")


def load_probe():
    """Import the container-side script with the CHIA Ray bindings stubbed out."""
    for name in ("chia", "chia.base", "chia.base.ChiaFunction", "chia.simulators",
                 "chia.simulators.champsim", "module_effect_control",
                 "baseline_probe"):
        sys.modules.pop(name, None)
    modules = {
        "chia": {},
        "chia.base": {},
        "chia.base.ChiaFunction": {"get": lambda ref: ref},
        "chia.simulators": {},
        "chia.simulators.champsim": {"ChampSimNode": FakeNode},
        "module_effect_control": {"NOOP": "noop source",
                                  "NEXT_LINE": "next line source"},
    }
    for name, attrs in modules.items():
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module
    return importlib.import_module("baseline_probe")


class BaselineProbeTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, "scripts")
        self.addCleanup(sys.path.remove, "scripts")
        self.probe = load_probe()
        RECORDER["builds"].clear()
        RECORDER["runs"].clear()

    def test_each_design_builds_once_and_that_binary_serves_every_trace(self):
        out = self.probe.build_and_run(
            FakeNode(), "src", "probe_noop",
            ["/traces/a.xz", "/traces/b.xz", "/traces/c.xz"],
            warmup=1_000_000, sim=4_000_000)
        self.assertEqual(RECORDER["builds"], ["probe_noop"])
        self.assertEqual([r[0] for r in RECORDER["runs"]], [b"probe_noop"] * 3)
        self.assertEqual([r[1] for r in RECORDER["runs"]],
                         ["/traces/a.xz", "/traces/b.xz", "/traces/c.xz"])
        self.assertEqual([r[2] for r in RECORDER["runs"]], [4_000_000] * 3)
        self.assertEqual([row["cycles"] for row in out["runs"]], [1234] * 3)
        self.assertFalse(out["incremental"])

    def test_main_emits_one_record_per_reference_design(self):
        argv = sys.argv
        sys.argv = ["baseline_probe.py", "--trace", "/traces/a.xz"]
        stream = io.StringIO()
        try:
            with contextlib.redirect_stdout(stream):
                rc = self.probe.main()
        finally:
            sys.argv = argv
        records = [json.loads(line) for line in stream.getvalue().splitlines()
                   if line.startswith("{")]
        self.assertEqual(rc, 0)
        self.assertEqual([r["design"] for r in records], ["noop", "next_line"])
        self.assertEqual(RECORDER["builds"], ["probe_noop", "probe_next_line"])
        self.assertEqual(len(RECORDER["runs"]), 2)

    def test_main_returns_nonzero_when_a_reference_design_fails_to_build(self):
        original = self.probe.build_and_run
        self.probe.build_and_run = lambda *a, **k: {"module": "probe_noop",
                                                    "build_success": False,
                                                    "build_s": 1.0,
                                                    "incremental": False}
        argv = sys.argv
        sys.argv = ["baseline_probe.py", "--trace", "/traces/a.xz"]
        stream = io.StringIO()
        try:
            with contextlib.redirect_stdout(stream):
                rc = self.probe.main()
        finally:
            sys.argv, self.probe.build_and_run = argv, original
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
