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

## 2026-09-22 - DSW execution channel built, real trace source found, build blocker isolated

- Task: make the ModelScope DSW instance drivable from this session and resolve
  the two open blockers (real traces, previous build failure).
- Tools: authenticated browser tab as same-origin REST broker, Jupyter kernel
  websocket, DPC-4 public R2 bucket.
- Operations:
  - Recorded the probe results inside the plan document, including the corrected
    API base path `/dsw-2201946/`.
  - Established kernel-based remote execution and confirmed the instance is still
    the same container as the interrupted session.
- Verification:
  - Traces: 92 SPEC17 objects, 25.3 MB - 1.33 GB, 31.2 GB total; manifest 74 KB
    in 1.3 s; measured download rate ~182 KB/s, so only the small traces are
    usable here.
  - Previous failure confirmed as `curl (35)` reset on
    `release-assets.githubusercontent.com` during vcpkg bootstrap;
    `raw.githubusercontent.com` also times out now.
  - `python3 -m unittest discover -s chia_loop/tests` -> OK (12 tests).
  - No build, no grid, and no candidate was run in this step.
- Deviation: the browser bridge allows ~15 s per call, so long remote jobs must be
  detached and polled via the contents API; this constrains the plan's driver.
- Commit: `369c1c6` (amended after the placeholder was written; see record-maintenance history)

## 2026-09-22 - ChampSimNode incremental builds measured the image, not the candidate

- Task: measure one real candidate on one real trace so the grid is sized by
  data, and record what the measurement path is actually sensitive to.
- Tools: official `chia-champsim` image on the local Docker daemon, Ray,
  same-origin DSW REST broker for trace retrieval, `Explore`-free direct reads.
- Operations:
  - `chia_loop/sim/backends.py`: `incremental` now defaults to `False` and the
    adapter memoises binaries by (module name, source SHA-256).
  - `chia_loop/tests/test_champsim_node_backend.py`: new test asserting one
    build per design, never an incremental one, and that a repeat run reuses
    that design's binary.
  - `scripts/real_candidate_generate.py`, `scripts/module_effect_control.py` and
    `chia_loop/tests/test_real_candidate_generate.py` added.
  - `PRECOMPUTE.md` gate 2 and `docs/plans/2026-09-22-modelscope-dsw-timing.md`
    second-round findings updated.
- Verification:
  - `python3 -m unittest discover -s chia_loop/tests` -> Ran 18 tests, OK.
  - Three different modules through the old incremental path all returned
    binary SHA-256 `688278205d6c9fa4`, which is the digest of the binary the
    image ships (`strings` gives 0 hits for the module names, 424 for
    `ip_stride`), and all three returned 1,129,305 cycles. So the previous
    ChampSimNode "PASS" and any scorecard built on it measured the image default.
  - A real cold build changes both: `8a4884c11c4995dc`, 37,855,336 bytes,
    1,138,748 cycles, build 1,440 s, run 13.9 s at 1M warmup + 2M simulation
    (2,000,001 instructions) on `SPEC17-649.fotonik3d_s-1B`.
  - Three DPC-4 traces now live in `/traces` read-only, MD5-verified against the
    public R2 manifest; `.xz` needs no staging because `tracereader.cc:42`
    inflates it.
  - One-shot compile rate of the five generated candidates under the original
    prompt: 0 of the four screened compiled, each failure reported by `make` in
    ~48 s (`invalid static_cast` from `champsim::address`, `addr >> LOG2_BLOCK_SIZE`).
    The prompt now pins the typed address API; the six regenerated candidates use
    `champsim::block_number`/`champsim::offset` and contain no illegal pattern.
- Deviation: the funded-GCP window stayed `BLOCKED_PENDING_ACCOUNT_ACCESS`, so
  every number above is local-official-image evidence and is labelled as such.
- Follow-ups (not done here): `stage_run` lets a build failure abort the whole
  grid; the build runs `make -j1` because Ray exports `OMP_NUM_THREADS=1`;
  `--warmup-instructions` never reaches the `champsim_node` config block; the
  NO-GO list in `PRECOMPUTE.md` is numbered 1,3,4,5,6.
- Commit: `dd17585`

## 2026-09-22 - Compile-feedback repair protocol added; screening shows what the prompt pins

- Task: reach the number of compiling candidates that gate 2 asks for, without
  hiding how they came to compile.
- Tools: `scripts/real_candidate_generate.py`, `scripts/module_effect_control.py`
  in directory (screening) mode, official image containers on the local daemon.
