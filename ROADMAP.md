# CHIA Hackathon Execution Plan

Last updated: 2026-09-18

## Mission

Build and release an auditable CHIA loop that measures whether candidate
microarchitecture designs are evaluated reproducibly and fairly. The artifact
must make the measurement path inspectable: candidate identity, simulator
inputs, repeated-run variance, evaluation sensitivity, and publish gates all
need machine-readable provenance.

The immediate deliverable is a strong 4-page hackathon paper plus a public,
open-source artifact. The current stub loop validates orchestration and audit
logic; it is not yet evidence that LLM-driven architecture discovery
generalizes.

## Official Requirements

Source: <https://agentic-arch.org/hackathon.html#final-submission>

- Final submission: 2026-09-24 AoE, which is 2026-09-25 19:59 in Shanghai.
- Paper: PDF, at most 4 pages, two-column ACM/IEEE style.
- AI assistance: allowed, but must be acknowledged at the end of the paper.
- Artifact: open-sourced loop and the results it produced.
- Artifact URL: required in the HotCRP submission form. GitHub is preferred;
  the current internal Gitea URL is not a public submission URL.
- HotCRP: <https://a3-chia-hackathon-26.hotcrp.com/>

The organizers' email also asks teams to register a title, preliminary authors,
and abstract as soon as possible. Those fields can be edited before the final
deadline.

## Compute Window

The organizers confirmed short-term funding on 2026-09-18. New account details
will be sent on Sunday 2026-09-20 evening PDT. No additional confirmation
action is required.

The confirmed usage window is:

- Start: 2026-09-21 00:00 PT = 2026-09-21 15:00 Shanghai.
- End: 2026-09-23 23:59 PT = 2026-09-24 14:59 Shanghai.

This leaves only 72 hours for funded runs. Local smoke tests and integration
must therefore finish before the window opens.

The pre-compute checklist and stop condition are frozen in `PRECOMPUTE.md`.

## Project Goal

Ship a loop that answers four separate questions without conflating them:

1. **Repeated-run repeatability:** Does the same candidate, trace, binary, and
   environment produce the same result on repeated execution?
2. **Candidate-seed sensitivity:** When candidate generation is repeated with
   a different seed, how much does the measured cycle count move?
3. **Prompt sensitivity:** When only the generation prompt changes, how much
   does the selected candidate or measured result move?
4. **Trace sensitivity:** How stable is the result or ranking under the trace
   subset used for evaluation?

The double-blind audit is a separate correctness-calibration layer:

- E0: equivalent
- E1: parameter mislink
- E2: direction error
- E3: missing component
- E4: added or fabricated component

The audit gate is evidence about the evaluator, not a substitute for real
simulator evidence.

## Workstreams

### P0 - External Blockers

- Prepare for the new GCP account delivery on Sep 20 evening PDT. Do not reuse
  old projects, credentials, API keys, or billing configuration.
- HotCRP title, authors, abstract, and public artifact URL are registered as
  draft submission `#27`.
- Decide whether the paper reports the present audit-harness pilot or includes
  an actual candidate-generation loop. Do not claim the latter without data.

### P1 - Local Integration, Sep 18-20

- Run the official `ghcr.io/ucb-bar/chia-champsim:latest` image locally.
  The amd64 manifest was verified on 2026-09-18
  (`sha256:4e5c32c94717d97689188e6045afdc65020b0300f321f1b97a4c503afcaa285f`);
  the compressed image is roughly 1.8 GB. A prepull was started but stopped
  because the local link was too slow; Docker preserved the partial layers, so
  resume with `docker pull ghcr.io/ucb-bar/chia-champsim:latest`.
- Exercise CHIA's official `ChampSimNode` with the upstream smoke trace.
- A direct pinned source-build smoke is already complete; it produced
  identical metrics across two runs. This does not replace the official image
  or `ChampSimNode` smoke.
- Optionally run `scripts/kaggle_champsim_smoke.py` in a CPU-only Kaggle
  notebook to catch source-build, trace, and parser failures before GCP.
- Replace or clearly quarantine the legacy hand-written ChampSim command
  adapter until a real build/run is verified.
- Define one candidate unit with a content digest and one reference unit.
- Add an end-to-end smoke result that records git SHA, image digest, trace
  digest, command, raw output, and parsed metrics.
- Keep `python3 -m unittest discover -s chia_loop/tests -v` green.

Acceptance gate for P1:

- One command reproduces the stub result.
- One command runs one real ChampSim measurement in the official image.
- The two commands and their outputs are documented in the public artifact.
- Kaggle, when used, is reported only as a preliminary source-build check.

### P2 - Funded Runs, Sep 21-23

Run in this order and stop when the next stage no longer fits the window:

1. **Smoke:** one candidate, one trace, one run.
2. **Core:** one candidate, three traces, one run per trace.
3. **Sensitivity:** multiple candidates or seeds across three traces. Use
   candidate generation, not arbitrary simulator seeds, for the seed axis.
4. **Audit:** all 10 gold/adversarial classification cases.
5. **Replication:** repeat one core cell to test repeated-run stability.

Required evidence:

- Raw stdout/stderr and structured metrics.
- Candidate and trace hashes.
- Tool/image versions and build revision.
- Cost or wall-clock estimate per run.
- Failed runs retained rather than deleted.

### P3 - Paper and Release, Sep 24

- Replace every stub placeholder with measured values or label it explicitly
  as a stub validation.
- Correct the prompt-sensitivity and trace-variance definitions in the paper.
- Add the required AI-assistance disclosure at the end of the paper.
- Verify the PDF is at most 4 pages and uses a two-column ACM/IEEE layout.
- Freeze the artifact at the measured revision and verify the public URL.
- Submit through HotCRP with paper, artifact URL, authors, and abstract.

## Current Gaps

- The official CHIA Docker image and `ChampSimNode` path are still unverified;
  the direct pinned source-build smoke passed.
- Seed and prompt now select concrete candidates, but the default catalog is a
  fixture; real agent output must be loaded through directory mode.
- The full trace grid has not yet run; only the 5,003-instruction smoke path
  has.
- The source-build smoke script has not yet run in a live Kaggle session.
- The official ChampSim image has not finished downloading locally.

## Non-Negotiable Claims

- Stub numbers must always be labeled as stub numbers.
- Deterministic simulator reruns must not be described as inter-annotator
  agreement.
- Cohen's kappa from identical deterministic auditors is a protocol self-test,
  not a human reliability estimate.
- "No existing work" claims must be softened unless backed by a current,
  reproducible literature search.
- A non-reproducible result is a valid result if the measurement protocol is
  sound and the evidence is retained.

## Immediate Next Action

Before any new experiment:

1. Confirm HotCRP draft `#27` before the final ready marker.
2. Complete the new-account preflight in `COMPUTE_WINDOW.md`.
3. Verify the public GitHub artifact remains available.
4. Run the official ChampSim smoke path locally.
