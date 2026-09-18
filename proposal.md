# CHIA 算力资助提案（登记表单内容，2026-09-13 已提交）

> **Historical record:** This is the proposal text submitted for compute
> funding. It is not the current execution plan or evidence statement. See
> `ROADMAP.md` for claim boundaries, blockers, and the Sep 18-24 plan.

## Project Description / Overview

We propose an agentic architecture-design loop, built on the CHIA framework, that performs systematic reproducibility and correctness auditing of AI-generated hardware-design artifacts (RTL and microarchitectural decisions) using Chipyard/gem5/ChampSim simulation. The core hypothesis: as LLM agents increasingly generate RTL and make microarchitectural choices, the community lacks a verifiable, reproducible benchmark for measuring (a) whether such outputs are correct, and (b) how their performance claims generalize beyond the training distribution. We build a CHIA-based loop that takes a candidate AI-generated design, runs it through a standardized gem5/ChampSim simulation pipeline with pinned commit hashes, and emits a reproducibility scorecard (cycle-count deltas, sensitivity to flags, cross-iteration variance) — turning the hackathon's "agentic architecture" theme into a measurable, publishable audit of agent trustworthiness in HW/SW co-design.

## Methodology

We use CHIA's built-in toolchain (Chipyard, gem5, ChampSim, Verilator, Spike) as the deterministic execution substrate:

1. Scaffold a minimal "audit loop": an orchestrator agent proposes or fetches an AI-generated RTL/microarchitectural artifact; a runner agent pins the environment and executes the standardized simulation; an auditor agent computes reproducibility/correctness metrics; a feedback agent routes failures back into the loop for bounded retries.
2. Pre-register the metrics and the acceptance thresholds before running (per best practice from the benchmark-integrity literature), so we don't overfit to a favorable outcome.
3. Run the loop across multiple problem tracks from the hackathon list (e.g., BOOM core bug discovery, mid-level cache RTL, agentic formal verification of RTL IP) to test generalization.
4. Release the loop, the pinned configs, and the raw simulation logs as composable CHIA blocks.

## Expected Results

1. A reusable, open-source CHIA loop for reproducibility auditing of agent-generated hardware designs — applicable beyond the hackathon.
2. A first dataset of "agent-generated RTL/design artifacts vs. verified reference" with reproducibility and correctness scores, filling a gap the 2026 scan identified (no existing benchmark measures whether AI-generated designs are trustworthy at the metric level).
3. A short paper (4 pages) for the A³ workshop describing what the audit found — including honest negative results if agent outputs prove non-reproducible.

## Cost Estimate

Short-term funding requested: **$800** (target range $100–$1,500).

- GCP compute for gem5/ChampSim runs across ~20 artifacts × 3 seeds: ≈ $500
- Gemini/API credits for the orchestrator+auditor agent calls over the build window: ≈ $200
- Contingency for larger runs / storage of raw logs: ≈ $100

**Total estimated compute cost: $800 USD**
