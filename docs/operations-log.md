# Operations Log

## 2026-09-18 - Publish public GitHub artifact

- Task: create a public GitHub artifact repository and register its URL in
  HotCRP submission #27.
- Tools: GitHub CLI 2.101.0, GitHub device login, in-app browser, git.
- Operations:
  - Revoked the exposed GitHub token; no replacement token was written to the
    repository or chat.
  - Created `https://github.com/ListenJ/chia-repo-audit` as a public
    repository.
  - Pushed local `main` commit `6c959c109a01972958e3ffc2c3b1117d9b2f5bed`
    unchanged to GitHub.
  - Filled the HotCRP `Open-source artifact URL` and saved submission #27 as
    a draft.
- Verification:
  - Anonymous GitHub API reports `visibility=public` and
    `default_branch=main`.
  - `git ls-remote github refs/heads/main` matches local `main`.
  - HotCRP reports `Updated submission (changed Open-source artifact URL)`.
- Deviation: AGENTS rule 3 names `agent/Axiom` as the normal target. This task
  intentionally used the public artifact repository `ListenJ/chia-repo-audit`
  per the user's submission request. No force push or history rewrite was
  performed.
- Commit: `72480ca`

## 2026-09-18 - Kaggle review and pinned ChampSim smoke

- Task: review Kaggle feasibility, add a CPU-only preliminary validation
  path, and verify the pinned ChampSim source build before GCP availability.
- Tools: official Kaggle documentation, DPC4-ChampSim, upstream CHIA smoke
  trace, Python 3.12, vcpkg, g++, make, Tectonic.
- Operations:
  - Added `KAGGLE_VALIDATION.md` with platform facts and claim boundaries.
  - Added `scripts/kaggle_champsim_smoke.py` with pinned source/trace inputs,
    dependency retries, JSON parsing, and repeated-run comparison.
  - Added `chia_loop/tests/test_kaggle_smoke.py`.
  - Ran the pinned source build after one vcpkg download retry and executed the
    smoke trace twice.
  - Added the preliminary real-smoke paragraph to the four-page paper PDF.
- Verification:
  - Unit tests: 7 passed.
  - Smoke result: 5,003 instructions, 40,459 cycles, IPC 0.123656.
  - Repeated runs identical: true.
  - Machine-readable evidence:
    `results/kaggle_champsim_smoke_result.json`.
  - Kaggle facts cited from official Kaggle notebooks, GPU, and TPU docs.
- Deviation: Kaggle itself was not executed live in this run; the same
  source-build smoke was validated on a generic Linux host. The document
  explicitly keeps Kaggle as an optional portability check rather than a
  substitute for the official CHIA image.
- Commit: `2ac15e0`

## 2026-09-18 - Pre-compute hardening and no-go gate

- Task: complete all optimization work possible without GCP and define a
  strict stop condition for the funded window.
- Tools: Python 3.12, unittest, CHIA ChampSimNode API, Tectonic, local
  DPC4-ChampSim source build.
- Operations:
  - Added seed/prompt candidate generation with catalog and directory modes.
  - Added leave-one-trace-out top-1 and Kendall-tau stability metrics.
  - Combined reproducibility and audit results into the publish gate.
  - Added an injectable official `ChampSimNode` backend adapter.
  - Added `PRECOMPUTE.md` with GO/NO-GO criteria and real candidate contract.
  - Updated public documentation and the paper to config v5.
  - Removed the unsupported companion `pass@k` numbers from the paper.
- Verification:
  - Unit tests: 12 passed.
  - Source smoke: five independent processes produced identical metrics.
  - Stub v5: seed CV 3.6502%, prompt spread 0.7899%, trace top-1 stability
    1.0, Kendall tau 1.0.
  - Paper compiles to four pages.
  - Non-reproducible synthetic evidence now blocks publication.
- Deviation: the official CHIA image and a live agent-generated candidate set
  remain unverified; `PRECOMPUTE.md` classifies that as a NO-GO condition.
- Commit: `3af0f29`
