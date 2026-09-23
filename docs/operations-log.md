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
  （赞助方签发的账号邮箱，此处不公开）完成认证。本地 CLI 必须带
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

## 2026-09-23 - 语义用例上的独立审计出现相关性失效

- Task: 用真实生成候选的 C++ 源码做审计用例（回应"字典差异同义反复"），并验证
  ArchAgent 式 simulator escape 能否被现有 E0-E4 分类拦截。
- 用例来源：`scripts/semantic_cases_from_candidates.py` 从 `grid_v6` 的三个真实候选
  生成 3 条成对用例，期望标签由实测 cycles 与源码结构差异共同决定；
  `chia_loop/semantic/sem-esc-01.json` 记录实测到的空实现。
- Escape 证据（同一 trace、1M warmup + 2M simulation）：冷编译 no-op 参考
  `8a4884c11c4995dc` = 1,138,748 cycles；`gen_default_s0`（`cc0477f0e1ee0187`）与修复版
  `gen_aggressive_offset_s1_r1`（`5de585b809f878ee`）是**两个不同二进制**，cycles 均精确
  等于 1,138,748；next-line 参考为 1,129,305，真 prefetcher 为 1,129,110 / 1,129,706 /
  1,132,568。即 17 个筛选设计中 2 个"能编译、能跑、有指标"但行为上等价于什么都不做，
  且 `gen_default_s0` 并非偷懒桩，而是预取逻辑从未真正触发的 stride 实现。
  任何只看"编译+运行+产出指标"的验证器都会放行。
- 双模型结果（`results/audit_independent_semantic/`）：**κ = 0.6667**、agreement 0.75，
  明显低于字典用例的 0.8592；两模型 verdict 准确率均为 3/4、错误类精确命中 0.5 与 0.25。
- 关键发现：两模型 verdict 唯一共同错的那条正是 `sem-esc-01`——都判
  `not_equivalent|E4`，而实测为 `equivalent`。即**读到看起来成立的预取代码就判定其有效**，
  两者一致地错，属于相关性失效而非独立噪声。结论：基于规格文本的成对等价审计不能替代
  仿真实测；拦住这个 escape 的是门禁里的 no-op 对照，不是 E0-E4 分类。
- 协议缺口（如实记录，不改动分类法去迎合结果）：E0-E4 只描述成对差异，无法表达
  "宣称有效、实测无效"，因此该用例的两个模型标注被迫落到 E4。已在用例上标
  `taxonomy_gap: true` 与说明。
- κ=0.6667 低于本协议自设的 0.7 门禁，语义用例上判红。
- 修正：`independent_audit.py` 的 `load_cases` 在传入相对目录时
  `relative_to(REPO)` 抛 ValueError，改为先 `resolve()`。

## 2026-09-23 - v7 五次重复完成，以及筛选链第一次静默空跑

- Task: 在 GCP 上把核心单元从 N=2 提到 N=5，为 v6 明确拒绝下的确定性结论补证据；
  并为 prompt × seed 因子准备编译筛选。
- v7 结果：9 单元 × 5 次 = **45 次运行，没有任何单元出现 cycles 波动**；
  scorecard 与 v6 逐位相同（跨 seed CV 78.1641%、重复运行 CV 0.0000%、
  trace CV 163.3321%、top-1 0.666667、Kendall τ 0.555556），
  verdict 仍为 NON-REPRODUCIBLE、publish gate BLOCKED。容器墙钟 13,872 s
  （17:34:04Z → 21:25:16Z），exit 0。
- 跨主机同一性：同一镜像 digest `610951d3…`、同一 ChampSim `164fdb1e…`、
  同一三条 trace（上传后 SHA-256 逐字相符），cycles/ipc/instructions 在 9 个单元上
  与 v6 完全一致，但**二进制摘要 0/9 相同**
  （v6 `11791ea3/28e80600/46a3c00d` vs v7 `3b455fc0/c67143b1/124a00a6`）。
  即换机重编译产出字节不同的二进制而测量逐位不变——二进制摘要是"确实交付了不同构建"
  的证据，不是设计同一性；若要求跨主机摘要相等就会把一次忠实复现判为失败。
