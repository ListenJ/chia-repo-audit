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

## 2026-09-20 - Local GPU and official CHIA image gate

- Task: validate the local GPU and official CHIA container path before the
  funded compute window.
- Tools: NVIDIA driver, CUDA PyTorch venv, local llama.cpp 0.8B model,
  Docker, official `chia-champsim` image, Ray, and `ChampSimNode`.
- Operations:
  - Added `scripts/champsim_node_smoke.py`.
  - Added `scripts/local_gate.py`.
  - Pulled the official image and validated build/run through Ray.
  - Recorded machine-readable gate outputs in `results/local_gate.json` and
    `results/local_champsim_node_result.json`.
- Verification:
  - Official image: PASS, image ID
    `sha256:610951d382f9e6cdfc51a4526ba70e36c80f3375b1dc19d60117bc47f20e94c4`.
  - ChampSimNode: build and run success, 5,003 instructions, 40,459 cycles,
    IPC 0.123656.
  - CUDA PyTorch: PASS after bounded retry.
  - Local 0.8B strategy model: WARNING, instruction following unstable.
- Deviation: local GPU check is supported by PyTorch, but the GPT-like 0.8B
  model remains only a portability check and not a production candidate
  generator.
- Commit: `1ca163b`

## 2026-09-21 - GCP account login rejected

- Task: verify the newly supplied short-term GCP account and begin setup.
- Tools: in-app browser and Google account sign-in.
- Operations:
  - Received short-term account credentials through the organizer email.
  - Attempted the first Google login in a clean in-app browser tab.
  - Google rejected the login before GCP Console as unverifiable and
    directed the user to the organization administrator or account recovery.
  - Stopped further password attempts to avoid account lockout.
- Verification: browser visibly shows the Google login rejection page.
- Impact: GCP setup is `BLOCKED_PENDING_ACCOUNT_ACCESS`; local validation
  remains available.
- Commit: `479399e`

## 2026-09-22 - Colab CPU portability validation

- Task: use the authenticated Colab CLI as a fallback compute path and stop
  if the real-evidence gate could not be completed.
- Tools: Google Colab CLI 0.7.1, standard CPU runtime, pinned DPC4-ChampSim,
  upstream CHIA smoke trace, Python 3.13, vcpkg, g++, and make.
- Operations:
  - Added the T3 execution and rollback plan under `docs/plans/`.
  - A high-memory CPU allocation returned `Service Unavailable`; no session
    was allocated by that request.
  - Allocated one standard CPU session (2 vCPU, 12.7 GiB RAM), ran the pinned
    source-build smoke, downloaded the result, and terminated the session.
  - Stopped before the large trace grid because real generated candidates and
    a second independent auditor were unavailable.
- Verification:
  - Pinned commit `164fdb1ed01185a21a39c292937bf26bb7f4c694` and trace SHA-256
    `3516e79d7523a1b2c88a5abd364be8704b4d7de117f4820724b15002bd8428e8`.
  - Two runs were identical: 5,003 instructions, 40,459 cycles, IPC 0.123656.
  - `colab sessions` reported no active sessions after cleanup.
  - Evidence: `results/colab_champsim_smoke_result.json`.
- Deviation: Colab had no Docker and therefore cannot replace the already
  validated local official-image/ChampSimNode gate or support a GCP claim.
- Commit: `6d0d2a9`

## 2026-09-22 - ModelScope DSW channel established, prior run root cause corrected

- Task: reach the running ModelScope (PAI-DSW) free CPU instance in a scriptable
  way and recover the state of the interrupted smoke job.
- Tools: browser tab as authenticated same-origin REST broker, Jupyter contents
  API, Gitea/GitHub remotes, upstream CHIA docs.
- Operations:
  - Added the T3 plan `docs/plans/2026-09-22-modelscope-dsw-timing.md`.
  - Confirmed local unauthenticated access is impossible: `/dsw-2201946/api/status`
    from this host returns 302 to Aliyun login, so the gateway session cookie
    stays in the browser and is never exported or stored.
  - Broker base path corrected to `/dsw-2201946/`; the previous
    `/api/contents/...` call returned 400 "Invalid url", which is why the earlier
    conclusion "the probe file was lost to a container rebuild" was wrong.
  - Read back the persistent volume: all prior artifacts survive under the
    contents root (`chia-probe.txt`, `chia-run.log`, `chia-status.json`,
    `champsim-smoke/`, `chia-repo-audit/` at `f1a16a9`).
- Verification:
  - Instance shape: 8 vCPU, 30 GiB RAM, x86_64, Python 3.11.11, g++ 11.4.0,
    NAS 1.0 PiB mount with 1002 TiB free, tmux present.
  - Docker CLI 28.1.0 exists but the daemon is unavailable, so the official
    image path cannot be claimed on this instance.
  - Recorded failure: `{"state":"failed","exit_code":1,"finished_at":
    "2026-09-22T15:10:40+08:00"}`, cause `curl (35) ... connection reset` to
    `release-assets.githubusercontent.com:443` during vcpkg bootstrap, i.e. an
    egress/CDN reachability failure, not a browser or code failure.
- Deviation: real-trace sourcing is unresolved; the documented
  `dpc4-all-traces` bucket is not anonymously listable (404). No grid started.
- Commit: `475b8c3`
