# Research Notes — 支撑证据（来自 2026-09 15 路领域扫描）

本项目不是一个从零开始的灵光一现，而是 15 路并行检索收敛结果的具体落地。
以下是支撑本项目的关键证据。

## 1. 生态位收敛（6 个独立领域一致指向「审计/测量/验证」）

| 领域 | 各自独立结论 |
| --- | --- |
| 06 评测 | 三项 harness 自检是发布任何 benchmark 分数的前置条件；统计层已被 evalci/Inspect AI 商品化 |
| 12 AI4Science | 主项目建议 = 开源 u-MLIP 可信度审计与失效图谱 |
| 13 机器人 | 建议「造标尺」而非「造方法」；零真机的评测/审计类贡献被顶会接受 |
| 14 生成模型 | 世界模型几何漂移的内部可预测性（表示级诊断） |
| 11 安全 | AI 漏洞发现宣称的独立复现审计 + 面向 CRA 的证据化分诊 |
| 07 形式化 | AI 生成 Lean 证明的「伪证明」测量学 |

## 2. CHIA 框架事实（2026-09 实测）

- 仓库：github.com/ucb-bar/chia（BSD-3-Clause，90 stars，2026-09-09 更新）
- 论文：arXiv 2606.27350 ｜ 文档：docs.chialoops.ai
- 内置：Chipyard / gem5 / ChampSim / FireSim / Verilator / Spike / Hammer / CIRCT
- 内置 AI 平台：Gemini / Antigravity / GCP / AlphaEvolve
- 论文实测：gem5↔RTL 对齐 202 次迭代达 ~3% cycle 误差；MegaBOOM 实现 RISC-V Bitmanip/Crypto/Zicond，25.5 万亿指令 SPEC CPU2006 验证

## 3. 被审计对象（2026 快速膨胀的 agentic 芯片设计生态）

- ArchAgent：用仿真在 SPEC cache replacement 取得 SoTA（无硬件）
- CHIA、QuArch、HLS-Eval：Architecture 2.0 生态
- ISCA 2026 Architecture 2.0 workshop：无正式 proceedings、4 页 WIP 门槛
- **缺口：无任何工作测量「AI 生成设计的可复现性/评测公平性」**（这是本项目的核心主张）

## 4. 评测可信度危机的先例（为什么这个问题是真实且紧迫的）

- Meerkat 审计（2026-04）：Terminal-Bench 2 前三名提交全部作弊；根因是开发者用 coding agent 写 scaffold，元 agent 自己作弊
- OpenAI 弃用 SWE-bench Verified（2026-02）、撤回 SWE-bench Pro（2026-07）
- Anthropic：资源配比单独就能让 Terminal-Bench 2.0 摆动 6pp；差异低于 3pp 值得怀疑

→ 如果软件侧的 agent 评测已经出现如此严重的可信度危机，**硬件侧的 agent 设计结果只会更严重（更贵、更难复现）**。

## 5. 资源约束

- 本机：Ryzen 5 5600H（6C/12T）/ 13 GiB / RTX 3050 Mobile（4 GB，CUDA 已验证可用，2026-09-13）
- 短期算力：CHIA 资助提供 GCP/Gemini 额度（09-21..23 可用）
- 策略：先本地跑桩验证循环逻辑；算力到账后跑真实 ChampSim