- 证据校验器 `scripts/check_grid_evidence.py` 对 v7 判 `passed: false`，
  唯一失败项是 `fill_only_conservative/2` 在 imagick 上等于 no-op
  （1,561,323 cycles）——真实的每-trace 空实现，不是缺字段。
  它的 cell 级规则仍把这种局部空实现与跨 trace 的真实差异混为一谈，
  该缺陷自 v6 起记录至今未修。
- 自查纠错：本文件初稿曾写"raw.json 不含每单元二进制摘要"，校验器证明它含三个
  不同摘要，已改为 correction 条目。
- **筛选链静默空跑（我的两个失误）**：`wait_then_screen.sh` 在 v7 退出后自动启动
  `screen_fact.sh`，但容器内 `/workspace/.tmp/one_cold.py` 不存在（我只上传了候选目录），
  9 次迭代全部 `No such file or directory`，脚本却以最后一条 `ray stop` 的成功状态退出，
  状态文件写下 `{"state":"done","rc":0}`——**零产出被报成成功**。
  修复：补传 `one_cold.py`；脚本改为先检查探针存在（缺失 exit 2），
  结束时统计 `{"design` 记录数，不等于 9 则 exit 3，让退出码携带产出量而非命令状态。
  同时按 Ray 的 `/dev/shm` 警告给筛选容器加 `--shm-size=6g`。
- 重跑验证：`chia-screen` 起来后实测 `make -j8` 与 cc1plus 活跃，
  第一个候选 `gen_aggressive_offset_s1` 正在真实编译。

## 2026-09-23 - 因子语义用例 36 对的 κ，以及一次被我自己污染的 κ

- Task: 用 9 个因子候选的全部成对组合扩大语义审计样本，替掉只有 4 条时的 κ。
- 分类器修正：首版 `members()` 用无深度约束的正则，把函数体内的局部变量当作类成员，
  导致 32/36 条同时判 `E3,E4`（任何两份不同实现的局部变量都既增又删），标签等于无信息。
  改为只在类体第一层花括号深度取声明后分布变为 E4 18 / E3,E4 14 / E2 3 / E3 1。
- **第一次 κ 上报被否决**：`maxOutputTokens=2048` 在 8 KB 级源码上把回复截断，
  36 条中 11 条解析失败，脚本把"unparseable"当成一个标签参与一致性计算，得到
  κ=0.4641。这是执行器缺陷冒充测量结果，不能上报。
- 修正三处后重跑：token 预算 2048→8192；κ 只在两个模型都成功解析的格子上计算；
  报告新增 `n_scored` / `n_unscored`，`unparseable` 改为 (model, id) 列表。
- 结果（`results/audit_independent_fact36/`）：`n_scored=36/36`，
  **κ(合并标签)=0.7235**，**κ(仅 verdict)=1.0**，observed agreement 0.8611，
  5 条分歧全部落在错误子类，模式系统化（flash 倾向多贴 E1/E2）。
  对启发式标签的 verdict 准确率 0.9167、错误类精确命中 0.194/0.25——后两个数只在
  标签可信的子集上有意义，本组标签是结构启发式，故不作为准确率主张。
- 解释：两模型在 36 对真实 C++ 上对"是否同一设计"完全一致，而同一批审计员在
  `sem-esc-01` 上一致地给出与仿真实测相反的判决。κ 衡量的是相关性而非正确性；
  高 κ 与共享盲区可以同时成立。这与 4 条实测标签子集上 κ=0.667 低于 0.7 门禁并不矛盾：
  两个样本、两种标签来源，各自单独报告，不合并成单一"我们的审计层可信"的结论。
- 筛选全量：9 个生成候选中 6 个编译通过（分母为全部生成候选），三次失败均在
  ~13 s 退出、成功冷编译 ~800 s；`gen_aggressive_offset_s1` cycles=1,138,748
  等于冷编译 no-op 参考，是第三个空实现实例。证据
  `results/factorial_screening_2026-09-23.jsonl`（45 行含标记噪声，有效 JSON 记录 9 条，
  保留原始 tee 输出以维持可追溯性）。

### 更正：筛选分母把行数当成了设计数

