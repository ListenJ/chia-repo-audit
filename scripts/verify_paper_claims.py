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


# 名字不是设计标识：两个批次里同名模块交付了不同 binary、测出不同 cycle。
# 断言的是"冲突真实存在且论文披露过"，不是"数据干净"。
batches = {}
for tag, rel in (("A", "results/candidate_compile_screening_2026-09-22.jsonl"),
                 ("B", "results/factorial_screening_2026-09-23.jsonl")):
    for r in load_jsonl(rel):
        if r.get("cycles") and r.get("module") and r.get("binary_sha256"):
            batches.setdefault(r["module"], {})[(r["binary_sha256"], tag)] = r["cycles"]
collide = {m: v for m, v in batches.items() if len(set(v.values())) > 1}
check("a module name carries two measurements", ["gen_fill_only_conservative_s2"],
      sorted(collide), "gen_fill_only_conservative_s2")
check("and the two differ in binary digest too", True,
      all(len(k) == 2 for k in collide.values()), r"different delivered binaries")

# 图必须由 artifact 重derive，且真的被论文引用
check("figure is generated and included", True,
      (REPO / "paper/fig_decomposition.pdf").is_file()
      and "fig_decomposition.pdf" in PAPER, r"fig_decomposition")
check("figure generator exists", True,
      (REPO / "scripts/make_figures.py").is_file(), r"make_figures")

# 论文里说"每个真 prefetcher 都偏离 no-op"，逐个回代
check("no functioning prefetcher equals the no-op", True,
      all(c != noop_ref for m, v in batches.items() for c in v.values()
          if "fill_only" in m or m in ("gen_default_s1", "gen_aggressive_offset_s3")),
      r"functioning prefetcher")


# 论文写的是 Anonymous Submission，所以 PDF 源码里不能出现任何指向作者或赞助方
# 账号的标识。这条检查存在的意义是：以后有人为了"方便 reviewer"把仓库 URL 粘回正文，
# 会立刻翻红，而不是等到 desk reject。
# 不能写成裸 `github.com/`：那会把 \bibitem 里引用的 ucb-bar/chia 也算成泄露，
# 一个会误报的门禁很快就会被无视。只匹配我们自己的仓库与身份串。
IDENTITY = re.compile(r"ListenJ|jlinshan6|devstar7744|Listen Jiang|gcplab|"
                      r"a3-chia-hack26ath|github\.com/ListenJ|chia-repo-audit", re.I)
tex_src = (REPO / "paper/paper.tex").read_text(encoding="utf-8")
check("paper source leaks no identity", [], IDENTITY.findall(tex_src))
check("paper still claims anonymity consistently", "Anonymous Submission",
      "Anonymous Submission" if "Anonymous Submission" in tex_src else None)


# ---- 第二个 seed 系列：0.0000% 与跨系列同名不同物 ----------------------
s2g = load_json("results/grid_x_fill_only_s2s3/audit_report.json")
check("second series cross-seed CV", 0.0, pct(s2g["max_seed_cv"]), r"0\.0000\%")
check("second series gate blocked on unexercised prompt", ["prompt"],
      s2g.get("unexercised_axes"), r"One series per axis")
check("second series seed axis really has two levels", 2,
      s2g.get("axis_levels", {}).get("seed"))


def cand_sha(path, name):
    d = load_json(path)
    return {c.get("generator_seed", c.get("seed")): c["candidate_sha256"]
            for c in d["cells"].values() if c["candidate_id"] == name}


v6_s2 = cand_sha("results/grid_v6/raw.json", "gen_fill_only_conservative_s2").get(2)
x_s2 = cand_sha("results/grid_x_fill_only_s2s3/raw.json",
                "gen_fill_only_conservative_s2").get(2)
check("same module name, different candidate digest across series", True,
      v6_s2 is not None and x_s2 is not None and v6_s2 != x_s2,
      r"1\{,\}210 source characters")


# ---- 每-trace no-op 参考：论文三处相对量断言的落点 --------------------
refs = {}
for r in load_jsonl("results/reference_designs_2026-09-22.jsonl"):
    if r.get("design") and r.get("runs"):
        refs[r["design"]] = {Path(run["trace"]).name: run["cycles"] for run in r["runs"]}
noop_by_trace = refs.get("noop", {})
nl_by_trace = refs.get("next_line", {})
check("per-trace no-op reference exists for all three traces", 3, len(noop_by_trace))
check("noop and next_line are different cold builds", True,
      {r["binary_sha256"] for r in load_jsonl("results/reference_designs_2026-09-22.jsonl")}
      == {"b49ebf8858bedd46", "476f7ee0b9cfc286"})

v6 = load_json("results/grid_v6/raw.json")
s2 = {Path(k.split("/", 2)[2]).name: c["median"]["cycles"]
      for k, c in v6["cells"].items() if c.get("generator_seed", c.get("seed")) == 2}
bf = next(t for t in noop_by_trace if "BFSCC" in t)
im = next(t for t in noop_by_trace if "imagick" in t)
fo = next(t for t in noop_by_trace if "fotonik" in t)

faster = 100.0 * (noop_by_trace[bf] - s2[bf]) / noop_by_trace[bf]
check("s2 is 10.6% faster than the no-op on BFSCC", 10.62, round(faster, 2), r"10\.6")
check("s2 equals the no-op exactly on imagick", noop_by_trace[im], s2[im],
      r"reproduces the no-op cycle count exactly on")

sep_bf = 100.0 * (noop_by_trace[bf] - nl_by_trace[bf]) / noop_by_trace[bf]
sep_fo = 100.0 * (noop_by_trace[fo] - nl_by_trace[fo]) / noop_by_trace[fo]
check("control pair separates 23.15% on BFSCC", 23.15, round(sep_bf, 2), r"23\.15")
check("control pair separates only 0.42% on fotonik3d", 0.42, round(sep_fo, 2), r"0\.42")


def main() -> int:
    # The paper states how many claims this script checks, so that number is itself a
    # claim. Include this check in its own count, or the sentence can never be right.
    stated = re.search(r"\((\d+) claims, non-zero exit on drift\)", PAPER)
    check("stated claim count is self-consistent", True,
          stated is not None and int(stated.group(1)) == len(CHECKS) + 1)
    width = max(len(n) for n, _, _, _ in CHECKS)
    failed = 0
    for name, expect, actual, ok in CHECKS:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  expect={expect!r} actual={actual!r}")
        failed += not ok
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} claims re-derived from artifacts")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
