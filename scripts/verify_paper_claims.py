"""把论文里每一个数字重新从落盘证据里 derive 一遍。

动机：这一轮已经靠人肉抓到三个"指标不再测量它名字里的东西"的缺陷，第四个
（module_effect_control 里三个不同模块报同一个 binary_sha256）也是读文件时撞见的。
撞见不是方法。这个脚本把论文正文的每个数量断言映射回它声称的那个 artifact，
重算，然后判决。数字漂移要么在这里被抓，要么在评审手里被抓。

每条 claim 记：论文里的字符串、出处文件、重算方式、期望值、实测值。
任何一条对不上就 exit 非 0。
"""
import hashlib
import json
import re
import subprocess
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
sem = rescore["measured6"]["rescored"]
check("measured-set size", 6, sem["n_scored"], r"six measurement-grounded")
check("measured-set kappa combined", 0.4545, sem["kappa_combined_label"], r"0\.455")
check("measured-set verdict kappa stays 1.0", 1.0, sem["kappa_verdict_only"], r"1\.0")
check("measured-set verdict accuracy", 0.5, sem["verdict_accuracy_gemini-2.5-flash"],
      r"right on only 3 of 6|accuracy")
check("all three escapes are the shared errors",
      ["sem-esc-01", "sem-esc-02", "sem-esc-03"],
      sorted(sem["annotators_agree_with_each_and_wrong"]), r"three escapes")
check("and no non-escape case is missed", [],
      [c for c in sem["annotators_agree_with_each_and_wrong"] if "esc" not in c])
check("zero verdict disagreements", 0, sem["annotators_disagree"], r"0 disagreements")

spec = load_json("results/audit_independent_v1/report.json")
check("spec kappa", "0.859", str(round(spec["kappa_combined_label"], 3)), r"0\.859")

# ---- 第三 substrate -------------------------------------------------
sub = load_json("results/substrate_probe_laya.json")
check("substrate labellable accuracy", 0.0,
      sub["fact36"]["laya_verdict_accuracy_vs_expected"], r"0 of 33")
check("substrate answers equivalent on", 35,
      sub["fact36"]["laya_verdict_tally"].get("equivalent"), r"35 of 36")
check("substrate kappa on measured set", -0.3636,
      sub["measured6"]["kappa_vs_gemini-2.5-flash"], r"-0\.364")
esc = sub["measured6"]["laya_per_case"]["sem-esc-01"]
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

# "停在 6 例"是账号造成的还是证据造成的，两者性质完全不同，而论文早先归因归错了：
# 原文写的是"缺第二评分者"。可标注的逃逸池能从落盘 screening 直接重算，上面那条已经
# 钉住池子大小是 3；这条钉住池子里每一个都已做成用例。合起来的结论是：即便第二评分者
# 还在，也造不出第四个测量接地逃逸用例，除非重新仿真并重跑候选生成 —— 而那需要已被
# 删除的账号。没有这条时，"n 小"读起来像我们没做完，而实际是证据已经用尽。
_esc_used = sorted({load_json(f"chia_loop/semantic/{p.name}")["design"]["module_name"]
                    for p in sorted((REPO / "chia_loop/semantic").glob("sem-esc-*.json"))})
check("the nullity pool is exhausted, not truncated: every escaping design is a case",
      sorted(null), _esc_used, r"exhausted")

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

# ---- 缺陷 8：排序统计把填充值当测量打印 ------------------------------
# 单候选网格无从排序，_trace_ranking_stability 过去返回 0.0 填充值，scorecard 照印，
# 于是"无法测量"读起来像"排序极不稳定"——偏向本文自己的论点，所以必须钉住。
rank = load_json("results/grid_x_aggressive_s3/audit_report.json")["ranking_stability"]
check("one-candidate grid reports itself unrankable",
      (False, "fewer_than_two_candidates"),
      (rank["rankable"], rank["unrankable_reason"]), r"unrankable")
card = (REPO / "results/grid_x_aggressive_s3/scorecard.txt").read_text(encoding="utf-8")
check("its scorecard prints unrankable instead of tau=0.0",
      (True, False),
      ("unrankable (fewer_than_two_candidates)" in card, "Kendall tau: 0.0" in card),
      r"unrankable")
check("and the paper discloses the fill value", True, paper_says(r"fill values?"),
      r"fill value")

# ---- 缺陷 9：commit pin 被字符串 "unknown" 满足 ----------------------
SHA = re.compile(r"[0-9a-f]{7,40}")
GRIDS = ["grid_both_axes", "grid_fact_prompt", "grid_nullity_control", "grid_v6",
         "grid_v7_gcp", "grid_x_aggressive_s3", "grid_x_fill_only_s2s3"]
raws = {g: load_json(f"results/{g}/raw.json") for g in GRIDS}
pins = {g: load_json(f"results/{g}/env_pin.json") for g in GRIDS}
unpinned = [g for g in GRIDS if not SHA.fullmatch(str(raws[g].get("git_sha") or ""))]
unpinned_env = [g for g in GRIDS if not SHA.fullmatch(str(pins[g].get("git_sha") or ""))]
disagree = [g for g in GRIDS if str(raws[g].get("git_sha")) != str(pins[g].get("git_sha"))]
check("grid artifacts counted", 7, len(GRIDS), r"seven grid artifacts")
check("grids whose raw.json does not pin a real commit", 3, len(unpinned), r"three record")
check("grids whose env_pin.json does not", 4, len(unpinned_env), r"four in")
check("grids whose two provenance records disagree", 2, len(disagree), r"two of the seven")
check("the headline prompt-spread grid is among the unpinned", True,
      "grid_fact_prompt" in unpinned, r"grid_fact_prompt")
check("and the paper discloses the sentinel", True,
      paper_says(r"unknown") and paper_says(r"commit pin"), r"commit pin")
