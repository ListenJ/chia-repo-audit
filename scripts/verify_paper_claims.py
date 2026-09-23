"""把论文里每一个数字重新从落盘证据里 derive 一遍。

动机：这一轮已经靠人肉抓到三个"指标不再测量它名字里的东西"的缺陷，第四个
（module_effect_control 里三个不同模块报同一个 binary_sha256）也是读文件时撞见的。
撞见不是方法。这个脚本把论文正文的每个数量断言映射回它声称的那个 artifact，
重算，然后判决。数字漂移要么在这里被抓，要么在评审手里被抓。

每条 claim 记：论文里的字符串、出处文件、重算方式、期望值、实测值。
任何一条对不上就 exit 非 0。
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _flatten(tex: str) -> str:
    """LaTeX sources break lines mid-sentence, escape underscores and wrap phrases in
    \\textbf{}, so match against a stripped copy or a regex silently 'proves' the paper
    stopped saying something it says with markup around it."""
    out = re.sub(r"\\(?:textbf|emph|texttt|mathrm|mathbf)\{([^{}]*)\}", r"\1", tex)
    for esc in ("\\_", "\\%", "\\$", "\\{", "\\}"):
        out = out.replace(esc, esc[1])
    return re.sub(r"\s+", " ", out)


PAPER = _flatten((REPO / "paper/paper.tex").read_text(encoding="utf-8"))


def load_json(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def load_jsonl(rel):
    rows = []
    for line in (REPO / rel).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def paper_says(fragment):
    """claim 是否真的写在论文里——防止验了一个论文已经不说的数字。"""
    return re.search(fragment, PAPER) is not None


def pct(x):
    return round(100.0 * x, 2)


CHECKS = []


def check(name, expect, actual, in_paper=None):
    ok = expect == actual
    if in_paper is not None and not paper_says(in_paper):
        ok = False
        actual = f"{actual} (但论文里找不到 {in_paper!r})"
    CHECKS.append((name, expect, actual, ok))


# ---- 网格方差：来自 audit_report.json -------------------------------
v7 = load_json("results/grid_v7_gcp/audit_report.json")
check("cross-seed CV", 78.16, pct(v7["max_seed_cv"]), r"78\.16")
check("repeated-run CV", 0.0, pct(v7["max_repeat_cv"]), r"0\.0000")
check("trace CV", 163.33, pct(v7["max_trace_cv"]), r"163\.33")
check("verdict", "NON-REPRODUCIBLE", v7["verdict"])
check("publish gate", "BLOCKED", v7["publish_gate"])

fact = load_json("results/grid_fact_prompt/audit_report.json")
check("prompt spread", 249.18, pct(fact["max_prompt_spread"]), r"249\.18")
check("prompt-spread axis levels", 3, fact.get("axis_levels", {}).get("prompt"))
check("unexercised axis recorded", ["seed"], fact.get("unexercised_axes"))

rs = v7.get("ranking_stability", {})
check("top-1 stability", "0.667", str(round(rs.get("top1_stability", -1), 3)), r"0\.667")
check("kendall tau", "0.556", str(round(rs.get("mean_kendall_tau", -1), 3)), r"0\.556")

# ---- 标注层：修正后的数字 -------------------------------------------
rescore = load_json("results/semantic_relabel_and_rescore.json")["sets"]
f36 = rescore["fact36"]["rescored"]
check("fact36 labellable n", 33, f36["n_labellable"], r"33")
check("fact36 combined kappa", 0.6358, f36["kappa_combined_label"], r"0\.636")
check("fact36 verdict kappa", 1.0, f36["kappa_verdict_only"], r"1\.0")
check("fact36 flash verdict acc", 1.0, f36["verdict_accuracy_gemini-2.5-flash"],
      r"correct on all")
check("fact36 shared errors after correction", [],
      f36["annotators_agree_with_each_and_wrong"])
sem = rescore["semantic4"]["rescored"]
check("measured-set kappa combined", 0.6667, sem["kappa_combined_label"], r"0\.667")
check("measured-set shared error is the escape", ["sem-esc-01"],
      sem["annotators_agree_with_each_and_wrong"])

spec = load_json("results/audit_independent_v1/report.json")
check("spec kappa", "0.859", str(round(spec["kappa_combined_label"], 3)), r"0\.859")

# ---- 第三 substrate -------------------------------------------------
sub = load_json("results/substrate_probe_laya.json")
check("substrate labellable accuracy", 0.0,
      sub["fact36"]["laya_verdict_accuracy_vs_expected"], r"0 of 33")
check("substrate answers equivalent on", 35,
      sub["fact36"]["laya_verdict_tally"].get("equivalent"), r"35 of 36")
check("substrate kappa on measured set", -0.5,
      sub["semantic4"]["kappa_vs_gemini-2.5-flash"], r"-0\.500")
esc = sub["semantic4"]["laya_per_case"]["sem-esc-01"]
check("substrate right on the escape", "equivalent", esc["laya"], r"correct on")
check("substrate escape margin is negligible", True, esc["margin"] < 0.02, r"0\.010")

# ---- 逃逸用例：cycle 与 binary 归属 ---------------------------------
esc_case = load_json("chia_loop/semantic/sem-esc-01.json")
noop_ref = esc_case["evidence"]["reference_cycles"]
check("no-op reference cycles", 1138748, noop_ref, r"1.,.138.,.748")
check("escape design equals no-op", noop_ref, esc_case["evidence"]["design_cycles"])
check("escape uses two distinct binaries", True,
      esc_case["evidence"]["design_binary_sha256"]
      != esc_case["evidence"]["reference_binary_sha256"])

# 论文说"三批里三个 nullity"，跨两个 screening 文件才凑得齐，逐个查 binary 是否真的不同
screening = (load_jsonl("results/candidate_compile_screening_2026-09-22.jsonl")
             + load_jsonl("results/factorial_screening_2026-09-23.jsonl"))
runs = [r for r in screening if r.get("cycles") and r.get("binary_sha256")]
null = {}
for r in runs:
    if r["cycles"] == noop_ref:
        null.setdefault(r["module"], set()).add(r["binary_sha256"])
check("three distinct nullity designs", 3, len(null), r"[Tt]hree nullities")
check("every nullity has its own binary, not the no-op's", True,
      all(len(bins) == 1 and noop_ref not in bins and bins
          != {esc_case["evidence"]["reference_binary_sha256"]} for bins in null.values()))
check("genuine prefetchers all differ from the no-op", True,
      all(r["cycles"] != noop_ref for r in runs
          if r["module"].startswith("gen_fill_only")))

# 反向检查：module_effect_control 的 incremental 行能不能按模块归属
mec = load_jsonl("results/module_effect_control_2026-09-22.jsonl")
inc = [r for r in mec if r.get("incremental") and r.get("binary_sha256")]
inc_mods = {r["module"] for r in inc}
inc_bins = {r["binary_sha256"] for r in inc}
# 数据里这个缺陷是真的存在，重跑才能修。所以这里断言的不是"数据干净"，而是
# "缺陷仍然存在且论文如实披露"：哪天有人悄悄改了数据或删了这句披露，这里就会翻红。
collision = len(inc_bins) < len(inc_mods) and len(inc_mods) > 1
check("incremental rows still collide on one digest (defect present)", True, collision)
check("and the paper discloses it", True, collision and paper_says(r"binary attribution defect"),
      r"binary attribution defect")

# ---- 编译率与测试数 -------------------------------------------------
fac = [r for r in load_jsonl("results/factorial_screening_2026-09-23.jsonl")
       if r.get("build_success") is not None]
n_ok = sum(1 for r in fac if r.get("build_success"))
check("factorial compile rate", "6 of 9", f"{n_ok} of {len(fac)}", r"6 of 9")
static = sum(1 for p in (REPO / "chia_loop/tests").glob("*.py")
             for _ in re.finditer(r"^\s*def test_", p.read_text(encoding="utf-8"), re.M))
check("test count matches paper", True, static >= 39, r"39 unit tests")

# ---- 复现命令确实存在 -----------------------------------------------
# The reviewer copies this out of the PDF, so both the script and the config it names
# have to be in the artifact.
m = re.search(r"python3 (chia_loop/loops/[\w.]+) --version (\d+) --config ([\w/.]+)", PAPER)
if m:
    check("reproduce script exists", True, (REPO / m.group(1)).is_file())
    cfg = REPO / m.group(3)
    check("reproduce config is shipped", True, cfg.is_file(), r"Reproduce")
else:
    check("reproduce command parseable", True, False)


def main() -> int:
    width = max(len(n) for n, _, _, _ in CHECKS)
    failed = 0
    for name, expect, actual, ok in CHECKS:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  expect={expect!r} actual={actual!r}")
        failed += not ok
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} claims re-derived from artifacts")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
