# Citation audit

Every external claim in `paper/paper.tex` that is not our own measurement was checked
against its cited source on **2026-09-23**. This file records what was checked, against
which URL, and what changed as a result — because a paper about evaluation integrity
cannot ask readers to trust its references.

| # | claim in the paper | source checked | verdict |
| --- | --- | --- | --- |
| 1 | ArchAgent reports an agentic pipeline that discovered and exploited a loophole in a microarchitectural simulator | arXiv:2602.22425 — "ArchAgent: Agentic AI-driven Computer Architecture Discovery", R. Gupta et al. | **supported**, title and authors confirmed |
| 2 | CHIA is the framework this loop is built on | arXiv:2606.27350 — "CHIA: An open-source framework for principled, agentic AI-driven hardware/software co-design research", A. Cui, F. Hermida-Rivera, J. Toubes et al. | **supported**; bibitem upgraded from "CHIA framework" to the real title and authors |
| 3 | the top three Terminal-Bench 2 submissions all cheated via harness-level tricks | debugml.github.io/cheating-agents — "Finding Widespread Cheating on Popular Agent Benchmarks" | **supported**: "the top three submissions to Terminal-Bench 2 are guilty of cheating" (Pilot #1; ForgeCode #2, #3) |
| 4 | an automated audit of 168 agent benchmarks flags issues in over 25.7% of the evaluated tasks | arXiv:2605.26079 — "Automated Benchmark Auditing for AI Agents and Large Language Models", J. Wang, F. Bianchi, S. Zhu et al. | **was a unit error** — see below |
| 5 | OpenAI stopped evaluating on SWE-bench Verified; its audit of SWE-bench Pro found ~30% of tasks broken | openai.com/index/why-we-no-longer-evaluate-swe-bench-verified (2026-02-23); OpenAI audit of SWE-Bench Pro (2026-07) | **was cited to the wrong source** — see below |
| 6 | pre-registration makes a gate's verdict binding rather than negotiable | — | **citation removed** — see below |
| 7 | benchmark contamination is a recognised threat requiring detection methods | aclanthology.org/2026.gem-main.50 — "Are LLM Benchmarks Already Contaminated? A Systematic Review of Contamination Detection Methods", E. Nourbakhsh et al., GEM Workshop Outstanding Paper | **supported**, and re-attached to the claim it actually supports |

## Three defects found and fixed

**(a) A unit error.** The paper said ">25.7% of 168 reviewed benchmarks carry critical
defects". The source reviews **168 benchmarks** and flags issues in over **25.7% of the
evaluated tasks**. Tasks and benchmarks are different denominators, and the original
phrasing made the number look like a fraction of the 168. Rewritten to state both
denominators separately.

**(b) A citation that did not contain the claim.** "OpenAI deprecated SWE-bench Verified
and retracted SWE-bench Pro" was cited to the NeurIPS Call for Reproducibility. Fetched:
that page contains no mention of SWE-bench at all (and is labelled NeurIPS **2025**, not
2026). The claim is real and OpenAI-published, so the reference was replaced with the
OpenAI sources. The wording was also overstated: OpenAI *stopped evaluating* on Verified
and *audited* Pro finding ~30% of its tasks broken — "retracted" is not what the sources
say, so it is gone.

**(c) A decorative citation.** "Thresholds are frozen before any measured cell exists,
which is what makes the verdicts binding rather than negotiable" carried a citation to a
contamination-detection systematic review. That paper is real, correctly described, and
an outstanding-paper winner — and it says nothing about pre-registration. The citation
was doing reputational work, not evidential work. Removed from that clause, and re-attached
where the source genuinely bears on the claim: a new Limitations paragraph naming
**annotation contamination** as an uncontrolled threat in our own evaluation layer.

## What this does not cover

Claims about our own measurements are not checked here — they are covered mechanically by
`scripts/verify_paper_claims.py`, which re-derives them from committed artifacts and exits
non-zero on drift. This file covers only the external literature, which no local script can
verify. Fetches were performed on 2026-09-23; the OpenAI index page returned 403 to the
fetcher, so entry 5 rests on the publisher's page title and the announcement metadata
rather than on retrieved body text, and is the weakest of the seven.