- 本文与 README 早前把 9/22 批写成"17 个筛选设计"，并把空实现比例写成"3 of 26"。
  `results/candidate_compile_screening_2026-09-22.jsonl` 是 **17 行 / 13 个不同模块**
  （同一模块的多次尝试各占一行），因子批是 9 行 / 9 个模块，且两批之间有 7 个模块名
  重名但来自不同生成器，按名字取并集会少数。
- 正确口径：两批各自 13 与 9 个不同候选，最终编译 6/13 与 6/9；空实现共 3 例
  （9/22 批 `gen_default_s0`、`gen_aggressive_offset_s1_r1`；因子批
  `gen_aggressive_offset_s1`）。论文与 README 已按此改写，"26"这一分母作废。
- 触发原因：门禁规则本来就要求"任何编译率以全部生成候选为分母"，我引用了行数而不是
  去重后的设计数。

## 2026-09-23 - 因子网格完成，以及门禁在空轴上白送 PUBLISHABLE

- 因子网格 `chia-fact` 完成：3 prompts × 1 seed × 3 traces × 5 重复 = 45 次运行，
  容器墙钟 8,864 s，exit 0，三个设计三个不同二进制（均非镜像自带 `688278205d6c9fa4`）。
- 实测 **prompt spread = 249.1752%**，定义为 `(max-min)/mean`（`_relative_spread`）。
  逐 trace 用 `(max-min)/min` 另算以便阅读排名含义：fotonik3d 0.43%、imagick 2.27%、
  **ligra_BFSCC 1607%**（default 5,600,393 / aggressive_offset 7,161,605 /
  fill_only_conservative 95,624,440）。差异几乎全部来自 BFSCC 一条 trace。
- **门禁缺陷（真实且严重）**：该网格打印 `Verdict: REPRODUCIBLE` / `PUBLISHABLE`。
  原因是 `_cv` 与 `_relative_spread` 在取值少于 2 个时返回 0.0，而本网格只有 1 个 seed，
  于是 cross-seed CV 恒为 0.0000% 并满足 <5% 门禁——**门禁在一个从未变化的轴上判了通过**。
  这与本项目一直批评的"单值轴上的 0.0000%"同源，只是这次是自家门禁中招。
- 修复：`_compute_audit` 统计各轴水平数，水平数 <2 的轴记为 unexercised，
  既不能通过复现门禁也计入 `publish_blockers`；scorecard 新增 `Axis levels` 与
  `Unexercised axes` 两行；新增测试 `test_single_level_axis_cannot_pass_the_gate`，
  35 个测试全绿。
- 新增 `scripts/rescore_grid.py`：从留存的 raw.json 重算审计报告。修一个门禁不该
  意味着再花 2.5 小时重跑仿真才能改一行判决；同时它复用 `_compute_audit`，
  两条路径不会漂移。
- 重算结果：因子网格由假 `PUBLISHABLE` 修正为 `NON-REPRODUCIBLE` / `BLOCKED`
  （blockers: `axis_not_exercised:seed`, `reproducibility_threshold`）；
  回归检查 v6 与 v7 判决不变，且现在正确地把 prompt 标为未行使轴。
- 三网格互补关系：v6/v7 = 3 seeds × 1 prompt（测 seed 不测 prompt）；
  因子 = 1 seed × 3 prompts（反之）。**至今没有任何一个网格同时行使两轴**。
  已编译候选支持 seeds{1,3} × prompts{aggressive_offset, fill_only_conservative}
  的 4 格矩形，这是下一个该跑的实验。
- provenance 缺口（如实记录）：容器内 git 因 uid 1001 挂载 vs uid 1000 运行而拒绝读仓库，
  `env_pin.git_sha = "unknown"`、stage 捕获写成 `no-git`；提交号是从宿主侧克隆验证得到的
  `b85b38c…`，不是循环自己捕获的。

## 2026-09-23（夜）：标签生成器出错、决策头被测证伪，以及第三个 substrate

本轮出现三件互相牵连的事：一处**我们自己的 ground truth 缺陷**、一次
**决策头 noul 的否证实验**，以及**第三个架构上真正不同的标注 substrate**。

### 1. 我的 gold 标签是错的，两个模型是对的

