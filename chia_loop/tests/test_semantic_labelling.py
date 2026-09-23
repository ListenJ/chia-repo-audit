"""锁定两次真实发生过的"口径静默失效"：指标读不到被测对象，却仍然给出判决。

1. comparators() 曾在未预处理的源码上抓尖括号，于是 #include 的个数被当成比较方向，
   一对只差局部变量名的候选被判成 not_equivalent|E2（方向错误）。
2. classify() 曾在没有共享测量、也推不出任何错误类时默认返回 not_equivalent，
   等于把"文本不同"当成"设计不同"。
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from semantic_cases_from_candidates import classify, code_only, comparators  # noqa: E402

S1 = '''#include <cstdint>
#include "address.h"
#include "modules.h"

struct gen_a : public champsim::modules::prefetcher {
  using prefetcher::prefetcher;

  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip,
                                     uint8_t hit, bool p, access_type t, uint32_t m) {
    return m;
  }

  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way,
                                  uint8_t pf, champsim::address ev, uint32_t m) {
    champsim::block_number blk{addr};
    prefetch_line(champsim::address{blk + 1}, true, m);
    return m;
  }
};
'''

# 同一段设计：多 include 两个头文件、多写注释、换掉局部变量名、显式 this->
S2 = '''#include <cstdint>
#include <vector>
#include <algorithm>
#include "address.h"
#include "modules.h"

struct gen_b : public champsim::modules::prefetcher {
  using prefetcher::prefetcher;

  // never trains on demand misses
  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip,
                                     uint8_t hit, bool p, access_type t, uint32_t m) {
    return m;
  }

  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way,
                                  uint8_t pf, champsim::address ev, uint32_t m) {
    // one line ahead
    champsim::block_number current_block{addr};
    this->prefetch_line(champsim::address{current_block + 1}, true, m);
    return m;
  }
};
'''

# 真改了方向：+1 变 +2
S3 = S1.replace("gen_a", "gen_c").replace("blk + 1", "blk + 2")


class TestSemanticLabelling(unittest.TestCase):
    def test_include_angle_brackets_are_not_comparators(self):
        self.assertEqual(comparators(S1), comparators(S2))
        self.assertNotIn("<", code_only(S2))

    def test_rename_and_comment_only_pair_is_not_labelled_not_equivalent(self):
        verdict, errors, note = classify(S1, S2, "gen_a", "gen_b", {}, {})
        self.assertEqual(verdict, "unlabellable")
        self.assertEqual(errors, [])
        self.assertIn("no verdict is derivable", note)

    def test_a_real_literal_change_still_labels_as_e1(self):
        verdict, errors, _ = classify(S1, S3, "gen_a", "gen_c", {}, {})
        self.assertEqual(verdict, "not_equivalent")
        self.assertIn("E1", errors)

    def test_measurement_agreement_overrides_textual_difference(self):
        cycles = {"fotonik3d": 1138748}
        verdict, errors, _ = classify(S1, S2, "gen_a", "gen_b", cycles, cycles)
        self.assertEqual(verdict, "equivalent")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
