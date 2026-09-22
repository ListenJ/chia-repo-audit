from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "real_candidate_generate.py"

spec = importlib.util.spec_from_file_location("real_candidate_generate", SCRIPT)
assert spec and spec.loader
gen = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gen
spec.loader.exec_module(gen)


FENCED_REPLY = """Sure, here is the design:

```cpp
struct evolved_pf : public champsim::modules::prefetcher {
  using prefetcher::prefetcher;
  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip,
                                    uint8_t cache_hit, bool useful_prefetch,
                                    access_type type, uint32_t metadata_in) {
    return metadata_in;
  }
};
```
"""

BARE_REPLY = """struct other_name : public champsim::modules::prefetcher {
  using prefetcher::prefetcher;
};
"""


class RealCandidateGenerationTests(unittest.TestCase):
    def test_extracts_fenced_module_and_pins_struct_name(self):
        parsed = gen.parse_candidate_source(FENCED_REPLY, module_name="gen_default_s0")
        self.assertEqual("fenced_cpp", parsed["parse"])
        self.assertEqual("gen_default_s0", parsed["module_name"])
        self.assertIn("struct gen_default_s0 : public champsim::modules::prefetcher",
                      parsed["source"])
        self.assertEqual(["struct_rename:evolved_pf->gen_default_s0"],
                         parsed["normalizations"])

    def test_accepts_bare_struct_and_records_missing_operate_hook(self):
        parsed = gen.parse_candidate_source(BARE_REPLY, module_name="gen_x_s0")
        self.assertEqual("bare_struct", parsed["parse"])
        self.assertIn("struct gen_x_s0", parsed["source"])
        self.assertIn("missing_prefetcher_cache_operate", parsed["warnings"])

    def test_rejects_reply_without_a_module(self):
        with self.assertRaises(ValueError):
            gen.parse_candidate_source("I am not able to help.", module_name="gen_x_s0")

    def test_seed_and_prompt_both_change_the_emitted_prompt(self):
        base = gen.build_prompt("default", 0)
        self.assertNotEqual(base, gen.build_prompt("default", 1))
        self.assertNotEqual(base, gen.build_prompt("aggressive_offset", 0))
        self.assertIn("gen_default_s0", base)

    def test_record_keeps_provenance_and_design_contract(self):
        record = gen.build_candidate_record(
            model="pro-model",
            prompt_name="default",
            seed=0,
            prompt_text="p",
            raw_response=FENCED_REPLY,
            parsed=gen.parse_candidate_source(FENCED_REPLY, module_name="gen_default_s0"),
            api_base="https://example.invalid/v1",
            latency_s=1.5,
            usage={"completion_tokens": 10},
        )
        self.assertEqual("gen_default_s0", record["module_name"])
        self.assertEqual(record["module_name"], record["design"]["module_name"])
        self.assertIn("prefetcher_source", record["design"])
        provenance = json.dumps(record["provenance"])
        for key in ("pro-model", "https://example.invalid/v1", "raw_response",
                    "prompt_sha256", "created_at"):
            self.assertIn(key, provenance)


if __name__ == "__main__":
    unittest.main()
