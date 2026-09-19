# CHIA Hackathon: Agentic Architecture Reproducibility Audit

**Project:** *Does Agentic Architecture Discovery Reproduce? Auditing Variance
and Evaluation Fairness in LLM-Driven Microarchitecture Search*

**Hackathon:** CHIA Hackathon at the MICRO 2026 A3 Workshop

**Final deadline:** 2026-09-24 AoE (2026-09-25 19:59 Shanghai)

**Submission:** <https://a3-chia-hackathon-26.hotcrp.com/>

**Internal repository:** `ssh://git@192.168.0.10:2222/agent/chia-repo-audit.git`

## Status

As of 2026-09-18, this repository contains:

- A CHIA audit loop with separate run, audit, and action stages.
- A deterministic stub backend for local protocol validation.
- A pinned ChampSim source-build smoke that completed with identical repeated
  metrics; the official CHIA Docker/Ray path still needs its own smoke.
- Candidate generation modes: an offline catalog fixture and a directory
  interface for real LLM-generated candidates.
- Local integration gate covering CUDA, the official CHIA image, Ray, and
  `ChampSimNode`.
- Five gold and five adversarial design-classification cases.
- Machine-readable repeatability, seed, prompt, and trace sensitivity metrics.
- A three-page paper draft whose measured numbers need to be refreshed.
- Public artifact: <https://github.com/ListenJ/chia-repo-audit>.
- Registered HotCRP submission `#27`, currently saved as a draft with the
  public artifact URL.

The most important external blockers are not code:

1. Receive the new GCP account details on Sep 20 evening PDT. Funding is
   already confirmed; no confirmation action is required.
2. Run the official ChampSim image smoke test before the experiment grid.
3. Finish the paper with real measurements and mark HotCRP `#27` ready.

See [ROADMAP.md](ROADMAP.md) for the 6-day execution plan, acceptance gates,
and claim boundaries. See [COMPUTE_WINDOW.md](COMPUTE_WINDOW.md) for the
new-account migration and 72-hour runbook. See
[KAGGLE_VALIDATION.md](KAGGLE_VALIDATION.md) for the CPU-only preliminary
validation decision. [PRECOMPUTE.md](PRECOMPUTE.md) defines the strict GO/NO-GO
gate and the real candidate contract for the funded window.

## Current Stub Validation

The stub run validates the audit plumbing, not ChampSim performance:

```text
Backend: stub
Verdict: REPRODUCIBLE
Max cross-seed CV: 3.6502% (gate < 5%)
Max repeated-run CV: 0.1964%
Max prompt spread: 0.7899%
Max trace CV: 0.2427%
Trace top-1 stability: 1.0
Trace ranking Kendall tau: 1.0
Cohen's kappa: 1.0 (deterministic protocol self-test)
Adversarial detection: 100%
Gold calibration: 5/5
Publish gate: PASS
```

The nonzero repeated-run CV comes only from the synthetic stub. A real
deterministic ChampSim run should be bit-identical unless the executable,
trace, or environment changes.

## Preliminary Real Smoke

On 2026-09-18, the pinned DPC4-ChampSim revision
`164fdb1ed01185a21a39c292937bf26bb7f4c694` built successfully and ran the
upstream smoke trace twice:

```text
Simulation instructions: 5003
Simulation cycles: 40459
IPC: 0.123656
Repeated runs identical: true
```

Machine-readable evidence:
`results/kaggle_champsim_smoke_result.json`. This validates source build,
trace resolution, JSON parsing, and repeated-run stability. It does not
validate CHIA's Docker/Ray worker or justify a performance claim.

## Run

No third-party Python dependencies are needed for the stub:

```bash
python3 chia_loop/loops/audit_repro.py --version 5
python3 -m unittest discover -s chia_loop/tests -v
```

Outputs:

```text
results/env_pin.json
results/raw.json
results/dblind_report.json
results/audit_report.json
results/scorecard.txt
results/kaggle_champsim_smoke_result.json
```

Use a separate output directory without touching the checked-in evidence:

```bash
python3 chia_loop/loops/audit_repro.py \
  --version 5 \
  --output-dir /tmp/chia-audit
```

CHIA execution is explicit and requires a running CHIA/Ray cluster:

```bash
python3 chia_loop/loops/audit_repro.py --execution chia --version 5
```

Real agent output can be loaded from a candidate directory:

```bash
python3 chia_loop/loops/audit_repro.py \
  --version 5 \
  --generator-mode directory \
  --candidates-dir /path/to/generated/candidates
```

Optional CPU-only source-build smoke test for Kaggle or another Linux
container:

```bash
python3 scripts/kaggle_champsim_smoke.py --dry-run
python3 scripts/kaggle_champsim_smoke.py \
  --work-dir /kaggle/temp/champsim-smoke \
  --output /kaggle/working/kaggle_champsim_smoke_result.json
```

Local GPU and official-image gate:

```bash
python3 scripts/local_gate.py
```

## Metric Definitions

- **Repeated-run CV:** coefficient of variation across repeated executions of
  the same candidate, trace, and environment.
- **Cross-seed CV:** variation across generation seeds for the same
  prompt/trace pair. With the current stub this is synthetic. In a real run,
  the seed must actually change candidate generation.
- **Prompt spread:** relative cycle-count spread across prompt variants for
  the same seed/trace pair.
- **Trace CV:** variation across traces for the same seed/prompt pair. This is
  a diagnostic, not a ranking-stability metric.

The current artifact is an audit-harness pilot. It does not yet establish that
an LLM architecture-discovery loop reproduces.

## Repository Layout

```text
README.md
ROADMAP.md
COMPUTE_WINDOW.md
KAGGLE_VALIDATION.md
PRECOMPUTE.md
proposal.md
paper/
  paper.tex
  paper.pdf
chia_loop/
  loops/audit_repro.py
  sim/backends.py
  gold/
  adversarial/
  tests/
  cluster.yaml
  cluster.gcp.yaml
  README.md
scripts/
  preflight_compute.sh
  kaggle_champsim_smoke.py
  local_gate.py
  champsim_node_smoke.py
results/
research-notes/
```

## Official Submission Requirements

- A PDF of at most four pages in two-column ACM/IEEE style.
- An open-source release of the loop and its results.
- A public artifact URL in the HotCRP form.
- An AI-assistance acknowledgment at the end of the paper.

The final submission does not require prior registration or use of hackathon
funding. The short-term funding request was a separate Sep 18 opportunity for
GCP and Gemini credits.
