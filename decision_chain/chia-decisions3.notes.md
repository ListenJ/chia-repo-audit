# Decision set 3 — reading, and two method notes

Machine record: `chia-decisions3.verdicts.json` (written by `laya_gate2.py` itself).
Spec: `chia-decisions3.json`. Reproduce:

```
wsl -d Arch /root/.venvs/laya/bin/python decision_chain/laya_gate2.py chia-decisions3.json
```

Run at 2026-09-23T18:52Z on the bf16 CUDA load of `/root/models/laya`.

## What it says

Four decisions that had *actually* arisen in the session that found defect 8, each with
the action the author really took recorded in the spec, so the comparison is against an
outcome and not a hypothetical.

| id | model top-1 | margin | noul | gate verdict | author did | agree |
| --- | --- | --- | --- | --- | --- | --- |
| D14 contaminated variance axes | `discard_axes_keep_nullity` | 0.010 | 0.763 | ESCALATE | same | yes |
| D15 land the harness fix | `fix_tests_then_keep` | 0.311 | 0.627 | AUTO | same | yes |
| D16 VM teardown timing | `keep_until_submission` | 0.118 | 0.835 | ESCALATE | same | yes |
| D17 publish uncompiled paper | `wait_for_compile` | 0.204 | 0.732 | AUTO | same | yes |

**Top-1 agreement is 4 of 4.** The two escalations are the two decisions whose trade-off
was genuinely close (0.3842 vs 0.3745 on "discard the axes" against three hours of
sponsored compute; 0.4271 vs 0.3086 on billing against option value), and the two
automated ones are the two with a clear winner. That is the behaviour v1 lacked.

**Do not read `AUTO 2/4` as progress over `0/6` from set 2.** Different decisions, later
stage, different wording: the denominator is not the same quantity. The only cross-set
claim made anywhere is about the *approval head*, which was re-tested deliberately.

## The approval head replicated its own failure, on different text

The first cut of this spec gave all four decisions the *same* `needs_approval` question
text, and the head returned `noul=0.170` four times — a constant, because a
discriminative model reading only the question text must return one answer for four
copies of it. The script then compared that constant with a per-option register and
printed a "disagrees with the register" line that was a property of the option label, not
of any judgment. Vacuous by construction.

After rewriting each noul question to describe its own decision, the scores spread to
**0.627 – 0.835**, ordering weakly sensibly (deleting two instances highest, a local test
rewrite lowest), which matches the ladder probe's Spearman **+0.406**: a weak positive
that does not separate. Decisively, **all four exceed the 0.5 "needs approval" hint**, so
a rule keyed on that threshold escalates 4 of 4 and automates nothing. Same conclusion as the paper's `sec:gate2`
finding, reached again on an independently built set with different wording — which is what
makes it a replication rather than a re-reading.

## Method note worth keeping

The author's first attempt at this record was a hand-written analysis saved to
`chia-decisions3.verdicts.json` — the exact path the gate uses for its own output. The
re-run silently overwrote it. Any file that a driver derives should not be authored by
hand at the same path; notes go in a `.notes.` file, and a run that writes evidence
should be started before, not after, the prose about it is drafted.
