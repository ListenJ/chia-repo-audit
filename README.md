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
- A scaffold for a real ChampSim backend; it has not yet passed a smoke run.
- Five gold and five adversarial design-classification cases.
- Machine-readable repeatability, seed, prompt, and trace sensitivity metrics.
- A three-page paper draft whose measured numbers need to be refreshed.

The most important external blockers are not code:

1. Confirm short-term compute access before the funding window on Sep 21-23.
2. Register the HotCRP title, authors, and abstract as soon as possible.
3. Publish the artifact to a public URL. The internal Gitea URL cannot be the
   final artifact link.

See [ROADMAP.md](ROADMAP.md) for the 6-day execution plan, acceptance gates,
and claim boundaries.

## Current Stub Validation

The stub run validates the audit plumbing, not ChampSim performance:

```text
Backend: stub
Verdict: REPRODUCIBLE
Max cross-seed CV: 3.5339% (gate < 5%)
Max repeated-run CV: 0.1964%
Max prompt spread: 0.7610%
Max trace CV: 0.2495%
Cohen's kappa: 1.0 (deterministic protocol self-test)
Adversarial detection: 100%
Gold calibration: 5/5
Publish gate: PASS
```

The nonzero repeated-run CV comes only from the synthetic stub. A real
deterministic ChampSim run should be bit-identical unless the executable,
trace, or environment changes.

## Run

No third-party Python dependencies are needed for the stub:

```bash
python3 chia_loop/loops/audit_repro.py --version 4
python3 -m unittest discover -s chia_loop/tests -v
```

Outputs:

```text
results/env_pin.json
results/raw.json
results/dblind_report.json
results/audit_report.json
results/scorecard.txt
```

Use a separate output directory without touching the checked-in evidence:

```bash
python3 chia_loop/loops/audit_repro.py \
  --version 4 \
  --output-dir /tmp/chia-audit
```

CHIA execution is explicit and requires a running CHIA/Ray cluster:

```bash
python3 chia_loop/loops/audit_repro.py --execution chia --version 4
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
  README.md
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
