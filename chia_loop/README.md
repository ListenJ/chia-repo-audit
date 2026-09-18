# CHIA Reproducibility Audit Loop

This directory contains the submitted audit loop and its calibration cases.

## What It Measures

| Metric | Definition | Pre-registered gate |
| --- | --- | --- |
| Repeated-run CV | Same candidate + trace + environment, repeated executions | Report; expected near zero for deterministic ChampSim |
| Cross-seed CV | Same prompt + trace, different generation seeds | `< 5%` for a reproducible result |
| Prompt spread | Same seed + trace, different generation prompts | Report |
| Trace CV | Same seed + prompt, different traces | Report; diagnostic only |
| Classification agreement | A/B gold and adversarial audit cases | Cohen's kappa `>= 0.7` |
| Adversarial detection | Known-bad design cases caught | `100%` |

The catalog generator maps seed and prompt to concrete fixture candidates. The
directory generator loads JSON candidates emitted by an external LLM agent.
The real ChampSim backend must receive a candidate with generated
`prefetcher_source`; otherwise the numbers remain a plumbing test.

## Run Locally

```bash
python3 chia_loop/loops/audit_repro.py --version 5
python3 -m unittest discover -s chia_loop/tests -v
```

To keep generated evidence separate:

```bash
python3 chia_loop/loops/audit_repro.py \
  --version 5 \
  --output-dir /tmp/chia-audit
```

## Run Through CHIA

The `--execution chia` path uses the decorator dispatch only when a CHIA/Ray
cluster is already running:

```bash
python3 chia_loop/loops/audit_repro.py \
  --execution chia \
  --version 5 \
  --output-dir /shared/results/chia-audit
```

See `cluster.yaml` for the documented `chia-champsim` worker setup. The
legacy `ChampSimBackend` in `sim/backends.py` remains a scaffold until it is
validated against an official ChampSim build.

## Cases

- `gold/gold-01.json` through `gold-05.json`: calibration set covering E0-E4.
- `adversarial/av-001.json` through `av-005.json`: planted failure cases,
  including the weak-verifier `always-PASS` trap.
- `gold/answer-key.json`: human-readable key; the runner uses the `expected_*`
  fields embedded in each case.

## Outputs

- `env_pin.json`: git SHA, Python version, config digest.
- `raw.json`: every measured trial plus candidate and configuration digests.
- `dblind_report.json`: per-case classification and publish gate.
- `audit_report.json`: computed reproducibility and sensitivity metrics.
- `ranking_stability`: top-1 and Kendall-tau stability across leave-one-trace-out
  evaluations.
- `scorecard.txt`: compact human-readable result.