- Operations:
  - `scripts/real_candidate_generate.py`: `MODULE_SPEC` gains the
    `champsim::block_number` constraints (`no operator%`, `/`, `>>`; use
    `champsim::offset(base, blk)`; include what you use), a `build_repair_prompt`
    one-turn repair mode driven by `--repair-from <screening log> --source-dir`,
    and `build_candidate_record(extra=...)`, so a repaired record carries
    `repair_round`, `repaired_from` and `diagnostics_sha256`.
- Verification:
  - `python3 -m unittest discover -s chia_loop/tests` -> Ran 19 tests, OK.
  - Screening, one-shot candidates, real cold builds: prompt spec v1 compiled
    0/4 screened (each `make` failure in ~48 s); prompt spec v2 compiled 0/3
    screened so far. Every observed failure was API conformance, not algorithm:
    `static_cast<int64_t>(champsim::address)`, `addr >> LOG2_BLOCK_SIZE`,
    `block_number % REGION_SIZE`, `block_number >> n`, `block_number & mask`.
  - `--dry-run` over the v2 screening log emits exactly the three failed cells as
    `gen_aggressive_offset_s{0,1,2}_r1` and skips the unfailed cells.
- Limitation recorded now, not later: the repair prompt carries spec v3 while the
  source it repairs was generated under spec v2, so the repair round is not a
  single-variable ablation. Each artifact stores its own `prompt_text` and
  `prompt_sha256`, so the exact protocol per candidate is recoverable.
- Commit: `77759ad`

## 2026-09-22 - Screening closes at 2/12 compiling; one candidate compiles but is behaviorally null

- Task: finish the compile screening that gate 2 depends on, and make the grid
  unable to mix prompt contracts.
- Tools: official image containers on the local daemon (5 in parallel),
  `scripts/module_effect_control.py` (screening mode),
  `scripts/real_candidate_generate.py`, `.tmp/make_grid_config.py`.
- Operations:
  - `scripts/real_candidate_generate.py`: the skeleton comment said
    `prefetch_line(addr, metadata, in)`; `inc/modules.h:104` in the image is
    `prefetch_line(champsim::address, bool, uint32_t)`. Comment corrected, since
    one candidate failed on exactly that call.
  - `.tmp/make_grid_config.py`: compiled designs are grouped by a contract key
    hashed from the retained prompt text (prefix before the cell brief, module
    names normalised out), so a grid cannot silently blend briefs; repair-round
    designs stay out of the one-shot grid; only the selected rectangle is staged.
  - Screening evidence collected from every `chia-screen*` container into
    `results/candidate_compile_screening_2026-09-22.jsonl` (written by the chain).
- Verification:
  - 12 designs screened, 2 compiled: `gen_fill_only_conservative_s0` (1,411.2 s,
    `312911d8236d3fa0`, 1,129,706 cycles) and `gen_default_s0` (1,417.1 s,
    `cc0477f0e1ee0187`, 1,138,748 cycles). Failures took 47.3-52.8 s.
  - `gen_default_s0` matches the cold `noop` control's cycle count exactly while
    its binary digest differs: it compiles, enters the machine, and changes
    nothing. Gate wording must be "compiles and moves cycles", not "compiles".
  - `python3 -m unittest discover -s chia_loop/tests` -> Ran 19 tests, OK.
  - Naming clarification: the previous entry's "spec v3" meant the repair prompt;
    from this entry on, contract v3 means the corrected-signature brief, and the
    repair designs' contract prefix is v2 (their extra text is post-brief).
- Follow-ups: 3 contract-v3 designs screening in parallel; grid blocked until one
  contract yields 3 cells; `stage_run` still aborts a whole stage on one build
  failure.
- Commit: `7493c7d` (hash backfill; record maintenance only)

## 2026-09-22 - Per-trace reference designs added; gate 2 requires a moved cycle count

- Task: make the grid evidence readable, after the screening showed a candidate
  that compiles, gets its own binary digest, and still equals the no-op control.
- Tools: `scripts/baseline_probe.py` (new), `chia_loop/tests/test_baseline_probe.py`
  (new), official image containers, `.tmp/run_baseline_chain.sh`.
