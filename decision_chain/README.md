# Decision chain: a local discriminative head routing real submission decisions

This directory ships the code and the recorded output behind §3.8 of the paper
("An approval score that cannot separate the safe action from the destructive one").
It is here rather than only in the paper because the paper quotes numbers from it.

## What it is

`laya_gate2.py` runs a 421M ModernBERT **discriminative** decision head
(`convaiinnovations/laya`) over a list of live project decisions and emits a routing
verdict for each. The head chooses among options; **whether an option needs a human is
decided in code**, from a per-option `blast_radius` register in the spec.

The head's own `needs_approval` score is recorded but does not gate anything, because
`laya_noul_ladder.py` measured it and it failed:

```
Spearman(blast tier, noul) = +0.4064   n=10
tier0 (local reversible)  mean=0.2155  max=0.4044
tier3 (irreversible)      mean=0.4581  min=0.2358
separation min(tier3)-max(tier0) = -0.1686
verdict: NOT-USABLE-AS-GATE
```

Ten scenarios of known blast radius, four tiers. `min(tier3) < max(tier0)` means no
threshold separates the safest action from the most destructive one, so a rule of the
form "escalate when the approval score exceeds 0.5" is a constant, not a conservative
policy. `results/noul_approval_ladder.json` carries the per-scenario rows.

## Files

| file | role |
| --- | --- |
| `laya_noul_ladder.py` | the falsification control; writes `noul-ladder.json` |
| `laya_gate2.py` | the gate: register decides blast radius, model only chooses |
| `chia-decisions2.json` | the spec, including each option's `blast_radius` |
| `chia-decisions2.verdicts.json` | the recorded routing output the paper cites |

## Running it

Needs the checkpoint locally (`/root/models/laya`) and a CUDA device; there is no
service to call. From this repository's directory on the machine that has them:

```
wsl -d Arch /root/.venvs/laya/bin/python decision_chain/laya_noul_ladder.py
wsl -d Arch /root/.venvs/laya/bin/python decision_chain/laya_gate2.py decision_chain/chia-decisions2.json
```

`laya_gate2.py` also writes `<spec>.verdicts.json` next to the spec it was given.

## What was actually done with it

The recorded verdicts routed four live decisions: two were escalated because the chosen
option is an outside write (`push` to the public artifact, editing the HotCRP form) and
those were handed to the human rather than executed; two were automatic
(freeze the evidence set after the grid already running; keep the instances up until
collection finishes) and were executed. The gate's cross-check agreed with the register
on three of the four.

## Known limits of this measurement

- `n=10` scenarios, one author-written ladder. It establishes non-separability on that
  ladder; it is not a general calibration study of the checkpoint.
- The checkpoint ships invalid temperatures for some option counts and warns that
  affected entries are uncalibrated, so treat the scores as ordinal, not probabilistic.
- The register is hand-authored. That is the point -- blast radius is a property of the
  action, and making it a declared input is what let the `keep_running`
  misclassification be caught at all.