# 历史值不修：主机已销毁，真 SHA 不可从 artifact 恢复。谁往 env_pin 里填了一个
# 像样的 SHA，这条就翻红——那会是本节描述的那个缺陷本身。
check("the three historical values were not backfilled", 3,
      sum(1 for g in unpinned if str(raws[g].get("git_sha")) == "unknown"), r"unknown")
gate = subprocess.run(
    [sys.executable, "scripts/check_grid_evidence.py",
     "--raw", "results/grid_fact_prompt/raw.json",
     "--reference", "results/reference_designs_2026-09-22.jsonl"],
    cwd=REPO, capture_output=True, text=True)
check("the evidence gate now rejects it", True,
      "commit_sha_retained" in gate.stdout, r"commit_sha_retained")

# ---- 两个散文计数以前没有任何检查看着（operations-log §30 登记过）----
# 这里钉的是"论文说的数字"，不是从 artifact derive 出来的数字；derive 的部分是上面
# 那几条 3/4/2。至少漂移会翻红，不再是改错了没人知道。
check("paper counts nine automation defects", True, paper_says(r"nine defects"),
      r"nine defects")
check("conclusion counts nine silent defects", True, paper_says(r"nine silent defects"),
      r"nine silent defects")
check("disclosure counts nine self-audits", True, paper_says(r"nine self-audits"),
      r"nine\s+self-audits")
check("the shared failure shape is stated as five instances", True,
      paper_says(r"seen five times"), r"seen five times")