- Operations:
  - `scripts/baseline_probe.py`: builds `probe_noop` and `probe_next_line` once
    each and runs those binaries across every trace at 1M warmup + 4M simulation,
    so the reference costs 2 cold builds plus 6 runs instead of 6 builds.
  - Launcher waits for zero `chia-screen*`, at most one other `chia-*` container
    and >= 6,000 MiB free before starting, because the host has 15.8 GiB and four
    concurrent build containers measured 2.0-2.3 GiB each.
  - `PRECOMPUTE.md` gate 2 now requires the cycle count to differ from a no-op
    reference on the same trace and budget, and requires any compile rate to use
    all generated candidates as the denominator.
- Verification: `python3 -m unittest discover -s chia_loop/tests` -> Ran 22 tests,
  OK. The build-per-trace variant records 4 builds, so the new test has teeth
  against the regression it guards.
- Deviation: these two files were not in the frozen change list; the reason is
  recorded in `docs/plans/2026-09-22-modelscope-dsw-timing.md`.
- Commit: `f69284c` (hash backfill; record maintenance only)

## 2026-09-22 - Grid measurements now carry the binary digest they were taken with

- Task: make gate 2 checkable from the grid artifact alone.
- Tools: `chia_loop/sim/backends.py`, `chia_loop/tests/test_champsim_node_backend.py`.
- Operations: `SimResult` gains `binary_sha256`, filled by `ChampSimNodeBackend`
  from the binary it actually ran, and it is part of `asdict()` so it lands in
  `raw.json` per trial.
- Verification: test written first and observed red (`AttributeError:
  'SimResult' object has no attribute 'binary_sha256'`), then
  `python3 -m unittest discover -s chia_loop/tests` -> Ran 22 tests, OK.
- Commit: `8227ef0` (hash backfill; record maintenance only)

## 2026-09-22 - Grid evidence checker added; measurements now carry their instruction count

- Task: make gate 2 and gate 8 re-derivable from `raw.json` instead of from an
  agent reading JSON by eye.
- Tools: `scripts/check_grid_evidence.py` (new), `chia_loop/tests/test_check_grid_evidence.py`
  (new), `chia_loop/sim/backends.py`, `chia_loop/tests/test_champsim_node_backend.py`.
- Operations: `SimResult` gains `instructions` from the run result; the checker
  asserts real backend, per-design binary digest distinct and not the image's own
  `688278205d6c9fa4`, one design per binary, repeats within 1%, above the
  1,000,000-instruction smoke floor, and cycles differing from the no-op
  reference on the same trace.
- Verification:
  - `python3 -m unittest discover -s chia_loop/tests` -> Ran 29 tests, OK.
  - Red case on the existing stub artifact: `python3 scripts/check_grid_evidence.py
    --raw results/raw.json` -> rc=1 with `backend_is_real`,
    `binary_digest_recorded` (9 designs) and `reference_available`, so the
    checker is not a rubber stamp.
  - A NaN instruction count is normalised to missing, because NaN comparisons
    would otherwise clear the smoke floor silently.
- Commit: `d1113e0` (hash backfill; record maintenance only)

## 2026-09-22 - Screening frozen at 6/17 compiling; grid launched on one contract

- Task: close the compile screening and start the sized grid without mixing
  prompt contracts.
- Tools: `.tmp/run_grid_chain.sh` (detached), `.tmp/make_grid_config.py`,
  official image containers (`chia-screen*` -> `chia-grid`, `chia-baseline`).
- Operations:
  - `results/candidate_compile_screening_2026-09-22.jsonl`: 17 real designs, 6
    compiled. Per contract v1 1/5, v2 1/6, v2+repair 1/3, v3 3/3. Failures died
    in 47.3-54.5 s; successes cost 1,411-1,674 s of cold build. The retained
    `diagnostics_tail` is the last 1,500 characters, so 4 of the 11 failing rows
    keep no `error:` line and only 7 support a named error family; the four
    module names generated under two contracts also mean the artifact has no
    contract column, so per-row attribution rests on the launch-wave logs.
  - `.tmp/cfg/grid.json` from contract `39fb3caf1be1`,
    prompt `fill_only_conservative`, seeds {1,2,3}, 3 traces, 2 repeats,
    1M warmup + 4M simulation, `incremental=False`; the three other compiled
    designs were dropped as foreign contracts rather than blended into the grid.
  - Reference designs (`chia-baseline`) launched only after the memory guard saw
    no screening container, at most one heavy container and >= 6 GiB free.
- Verification: `scripts/check_grid_evidence.py` will judge the artifact when the
  grid exits; the watcher `.tmp/watch_grid_and_check.sh` runs it. Screening file
  scanned for host paths and credential patterns: none.
