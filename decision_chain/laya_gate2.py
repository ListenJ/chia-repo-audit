"""决策闸门 v2：模型只负责在候选动作里选一个，**爆炸半径由代码侧登记表决定**。

v1 的三条规则里，第 3 条（任一 noul>0.5 ⇒ ESCALATE）已被对照实验否证：
laya_noul_ladder.py 对 10 个已知层级的场景打分，Spearman(层级, noul)=+0.406，
且 min(tier3)-max(tier0) = -0.169 —— 真实的外写动作 edit_submission 得 0.126，
比"本地可逆改写、原件留在 git 历史"的 0.160 还低。信号是反的。
建立在这种分数上的规则不是保守，是没有规则：它对所有输入一律 ESCALATE，
于是"自动化"名存实亡，而人并没有因此多看到任何模型真正拿不准的地方。

v2 规则：
  1. 选中动作的 blast_radius ∈ {external_write, destructive} ⇒ ESCALATE（代码判定，不看概率）；
  2. choice 的 top1-top2 < MARGIN_MIN ⇒ ESCALATE（模型自己拿不准，这才是它的信号）；
  3. noul 降级为**交叉核对**：与登记表不一致时打一行分歧，不改变裁定。
第 1 条按**选项**粒度而非问题粒度判定 —— v1 把整道题标成不可逆，
于是 D5 选出"先别删、继续跑"这个最不不可逆的动作也被判成不可逆。
"""
import json
import sys
from pathlib import Path

import torch

from laya import RLAgent

CKPT = "/root/models/laya"
MARGIN_MIN = 0.15
ESCALABLE = {"external_write", "destructive"}
NOUL_HINT = 0.5


def main(path: str) -> int:
    spec = json.load(open(path, encoding="utf-8"))
    agent = RLAgent(model_id_or_path=CKPT, device="cuda")
    for m in vars(agent).values():
        if isinstance(m, torch.nn.Module):
            m.to(torch.bfloat16)

    verdicts = []
    for dec in spec["decisions"]:
        out = agent.predict(spec["state"], dec["questions"])["answers"]
        radius = dec.get("blast_radius", {})
        reasons, auto, chosen = [], True, None

        for q, r in out.items():
            if r["type"] != "choice":
                continue
            p = r["probabilities"]
            top = sorted(p.items(), key=lambda kv: -kv[1])
            margin = top[0][1] - top[1][1]
            chosen = top[0][0]
            tag = radius.get(chosen)
            if margin < MARGIN_MIN:
                auto = False
                reasons.append(f"margin {margin:.3f} < {MARGIN_MIN}：模型自己拿不准")
            if tag in ESCALABLE:
                auto = False
                reasons.append(f"选中 {chosen} 登记为 {tag}，外写/不可逆由代码判定")
            print(f"  [{dec['id']}/{q}] choice={chosen} margin={margin:.3f} blast={tag} "
                  f"probs={json.dumps(p, ensure_ascii=False)}", flush=True)

        # 交叉核对：noul 与代码登记表不一致只留痕，不改裁定
        for q, r in out.items():
            if r["type"] != "noul" or "approval" not in q:
                continue
            v = r["noul"]
            if (v > NOUL_HINT) != (not auto):
                reasons.append(f"[核对] noul={v:.3f} 与登记表不一致（模型判"
                               f"{'需批' if v > NOUL_HINT else '可自动'}，不作依据）")
            else:
                reasons.append(f"[核对] noul={v:.3f} 与登记表一致")

        verdicts.append((dec["id"], "AUTO" if auto else "ESCALATE", reasons, chosen))

    print("\n=== 裁定 (v2) ===")
    n_auto = 0
    records = []
    for did, v, rs, ch in verdicts:
        n_auto += v == "AUTO"
        print(f"{v:<9} {did}" + (f"   [{ch}]" if ch else "")
              + "".join(f"\n          · {r}" for r in rs))
        records.append({"id": did, "verdict": v, "chosen_action": ch, "reasons": rs})
    print(f"\nAUTO {n_auto}/{len(verdicts)}   ESCALATE {len(verdicts) - n_auto}/{len(verdicts)}")

    # 机器可读的派发结果：驱动可以据此直接执行 AUTO 格，不必让人先读一遍散文。
    Path(path).with_suffix(".verdicts.json").write_text(json.dumps({
        "gate_version": 2,
        "margin_min": MARGIN_MIN,
        "escalable_blast_radii": sorted(ESCALABLE),
        "noul_role": "advisory cross-check only; measured Spearman(blast tier, noul)=+0.406 "
                     "with min(tier3)-max(tier0)=-0.169, so it is not used as a veto",
        "decisions": records,
        "auto": [r["id"] for r in records if r["verdict"] == "AUTO"],
        "escalate": [r["id"] for r in records if r["verdict"] == "ESCALATE"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
