"""修正 sem-esc-01 的源文件归属，并把证据链写进用例。

事实链（全部来自仓库内文件，不靠记忆）：
1. `chia_loop/semantic/sem-esc-01.json` 内嵌的源码 sha256 = 5de9bd24…，
   等于 `.tmp/cand/gen_default_s0.json`。
2. 那份源码在钉死镜像里**编译不过**：`invalid 'static_cast' from
   champsim::address to int64_t`（2026-09-23 在 VM2 用真实 grid 路径复现，
   与 screening 里那条 build_success=False 的 diagnostics_tail 逐字相同）。
3. `run_grid_chain.sh:27` 显示 screening 扫了 `.tmp/cand .tmp/cand2 .tmp/cand3 .tmp/cand4`。
   各目录文件数为 5/6/3/3 = 17，与 `.tmp/screens_all.jsonl` 的 17 行按序对应，
   因此第 9 行（gen_default_s0，build_success=True，binary cc0477f0e1ee0187，
   cycles 1,138,748）落在 cand2 区间内，即它测的是 `.tmp/cand2/gen_default_s0.json`
   （sha256 671bafcf…，无非法 cast，是真正的 block_number 算术 stride prefetcher）。
4. 所以用例把 A 文件的源码配上了 B 文件的测量。

本脚本把内嵌源码与哈希换成 cand2 那份，保留 binary 与 cycles（它们本来就属于 cand2 的构建），
并写入 attribution_correction。
"""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "chia_loop/semantic/sem-esc-01.json"
TRUE_SOURCE = REPO / ".tmp/cand2/gen_default_s0.json"

WRONG_SHA = "5de9bd2414de745f2d5778b3e452e6d4ad98a81df7ba57139bd965cff9ac7d0a"


def main() -> int:
    case = json.loads(CASE.read_text(encoding="utf-8"))
    cand2 = json.loads(TRUE_SOURCE.read_text(encoding="utf-8"))
    src = cand2["design"]["prefetcher_source"]
    true_sha = hashlib.sha256(src.encode()).hexdigest()

    embedded = case["design"]["prefetcher_source"]
    embedded_sha = hashlib.sha256(embedded.encode()).hexdigest()
    if embedded_sha != WRONG_SHA:
        print(f"refusing: case no longer carries the wrong source (sha {embedded_sha[:16]})")
        return 2

    case["design"]["prefetcher_source"] = src
    ev = case["evidence"]
    ev["design_source_sha256"] = true_sha
    ev["attribution_correction"] = {
        "corrected_utc": "2026-09-23",
        "previous_design_source_sha256": WRONG_SHA,
        "previous_source_file": ".tmp/cand/gen_default_s0.json",
        "corrected_design_source_sha256": true_sha,
        "corrected_source_file": ".tmp/cand2/gen_default_s0.json",
        "why": ("The embedded source used static_cast<int64_t> on a champsim::address and does "
                "not compile in the pinned image, reproducing verbatim the build_success=false "
                "row in the screening log. The successful row for the same module name "
                "(binary cc0477f0e1ee0187, 1,138,748 cycles) came from a different directory "
                "swept by the same run: run_grid_chain.sh passed --candidate-dirs .tmp/cand "
                ".tmp/cand2 .tmp/cand3 .tmp/cand4, whose file counts 5/6/3/3 match the 17 "
                "screening rows in order, placing the successful gen_default_s0 inside cand2."),
        "root_cause": ("Screening rows record a module name and a delivered-binary digest but "
                       "no source digest, so 'which file produced this measurement' cannot be "
                       "answered from the artifact. Module names are not design identifiers: "
                       "gen_default_s0 exists twice with different content."),
        "what_was_preserved": ("design_binary_sha256, reference identities and both cycle counts "
                              "are unchanged: they always described the cand2 build."),
        "consequence_for_the_annotation_layer": (
            "Both generative annotators had been shown the cand variant's text while the "
            "equivalent verdict came from the cand2 build. The four-case annotation was "
            "re-run against the corrected source before quoting kappa."),
    }
    CASE.write_text(json.dumps(case, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"re-attributed sem-esc-01 design source: {WRONG_SHA[:16]} -> {true_sha[:16]}")
    print(f"source length {len(embedded)} -> {len(src)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
