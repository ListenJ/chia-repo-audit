# Pre-Compute Completion and Go/No-Go Gate

Updated: 2026-09-18

## Purpose

Finish every code and protocol step that does not require the funded GCP
account. The remaining work must be limited to running the official image,
generating real candidates, collecting evidence, and updating the paper.

If the pre-compute path cannot pass the GO gate after the account arrives, do
not keep polishing the submission. Leave HotCRP #27 as a draft or withdraw it.

Current access status: `BLOCKED_PENDING_ACCOUNT_ACCESS`. Credentials were
received on 2026-09-21, but Google rejected the first login as unverifiable.
The account must be reset, reissued, or have its login challenge adjusted
before any GCP experiment can run.

## Completed Without GCP

- Stub audit loop and unit tests.
- Candidate catalog in which seed and prompt select different designs.
- Directory generator for real LLM candidate artifacts.
- Separate repeatability, seed, prompt, trace, top-1, and Kendall-tau metrics.
- Combined publish gate requiring both reproducibility and audit success.
- Official CHIA `ChampSimNode` adapter with injectable runners.
- Pinned DPC4-ChampSim source build and five repeated smoke runs.
- Official `chia-champsim` image, local Ray, and `ChampSimNode` build/run
  smoke.
- CUDA PyTorch sanity check on the local RTX 3050.
- Kaggle CPU feasibility review and a CPU-only smoke script.
- Public GitHub artifact and HotCRP #27 registration.

## Real Candidate Contract

Directory mode expects one JSON file per generated candidate:

```json
{
  "candidate_id": "gemini-001",
  "generator_seed": 0,
  "prompt": "default",
  "module_name": "candidate_001",
  "design": {
    "prefetcher_source": "struct candidate {};"
  }
}
```

The `prefetcher_source` must compile with the pinned DPC4-ChampSim checkout.
Keep the raw model response and prompt alongside the candidate in the future
evidence bundle.

Run:

```bash
python3 chia_loop/loops/audit_repro.py \
  --version 6 \
  --generator-mode directory \
  --candidates-dir /path/to/generated/candidates \
  --backend champsim_node \
  --chia-root /home/ray/champsim \
  --traces-dir /traces
```

The final backend is selected only after the official `chia-champsim` image
smoke passes.

Run the local gate:

```bash
python3 scripts/local_gate.py
```

Observed on 2026-09-20:

```text
Official image + Ray + ChampSimNode: PASS
Local CUDA matmul: PASS
Local 0.8B strategy model: WARNING (unstable instruction following)
```

The warning is retained. A 0.8B local model is only a portability check and
must not be treated as the final candidate generator.

## GO Gate

A submission is GO only if all conditions below are visible in the artifact:

1. Official `ghcr.io/ucb-bar/chia-champsim:latest` container starts. [Local
   gate: PASS]
2. Real `ChampSimNode.build_champsim` compiles at least three generated
   candidate modules.
3. `ChampSimNode.run_champsim` completes on at least three traces.
4. Raw JSON, commands, image digest, commit SHA, and trace hashes are retained.
5. Two genuinely different auditors or annotators produce labels for the
   hidden evaluation set.
6. Reproducibility, ranking stability, disagreement, and error classes are
   reported from real runs.
7. The combined gate blocks any run whose reproducibility or audit criteria
   fail.
8. The paper contains at least one concrete result that is not a stub number
   or a 5,000-instruction smoke metric.

## NO-GO Gate

Stop and do not claim a competitive submission if any of these remains true:

1. No real LLM-generated candidate compiles.
3. Seed/prompt still do not change the candidate artifact.
4. A/B auditors are still the same deterministic function.
5. The only quantitative evidence is the synthetic stub or source smoke.
6. The paper requires treating an unaudited result as publishable.

NO-GO action:

- Do not mark HotCRP #27 ready.
- Withdraw #27 if no real evidence can be produced before the deadline.
- Keep the public repository as a protocol pilot if withdrawal is chosen.

## Compute-Day Order

1. Official image smoke.
2. One generated candidate build/run.
3. Three generated candidates across three traces.
4. Independent audit on hidden labels.
5. Ranking-stability and repeatability analysis.
6. Paper update and HotCRP PDF replacement.

Do not start with the full grid. Do not optimize the artifact further after a
NO-GO result; either replace the missing evidence or withdraw.
