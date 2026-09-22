# Colab CPU Validation Implementation Plan

**Goal:** Use the authenticated Colab CLI to validate the pinned ChampSim path on a named high-memory CPU runtime and preserve only evidence that can be traced to exact inputs.

**Architecture:** Provision one named Colab CPU session, inspect its machine shape, then execute the repository's pinned source-build smoke through a small bootstrap script. Download the result before releasing the runtime. Continue to the real candidate grid only if three generated candidate artifacts and three independent traces are available; otherwise stop at the smoke result and record the evidence gap.

**Tech Stack:** Google Colab CLI 0.7.1, Python 3, Git, DPC4-ChampSim, repository audit scripts.

---

## Task Contract

任务: Create and operate a Colab high-memory CPU session for CHIA/ChampSim validation.

验收标准:
- A named Colab session reports its actual CPU and memory shape.
- The pinned ChampSim smoke completes and produces a downloadable JSON result.
- The result records the pinned ChampSim commit and smoke-trace SHA-256.
- The Colab session is stopped after evidence is downloaded.
- Real experiment claims are made only if three real LLM candidates and three traces are present.

改动清单（文件级）:
- Create `docs/plans/2026-09-22-colab-cpu-validation.md`.
- Create `scripts/colab_champsim_job.py` only if the existing smoke script cannot run through `colab exec` without a bootstrap wrapper.
- Create or update a Colab result JSON under `results/` only after a successful remote run.
- Modify `docs/operations-log.md` after validation to record commands, outputs, cleanup, and evidence boundaries.

不做项:
- Do not purchase Colab compute units or change subscription settings.
- Do not use GPU/TPU resources for the CPU-bound ChampSim simulation.
- Do not store API keys, passwords, OAuth tokens, or account identifiers in the repository.
- Do not treat the source-build smoke as an official CHIA Docker/Ray experiment.
- Do not mark HotCRP submission #27 ready without real candidate-grid evidence.

验证命令:
```bash
colab sessions
colab status -s chia-cpu-audit
python3 -m unittest discover -s chia_loop/tests -v
git diff --check
git status -sb
```

风险/回滚:
- A Colab session consumes compute units while allocated. Stop it immediately on an abort condition and always run `colab stop -s chia-cpu-audit` after downloading evidence.
- Colab VMs are ephemeral. Download the JSON result before stopping the session.
- If high-memory CPU is unavailable, retry once with standard CPU only when the high-memory request fails without allocating a session.
- If required build tools, network access, or the pinned source build fail, retain logs, stop the session, and do not broaden the task.
- If real candidates or three traces are absent, stop after smoke validation and report the exact missing evidence.

## Execution Steps

1. Create `chia-cpu-audit` with `colab new -s chia-cpu-audit --high-mem`.
2. Inspect `colab status -s chia-cpu-audit` and an in-VM hardware probe.
3. Execute the pinned source-build smoke with a 30-minute ceiling.
4. Download the result JSON and verify commit/hash/metrics locally.
5. Check whether the real candidate and trace contracts are satisfied.
6. Stop the Colab session in all success or failure paths.
7. Run repository tests and record the operation.
8. Commit and push only task-related evidence to both remotes.