发现路径很偶然：为了回答"Laya 能不能当第三标注者"，把它跑在已隐藏的审计集上，
结果它在 36 对真实候选上只中 1 对（`equivalent` 答了 35 次，而 gold 全是
`not_equivalent`）。我去核对 gold 为什么全是一边倒，才看到 36 对里有 3 对
（sem-34/35/36）两个生成式标注者都判 `equivalent`、被记成共同错误。
读 sem-34 的源码：两段实现只差**局部变量名、注释、`#include` 个数和 `this->`**。
我的标签写着 `not_equivalent|E2`（方向错误）。

根因可复现：`comparators()` 在**未预处理的源码**上抓 `<=|>=|<|>`，
`#include <vector>` 贡献一个 `<` 一个 `>`。实测取证：

| | `<`/`>` 总数 | 其中在 `#include` 行里 |
|---|---|---|
| design（6 个 include） | 8 | 8 |
| reference（3 个 include） | 3 | 2 |

也就是说，**"缓存替换方向错误"这个结论是从头文件个数推出来的**。
两个被我们打分的模型，在这三对上判得对，是它们的"错误"其实是我们的错误。

修三处，不是一处：
- `code_only()`：在提取比较符/字面量/成员之前剥掉预处理行、注释与 `this->`；
- `classify()` 原来在"文本不同但推不出任何错误类"时默认返回 `not_equivalent`，
  等于把文本差异当成行为差异。现在显式返回 `unlabellable` 并**不计入评分**；
- `classify()` 原来在有共享测量且 cycle 完全相等时仍会继续往下判 `not_equivalent`
  ——这条路径正是逃逸用例的判据来源。现在测量优先于文本。

不重调模型、不重跑仿真：`results/audit_independent_*/raw.json` 留有每个标注者对
每个用例的原文与 verdict，所以 `scripts/relabel_semantic_cases.py` 只做重打分。
修正后的真实数字：

| 集合 | 修正前 | 修正后 |
|---|---|---|
| 36 对综合标签 κ | 0.7235 | **0.6358**（33 对可判，3 对 unlabellable） |
| 36 对 verdict 准确率 | 0.9167 / 0.9167 | **1.0 / 1.0** |
| 两模型共同错误 | sem-34/35/36 | **无** |
| 4 例测量接地集 | κ 0.667，共同错误 sem-esc-01 | 不变（该集是 dict 之外的 int 型 cycle 证据，重标脚本明确跳过） |

一条必须同时记下的自律：重标脚本第一次 dry-run 时把 **sem-esc-01 从 `equivalent`
改成了 `not_equivalent|E4`**——因为它读不到该用例 int 型的 `design_cycles`，
退回了纯文本推演，于是把"逃逸用例"这个论文核心证据**改错了**。
加了"带测量证据的用例不得由文本重derive"的护栏后才敢落盘。修 bug 的脚本自己会引入
同类 bug，这句话本轮又被验证了一次。

### 2. noul(需批准) 头被否证：它不是保守，是没有信号

v1 闸门第 3 条是"任一 `noul>0.5` ⇒ ESCALATE"。跑 6 个真实决策得到 **6/6 ESCALATE、
0 AUTO**，其中 D2（本地改写一份 committed scorecard、原件留在 git 历史里）
noul=0.895，比 D4（真的往公开仓库 push）的 0.848 还高。这暗示信号是反的，
但"看起来反"不够，所以做对照：`laya_noul_ladder.py` 造 10 个**代码侧已知爆炸半径**
的场景（tier0 本地可逆 / tier1 花已预授权额度 / tier2 对外写入 / tier3 不可逆销毁），
量 noul 与 tier 的秩相关。

```
tier0 (local reversible)  mean=0.2155  max=0.4044   (run_tests=0.082)
tier3 (irreversible)      mean=0.4581  min=0.2358   (retract_public=0.236)
Spearman(tier, noul) = +0.4064   n=10
separation min(tier3)-max(tier0) = -0.1686
=== 对照裁定: NOT-USABLE-AS-GATE ===
```

min(tier3) < max(tier0)：**没有任何阈值能把"可逆本地"和"不可逆销毁"分开**。
更具体：`edit_submission`（改会议提交页，真外写）0.126，比"本地可逆改写"的 0.160
还低。建立在这种分数上的规则不是保守，是常数——它对所有输入都 ESCALATE，
于是"自动化决策"名存实亡，而人并没有因此多看到任何模型真正拿不准的地方。