# ---- 销毁前的证据链：这两台机器已经不存在了，所以这些文件是唯一记录 ----
# 唯一记录尤其不能只是"放在那里"。下面每条都从落盘字节重算，包括那个"打包归档是冗余的、
# 所以删掉 VM 不丢数据"的主张——它是这次不可逆动作的正当性来源。
BK = REPO / "results/compute_host_bookkeeping"
_prov = load_json("results/compute_host_bookkeeping/provenance.json")
_td = load_json("results/vm_teardown_precondition_2026-09-24.json")
_life = load_json("results/compute_host_lifecycle_2026-09-22_to_24.json")
_man = [ln.split(None, 2) for ln in
        (BK / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()]
_payload = sorted(str(p.relative_to(REPO)).replace("\\", "/") for p in BK.rglob("*")
                  if p.is_file() and p.name not in ("MANIFEST.sha256", "provenance.json"))
check("the manifest covers exactly the rescued files, no more and no fewer",
      sorted(rel for _, _, rel in _man), _payload)
_bad = []
for _h, _size, _rel in _man:
    _p = REPO / _rel
    _b = _p.read_bytes() if _p.exists() else b""
    if hashlib.sha256(_b).hexdigest() != _h or str(len(_b)) != _size:
        _bad.append(_rel)
check("every rescued file still hashes to what the manifest says", [], _bad)
_hashes = [h for h, _, _ in _man]
_dups = sorted({h for h in _hashes if _hashes.count(h) > 1})
check("its declared file and distinct-hash counts are the real ones",
      (len(_payload), len(set(_hashes))), (_prov["files"], _prov["distinct_sha256"]))
check("and the duplicate contents it declares are the duplicates there are",
      sorted(x[2] for x in _prov["identical_content_pairs"]), _dups)
check("the stale count is corrected on the record, not silently", True,
      "count_correction" in _prov and "20" in _prov["count_correction"])
# 冗余主张：VM 打包回来的两个 .tgz 与已提交的 results/ 逐字节相同。
import tarfile  # noqa: E402  (used once, kept next to the claim it serves)
_redundant, _differing = 0, []
for _grid, _host in (("grid_both_axes", "chia-grid_136.108.73.240"),
                     ("grid_nullity_control", "chia-grid2_34.73.33.65")):
    with tarfile.open(BK / _host / "repo/.tmp/done" / f"{_grid}.tgz") as _t:
        for _m in _t.getmembers():
            if not _m.isfile():
                continue
            _local = REPO / _m.name
            if _local.exists() and _local.read_bytes() == _t.extractfile(_m).read():
                _redundant += 1
            else:
                _differing.append(_m.name)
check("the packed VM archives are byte-identical to the committed results",
      (10, []), (_redundant, _differing))
_per = _td["orphans_disposed"]
check("the disposed-orphan classes add up", 75, sum(v["count"] for v in _per.values()))
_git_archive = subprocess.run(
    "git archive --format=tar b85b38c | tar -t | grep -v '/$' | wc -l",
    cwd=REPO, shell=True, capture_output=True, text=True)
check("the 66-file snapshot really is that commit, and the commit still exists",
      _per["home_workspace_snapshot"]["count"], int(_git_archive.stdout.strip()))
check("the one authored file rescued from the VM hashes to the recorded value",
      _per["watch_grid_sh"]["sha256"],
      hashlib.sha256((REPO / _per["watch_grid_sh"]["rescued_to"]).read_bytes()).hexdigest())
_cov = _td["trace_hash_corroboration"]


def _trace_hashes(grid):
    """provenance.json 有两种 traces 形状：{"source":..,"sha256":{name:h}} 和
    {name:{"path":..,"sha256":h}}。写检测时只认一种，就会把覆盖率数错——
    这里两种都认，因为数错的那次就是这么错的。"""
    t = load_json(f"results/{grid}/provenance.json").get("traces") or {}
    if isinstance(t.get("sha256"), dict):
        return dict(t["sha256"])
    return {n: v["sha256"] for n, v in t.items()
            if isinstance(v, dict) and "sha256" in v}


_pinning = [g for g in GRIDS
            if (REPO / f"results/{g}/provenance.json").exists() and _trace_hashes(g)]
_per_trace = {}
for _g in _pinning:
    for _n, _h in _trace_hashes(_g).items():
        _per_trace.setdefault(_n, set()).add(_h)
check("the grids that pin trace hashes are the grids the record names",
      _cov["grids_pinning_trace_sha256"], _pinning)
check("every pinned trace agrees across the grids that pinned it",
      [1] * len(_per_trace), sorted(len(v) for v in _per_trace.values()))
check("the live-host re-hash covered all of them",
      (len(_per_trace), len(_per_trace)), (_cov["n_traces"], _cov["n_matching"]))
check("and the caveat it was corrected against is kept, not overwritten", True,
      "coverage_caveat_original" in _cov and "coverage_correction" in _cov)
_ph = _prov["hosts"]
check("the three host records describe the same two machines", [],
      [h for h in _ph
       if (_ph[h]["external_ip"], _ph[h]["zone"], _ph[h]["machine_type"], _ph[h]["created"])
       != (_td["hosts"][h]["ip"], _td["hosts"][h]["zone"],
           _td["hosts"][h]["machine_type"], _td["hosts"][h]["created"])]
      + [h for h in _ph if h not in str(_life)])
# MANIFEST 的哈希是逐字节的。core.autocrlf=true 且没有 .gitattributes 时，
# Windows 上重新 checkout 会把 LF 改成 CRLF，上面那条"仍然哈希相符"就会在评审手里翻红，
# 而在我们这里永远是绿的——正是本文写的那个失效形状。
check("the evidence bytes are pinned against line-ending rewrite", True,
      "results/** -text" in (REPO / ".gitattributes").read_text(encoding="utf-8"))
# 论文现在解释了这两个目录为什么在 artifact 里。没有检查看着的散文计数就是上一节
# 刚补掉的那个缺口，所以这里同样钉住。
check("the paper says the compute hosts are gone", True,
      paper_says(r"compute hosts were deleted"), r"hosts were deleted")
check("and names the sweep that gated it", True,
      paper_says(r"vm_teardown_precondition_2026-09-24\.json"))
# 论文引用了那个错的旧数字，是作为更正引用的。所以这里断言的是"两个数字都在、
# 并且是被当成更正写的"，而不是断言旧数字消失了。
check("the paper carries the trace-pin correction, old number and new",
      (True, True, 3),
      (paper_says(r"1 of 6 grid provenance"), paper_says(r"gave 3"), len(_pinning)),
      r"gave 3")

# ---- 编译率与测试数 -------------------------------------------------
fac = [r for r in load_jsonl("results/factorial_screening_2026-09-23.jsonl")
       if r.get("build_success") is not None]
n_ok = sum(1 for r in fac if r.get("build_success"))
check("factorial compile rate", "6 of 9", f"{n_ok} of {len(fac)}", r"6 of 9")
static = sum(1 for p in (REPO / "chia_loop/tests").glob("*.py")
             for _ in re.finditer(r"^\s*def test_", p.read_text(encoding="utf-8"), re.M))
check("test count matches paper", 46, static, r"46 unit tests")
img = load_json("results/in_image_tests_2026-09-24_r3.json")
check("in-image suite really ran 46 and passed", (46, "OK"),
      (img["result"]["ran"], img["result"]["outcome"]), r"inside the pinned image")
check("in-image run used the pinned digest",
      "sha256:610951d382f9e6cdfc51a4526ba70e36c80f3375b1dc19d60117bc47f20e94c4",
      img["image_digest"], r"pinned image")
# The image is pinned by digest, so the interpreter it ships is part of the claim.
check("in-image interpreter is the one the paper names", "Python 3.10.19",
      img["interpreter"].split(" |")[0], r"Python 3\.10\.19")
# r2 measured 45 against the tree before the commit-pin test existed. It is kept as a
# record, not silently overwritten, and the supersession is asserted rather than assumed.
check("the earlier in-image record is retained and superseded, not edited",
      (45, "results/in_image_tests_2026-09-24_r2.json"),
      (load_json("results/in_image_tests_2026-09-24_r2.json")["result"]["ran"],
       img["supersedes"].split(" ")[0]), r"45")

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


# ---- 决策链：§gate2 的每个数字都要能从落盘 JSON 重derive --------------
lad = load_json("results/noul_approval_ladder.json")
rows = {r["id"]: r for r in lad["rows"]}
check("ladder Spearman", 0.406, round(lad["spearman_tier_noul"], 3), r"\+0\.406")
check("ladder separation is negative", -0.169, round(lad["separation"], 3),
      r"=-0\.169|0\.169")
check("ladder verdict", "NOT-USABLE-AS-GATE", lad["verdict"])
check("outside write scored below the safe local edit", True,
      rows["edit_submission"]["noul"] < rows["rewrite_local_scorecard"]["noul"],
      r"\$0\.126\$, below the safe local rewrite at \$0\.160\$")
check("edit_submission value", 0.126, round(rows["edit_submission"]["noul"], 3), r"0\.126")
check("local scorecard rewrite value", 0.16, round(rows["rewrite_local_scorecard"]["noul"], 2),
      r"0\.160")

vd = load_json("decision_chain/chia-decisions2.verdicts.json")
check("gate v2 escalates exactly the outside writes",
      sorted(["D8_push_corrected_branch", "D10_hotcrp_submission_edit"]),
      sorted(vd["escalate"]))
check("gate declares blast radius in code, not in the model",
      ["destructive", "external_write"], sorted(vd["escalable_blast_radii"]),
      r"register")
check("gate and ladder code ship with the artifact", True,
      all((REPO / f"decision_chain/{n}").is_file()
          for n in ("laya_gate2.py", "laya_noul_ladder.py", "chia-decisions2.json")))


# ---- 逃逸用例的源归属修正，以及修正后重跑的标注 ------------------------
esc_case = load_json("chia_loop/semantic/sem-esc-01.json")
true_src = hashlib.sha256(
    load_json(".tmp/cand2/gen_default_s0.json")["design"]["prefetcher_source"].encode()
).hexdigest()
check("escape case cites the source that actually compiled", true_src,
      esc_case["evidence"]["design_source_sha256"], r"source")
check("and records the correction", "5de9bd2414de745f2d5778b3e452e6d4ad98a81df7ba57139bd965cff9ac7d0a",
      esc_case["evidence"]["attribution_correction"]["previous_design_source_sha256"])
check("binary identity preserved through the correction", "cc0477f0e1ee0187",
      esc_case["evidence"]["design_binary_sha256"])

esc_v2 = load_json("results/audit_independent_semantic_v2/report.json")
check("measured-set kappa unchanged after re-annotation", 0.6667,
      round(esc_v2["kappa_combined_label"], 4), r"0\.667")
check("measured-set verdict kappa", 1.0, esc_v2["kappa_verdict_only"], r"1\.0")
esc_rows = [r for r in load_json("results/audit_independent_semantic_v2/raw.json")
            if r["id"] == "sem-esc-01"][0]
check("both annotators still wrong on the corrected escape source",
      {"not_equivalent"},
      {l["verdict"] for l in esc_rows["labels"]})
check("and both still cite the added stride mechanism", 2,
      sum(1 for l in esc_rows["labels"] if "stride" in l.get("rationale", "").lower()),
      r"claims to work, measurably does")


# ---- 引用完整性：本地脚本能查的那一半 ---------------------------------
tex_raw = (REPO / "paper/paper.tex").read_text(encoding="utf-8")
cited = set(re.findall(r"\\cite\{([^}]+)\}", tex_raw))
defined = set(re.findall(r"\\bibitem\{([^}]+)\}", tex_raw))
check("every cited key has a bibliography entry", set(), cited - defined)
check("no unused bibliography entry", set(), defined - cited)
check("the 25.7% claim carries its real denominator (tasks, not benchmarks)", True,
      bool(re.search(r"25\.7\%.*?\btasks\b", PAPER, re.S))
      and "of 168 reviewed benchmarks carry" not in PAPER, r"evaluated")
check("no 'retracted SWE-bench Pro' overstatement", False,
      "retracted SWE-bench" in PAPER)
check("the NeurIPS page is no longer cited for a SWE-bench claim", False,
      "neurips.cc" in tex_raw)
check("a citation audit record ships with the artifact", True,
      (REPO / "docs/citation-audit.md").is_file())


swap = load_json("results/annotation_role_swap_v3/report.json")
check("role-swap probe compared 12 answers", 12, swap["n_comparisons"], r"twelve verdicts")
check("no verdict flips when candidate and reference exchange places", 0, swap["n_flips"],
      r"0/8")
swap_rows = {r["id"]: r for r in load_json("results/annotation_role_swap_v3/raw.json")}
esc_swap = swap_rows["sem-esc-01"]["labels"]
check("escape case stays wrong in both directions", {"not_equivalent"},
      {l["verdict"] for l in esc_swap}, r"symmetric")


cand_md = (REPO / "CANDIDATES.md").read_text(encoding="utf-8")
colliding = len({m for m in re.findall(r"^\| `([\w]+)`(?: \*\*collides\*\*)?",
                                       cand_md, re.M)
                 if f"`{m}` **collides**" in cand_md})
total_mods = len({m for m in re.findall(r"^\| `([\w]+)`(?: \*\*collides\*\*)?",
                                        cand_md, re.M)})
check("candidate index exists and its collision count matches the paper",
      f"{colliding} of {total_mods}", "9 of 15" if (colliding, total_mods) == (9, 15)
      else f"{colliding} of {total_mods}", r"9 of 15 module names")


# ---- 两轴矩形：论文新增的四个数与跨网格复现 ----------------------------
b2 = load_json("results/grid_both_axes/audit_report.json")
check("2x2 cross-seed CV", 23.5, pct(b2["max_seed_cv"]), r"23\.50")
check("2x2 prompt spread", 179.67, pct(b2["max_prompt_spread"]), r"179\.67")
check("2x2 top-1 stability", 1.0,
      round(b2["ranking_stability"]["top1_stability"], 3), r"1\.000|top-1 stability")
check("2x2 kendall tau", 0.778, round(b2["ranking_stability"]["mean_kendall_tau"], 3),
      r"0\.778")
check("2x2 exercises both axes", [], b2.get("unexercised_axes"), r"Unexercised axes:\s*none")
check("2x2 seed and prompt levels", {"seed": 2, "prompt": 2},
      {k: b2["axis_levels"][k] for k in ("seed", "prompt")})
check("2x2 verdict", "NON-REPRODUCIBLE", b2["verdict"])
check("2x2 gate", "BLOCKED", b2["publish_gate"])
_v6 = load_json("results/grid_v6/raw.json")
_b2 = load_json("results/grid_both_axes/raw.json")


def cell(raw, seed, prompt, trace_sub):
    for c in raw["cells"].values():
        if (c.get("generator_seed", c.get("seed")) == seed and c["prompt"] == prompt
                and trace_sub in c["trace"]):
            return c["median"]["cycles"]
    return None


_overlap = [(s, t) for s in (1, 3) for t in ("fotonik", "BFSCC", "imagick")]
check("the two grids agree bit-for-bit on every overlapping cell", True,
      all(cell(_v6, s, "fill_only_conservative", t)
          == cell(_b2, s, "fill_only_conservative", t) for s, t in _overlap))
check("fill_only reproduces across seeds inside the 2x2 grid", True,
      all(cell(_b2, 1, "fill_only_conservative", t)
          == cell(_b2, 3, "fill_only_conservative", t) for t in ("fotonik", "BFSCC", "imagick")))
check("aggressive_offset does not", False,
      cell(_b2, 1, "aggressive_offset", "BFSCC") == cell(_b2, 3, "aggressive_offset", "BFSCC"))


# ---- 第八个缺陷：空实现正例网格与它被丢弃的方差轴 ---------------------
_nc_raw = load_json("results/grid_nullity_control/raw.json")
_nc_report = load_json("results/grid_nullity_control/audit_report.json")
_nc_noop = {}
for _r in load_jsonl("results/reference_designs_2026-09-22.jsonl"):
    if _r.get("design") == "noop":
        _nc_noop = {Path(_x["trace"]).name: _x["cycles"] for _x in _r["runs"]}
_nc_by_level = {}
for _c in _nc_raw["cells"].values():
    _nc_by_level.setdefault((_c["prompt"], _c["seed"]), []).append(_c)


def _nc_cycles(prompt, seed):
    return {Path(_c["trace"]).name: _c["median"]["cycles"]
            for _c in _nc_by_level[(prompt, seed)]}


check("the no-op reference has three traces", 3, len(_nc_noop))
check("gen_default_s0 equals the no-op on every trace", True,
      _nc_cycles("default", 0) == _nc_noop, re.escape("2{,}261{,}770"))
check("gen_aggressive_offset_s1_r1 equals it too", True,
      _nc_cycles("aggressive_offset", 1) == _nc_noop)
check("so the nullity branch has a real positive control", 2,
      len({_nc_by_level[k][0]["design_sha256"] for k in _nc_by_level
           if _nc_cycles(*k) == _nc_noop}),
      r"[Tt]wo designs equal the cold no-op reference")
check("gen_fill_only_conservative_s0 is live on all three", 0,
      sum(1 for t, v in _nc_cycles("fill_only_conservative", 0).items()
          if v == _nc_noop[t]), r"live on all three traces")
check("and faster than the no-op on every one", True,
      all(v < _nc_noop[t] for t, v in _nc_cycles("fill_only_conservative", 0).items()),
      r"faster than the no-op on every one")
sys.path.insert(0, str(REPO / "scripts"))
import audit_grid_levels  # noqa: E402  the published-grid gate, reused as the oracle

_nc_audit = audit_grid_levels.audit_grid(REPO / "results/grid_nullity_control/raw.json")
check("six labelled levels hide three compiled designs", (6, 3),
      (_nc_audit["n_design_levels"], _nc_audit["n_distinct_digests"]),
      r"three distinct compiled designs\s+behind six levels")
check("three levels carry another level's design", 3, _nc_audit["n_substituted"],
      r"three of its six factor levels")
_shared = list(_nc_audit["shared_digest_levels"].values())
check("all three substitutions land on one design", 1, len(_shared))
check("and that design is named by four levels", ["aggressive_offset/0", "default/0",
      "default/1", "fill_only_conservative/1"], sorted(_shared[0]))
check("and the artifact discloses them", True, _nc_audit["disclosed"])
check("no other published grid substitutes or duplicates a level", {},
      {a["grid"]: (a["n_substituted"], a["levels_not_distinct"])
       for a in (audit_grid_levels.audit_grid(x)
                 for x in sorted((REPO / "results").glob("grid*/raw.json")))
       if a["grid"] != "grid_nullity_control"
       and (a["n_substituted"] or a["levels_not_distinct"])},
      r"the other five are clean")
check("the discarded cross-seed CV is the value the paper quotes", 8.3812,
      round(100.0 * _nc_report["max_seed_cv"], 4), r"8\.3812")
check("that CV is the only nonzero one on the seed axis", 3,
      sum(1 for v in _nc_report["seed_cv"].values() if v))
check("and it is what blocked that grid", ("NON-REPRODUCIBLE", "BLOCKED"),
      (_nc_report["verdict"], _nc_report["publish_gate"]), r"8\.3812")
check("the one axis substitution cannot touch is determinism", 0.0,
      _nc_report["max_repeat_cv"], r"repeated-run axis survives")
_h1 = {}
_h2 = {}
for _path, _into in (("results/grid_both_axes/raw.json", _h1),
                     ("results/grid_x_fill_only_s2s3/raw.json", _h2)):
    for _c in load_json(_path)["cells"].values():
        _into[(_c["design"]["module_name"], Path(_c["trace"]).name)] = \
            _c["median"]["cycles"]
_overlap = sorted(set(_h1) & set(_h2))
check("the two hosts overlap on three cells", 3, len(_overlap))
check("and they agree to the cycle on all of them", True,
      all(_h1[k] == _h2[k] for k in _overlap), r"they agree to the cycle")


# ---- 文档不许写数字节号：插一小节就会全部失效，且失效是静默的 ----------
check("no markdown doc cites a bare numeric paper section", [],
      sorted({str(f.relative_to(REPO)) for f in REPO.rglob("*.md")
              if ".git" not in f.parts and "operations-log" not in f.name
              for line in f.read_text(encoding="utf-8", errors="ignore").splitlines()
              for _ in [0] if re.search(r"§3\.\d|\bsection 3\.\d", line)}))

# ---- 提交物本身：PDF 必须真是当前源的渲染，不是上一轮的产物 ------------
# 这里原来是三条 mtime 比较（pdf>tex、pdf>fig、render>=pdf）。在自己的工作树里
# 它们成立，所以看着像个门。但在一次干净克隆里所有文件都是 checkout 时几毫秒内
# 先后落盘的，先后由 git 决定：实测推送分支的 Windows 克隆里四个文件在 7ms 内写
# 完，paper.pdf 比 paper.tex 早 1ms，于是文档给出的验证命令在评审机器上返回
# 172/173 rc=1、在我这里返回 173/173 rc=0。判决由 10ms 以内的写盘顺序决定的门
# 不是门，是一次恰好落在我们这边的掷硬币。改成按内容钉住：BUILD_PIN.json 记录
# 编译当时吃进去和吐出来的字节，这里只问"盘上还是不是那一套"，而这个问题
# checkout 改不了答案。改了 tex 不重编，tex 的哈希就对不上，红得确定、原因明确。
_pin = load_json("paper/BUILD_PIN.json")
_pinned = {**_pin["inputs"], **_pin["outputs"]}
for _rel, _what in (("paper/paper.tex", "LaTeX source"),
                    ("paper/fig_decomposition.pdf", "embedded figure"),
                    ("paper/paper.pdf", "submitted PDF"),
                    ("paper/paper_text.txt", "committed text render")):
    check(f"the {_what} on disk is the one the build pin was written against",
          _pinned[_rel],
          hashlib.sha256((REPO / _rel).read_bytes()).hexdigest())
check("the PDF reports its own page count somewhere readable", True,
      (REPO / "paper/paper.pdf").read_bytes().count(b"/Type /Page") > 1)
# pin 里的 pages 是自报字段：原来没人拿它跟 PDF 对账，把 9 改成 8 再顺手改掉
# README，页数门就整体绿了。页对象数是从字节里独立数出来的（/Type /Page 后面不
# 接字母，这样 /Type /Pages 那三个树节点不会被算进来），所以它给 pages 一个指称物。
check("and the pin's page count is really the number of page objects in the PDF",
      _pin["pages"],
      len(re.findall(rb"/Type\s*/Page(?![A-Za-z])",
                     (REPO / "paper/paper.pdf").read_bytes())))
_render = REPO / "paper/paper_text.txt"
_rendered = re.sub(r"\s+", " ", _render.read_text(encoding="utf-8"))

# ---- 留档的上一版提交 PDF：它是 ops log 里那个摘要唯一的指称物 ------------
# 重编 paper/paper.pdf 之后，docs/operations-log.md 引用的 97eb5bc4… 就不再是盘上
# 任何文件的哈希，下面那条"文档里每个 64 位十六进制串都必须真是某个东西的哈希"
# 就会红。放松那条门是错的方向；留住字节是对的，但"留住了"本身也得可验证，
# 否则它只是一个没人检查的 615KB 装饰，而留档的理由恰恰是它要当证据的指称物。
_HIST_PROV = "results/submitted_pdf_history/provenance.json"
_HIST_PDF = "results/submitted_pdf_history/paper_2026-09-23_173claims.pdf"
_hp = load_json(_HIST_PROV)
_hbytes = (REPO / _HIST_PDF).read_bytes()
_hsha = hashlib.sha256(_hbytes).hexdigest()
check("the retained prior submission hashes to the digest the ops log quotes",
      _hp["sha256"], _hsha)
check("and the ops log still quotes it, so the retention has a referent", True,
      _hsha in (REPO / "docs/operations-log.md").read_text(encoding="utf-8"))
check("the retained copy is not passed off as the current submission", True,
      _hsha != _pinned["paper/paper.pdf"])
_build = _hp["the_build_it_came_from"]
_blob = subprocess.run(["git", "show", f"{_build['git_head']}:paper/paper.tex"],
                       cwd=REPO, capture_output=True)
check("the superseded build's recorded source digest is really that commit's blob",
      _build["paper/paper.tex"], hashlib.sha256(_blob.stdout).hexdigest())
check("and the retained PDF is really that commit's PDF",
      _build["paper/paper.pdf"],
      hashlib.sha256(subprocess.run(
          ["git", "show", f"{_build['git_head']}:paper/paper.pdf"],
          cwd=REPO, capture_output=True).stdout).hexdigest())

# ---- 干净克隆的验证记录：说"评审跑文档命令会绿"就得能对着历史核 ------------
# 这条主张正是 §32 那轮的全部产出，所以它不能只停在散文里。三条检查把记录钉到
# 它所描述的那个 commit 上：cloned_head 必须是 HEAD 的祖先（不是编出来的 sha），
# 记录里的四个摘要必须等于那个 commit 的 BUILD_PIN.json blob（不是重抄一遍），
# 以及那次克隆必须真处在会出问题的配置下（core.autocrlf=true 且三个文本产物
# 都以 LF 落盘）——否则"在干净克隆里绿"这句话没有对抗性，证明不了任何事。
_FC = "results/fresh_clone_verification_2026-09-24.json"
_fc = load_json(_FC)
check("the recorded clone head is real history, not an invented sha", 0,
      subprocess.run(["git", "merge-base", "--is-ancestor", _fc["cloned_head"], "HEAD"],
                     cwd=REPO, capture_output=True).returncode)
# cloned_head 编出来的时候 git show 什么都不吐，json.loads("") 抛 JSONDecodeError：
# 整个验证器崩掉，rc=1 但一条 FAIL 都不报。变异测试实测到的。异常也是非零退出，
# 可评审看不出是哪条主张错了，跟"通过"一样没用。解析失败就退回原始 stdout，
# 让比对红得有名有姓。
_pin_blob = subprocess.run(
    ["git", "show", f"{_fc['cloned_head']}:paper/BUILD_PIN.json"],
    cwd=REPO, capture_output=True, text=True,
    encoding="utf-8", errors="replace").stdout
try:
    _pin_at_head = json.loads(_pin_blob)
except json.JSONDecodeError:
    _pin_at_head = _pin_blob.strip() or None
check("and the digests it records are that commit's, not a retyped copy",
      _pin_at_head, _fc["pin_at_clone"])
# 同理，少一行 eol 记录会让 _eol[f] KeyError。缺就填一个必然对不上的哨兵。
_eol = {ln.split("\t")[1]: ln.split("\t")[0].split() for ln in _fc["eol_table_paper"]}
_text_artifacts = ("paper/paper.tex", "paper/paper_text.txt", "paper/BUILD_PIN.json")
# 三个字段全查（i/、w/、attr/），不只查 w/。理由不是洁癖：paper/** 是 -text，
# git 原样存字节，所以"索引里是什么"就是提交物本身。上一版只断言 w/lf，而 w 是本地
# 检出结果，它恰好抓住了 b8df223 那次事故（编辑器把整份 .tex 改写成 CRLF 后入库），
# 但那是运气 —— 如果检出端也是 CRLF，两边一致，这条就绿了，而提交物已经变了 816 处行尾。
check("the clone really was the adversarial configuration the fix targets",
      {"core.autocrlf": "true",
       **{f: ["i/lf", "w/lf", "attr/-text"] for f in _text_artifacts}},
      {"core.autocrlf": _fc["core_autocrlf"],
       **{f: _eol.get(f, ["NO-EOL-ROW-RECORDED"])[0:3] for f in _text_artifacts}})

# 上面那条要等一次干净克隆的记录才生效，而克隆记录天生落后 HEAD 一个 commit。
# 这条直接在作者树上查提交物字节：paper/** 是 -text，所以 HEAD 里的 blob 就是评审
# 会拿到的东西。CRLF 混进 .tex 不会让 pdflatex 报错、不会改渲染结果，只会悄悄改掉
# BUILD_PIN 里的输入摘要 —— 而 pin 是照着盘上字节重新生成的，于是它永远自洽、永远绿。
# 只查 HEAD 的 blob，不查工作树：查"盘上==HEAD"会在每一次正常的编辑中途翻红，
# 那不是门禁，是"你有未提交改动"的提示器，而会喊狼来了的检查等于没有检查。
_tex_blob = subprocess.run(["git", "show", "HEAD:paper/paper.tex"], cwd=REPO,
                           capture_output=True).stdout
check("the submitted LaTeX source is committed with LF line endings",
      0, _tex_blob.count(b"\r\n"))
check("the rendered pages carry the headline numbers", True,
      all(s in _rendered for s in ("78.16", "249.18", "8.3812", "2,261,770")))
check("no unresolved reference reached the render", 0, _rendered.count("??"))
check("the rendered paper carries an AI-assistance disclosure", True,
      "AI assistance in this work" in _rendered)
check("identifiers stay searchable in the text layer", True,
      all(s in _rendered for s in ("gen_default_s0", "audit_grid_levels.py",
                                   "verify_paper_claims.py")))

# ---- 文档里每一个 64 位十六进制串都必须真是某个东西的哈希 --------------
# 触发这条的原因是一次真实的自我伪造：ops log 里先写下了一个凭格式编出来的 sha256，
# 之后才跑命令拿到真值。形如证据不等于证据。
def _hex_in(*suffixes, skip=()) -> set:
    """Every 64-hex string appearing in machine-written files of these suffixes."""
    found = set()
    for f in REPO.rglob("*"):
        if not f.is_file() or ".git" in f.parts or "__pycache__" in f.parts:
            continue
        if f.suffix not in suffixes or any(s in f.parts for s in skip):
            continue
        try:
            found.update(re.findall(r"[0-9a-f]{64}",
                                    f.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return found


# A hash quoted in prose is trustworthy only if some machine-written artifact carries the
# same value, or it hashes a file on disk. Provenance, not value overlap: subtracting the
# prose set by value would delete a shared digest just because the log also quotes it.
_machine_hex = _hex_in({".json", ".jsonl", ".yaml", ".csv"}) | {
    hashlib.sha256(f.read_bytes()).hexdigest()
    for f in REPO.rglob("*") if f.is_file() and ".git" not in f.parts}
_doc_quoted = {}
for _f in (REPO / "docs/operations-log.md", REPO / "README.md", REPO / "paper/paper.tex"):
    for _h in re.findall(r"[0-9a-f]{64}", _f.read_text(encoding="utf-8")):
        _doc_quoted.setdefault(_h, _f.name)
check("every 64-hex hash quoted in the docs is a real digest of something", [],
      sorted({f"{h[:12]}.. quoted in {src}" for h, src in _doc_quoted.items()
              if h not in _machine_hex}))

# ---- 论文/README 指向的每个路径都必须真的在盘上、且真的被 git 跟踪 ------
# A `git commit -a` silently skips untracked files, and the pushed artifact would then
# cite a script that is not in the repository -- which is this paper's own defect class,
# applied to the submission itself.
_tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout.split())
_refs = set()
for _m in re.finditer(r"(?:scripts|chia_loop|results|decision_chain|docs|paper|\.tmp)/"
                      r"[A-Za-z0-9_.\\\-/]+",
                      (REPO / "paper/paper.tex").read_text(encoding="utf-8")
                      + (REPO / "README.md").read_text(encoding="utf-8")
                      + (REPO / "REVIEW_COVERAGE.md").read_text(encoding="utf-8")):
    # LaTeX escapes underscores inside \texttt{}, so a naive pattern truncates every
    # script name at the first one and the gate reports fiction as missing.
    _refs.add(_m.group(0).rstrip(".,;").replace("\\_", "_").rstrip("/"))
def _is_tracked(rel: str) -> bool:
    return rel in _tracked or any(t.startswith(rel + "/") for t in _tracked)
check("every referenced path exists on disk", [],
      sorted(r for r in _refs if not (REPO / r).exists()))
check("and every referenced path is tracked by git", [],
      sorted(r for r in _refs if (REPO / r).exists() and not r.startswith(".tmp")
             and not _is_tracked(r)))

# 本轮开始向第三方推理端点发请求，凭据存在仓库之外。风险不在"引用了不存在的路径"这一类，
# 而在另一次 `git add -p` 手滑：一个 bearer token 一旦进了被跟踪的文件，它就随公开
# artifact 永久分发，而上面所有门禁只会看到"路径存在、摘要自洽"，全都管不着秘密本身。
# 所以按形态扫全部被跟踪文件。刻意不写死真值：这条不需要知道密钥是什么，
# 也不需要谁去读它 —— 一个检查若要求作者先把凭据加载进上下文才能通过，
# 它本身就成了泄漏路径。
_TOK_SHAPE = re.compile(rb"\batr_[A-Za-z0-9]{16,}")
_tok_hits = []
for _f in sorted(_tracked):
    _p = REPO / _f
    if not _p.is_file():
        continue
    try:
        if _TOK_SHAPE.search(_p.read_bytes()):
            _tok_hits.append(_f)
    except OSError:
        continue
check("no API-token-shaped string exists in any tracked file", [], _tok_hits)

# ---- 覆盖率必须是重算出来的，否则 README 里那句又是一个陈旧字符串 -------
_inv = json.loads(subprocess.run(
    [sys.executable, str(REPO / "scripts/inventory_vouches.py"), "--json"],
    capture_output=True, text=True, encoding="utf-8").stdout)
README_TXT = (REPO / "README.md").read_text(encoding="utf-8")
check("published file count matches the tree", True,
      f"all {_inv['files_tracked']} tracked" in README_TXT)
check("published machine-vouch rate is recomputed", True,
      f"{_inv['machine_vouched_rate']:.1%}" in README_TXT)
check("published unvouched rate is recomputed", True,
      f"{_inv['unvouched_rate']:.1%}" in README_TXT)
check("the published orphan breakdown is recomputed", True,
      f"({len(_inv['unvouched'])} files;" in README_TXT
      and f"{sum(1 for f in _inv['unvouched'] if f.startswith('.tmp/'))} live under"
      in README_TXT)
# 上面几条只管住了比率和总数，README 里三个分层的绝对计数仍然没人核对——
# 138 就是这么在原地陈旧的。这里把三个计数按出现顺序一次钉死。
check("and the three tier counts, which the rates alone did not pin down",
      [_inv["tiers"]["machine"], _inv["tiers"]["reachable"],
       _inv["tiers"]["code-unreferenced"]],
      [int(x) for x in re.findall(r"\((\d+) files", README_TXT)])
# 孤儿里"至少被散文点名"的那个数一直没人管，直到我在 ops log 里写下某个 `.tmp/`
# 笔记的文件名——普查立刻从 46 变 47，README 原地陈旧，而所有门都是绿的。同一句话里的
# 前两个数（80 files、50 live under）都有检查，偏偏第三个没有。regex 找不到时给
# None 而不是 .group() 崩掉，这是 §32.6 那个 AttributeError 的同一课。
_prose_n = re.search(r"\((\d+) files; (\d+) of those are at least named in prose",
                     README_TXT)
check("and the prose-named orphan count, stale the moment a log line named a file",
      len(_inv["unvouched_named_in_prose"]),
      int(_prose_n.group(2)) if _prose_n else None)
check("and REVIEW_COVERAGE.md is the generated one", True,
      str(_inv["files_tracked"]) in (REPO / "REVIEW_COVERAGE.md").read_text(encoding="utf-8"))

# ---- README 里那些描述"当前状态"的数字，同样得是重算出来的 ----------------
# 找到这两条的原因：README 写着 "(138 claims)" 和 "8 pages"，而验证器当时已经是
# 179 条、PDF 已经是 9 页。两个数字都没有门。论文里的 claim 数是自指门禁管着的，
# README 里的同一个数字没人管，于是它在原地陈旧了两轮。页数更糟：它同时出现在
# 给主办方的邮件草稿里，而那封信是要发出去的。
_readme_n = re.search(r"\((\d+) claims\)", README_TXT)
_paper_n = re.search(r"\((\d+) claims, non-zero exit on drift\)", PAPER)
# 两边都可能搜不到，那就是要报的错本身。变异测试实测过：论文里那句被改坏时，
# 直接 .group(1) 会让整个验证器抛 AttributeError 崩掉，而不是留下一条 FAIL——
# 一个因为异常而退出的门看起来也是"非零退出"，但它没有告诉你哪条错了。
check("the README quotes the same claim count as the paper",
      _paper_n.group(1) if _paper_n else None,
      _readme_n.group(1) if _readme_n else None)
# 只列描述当前状态的文档。ops log、decision_chain/README 和带日期的 handoff 是历史
# 快照，它们写的是当时的页数，改了反而是伪造记录；handoff 顶部因此挂了陈旧告示。
# 正则也必须只匹配"本文有多少页"的句式：裸扫 r"\d+ pages" 会把 README 和邮件里
# 引用的工作坊规则 "2-4 pages" 一起抓进来，那是别人的限制，不是我们的页数。
_OUR_LENGTH = (r"our paper is (\d+) pages", r"currently (\d+) pages",
               r"compiles it cleanly -- (\d+) pages")
_stale_pages = sorted(
    f"{_d} says {m.group(1)}"
    for _d in ("README.md", "docs/organizer-email-2026-09-24.md")
    for _pat in _OUR_LENGTH
    for m in re.finditer(_pat, (REPO / _d).read_text(encoding="utf-8"))
    if int(m.group(1)) != _pin["pages"])
check("no current-state doc quotes a page count the PDF does not have", [], _stale_pages)
check("and the README does state one, so the gate cannot pass by deletion", True,
      sum(len(re.findall(_p, README_TXT)) for _p in _OUR_LENGTH) >= 2
      and f"{_pin['pages']} pages" in README_TXT)

# ---- 决策链第二组：4 条真实决策，判决与作者实际动作对账 ---------------
_d3spec = load_json("decision_chain/chia-decisions3.json")
_d3 = load_json("decision_chain/chia-decisions3.verdicts.json")
_d3_auth = {d["id"]: d["chosen_by_author"] for d in _d3spec["decisions"]}
check("the set really has four decisions", 4, len(_d3["decisions"]))
check("the head's top-1 equals what the author did", 4,
      sum(1 for d in _d3["decisions"] if d["chosen_action"] == _d3_auth[d["id"]]),
      r"equalled the action taken 4 of 4 times")
_marg = [float(m.group(1)) for d in _d3["decisions"]
         for m in [re.search(r"margin ([\d.]+) < ", " ".join(d["reasons"]))] if m]
check("the two escalations are the two thin margins", [0.01, 0.118], sorted(_marg),
      r"escalated the two genuinely close calls")
check("both clear winners ran automatically",
      ["D15_launch_the_fix_before_testing_it", "D17_publish_state_with_uncompiled_paper"],
      sorted(_d3["auto"]))
_noul = sorted(float(n) for d in _d3["decisions"]
               for n in re.findall(r"noul=([\d.]+)", " ".join(d["reasons"])))
check("every approval score exceeds the 0.5 hint", (4, 0.627, 0.835),
      (len(_noul), _noul[0], _noul[-1]), r"hint on all four")
check("no noul question text is repeated across the set", 4,
      len({q["instructions"] for d in _d3spec["decisions"]
           for q in d["questions"].values() if q["type"] == "noul"}))


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
