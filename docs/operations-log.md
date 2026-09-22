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