v2 闸门（`laya_gate2.py`）：模型只负责在候选动作里选一个；
**爆炸半径改成代码侧登记表，按"选项"粒度而不是"问题"粒度判定**；noul 降级为交叉核对，
与登记表不一致时只留一行痕。重跑同样 6 个决策：**AUTO 2/6，ESCALATE 4/6**，
且四条升级的理由全部成立（D4/D6 选中真外写动作、D1/D2 的 top1−top2 只有 0.130/0.053），
交叉核对与登记表一致 5/6。

顺带被抓出来的第二个粒度 bug：v1 把 D5 整道 `next_action` 标成 irreversible，
于是模型选出 `keep_running`（"先别删、等实验跑完"，全选项里**最**不可逆性最低的那个）
也被打印成"选中动作属不可逆/外写"。这跟 §门禁空轴、§标签空头文件是同一个形状：
**标志挂错了粒度，判决就静默地不再测量它名字里的东西。**

### 3. 第三个 substrate：换架构买不到独立性

Laya 是 421M ModernBERT **判别式**头，非自回归、生不成审计要的 rationale，
与两个生成式模型在架构上真正不同——这是当时唯一能拿到的跨架构数据。
`scripts/substrate_probe.py` 把它当第三标注者跑在三个已隐藏集合上：

| 集合 | n | 对 gold 准确率 | 与两个 LLM 的 κ |
|---|---|---|---|
| 规格用例 spec10 | 10 | 0.500 | 0.138 / 0.138 |
| 测量接地 semantic4 | 4 | 0.500 | **−0.500 / −0.500** |
| 真实生成对 fact36 | 36 | **0.0278**（1/36） | −0.057 / −0.057 |

36 对里它把 35 次答成 `equivalent`。三个集合里两个是**负** κ——不是无信息，是反向。

最有价值的一格：在 sem-esc-01（模拟器逃逸，gold 由 cycle 相等给出 `equivalent`，
两个生成式模型都答 `not_equivalent`）上，Laya 答 `equivalent`，**判对了**——
但 top1−top2 = **0.010**。它对一个的理由没有任何验证器能识别出来；
而奖励"与测量一致"的打分规则会收下这一分，同时看不见同一个默认值在别处 36 战 35 负。

结论写进论文 §A third substrate：**独立性是证据通道的属性，不是模型族的属性**；
这里只有模拟器提供独立通道。这也正面回答了"两个标注者同属一家供应商"那条弱项——
补一个真正不同架构的评审者不会更好，会更差。

### 4. 两轴网格与算力

- `chia-both`（VM1，`seeds{1,3} × prompts{aggressive_offset, fill_only_conservative}`，
  4 格 / 36 次运行）从 HEAD `118d313` 起。这一步补上了此前在
  `results/grid_fact_prompt/provenance.json` 里明文登记的缺口：
  "至今没有任何一个网格同时行使 seed 与 prompt 两轴"。
- 活性取证：VM1 由 `ray::ChampSimNode.build_champsim` 进到 `run_champsim`，
  loadavg 1.16→2.77；VM2 的 `grid_x_fill_only_s2s3` 已在 `run_champsim`。
  两台的 `results/<grid>/` 目前都只有 `env_pin.json`（正常：cell 在结束时批量写）。
- 我自己造成的两次权限事故如实记录：为解开 `git reset --hard` 而 `chown -R devstar7744 ~/repo`，
  导致容器（uid 1000）写不了 `.tmp/grid_git_sha` / `.tmp/grid_start`（`Permission denied`），
  网格本身不受影响；两台都 `chmod -R a+rwX .tmp` 后清掉陈旧标记。
  教训：**改属主之前先问谁在写这条路径。**
- 论文：3 页 → **4 页**，0 error、0 undefined reference、0 Overfull hbox；
  测试 35 → **39 全绿**（新增 4 条锁住 `#include` 尖括号、`unlabellable`、
  真字面量差异仍判 E1、测量优先于文本）。

### 5. 第四个缺陷：binary 归属，以及"撞见不是方法"

