"""用修好的口径重derive 语义用例的 gold 标签，并把 κ 对着保留下来的标注原文重算。

发现的缺陷：``comparators()`` 在**未预处理的源码**上抓 ``<=|>=|<|>``，于是
``#include <vector>`` 的两个尖括号被当成比较运算符。三对被标成
``not_equivalent|E2``（方向错误）的真实候选，唯一的结构差异是**谁多 include 了几个头文件**。
两个生成式标注者在这三对上判 equivalent，判对了 —— 是我的 gold 标签错了。

这里不重新调用任何模型：``results/audit_independent_*/raw.json`` 保留了每个标注者对每个
用例的 ``verdict`` 与原文，所以标签修正后可以直接重算 κ 与准确率。
用 --write 落盘修正，否则只报告差异。
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from independent_audit import cohen_kappa  # noqa: E402
from semantic_cases_from_candidates import classify  # noqa: E402

SETS = {
    "measured6": (REPO / "chia_loop/semantic", REPO / "results/audit_independent_semantic_v3/raw.json"),
    "fact36": (REPO / "chia_loop/semantic_fact", REPO / "results/audit_independent_fact36/raw.json"),
}


def relabel(case_dir: Path, write: bool, stats: dict) -> list[dict]:
    out = []
    for path in sorted(case_dir.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if "design" not in case or "reference" not in case:
            continue
        d, r = case["design"], case["reference"]
        if "prefetcher_source" not in d or "prefetcher_source" not in r:
            continue
        ev = case.get("evidence", {})
        d_cyc = ev.get("design_cycles") if isinstance(ev.get("design_cycles"), dict) else {}
        r_cyc = ev.get("reference_cycles") if isinstance(ev.get("reference_cycles"), dict) else {}
        # A case whose label already comes from a measured cycle count is not up for
        # re-derivation from text: that is how sem-esc-01 earned "equivalent".
        if isinstance(ev.get("design_cycles"), (int, float)) or ev.get("label_basis") == "measured cycles":
            stats["measurement_grounded_skipped"].append(case["id"])
            continue
        verdict, errors, note = classify(
            d["prefetcher_source"], r["prefetcher_source"],
            d.get("module_name", ""), r.get("module_name", ""),
            d_cyc, r_cyc)
        stats["verdicts"][verdict] = stats["verdicts"].get(verdict, 0) + 1
        old = (case["expected_verdict"], sorted(case.get("expected_errors", [])))
        new = (verdict, sorted(errors))
        if old == new:
            continue
        out.append({"id": case["id"], "old": "|".join([old[0], ",".join(old[1])]),
                    "new": "|".join([new[0], ",".join(new[1])]), "note": note,
                    "path": str(path.relative_to(REPO))})
        # Only a case whose label actually moved carries the defect note: writing it
        # everywhere would claim 36 mislabels where there were three.
        if write:
            case["expected_verdict"] = verdict
            case["expected_errors"] = sorted(errors)
            ev = case.setdefault("evidence", {})
            ev["label_basis"] = "source structure only (headers and comments stripped)"
            ev["relabel_note"] = note
            ev["previous_expected"] = {"verdict": old[0], "errors": old[1]}
            ev["relabel_defect"] = ("comparators() previously matched the angle brackets in "
                                    "#include directives, so header-count differences were "
                                    "read as comparison-polarity (E2) differences")
            path.write_text(json.dumps(case, indent=1, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    return out


def rescore(name: str, case_dir: Path, llm_raw: Path) -> dict:
    gold = {}
    for path in sorted(case_dir.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        gold[case["id"]] = (case["expected_verdict"],
                           sorted(case.get("expected_errors", [])))
    if not llm_raw.is_file():
        return {"error": f"missing {llm_raw}"}
    records = json.loads(llm_raw.read_text(encoding="utf-8"))
    records = records if isinstance(records, list) else records.get("records", [])

    per_model: dict[str, dict] = {}
    for rec in records:
        cid = rec.get("id")
        if cid not in gold:
            continue
        for lab in rec.get("labels", []):
            if lab.get("parse_ok"):
                per_model.setdefault(lab["model"], {})[cid] = lab
    models = sorted(per_model)
    shared = sorted(set.intersection(*[set(per_model[m]) for m in models])) if models else []

    entry = {"n_scored": len(shared)}
    if not shared:
        return {**entry, "error": "no case is scored by every annotator"}
    # A case the labeler cannot label has no ground truth to be scored against.
    labellable = [c for c in shared if gold[c][0] != "unlabellable"]
    entry["n_labellable"] = len(labellable)
    entry["n_unlabellable"] = len(shared) - len(labellable)
    if not labellable:
        return {**entry, "error": "no case in this set carries a derivable label"}
    shared = labellable
    for m in models:
        entry[f"verdict_accuracy_{m}"] = round(
            sum(1 for c in shared if per_model[m][c]["verdict"] == gold[c][0]) / len(shared), 4)
        entry[f"combined_exact_{m}"] = round(
            sum(1 for c in shared
                if (per_model[m][c]["verdict"], sorted(per_model[m][c]["errors"])) == gold[c])
            / len(shared), 4)
    if len(models) >= 2:
        a, b = per_model[models[0]], per_model[models[1]]
        entry["kappa_verdict_only"] = round(
            cohen_kappa([(a[c]["verdict"], b[c]["verdict"]) for c in shared]), 4)
        entry["kappa_combined_label"] = round(cohen_kappa([
            (a[c]["verdict"] + "|" + ",".join(sorted(a[c]["errors"])),
             b[c]["verdict"] + "|" + ",".join(sorted(b[c]["errors"]))) for c in shared]), 4)
        entry["annotators_agree_with_each_and_wrong"] = [
            c for c in shared
            if a[c]["verdict"] == b[c]["verdict"] != gold[c][0]]
        entry["annotators_agree_and_right"] = sum(
            1 for c in shared if a[c]["verdict"] == b[c]["verdict"] == gold[c][0])
        entry["annotators_disagree"] = sum(1 for c in shared if a[c]["verdict"] != b[c]["verdict"])
    entry["gold_class_tally"] = {}
    for c in shared:
        entry["gold_class_tally"][gold[c][0]] = entry["gold_class_tally"].get(gold[c][0], 0) + 1
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply corrected labels to the case files")
    args = ap.parse_args()

    report = {}
    for name, (case_dir, llm_raw) in SETS.items():
        stats = {"verdicts": {}, "measurement_grounded_skipped": []}
        changed = relabel(case_dir, args.write, stats)
        print(f"[{name}] relabelled {len(changed)} cases (write={args.write}) "
              f"verdicts={stats['verdicts']} "
              f"measurement-grounded-kept={stats['measurement_grounded_skipped']}")
        for c in changed:
            print(f"   {c['id']}: {c['old']}  ->  {c['new']}   ({c['note'][:90]})")
        report[name] = {"relabelled": changed, "label_stats": stats,
                        "rescored": rescore(name, case_dir, llm_raw)}
        print(f"   rescore: {json.dumps(report[name]['rescored'], ensure_ascii=False)[:400]}")

    out = REPO / "results/semantic_relabel_and_rescore.json"
    out.write_text(json.dumps({"mode": "write" if args.write else "dry-run",
                               "defect": ("comparators() matched angle brackets inside "
                                          "#include directives, so a difference in how many "
                                          "headers a generated candidate included was labelled "
                                          "E2 'comparison polarity differs'"),
                               "sets": report},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
