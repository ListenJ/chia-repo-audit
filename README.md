# CHIA Hackathon 提交项目：Agentic Architecture 复现性审计

> **项目**：*Does Agentic Architecture Discovery Reproduce? Auditing Variance and Evaluation Fairness in LLM-Driven Microarchitecture Search*
> **Hackathon**：CHIA Hackathon @ A³ (MICRO 2026)
> **提交截止**：2026-09-24 (AoE) ｜ **算力资助登记**：2026-09-13（已登记）
> **交付物**：4 页论文 + 开源 CHIA loop + 结果

## 一句话

用 CHIA/ChampSim 复现 AI 驱动的微架构搜索流程，测量其跨种子方差、提示词敏感性与轨迹子集敏感性——回答「agent 发现的东西，可复现、可信吗」这一 2026 年尚未被系统回答的问题。

## 背景（来自本团队 2026-09 15 路领域扫描）

ISCA 2026 首设 Architecture 2.0 workshop（无正式 proceedings、4 页 WIP、门槛极低）；CHIA 框架 2026-06 由 UC Berkeley SLICE lab 发布（BSD-3-Clause、开源、内置 Chipyard/gem5/ChampSim/FireSim）。**但 2026 检索未发现任何工作测量「AI 生成硬件设计的可复现性与评测公平性」**——Agent 基础设施、AI4Science、机器人、形式化方法、安全、体系结构共 6 个独立领域一致指向同一生态位：「审计/测量/验证」。本项目正是这一生态位在体系结构领域的具体落地。

## 策略

1. **占位**（本周）：提交一个最小合规 CHIA loop，拿到短期算力资助（GCP/Gemini）与 office hours 支持
2. **做深**（09-21 算力到账后）：接入真实 ChampSim，跑预注册的种子×提示词×轨迹审计网格
3. **提交**（09-24）：4 页 A³ 论文 + 开源 loop + 原始日志

## 内容

```
├── README.md           ← 本文件
├── proposal.md         ← 登记表单内容（已提交）
├── paper/              ← 4 页论文（A³/ICLR 轨道）
├── chia_loop/          ← 开源 CHIA loop（提交的核心交付物）
│   ├── loops/audit_repro.py
│   ├── cluster.yaml
│   └── README.md
├── research-notes/     ← 支撑证据（来自 15 路检索）
├── scripts/            ← 构建/运行辅助
└── results/            ← 运行输出（原始日志 + 记分卡）
```

## 资格与奖励

- GPU 奖（RTX 5080）：**中国大陆不在资格名单** → 不认
- **GCP/Gemini 算力补贴：不受居住地限制，提交提案即得** → 本项目登记的核心收益
- UC Berkeley 附属机构不可参加：不适用，符合资格 ✅

## 运行

```bash
cd ~/repos/chia-repro-audit
python3 chia_loop/loops/audit_repro.py --version 1
# → results/scorecard.txt 复现性记分卡
```

## 当前状态

- [x] 算力资助登记（2026-09-13）
- [x] 最小合规 CHIA loop（桩仿真，本地可跑）
- [ ] 真实 ChampSim 后端（09-21 算力到账后）
- [ ] 4 页论文草稿
- [ ] 09-24 提交