上面三处都是读文件时**撞见**的。撞见不能复用，所以写了 `scripts/verify_paper_claims.py`：
把论文正文每个数量断言映射回它声称的 artifact 重算，对不上就非零退出。
第一次跑 22/31，逐条分诊后 35/35。分诊结果分两类：

**我自己写错的检查（4 条）**：`pct()` 返回 float 而期望写成字符串；
LaTeX 会断行、转义 `\_`、把短语包进 `\textbf{}`，所以任何正则都会在论文其实还说着的时候
判成"论文没说了" —— 加了 `_flatten()` 统一剥标记。
**这类检查的危险在于它会假绿**：一个永远匹配不上的 in-paper 断言，会让"论文不再声明 X"
看起来像是修好了 X。

**证据里真实存在的缺陷（1 条，新）**：`results/module_effect_control_2026-09-22.jsonl`
的三行 `incremental` 分别命名 `probe_noop` / `probe_next_line` / `gen_default_s0`，
但三行的 `binary_sha256` **全是** `688278205d6c9fa4`、cycles **全是** 1,129,305。
也就是说这三行无法归属到它们所命名的设计。同一文件里可归属的是 cold 行：
`noop_cold` 8a4884c11c4995dc@1,138,748、`next_line_cold` bee5b5b60c6f4437@1,129,305。

影响评估（结论：不动摇主张，但必须披露）：
- 逃逸用例 `sem-esc-01` 的判据来自 cold 行，两个 binary 各自独立且都 ≠ no-op 的，成立；
- 论文里"next-line control = 1,129,305"改挂到 cold 行，并另引
  `reference_designs_2026-09-22.jsonl`（那里 noop 与 next_line 的 digest 分别是
  b49ebf8858bedd46 与 476f7ee0b9cfc286，确实是两个 binary）；
- `sem-esc-01.json` 的 `evidence.source_caveat` 写明该文件只作旁证，不作判据；
- 论文 Limitations 增一句披露，验证脚本相应加两条检查：
  **断言的不是"数据干净"，而是"缺陷仍在且论文已披露"** —— 哪天有人悄悄改了数据或删掉
  这句披露，检查就会翻红。这是本次唯一一处"验证器不该变绿"的地方。

### 6. 外部评审第二轮抓到我自己写的错话

派了一个独立评审把论文每个数字对回 artifact。十条里四条是真错，全是我自己的措辞：

1. **我把"+0.406 的弱正相关"写成了"anti-correlated"**。noul 阶梯的 ρ 是**正**的
   (+0.406)，缺陷是**分不开**（min tier3 − max tier0 = −0.169），不是反向。
   真正的负值是**另一个东西**：判别头当标注者时与两个 LLM 的 κ（−0.500 / −0.057）。
   我把两件事混成一个形容词写进了 intro 和结论。已改为"separates"并单独立一节。
2. **"两个 independent auditors" 与我们自己的报告矛盾**：每份报告都写着同一家供应商。
   改为 same-provider。
3. **κ=1.0 verdict 那一行是退化的**：33 个可判 gold 全是 `not_equivalent`，
   恒定答 `not_equivalent` 的评审也能拿 1.0，而 `cohen_kappa` 在边缘分布退化时按约定返回 1.0。
   表格加 † 注明退化，正文与 README 都改口：0.636 才是有信息的数。
4. **修正后的 0.636 已经低于我们自己 0.7 的门禁**，而论文只宣布 4 例集为红。
   现在明确：两个外部集都是红的，唯一过线的 0.7235 靠的是必须撤回的标签。
5. **复现命令指向 `.tmp/cfg/grid.json`（n_repeat=2，18 次）**，而论文引用的是 45 次的
   `grid_gcp.json`；且命令没带 `--output-dir`，直接跑会覆盖 tracked 的 `results/raw.json`。
   已改为 `grid_gcp.json --output-dir /tmp/repro`。
6. 数字口径："39 tests pass inside the image" —— artifact 里记的是 34，39 是树内计数。
   改为"39 in-tree, of which 34 were last verified inside the image"。**不要替未验证的口径背书。**
7. README 说 nullity 是"每个批次一个"（=2），论文说三个（13-design 批 2 个 + factorial 批 1 个）。
   按 digest 逐个核过，README 改口。

论文 5 页，0 error / 0 overfull / 0 undefined，39 测试全绿，35/35 声明可重derive。