- Deviation to remember: v3's 3/3 is not evidence that the corrected signature
  raised the compile rate, because v3 was screened only on the brief family that
  had already compiled once. Two variables moved.
- Commit: `d08a112` (hash backfill; record maintenance only)

## 2026-09-22 - Grid checker no longer crashes on a trial that never measured cycles

- Task: make the verdict readable when one repeat of a cell fails, while the grid
  is running (the checker is the only thing that turns `raw.json` into a claim).
- Tools: direct edit, `python3 -m unittest`.
- Operations:
  - `scripts/check_grid_evidence.py`: `load_cells` now separates measured from
    `None` cycle counts and reports `n_unmeasured`; a new named failure
    `all_repeats_measured` fires instead of `statistics.mean` raising.
  - `chia_loop/tests/test_check_grid_evidence.py`: added the failing-trial test
    and replaced the `trial_cycles=None` helper default with an `_UNSET`
    sentinel, because `None` was indistinguishable from "not specified" and the
    first version of the test asserted on data that contained no `None` at all.
- Verification: red first (`TypeError: can't convert type 'NoneType' to
  numerator/denominator`), then `python3 -m unittest discover -s chia_loop/tests`
  -> Ran 30 tests, OK. No container or host state touched.
- Commit: `4b2414b` (hash backfill; record maintenance only)

## 2026-09-22 - Reference designs measured on all three grid traces

- Task: produce the no-op / next-line baselines the grid verdict compares
  against, at the grid's own instruction budget.
- Tools: `scripts/baseline_probe.py` in container `chia-baseline` (official
  image, Ray), `.tmp/run_baselines.sh` launcher, `scripts/check_grid_evidence.py`.
- Operations:
  - `results/reference_designs_2026-09-22.jsonl`: 2 designs, one cold binary each
    (`b49ebf8858bedd46`, `476f7ee0b9cfc286`), 1,380.3 s and 1,348.4 s builds, run
    across fotonik3d, ligra_BFSCC and imagick at 1M warmup + 4M simulation.
    Container exited rc=0 at 19:59:52.
  - Plan doc records the trace-by-trace gap (0.42% / 23.15% / 4.13%) and the
    consequence that `instructions` counts the simulated window only, so the
    smoke floor applies to that window, not warmup + simulation.
- Verification:
  - `python3 -` join check: a synthetic cell per reference trace resolved all 3
    traces through `check_grid_evidence.verdicts` with `failures: {}`, so the
    reference file and the grid artifact share a key before the grid finishes.
  - Re-running the checker's own suite: `Ran 30 tests, OK`.
- Note: not yet verified whether the grid's first design cost more than a solo
  screening build; recorded once `.tmp/grid_start`/`grid_end` exist.
- Commit: `a0b0afb` (hash backfill; record maintenance only)

## 2026-09-22 - Grid config builder promoted to scripts/, plus an incident I caused

- Task: make the contract selection that tonight's grid depends on re-derivable,
  i.e. out of `.tmp/` and into version control with tests.
- Tools: `scripts/make_grid_config.py` (new, copied from `.tmp/`),
  `chia_loop/tests/test_make_grid_config.py` (new), mutation check in `/tmp`.
- Operations:
  - Four tests pin the safety properties: largest single-contract rectangle,
    leftovers dropped and never staged, repairs excluded, and a colliding module
    name in the dropped remainder not blocking a valid grid. Staged files are
    re-read to prove all carry the chosen contract's header.
  - A duplicate-name guard I wrote first was removed: run against tonight's real
    input shape it returned rc=1 on `gen_default_s0` (present under v1 and v2,
    neither selected), so it rejected a grid that is actually safe. The existing
    cell-collision check plus one-contract-per-rectangle already cover the hazard.
