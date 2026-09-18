from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "kaggle_champsim_smoke.py"

spec = importlib.util.spec_from_file_location("kaggle_champsim_smoke", SCRIPT)
assert spec and spec.loader
kaggle_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kaggle_smoke
spec.loader.exec_module(kaggle_smoke)


class KaggleSmokeParsingTests(unittest.TestCase):
    def test_parse_simulation_metrics(self):
        stats = [
            {
                "name": "Warmup",
                "roi": {"cores": [{"instructions": 100, "cycles": 80}]},
            },
            {
                "name": "Simulation",
                "roi": {
                    "cores": [{"instructions": 5000, "cycles": 2500}],
                    "cpu0_L2C": {
                        "prefetch requested": 10,
                        "prefetch issued": 8,
                        "useful prefetch": 6,
                    },
                },
            },
        ]

        metrics = kaggle_smoke.parse_simulation_metrics(stats)

        self.assertEqual(metrics["instructions"], 5000)
        self.assertEqual(metrics["cycles"], 2500)
        self.assertEqual(metrics["ipc"], 2.0)
        self.assertEqual(metrics["l2c_prefetch_requested"], 10)
        self.assertEqual(metrics["l2c_useful_prefetch"], 6)

    def test_verify_sha256_rejects_wrong_digest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "trace.gz"
            path.write_bytes(b"trace")

            with self.assertRaises(ValueError):
                kaggle_smoke.verify_sha256(path, "0" * 64)


class KaggleSmokeCliTests(unittest.TestCase):
    def test_dry_run_uses_pinned_versions(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--dry-run",
                "--work-dir",
                "/tmp/kaggle-smoke",
                "--output",
                "/tmp/kaggle-smoke/result.json",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        output = json.loads(completed.stdout)

        self.assertEqual(
            output["champsim_commit"],
            kaggle_smoke.CHAMPSIM_COMMIT,
        )
        self.assertEqual(
            output["trace_sha256"],
            kaggle_smoke.SMOKE_TRACE_SHA256,
        )
        self.assertTrue(
            any("config.sh" in command for command in output["commands"])
        )


if __name__ == "__main__":
    unittest.main()
