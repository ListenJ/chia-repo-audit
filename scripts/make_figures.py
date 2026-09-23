"""从落盘 artifact 重derive 论文的两张图，不硬编码任何数字。

(a) 方差分解：一个聚合分数背后四个来源的量级差 —— 重复运行 0.0000% 而种子 78.16%。
    门禁线 5% 画在同一坐标上，读者一眼看见"确定性不等于可复现"。
(b) 空转逃逸：同一 trace、同一指令预算下，几个生成设计与 no-op 参考的 cycle 数。
    真正的 prefetcher 全都偏离 no-op，两个恰好落在 no-op 上。

用法：python3 scripts/make_figures.py   ->  paper/fig_decomposition.pdf
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "paper" / "fig_decomposition.pdf"


def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def main() -> int:
    v7 = load("results/grid_v7_gcp/audit_report.json")
    fact = load("results/grid_fact_prompt/audit_report.json")

    sources = [
        ("repeated run\n(N=5, 45 runs)", 100 * v7["max_repeat_cv"]),
        ("generation seed\n(3 seeds x 1 prompt)", 100 * v7["max_seed_cv"]),
        ("trace choice\n(same designs)", 100 * v7["max_trace_cv"]),
        ("prompt variant\n(1 seed x 3 prompts)", 100 * fact["max_prompt_spread"]),
    ]
    gate = 100 * v7["acceptance_threshold"]

    esc = load("chia_loop/semantic/sem-esc-01.json")["evidence"]
    noop = esc["reference_cycles"]
    # Keyed on (module, binary), never on module alone: gen_fill_only_conservative_s2
    # appears in both screening batches with different delivered binaries and
    # different cycle counts (1,132,568 vs 1,129,110). Keying by name silently dropped
    # one of them -- an identifier that looks like design identity but is not.
    batches = {"A": "results/candidate_compile_screening_2026-09-22.jsonl",
               "B": "results/factorial_screening_2026-09-23.jsonl"}
    measured, collisions = {}, {}
    for tag, rel in batches.items():
        for line in (REPO / rel).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not (r.get("cycles") and r.get("module") and r.get("binary_sha256")):
                continue
            measured[(r["module"], r["binary_sha256"], tag)] = r["cycles"]
            collisions.setdefault(r["module"], set()).add(r["cycles"])
    name_collisions = sorted(m for m, v in collisions.items() if len(v) > 1)

    labels, values, colours = [], [], []
    for (mod, digest, tag), cyc in sorted(measured.items()):
        labels.append(f"{mod.replace('gen_', '').replace('probe_', '')}·{tag}")
        values.append(cyc)
        colours.append("#b03030" if cyc == noop else "#31527a")
    # The no-op reference itself is not a screening row; draw it first as the zero.
    labels.insert(0, "no-op ref")
    values.insert(0, noop)
    colours.insert(0, "#8a8a8a")

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.65))

    ax = axes[0]
    y = range(len(sources))
    ax.barh(list(y), [v for _, v in sources], color=["#31527a", "#b03030", "#b03030", "#b03030"],
            height=0.6)
    ax.axvline(gate, color="black", ls="--", lw=1)
    ax.text(gate * 1.25, -0.42, f"gate {gate:g}%", fontsize=6.8, va="center")
    ax.set_yticks(list(y), labels=[n for n, _ in sources], fontsize=6.4)
    ax.set_xscale("symlog", linthresh=1.0)
    ax.set_xticks([0, 1, 10, 100, 250])
    ax.set_xticklabels(["0", "1", "10", "100", "250"], fontsize=7)
    ax.set_xlabel("max relative spread across the axis (%)", fontsize=7.5)
    ax.set_title("(a) one aggregate score hides four axes", fontsize=8, loc="left")
    for (name, val), yy in zip(sources, y):
        if val == 0:
            ax.text(1.15, yy, "exactly 0.0000%", fontsize=6.5, va="center")
        else:
            ax.text(val + 3, yy, f"{val:.4g}%", fontsize=6.5, va="center")
    ax.tick_params(axis="y", length=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    ax = axes[1]
    # Cycles plotted against a zero baseline differ by <1%, which is invisible; the
    # claim is exact equality with the no-op, so the axis has to encode that directly.
    deltas = [100.0 * (v - noop) / noop for v in values]
    x = range(len(labels))
    ax.bar(list(x), deltas, color=colours, width=0.62)
    ax.axhline(0.0, color="black", lw=1)
    ax.set_xticks(list(x), labels=labels, fontsize=5.6, rotation=38, ha="right")
    ax.set_ylabel(r"$\Delta$ cycles vs no-op reference (%)", fontsize=7.5)
    ax.set_title(f"(b) three designs sit exactly on the no-op ({noop:,} cycles)",
                 fontsize=8, loc="left")
    ax.tick_params(axis="both", labelsize=6.5)
    # A bar of height zero is invisible, and four "+0.000%" labels stack on top of each
    # other, so the nullities get a tick mark and one shared annotation instead.
    zero_idx = [i for i, d in enumerate(deltas) if d == 0.0 and i != 0]
    for i in zero_idx:
        ax.plot([i], [0.0], marker=3, markersize=8, color="#b03030", ls="none", clip_on=False)
    for i, d in enumerate(deltas):
        if i == 0 or d == 0.0:
            continue
        ax.text(i, d - 0.16 - (0.13 if i % 2 else 0.0), f"{d:+.2f}%", fontsize=5.6, ha="center")
    ax.text(0.02, 0.94, "red tick = design measured bit-identical to the no-op",
            transform=ax.transAxes, fontsize=6.0, color="#b03030", va="top")
    ax.set_ylim(min(deltas) - 0.5, max(deltas) + 0.55)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    fig.tight_layout(pad=0.4)
    fig.savefig(OUT, bbox_inches="tight")
    print(f"wrote {OUT}")
    print("panel a:", [(n.replace(chr(10), ' '), round(v, 4)) for n, v in sources])
    print("panel b: bars =", len(labels),
          " nullities =", sum(1 for i, c in enumerate(colours) if c == "#b03030"),
          " module names with >1 cycle count =", name_collisions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