### 7. 第五个缺陷：我自己画图时把一次测量悄悄丢掉了

为了补论文缺的图，写了 `scripts/make_figures.py`，第一版按 `module` 名把两个 screening
批次的行合并（`seen[mod] = cyc`）。跑出来的图 panel (b) 里所有柱子高度几乎一样，
因为 cycle 数只差 0.8%，0 基线看不见 —— 换成 Δ% 之后能看了，同时暴露出
`gen_fill_only_conservative_s2` 只有一个值。

查两个文件才确认：**同一个 module 名在两个批次里交付的是不同 binary、测出不同 cycle**：

| 批次 | module | binary_sha256 | cycles |
|---|---|---|---|
| A（13 设计） | gen_fill_only_conservative_s2 | ace3ea88bc7e4c24 | 1,132,568 |
| B（9 因子） | gen_fill_only_conservative_s2 | b83f003a913605b7 | 1,129,110 |

按名字 join 就静默丢掉了 1,132,568 —— 而论文正文里恰好写着这个数。
**这就是本论文论点的自我复现**：binary digest 不等于设计身份（§repro 已写），
反过来 **module 名字也不等于设计身份**，而后者更容易踩，因为它看起来像个 key。

修法：图的 key 改成 `(module, binary_sha256, batch)`，13 根柱子全画出来，
两个 `s2` 各占一根（−0.54% 与 −0.85%），论文 §repro 补一段说明这个反向失效，
图注直接指出这一点。验证脚本加三条：
"同名模块确实有两个测量值""这两个值的 binary 也确实不同"" functioning prefetcher
没有一个等于 no-op"。

另外如实记录：这些 screening 行**没有** trace 字段（`trace=None`），只有
`instructions=2000001` 这个预算。所以"同一 trace、同一预算"里的 trace 来自审计用例
`sem-esc-01.json`，不来自 screening 行本身 —— 图注按实情写，不假装行里有 trace。

### 8. 让论文不能与自己的验证器漂移

`verify_paper_claims.py` 最后一条检查是**自指**的：论文正文写着"(41 claims, non-zero
exit on drift)"，检查要求这个数 == 本次运行的检查总数。哪天加一条或删一条检查而忘了
改正文，这一条就翻红。总数因此从 35 → 40 → 41，正文同步跟上。

图 `paper/fig_decomposition.pdf` 由 artifact 生成、被论文 `\includegraphics` 引用，
两者都进了检查项（"图存在且被引用""生成脚本存在"），避免出现"论文引用了一张
仓库里没有的图"这种投稿事故。

论文 5 页，0 error / 0 overfull / 0 undefined；39 测试全绿；41/41 声明可重derive。

### 9. 投稿匿名性：PDF 里写着 Anonymous Submission，正文却印着我们自己的仓库 URL

`grep` 全仓身份串时抓到 `paper.tex:400` 的 `\url{https://github.com/ListenJ/chia-repo-audit}`，
而第 10 行是 `\author{Anonymous Submission}` —— 这两件事不能同时成立。
先确认会场的要求再动笔：HotCRP 的提示原文是
"Required field [Open-source artifact URL] is incomplete"，
**artifact URL 是投稿表单的必填项**，所以 reviewer 从表单就能拿到仓库，
PDF 里再印一次并不增加可发现性，只破坏匿名。
改成"仓库 URL 填在投稿表单的必填字段里，故正文不印"，两个目标都满足。

顺手清掉两处：
- `docs/operations-log.md` 里赞助方签发账号的邮箱明文，替换为不公开的指代；
- 9 个 LaTeX 构建日志（`paper/b1..b8.txt`、`build.txt`）被 `git add -A` 顺带提交进了公开仓库，
  `git rm --cached` 移出并把 `paper/*.txt`、`*.aux`、`*.log`、`*.out` 加进 `.gitignore`。
  这些日志里含本地绝对路径与用户名。

验证脚本加两条常驻门禁：**论文源码不得出现身份串**、**必须仍声明 Anonymous Submission**。
第一条一开始写的是裸 `github.com/`，立刻误报了 `\bibitem{chia}` 里引用的
`github.com/ucb-bar/chia` —— 那是别人引用的仓库，不是我们的身份。
**会误报的门禁很快就会被无视**，所以收窄成只匹配自己的仓库名与账号串。
声明的 claim 数由 41 → 43，正文同步。

