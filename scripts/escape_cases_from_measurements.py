"""从已有测量生成第二、第三个 nullity 逃逸用例，归属由文件本身算出来。

为什么要做：论文 Limitations 自己写着"测量接地集上的共同错误是 n=1"。
但 screening 里其实有**三个**编译通过、跑起来、出指标、且 cycle 数与冷启动 no-op
参考逐位相同的设计 —— 只做了其中一个用例。剩下两个的源码与测量都已经在仓库里，
不需要再花一次仿真。

归属不靠手抄：每个设计都从它真正来自的候选目录读文件、现算 sha256，
并把"这个模块名在哪些目录里还有不同内容的同名副本"一并写进证据里。
这正是 sem-esc-01 曾经做错的地方（内嵌了编译不过的那份源码）。
"""
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "chia_loop/semantic"
TRACE = "SPEC17-649.fotonik3d_s-1B.champsimtrace.xz"
NOOP_CYCLES = 1138748
NOOP_BINARY = "8a4884c11c4995dc"
INSTRUCTIONS = 2000001

# (case id, module, source dir, screening file, binary digest from that screening row)
DESIGNS = [
    ("sem-esc-02", "gen_aggressive_offset_s1_r1", ".tmp/cand3",
     "results/candidate_compile_screening_2026-09-22.jsonl", "5de585b809f878ee",
     "13-design screening batch, cold build"),
    ("sem-esc-03", "gen_aggressive_offset_s1", ".tmp/cand_fact2",
     "results/factorial_screening_2026-09-23.jsonl", "e4d8a8fdf55c2d95",
     "9-candidate prompt x seed factorial batch; screen_fact.sh swept only cand_fact2"),
]


def source_variants(module: str) -> dict:
    """Every distinct source on disk carrying this module name: sha -> directory."""
    found = {}
    for path in glob.glob(str(REPO / ".tmp" / "*" / f"{module}.json")):
        try:
            c = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        src = (c.get("design") or {}).get("prefetcher_source")
        if not src:
            continue
        found[hashlib.sha256(src.encode()).hexdigest()] = os.path.relpath(
            Path(path).parent, REPO)
    return found


def screening_row(rel: str, module: str, binary: str) -> dict:
    for line in (REPO / rel).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("module") == module and d.get("binary_sha256") == binary:
            return d
    raise SystemExit(f"no screening row for {module} with binary {binary} in {rel}")


def main() -> int:
    written = []
    for case_id, module, src_dir, screen_rel, binary, provenance_note in DESIGNS:
        src_path = REPO / src_dir / f"{module}.json"
        cand = json.loads(src_path.read_text(encoding="utf-8"))
        src = cand["design"]["prefetcher_source"]
        sha = hashlib.sha256(src.encode()).hexdigest()
        row = screening_row(screen_rel, module, binary)

        if row.get("cycles") != NOOP_CYCLES:
            raise SystemExit(f"{module}: screening says {row.get('cycles')}, not {NOOP_CYCLES}")
        if row.get("instructions") != INSTRUCTIONS:
            raise SystemExit(f"{module}: instruction budget {row.get('instructions')}")

        variants = source_variants(module)
        reference_src = (REPO / "chia_loop/sim/probe_noop.cc").read_text(encoding="utf-8") \
            if (REPO / "chia_loop/sim/probe_noop.cc").is_file() else None
        if reference_src is None:
            # Fall back to the reference already embedded in the first escape case so the
            # no-op side is byte-identical across cases rather than re-typed.
            first = json.loads((OUT / "sem-esc-01.json").read_text(encoding="utf-8"))
            reference_src = first["reference"]["prefetcher_source"]
            ref_sha = first["evidence"]["reference_source_sha256"]
        else:
            ref_sha = hashlib.sha256(reference_src.encode()).hexdigest()

        case = {
            "id": case_id,
            "design": {"module_name": module, "prefetcher_source": src},
            "reference": {"module_name": "probe_noop", "prefetcher_source": reference_src},
            "expected_verdict": "equivalent",
            "expected_errors": [],
            "planting": ("real generated prefetcher that compiles, runs and reports "
                         "metrics, but is behaviourally indistinguishable from doing "
                         "nothing on this trace and instruction budget"),
            "evidence": {
                "design_source_sha256": sha,
                "reference_source_sha256": ref_sha,
                "design_binary_sha256": binary,
                "reference_binary_sha256": NOOP_BINARY,
                "trace": TRACE,
                "warmup_instructions": 1000000,
                "simulation_instructions": 2000000,
                "design_cycles": row["cycles"],
                "reference_cycles": NOOP_CYCLES,
                "distinct_binaries": True,
                "source": screen_rel,
                "provenance": provenance_note,
                "attribution_method": ("source read from " + src_dir + " and hashed here, "
                                       "not transcribed; the screening row is matched on "
                                       "(module, binary_sha256)"),
                "same_module_name_other_sources": {h[:16]: t for h, t in variants.items()
                                                   if h != sha},
            },
            "taxonomy_gap": True,
            "taxonomy_note": ("E0-E4 audits design-vs-reference equivalence. A nullity "
                              "escape is equivalent to the no-op and therefore scores E0 "
                              "here even though the candidate claims to prefetch; only the "
                              "harness's no-op comparison catches it."),
        }
        path = OUT / f"{case_id}.json"
        path.write_text(json.dumps(case, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        written.append((case_id, module, sha[:16], len(src)))
        print(f"wrote {case_id}: {module} sha={sha[:16]} len={len(src)} "
              f"cycles={row['cycles']}==noop "
              f"other_copies={ {h[:8]: t for h, t in variants.items() if h != sha} }")

    print(f"\n{len(written)} cases written; measurement-grounded set is now "
          f"{len(list(OUT.glob('*.json')))} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
