"""Tests for the grid config builder's contract discipline.

The builder is what keeps the grid honest: directory mode falls back to the whole
candidate pool for a cell with no match, so a config whose seed x prompt rectangle
is not exactly the staged designs would silently score one design as another.
"""
import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "make_grid_config.py"
spec = importlib.util.spec_from_file_location("make_grid_config", MODULE)
make = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make)


def candidate(module, prompt, seed, contract, repaired=False):
    return {
        "design": {"module_name": module, "prefetcher_source": "struct x {};"},
        "prompt": prompt,
        "generator_seed": seed,
        "provenance": {
            "prompt_text": f"{contract} header\nDesign brief for {prompt} seed {seed}",
            "repair_round": 1 if repaired else 0,
        },
    }


class MakeGridConfigTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        make.REPO = self.root

    def tearDown(self):
        self._dir.cleanup()

    def pool(self, directory, designs):
        path = self.root / directory
        path.mkdir(parents=True, exist_ok=True)
        for name, record in designs.items():
            (path / f"gen_{name}.json").write_text(json.dumps(record))
        return path

    def screening(self, built, name="screen.jsonl"):
        lines = [json.dumps({"design": m, "module": m, "build_success": True})
                 for m in built]
        log = self.root / name
        log.write_text("\n".join(lines) + "\n")
        return log

    def run_builder(self, logs, dirs, out="cfg/grid.json"):
        argv = ["make_grid_config.py", "--logs", *[str(l) for l in logs],
                "--candidate-dirs", *[str(d) for d in dirs], "--out", str(self.root / out)]
        old, sys.argv = sys.argv, argv
        err = io.StringIO()
        try:
            with redirect_stderr(err):
                rc = make.main()
        finally:
            sys.argv = old
        return rc, err.getvalue()

    def staged(self):
        staging = self.root / ".tmp/grid_cand"
        return sorted(p.name for p in staging.glob("*.json")) if staging.is_dir() else []

    def config(self, out="cfg/grid.json"):
        return json.loads((self.root / out).read_text())

    def test_takes_the_largest_rectangle_inside_one_contract(self):
        a = "CONTRACT-A"
        dirs = [self.pool("cand", {
            f"fill_only_conservative_s{s}": candidate(
                f"gen_fill_only_conservative_s{s}", "fill_only_conservative", s, a)
            for s in (1, 2, 3)})]
        dirs.append(self.pool("cand2", {
            "cot_s9": candidate("gen_cot_s9", "cot", 9, "CONTRACT-B")}))
        rc, _ = self.run_builder([self.screening(
            [f"gen_fill_only_conservative_s{s}" for s in (1, 2, 3)] + ["gen_cot_s9"])], dirs)
        self.assertEqual(rc, 0)
        cfg = self.config()
        self.assertEqual(cfg["seeds"], [1, 2, 3])
        self.assertEqual(cfg["prompts"], ["fill_only_conservative"])
        self.assertFalse(cfg["champsim_node"]["incremental"])
        self.assertEqual(self.staged(),
                         [f"gen_fill_only_conservative_s{s}.json" for s in (1, 2, 3)])

    def test_a_colliding_module_name_outside_the_rectangle_does_not_block(self):
        # Tonight's real shape: `gen_default_s0` compiled under one contract and
        # also exists under another. Only designs of the chosen contract may be
        # staged, and a collision in the dropped remainder must not stop the grid.
        a = self.pool("cand", {
            **{f"fill_only_conservative_s{s}": candidate(
                f"gen_fill_only_conservative_s{s}", "fill_only_conservative", s,
                "CONTRACT-A") for s in (1, 2, 3)},
            "default_s0": candidate("gen_default_s0", "default", 0, "CONTRACT-A")})
        b = self.pool("cand2", {
            "default_s0": candidate("gen_default_s0", "default", 0, "CONTRACT-B")})
        rc, err = self.run_builder(
            [self.screening(["gen_fill_only_conservative_s1", "gen_fill_only_conservative_s2",
                             "gen_fill_only_conservative_s3", "gen_default_s0"])], [a, b])
        self.assertEqual(rc, 0, err)
        cfg = self.config()
        self.assertEqual(cfg["prompts"], ["fill_only_conservative"])
        self.assertEqual(cfg["seeds"], [1, 2, 3])
        self.assertEqual(self.staged(), [f"gen_fill_only_conservative_s{s}.json"
                                         for s in (1, 2, 3)])
        for name in self.staged():
            record = json.loads((self.root / ".tmp/grid_cand" / name).read_text())
            self.assertIn("CONTRACT-A", record["provenance"]["prompt_text"])

    def test_repairs_are_kept_out_of_a_one_shot_grid(self):
        a = "CONTRACT-A"
        path = self.pool("cand", {
            **{f"fill_only_conservative_s{s}": candidate(
                f"gen_fill_only_conservative_s{s}", "fill_only_conservative", s, a)
                for s in (1, 2)},
            "aggressive_offset_s1_r1": candidate(
                "gen_aggressive_offset_s1_r1", "aggressive_offset", 1, a, repaired=True)})
        rc, err = self.run_builder(
            [self.screening(["gen_fill_only_conservative_s1",
                             "gen_fill_only_conservative_s2",
                             "gen_aggressive_offset_s1_r1"])], [path])
        self.assertEqual(rc, 1)
        self.assertIn("rectangle has 2 cells", err)
        self.assertNotIn("gen_aggressive_offset_s1_r1.json", self.staged())

    def test_the_largest_rectangle_wins_and_leftovers_are_dropped(self):
        a = "CONTRACT-A"
        designs = {f"fill_only_conservative_s{s}": candidate(
            f"gen_fill_only_conservative_s{s}", "fill_only_conservative", s, a)
            for s in (1, 2)}
        designs["cot_s1"] = candidate("gen_cot_s1", "cot", 1, a)
        designs["cot_s2"] = candidate("gen_cot_s2", "cot", 2, a)
        designs["cot_s3"] = candidate("gen_cot_s3", "cot", 3, a)
        path = self.pool("cand", designs)
        rc, _ = self.run_builder(
            [self.screening([d["design"]["module_name"] for d in designs.values()])], [path])
        self.assertEqual(rc, 0)
        cfg = self.config()
        # A 2x2 block inside one contract is more cells than a 3-cell column, and
        # a complete rectangle is what directory mode needs; mixing prompts is
        # safe as long as every cell has exactly one staged design.
        self.assertEqual(cfg["prompts"], ["cot", "fill_only_conservative"])
        self.assertEqual(cfg["seeds"], [1, 2])
        self.assertEqual(self.staged(), ["gen_cot_s1.json", "gen_cot_s2.json",
                                         "gen_fill_only_conservative_s1.json",
                                         "gen_fill_only_conservative_s2.json"])


if __name__ == "__main__":
    unittest.main()