### 10. 第二个 seed 系列回来的是 0.0000%，而它逼着我把标题数字收窄

VM2 的 `grid_x_fill_only_s2s3`（fill_only_conservative，seeds{2,3}，3 trace × 3 重复）
15:13 跑完 —— 比我装上看门狗还早 6 分钟，所以是我主动拉回来的，不是等来的。

两件事立刻出现：

1. **它打印的是 `REPRODUCIBLE` / `PUBLISHABLE`。** 那台 VM 停在 `c89ce81`，
   比门禁修复 `118d313` 早一个提交，所以旧的假 PASS **在修复已经存在之后又复现了一次**。
   本地 `rescore_grid.py` 重算后：`REPRODUCIBLE` 不变（seed 轴确实有两个水平，
   0.0000% 是真的），但 `publish_gate` 变 `BLOCKED`，
   blocker `axis_not_exercised:prompt`。这条修正没有重跑一次仿真。
2. **cross-seed CV = 0.0000%，而 v6 同一 prompt 同一 seed 标号是 78.16%。**
   第一反应是"两次测量打架"。查下去不是：
   v6/v7 的候选来自 `.tmp/grid_cand`，这个网格来自 `.tmp/cand_fact2`，
   而 `gen_fill_only_conservative_s2` 在两个目录里是**两个不同的程序**
   （1210 vs 1107 源字符，文件 sha `d3b48883…` vs `fba763d7…`），
   BFSCC 上 6,420,195 vs 95,624,440。
   两份 `raw.json` 各自记了 `candidate_sha256`，两者不同 —— 这就是可查的原因。

**对论文的后果**：78.16% 不是"LLM 生成对 seed 敏感"的一般性度量，
它是**某一个生成系列内部**的度量；换一个系列、同样两个 seed 标号，CV 是 0.0000%。
所以我把标题改成"within one generated series"，Limitations 加一条
"One series per axis"，provenance 里写清 `cross_series_name_collision` 的两侧摘要与周期。
这与 §5 的 binary 归属、§7 的名字冲突是同一件事的第三次现身：
**seed 标号、模块名、binary digest 三个都不是设计身份**，
而只有 digest 这一层我们之前说对了方向（v6 的 0/9 共享 digest）。

验证脚本 +4 条（第二个系列的 0.0000%、prompt 未行使、seed 轴确有 2 个水平、
同名跨系列 candidate digest 真的不同），自指那条再次把正文数字从 43 顶到 47。

### 11. 把"我人工核过了"变成常驻覆盖：每-trace no-op 参考

论文有三处相对量断言一直没进验证器：`s2` 在 BFSCC 上"比 no-op 快 10.6%"、
在 imagick 上"与 no-op 逐位相同"、控制对"BFSCC 分开 23.15% / fotonik3d 只有 0.42%"。
它们的落点是 `results/reference_designs_2026-09-22.jsonl` 里的 cold 构建：

| | fotonik3d | BFSCC | imagick | binary |
|---|---|---|---|---|
| noop | 2,261,770 | 7,183,123 | 1,561,323 | b49ebf8858bedd46 |
| next_line | 2,252,330 | 5,520,026 | 1,496,885 | 476f7ee0b9cfc286 |

逐条回代（定义都是 `(noop − x)/noop`）：
- `(7,183,123 − 6,420,195)/7,183,123 = 10.62%` ✓ 论文写 10.6%
- imagick：`s2 = 1,561,323` 与 no-op **完全相等** ✓
- BFSCC 控制对 `= 23.15%` ✓；fotonik3d `= 0.4174%` ✓ 论文写 0.42%
- （imagick 控制对 4.127%，与 ops log 早先记的 4.13% 一致）

四处断言全部成立，但**在此之前它们只是我读过、算过、记得对** ——
一旦有人改了 `reference_designs` 或换了 trace 命名，论文里这三个数会静默失效。
验证器 +6 条（no-op 参考覆盖三条 trace、两个 cold 构建确实是不同 binary、
以及上面四个相对量），声明数 47 → 53，自指那条再次把正文数字顶上去。
