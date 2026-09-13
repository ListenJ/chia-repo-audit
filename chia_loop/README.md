# CHIA 复现性审计 loop

**题目**：*Does Agentic Architecture Discovery Reproduce? Auditing Variance and Evaluation Fairness in LLM-Driven Microarchitecture Search*

这个 CHIA loop 实现了一个**复现性审计**流程：它运行一个（当前为桩、09-23 后为真实 gem5/ChampSim 的）体系结构仿真器，在预注册的种子 × 提示词 × 轨迹网格上重复多次，输出一份**可复现性记分卡**。

## 为什么是它（对齐本团队 15 路检索的收敛结论）

2026 年 ISCA/MICRO 生态（ArchAgent、CHIA、QuArch、HLS-Eval）正在快速膨胀，但 2026 检索未发现任何工作系统性地衡量「**AI 生成的硬件设计结果是否可复现、评测是否公平**」——这正是一个真实且未被占用的测量缺口（候选清单 C50，报告 15）。

## 这个 loop 审计什么

| 维度 | 预注册口径 | 判定阈值 |
| --- | --- | --- |
| 跨种子方差 | 同 prompt+trace 下不同 seed 的 cycle 变异系数 | <5% 判可复现 |
| 提示词敏感性 | 同 seed+trace 下不同 prompt 的 cycle 极差比 | 报告中列出 |
| 轨迹子集敏感性 | 同 seed+prompt 下不同 trace 的变异系数 | 报告中列出 |

## 运行

```bash
# 本地跑桩（现在就能验证循环逻辑）
cd ~/repos/chia-repro-audit
python3 chia_loop/loops/audit_repro.py --version 1
# 输出在 results/scorecard.txt 与 results/audit_report.json

# 拿到算力后跑真实仿真（替换 _run_simulator 为 gem5/ChampSim 后端）
# CHIA:  chia run chia_loop/loops/audit_repro.py --cluster chia_loop/cluster.yaml
```

## 结构

```
chia_loop/
├── loops/
│   └── audit_repro.py   # 4 阶段 CHIA loop（prepare→run→audit→act）
├── cluster.yaml          # 集群节点定义
└── README.md
```

## 下一步（09-21 算力到账后）

1. 把 `_run_simulator()` 换成真实 ChampSim/gem5 调用，返回真实 cycles/IPC/L1 指标
2. 接入 ArchAgent 类 cache-replacement 自动发现流程，作为被审计对象
3. 用竞赛轨迹全集 vs 子集做敏感性对照（C50 的第三维度）
4. 产出 4 页 A³ 论文 + 开源 loop + 原始日志