- Incident: while mutation-testing, I executed the repo-resident copy with its
  real `REPO`, and because the script wipes `.tmp/grid_cand` before selecting, the
  staging pool of the live grid was deleted from ~20:14:30 to 20:16:36. The grid
  had already read seeds 1 and 2 (s2's build started 20:05:42) and the next pool
  read (seed 3) happens after s2's runs, around 20:30, so no cell scored the
  wrong design. Restored by copying from `.tmp/cand4`, verified byte-identical
  with `cmp` for all three files. Follow-up check on the artifact: confirm the
  seed-3 cell's design digest equals `529a404042b5` (its `prefetcher_source`).
  The builder's docstring now states that it must not be run while a grid is live.
- Verification: `python3 -m unittest discover -s chia_loop/tests` -> 34 tests OK.
- Commit: `6c4b57f` (hash backfill; record maintenance only)

## 2026-09-22 - DSW runnability re-tested against the live instance

- Task: answer whether the ModelScope DSW instance can really run the ChampSim
  evidence workload, instead of inheriting round 1's Docker-only inference.
- Tools: browser tab as authenticated cross-origin Jupyter REST/websocket
  broker, `docker exec` into the official image for the control comparison.
- Operations: extended `docs/plans/2026-09-22-modelscope-dsw-timing.md` with a
  third-round section; no code or configuration was changed.
- Verification:
  - Instance id had moved to `dsw-2203230`; kernel code executes and replies
    synchronously over `/api/kernels/<id>/channels`.
  - Shape measured in place: cgroup quota 8 cores, 28.0 GiB, root, g++ 11.4.0;
    the fotonik3d trace on the NAS is 25,294,572 B and the tree is the pinned
    commit with byte-identical `config.sh`/`Makefile`.
  - Blocker 1: still no Docker daemon. Blocker 2: `absolute.options` ends with a
    dangling `-isystem` because `vcpkg/` is empty, so the token swallows `-MM` in
    every compile rule and `make` exits 2 without producing `bin/`. Reproduced in
    place at `-j8`; building `module_decl.inc` and `legacy_bridge.h` first did not
    avoid the missing-include failure, so the ordering cause is separate.
  - Separately confirmed ordering hazard: on a genuinely emptied `.csconfig`,
    `make -j8` compiles core TUs before `module_decl.inc` is written; the image
    masks it because `make clean` leaves the `.inc` files in place.
- Verdict: DSW is not usable for this evidence tonight; the official image stays
  the single compute path.
- Commit: `e35e863` (hash backfill; record maintenance only)

## 2026-09-22 - Credential exposure incident during the DSW probe

- Event: a redaction routine in a probe checked key names but echoed nested
  objects, so one instance URL containing an `authCode` value appeared once in
  tool output visible to this session.
- Impact: the value was never written to a file, the repository, the plan
  document, memory, or any chat message authored by the user; the gateway cookie
  was never exported from the browser.
- Actions: the value is treated as leaked and rotates with the instance, which
  the platform recycles; only its name and location are recorded here, never the
  value. Subsequent probes printed whitelisted scalars only.
- Follow-up for the user: if the DSW instance is not recycled before its
  `authCode` expires, revoke/reissue it from the ModelScope console.
- Commit: `e35e863` (hash backfill; the incident has no code change of its own)

## 2026-09-22 - Real-candidate grid v6 completed and committed

- Task: finish the sizing decision with real evidence - 3 LLM-generated designs
  x 3 DPC-4 traces x 2 repeats inside the official image, then record the verdict.
- Tools: `chia-grid` container on `ghcr.io/ucb-bar/chia-champsim:latest`
  (`sha256:610951d3...`), Ray ChampSimNode, `scripts/check_grid_evidence.py`.
- Operations: committed `results/grid_v6/` (raw.json, audit/dblind reports,
  scorecard, env_pin) plus a new `provenance.json` holding the image digest, the
  container command, the three trace SHA-256s and the build timeline; extended
  `docs/plans/2026-09-22-modelscope-dsw-timing.md` with the grid outcome section;
  removed the verified `.tmp/backups/` copies (rule 2.5).
- Verification:
  - Container exit 0 after 8,746.7 s; 3 cold builds, 18 runs, 3 distinct binary
    digests, none equal to the image's prebuilt `688278205d6c9fa4`.
  - `python3 scripts/check_grid_evidence.py --raw results/grid_v6/raw.json
    --reference results/reference_designs_2026-09-22.jsonl` -> rc=1, one failure:
    seed 2 on imagick equals the no-op cycle count exactly.
  - `scorecard.txt`: cross-seed CV 78.16% (gate 5%) -> NON-REPRODUCIBLE, publish
    gate BLOCKED; repeated-run CV 0.0000% with all 9 cells bit-identical.
  - The seed-3 design's `prefetcher_source` digest is `529a404042b5`, matching the
    value recorded when the incident was opened.
  - `python3 -m unittest discover -s chia_loop/tests` -> 34 tests OK.
- Deviation: the image digest and trace hashes were not retained by the harness, so
  they were written into `provenance.json` after the run rather than by it.
- Commit: `0e8e4b1` (hash backfill; record maintenance only)

## 2026-09-22 - Evidence migrated to the Windows D: drive

- Task: copy the repository, the results, the documents and the reproducible
  inputs in `.tmp` to `18336@192.168.0.100:D:` so the night's evidence survives
  this host.
- Tools: ssh/scp (key auth, cmd.exe shell), `tar`/bsdtar 3.8.8, `certutil`.
- Operations: packed `chia-repo-audit` (working tree incl. `.git`, `results/`,
  `docs/`, `.tmp/`) into `chia-repo-audit-20260922.tar.gz`, created
  `D:\chia-repo-audit-from-linux-20260922`, uploaded the archive, extracted it
  there, and kept both the archive and the tree.
- Verification: archive sha256 `1ba856fe93065ba9...` identical on both hosts and
  the same 1,402,191 B; `results/grid_v6/raw.json` and the timing plan doc hash
  identically after extraction. No member name uses a character Windows rejects
  and the longest path stays under 130 characters.
- Correction: the archive hash/size and the "549 regular files on both sides"
  written above came from the first upload, which was then superseded by a
  repacked (pycache-free) archive; the numbers above now record the final archive
  as re-hashed this round. The destination equality claim was not established at
  the time: the extracted tree actually held 557 files, 20 of them `.pyc` under 4
  `__pycache__` directories, and those 20 are absent from the final archive, so
  they must have arrived with the first upload - re-extracting does not delete a
  file the new archive omits. See the re-verification record below.
- Also this round: removed `.tmp/backups/` (6 verified copies, all reconstructible
  from git, unreferenced) and every container-generated `__pycache__` directory.
- Credential check: `.tmp`, `results`, `docs`, `scripts`, `chia_loop` scanned for
  high-entropy key patterns and cookie/auth-token strings before packing - no hits.
- Commit: `4d61b6a` (hash backfill; record maintenance only)

## 2026-09-22 - Migration re-verified after the destination-tree count mismatch

- Task: resolve the 557-vs-537 file-count mismatch reported in the migration
  record above and prove destination equality beyond spot hashes.
- Tools: ssh (key auth, cmd.exe), local `find`/`diff`, remote `git fsck`.
- Operations: deleted the 4 stale `__pycache__` directories in the extracted tree
  (20 `.pyc` files left by the first extraction; a re-extract does not remove them)
  and the session scratch folder `D:\qoder-probe-20260922`. No repository file was
  touched on the destination.
- Verification: destination now 537 regular files; relative path lists from local
  `find . -type f` and remote `dir /s /b /a-d` (CRLF stripped, separators
  normalised) diff clean -> `LISTS_IDENTICAL`. Then upgraded the check from spot
  hashes to a full comparison: SHA-256 of all 148 non-`.git` files on both hosts
  (`Get-FileHash` remotely via `D:\tmp\qoder_remote_hash.ps1`, `sha256sum`
  locally) -> 147 identical, the single difference being this file, which is
  locally ahead of the last upload and re-uploaded after the record is committed.
  The list diff is against the destination's 537 files; the local side has since
  grown by the loose git objects these two commits create, which are not data
  drift.
  Remote `git rev-parse HEAD` =
  `d8325fb`, `git fsck --no-progress` reports only 3 dangling blobs. Archive
  re-hashed with `certutil`: `1ba856fe93065ba9...`, equal to local, 1,402,191 B.
  Rule 11 re-scan of the migrated set: pattern search over `authCode|sk-*|ghp_|
  AKIA*|PRIVATE KEY|password=` returns 1 file, `docs/operations-log.md`, and the
  only hits are the prose of the exposure record - no credential value is present.
- Destination git state: the packed `.git` keeps its branch ref at the HEAD that
  was current when packing; record-maintenance commits made afterwards are
  reachable there by `git fetch origin` (verified: `FETCH_HEAD` advanced
  `d8325fb..9968c98`). The one working file those commits change,
  `docs/operations-log.md`, was re-uploaded with `scp` and re-hashed on both
  hosts, so the destination tree is byte-identical to the newest local tree even
  though its packed object store predates those commits.
- Deviation: the 557 count was not caught before the migration record was
  committed; the record's "549 files on both sides" claim was corrected in place.
  The two follow-up edits to this file reused the committed version as the
  rollback point instead of re-creating a `.tmp/backups/` copy (rule 2).
- Commit: `8698ea3`, plus `15b71b8` (adds the full-tree hash detail recorded
  above and backfills hashes; record maintenance).

## 2026-09-22 - Session transcript and Qoder memory exported to Windows, redacted

- Task: also migrate the current Qoder session transcript and the Qoder memory
  directories to the Windows host, without carrying live credentials with them.
- Tools: ssh/scp (key auth), `tar`/bsdtar, `python3` (redaction), PowerShell
  `Get-FileHash`, `certutil`.
- Rule 11 finding first, before anything left this host: the raw transcript
  (7,855,147 B) contains the live LLM-provider API key verbatim 3 times - proved
  by counting occurrences of the string read from `~/.axiom/axiom-secrets/`
  (51 chars, value never printed) - plus 22 DSW `authCode` values. The Gitea
  token appears 0 times. Copying it raw would have spread a live credential.
- Operations: redacted copy built in `/tmp/qoder-export-20260922`
  (`transcripts/…redacted.jsonl`, `session-state/`, `memory/user/` 11 files,
  empty `memory/project/`, plus `REDACTION-NOTE.md` recording what was masked and
  that the raw file stays on this host); packed 1,864,370 B
  `qoder-export-20260922.tar.gz` (`d39771bc75828984...`); created
  `D:\qoder-export-from-linux-20260922` and extracted there.
- Verification: post-redaction scans all 0 hits (exact key substring, `authCode`
  followed by a value, `sk-[A-Za-z0-9]{20,}`, private-key blocks, any
  token/secret/cookie/authorization/password assignment carrying a 24+ char
  value, `jsessionid`/`cf_clearance`/`_sec_`); archive sha256 equal on both
  hosts; all 15 exported files hash-identical host to host; the temporary
  hashing script was deleted from `D:`.
- Owner action implied: rotate that API key (it sits in the raw transcript here)
  and let the DSW instance address re-issue so its `authCode` expires.
- Deviation: rollback point for this file was its committed blob `15b71b8` rather
  than a `.tmp/backups/` copy, so the repo's `.tmp/` stayed in step with the
  freshly verified `D:` copy.
- Commit: `69629c0` (this line updated by a record-maintenance commit; the export
  itself predates both).

## 2026-09-23 - GCP 正式网格启动，以及冲榜缺口的三项收敛

- Task: 在资助算力上跑 N=5 的正式网格；同时收敛 `proposal.md` 四问与
  `ROADMAP.md` 非协商条款中仍未满足的部分（真实独立审计、prompt 敏感性、
  校准集同义反复）。
- Tools: 本地 gcloud CLI 586.0.0（winget `Google.CloudSDK`）、Cloud Shell、
  `ssh`/`scp`、官方镜像 `ghcr.io/ucb-bar/chia-champsim@sha256:610951d382f9e6cdfc51a4526ba70e36c80f3375b1dc19d60117bc47f20e94c4`、
  Vertex AI `gemini-2.5-flash` / `gemini-2.5-pro`。

### 访问与算力

- 个人账户开启 2SV 后控制台可用；随后 Cloud Shell 与本地 gcloud 都以资助账户
  `devstar7744@gcplab.me` 完成认证。本地 CLI 必须带
  `HTTPS_PROXY=http://127.0.0.1:7897`：`ProxyEnable=0` 使命令行不走系统代理，
  直连 `oauth2.googleapis.com` 超时（`gcloud config list` 会挂住）。
- Cloud Shell **不会**自动带上凭据，`gcloud auth list` 报 No credentialed accounts，
  需要一次 `gcloud auth login`。
- `us-central1-a` 对 `c2d-standard-8` 返回 `stockout`；实例最终落在
  `us-east1-b`，创建于 2026-09-22T09:51:35-07:00，NAT `136.108.73.240`。
  Ubuntu 24.04 的 image family 是 `ubuntu-2404-lts-amd64`，不带 `-amd64` 会 404。
- 配额实测（`us-central1`）：C2D 1000 / N2 3000 / C3 300 vCPU，
  `DISKS_TOTAL_GB` 102400，`SSD_TOTAL_GB` 40960，用量全为 0。主办方随后答复
  无配额上限亦无预算封顶。
- 容器两个真实陷阱，都会静默毁掉实验：
  1. 镜像内以 `uid=1000(ray)` 运行，而挂载目录属 `uid=1001(devstar7744)`，
     首次启动直接 `PermissionError: /workspace/results/grid_v7_gcp`、`grid_rc=1`，
     **零测量产出**。以 `chmod -R a+rwX` 放开。
  2. coreutils `nproc` 服从 `OMP_NUM_THREADS`，而 Ray 给 actor 默认注入 1，
     于是 `make -j$(nproc)` 退化为 `-j1`。加 `-e OMP_NUM_THREADS=8` 后实测
     `make -j8`。冷编译从约 8 倍慢回到 13 分钟量级。
- 观测性缺口：`audit_repro.py` 不打印逐单元进度，`raw.json` 只在结束时一次性写出，
  `/tmp/champsim_stats_*.json` 每次只留一个。进度只能靠
  `/home/ray/champsim/champsim_config.json` 的 mtime 变化间接确认新编译已开始。
  实测 BFSCC 单元约 8 分钟，一个设计的 15 个单元约 47 分钟。
- 环境一致性：镜像内 `python3 -m unittest discover -s chia_loop/tests` 为
  `Ran 34 tests / OK`；Python 3.10.19、Ray 2.54.0、`/home/ray/champsim` 在
  `164fdb1ed01185a21a39c292937bf26bb7f4c694`，与 `grid_v6/provenance.json` 逐项相同，
  因此 v7 与 v6 可直接比较。三条 trace 上传后 SHA-256 与 provenance 记录逐字相符。
- v7 配置只改一处：`n_repeat` 2 → 5，输出 `results/grid_v7_gcp`，不覆盖 v6。
  进入 stage 时的 HEAD 钉为 `b85b38c34789b5b99a13fd8f4eca223391714786`
  （容器内 git 因 uid 不同报 dubious ownership，加 `safe.directory` 后写入）。

### 真实独立审计（补上 gate 5）

- 新增 `scripts/independent_audit.py`：标注负载按白名单只放
  `id/design/reference`，任何 `expected_*`/`category`/`variant`/`rationale`/`planting`
  残留即拒绝运行；两个模型独立上下文、temperature 0。
- 10 条隐藏用例结果：**κ = 0.8592**（合并标签），verdict 维度 κ = 1.0，
  observed agreement 0.9；两模型 verdict 准确率均 10/10，错误类精确命中
  7/10 与 8/10；唯一分歧 `av-002`（flash 判 E1，pro 判 E2，key 为 E2）。
- 更重要的发现：**2/10 校准用例的期望标签无法从可见证据推出**。
  `gold-03` 把 FIFO vs LRU 标为 E2 方向错误，但 FIFO 并非 LRU 的反向，
  两模型一致判 E1；`av-005` 期望 E4，而负载只含
  `output: PASS` 对 `output: expected: complex verification`，E4 只能靠隐藏意图得知。
  按非协商条款如实登记，**不修改 key 去迁就模型输出**。
- 证据落盘 `results/audit_independent_v1/{raw.json,report.json}`。

### 语义用例与生成侧修正

- 新增 `scripts/semantic_cases_from_candidates.py`：期望标签由仿真实测与源码结构
  差异共同决定，判不出的标 `class not derivable` 而不硬贴。
- 首版分类器的成员正则不支持模板类型，把 s2 的新增状态误判成 E1；对照真实
  unified diff 发现 s2 多了 `std::vector<champsim::block_number> last_fill;`，
  修正后：`sem-02` s1↔s3 判 **equivalent**，依据是"改名并归一空白后源码相同"
  且"三条 trace 上 cycles 相同"；s1↔s2 与 s2↔s3 因方向不同分别得 E3 / E4。
- prompt × seed 因子：首轮 9 格只有 3 格产出，6 格报 `unbalanced braces`。
  实测确认是 `maxOutputTokens=4000` 被思考 token 吃掉（`thoughtsTokenCount` 达
  3,836–10,066）导致答案被截断，**不是**模型产出畸形代码；提高到 16000 后
  **9/9 全部产出且源码互不相同**，3 prompts × 3 seeds 因子完整。
  因此首轮不得引用为"生成成功率 3/9"。
- 附带发现：同一 seed 下 `fill_only_conservative` 的 s2/s3 源码哈希与上一轮逐位相同
  （`8c39beb8e7`、`9be416ee0a`），但 s1 由 `bdd992e47b4f` 变为 `60f4a4f099`。
  固定 seed + temperature 0.9 **不保证生成可复现**，这正是本课题要测的方差来源。

### 投稿侧决定

- HotCRP #27 的 `Open-source artifact URL` 改指分支
  `https://github.com/ListenJ/chia-repo-audit/tree/codex/colab-cpu-validation`；
  公开仓库默认分支 `main` 仍停在 `f1a16a9`（9/21 的 stub 状态），按用户裁定不合并。
  分支 URL 匿名 HTTP 200 已验证。
