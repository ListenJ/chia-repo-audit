# ModelScope DSW Timing Probe Implementation Plan

**Goal:** Establish a scriptable channel to the running ModelScope (PAI-DSW) free
CPU instance, read back the state of the job that the interrupted session left
behind, and measure the wall-clock cost of one real generated candidate on one
real (non-smoke) trace, so the 3x3 grid is sized by measurement instead of by
assumption.

**Architecture:** The DSW gateway authenticates through Aliyun OAuth, so the
channel is chosen in this order: (A1) local HTTP client against the Jupyter
server REST API when the gateway hands a reusable credential; (A2) otherwise
the authenticated browser tab acts as a same-origin REST broker. Both paths only
move files and status JSON. Execution on the instance always runs inside a
`tmux`/`nohup` driver whose logs and status live on the persistent NAS volume, so
a browser or session drop never loses evidence.

**Tech Stack:** ModelScope free DSW instance (8 vCPU / 32 GiB, Ubuntu 22.04,
Python 3.12), JupyterLab REST API, Git, pinned DPC4-ChampSim source build,
repository audit scripts.

---

## Task Contract

任务: Connect to the ModelScope DSW notebook and produce a defensible timing
measurement for one real candidate on one real trace.

验收标准:
- The channel is verified by a round trip: a file written from this session is
  read back from `/mnt/workspace` on the instance with a matching SHA-256.
- The state of the previous session's job is recovered or its loss is recorded
  with evidence (`chia-status.json`, `chia-run.log`, build tree, disk usage).
- The instance shape is recorded: `nproc`, memory, free disk on the NAS path,
  Docker availability, compiler versions.
- Exactly one real LLM-generated candidate (raw prompt, raw response, model
  identity, timestamp retained) is compiled on the instance.
- That candidate runs on one real, non-smoke trace whose instruction count is
  recorded, and the wall-clock time is measured for a stated instruction budget.
- A written go/no-go statement for the 3 candidates x 3 traces grid inside one
  8-hour instance lifetime follows from the measured number. No grid is claimed
  or started before that statement.
- Result JSON is downloaded locally, unit tests stay green, and the operation is
  logged and pushed to both remotes.

改动清单（文件级）:
- Create `docs/plans/2026-09-22-modelscope-dsw-timing.md` (this file).
- Create `scripts/dsw_remote_driver.sh` - the only file pasted into the instance:
  it runs queued commands from a watched directory on the NAS and writes
  per-command status and log files.
- Create `scripts/modelscope_timing_probe.py` - local-side driver: uploads the
  probe through the channel, polls status files, downloads the result JSON.
- Create `scripts/real_candidate_generate.py` - one real candidate through a
  configured OpenAI-compatible endpoint, key read from `~/.axiom/axiom-secrets/`,
  with prompt/response/model/timestamp provenance written next to the candidate.
- Add `results/modelscope_timing_probe.json` only after a real remote run.
- Add the generated candidate and its raw provenance under
  `chia_loop/fixtures/generated_candidates/` only if the compile succeeds.
- Modify `docs/operations-log.md` with commands, outputs, cleanup, and the
  evidence boundary.
- Modify `tests` for the two new scripts only where a real call seam exists.
- Added after the screening, reason below: `scripts/baseline_probe.py` and
  `chia_loop/tests/test_baseline_probe.py` - a per-trace no-op / next-line
  reference. The screening showed a candidate can compile, produce its own
  binary digest, and still reproduce the no-op cycle count exactly, so a
  cycle-count comparison without a reference on the same trace and instruction
  budget cannot support any claim.

不做项:
- Do not download the full multi-gigabyte SPEC17 trace set in this slice.
- Do not run the 3x3 grid, sensitivity, or replication stages in this slice.
- Do not enable or claim the official CHIA Docker/Ray path on DSW unless the
  instance actually provides a working Docker daemon.
- Do not store gateway cookies, auth codes, API keys, or account identifiers in
  the repository, in logs, or in result JSON; cookies stay in
  `~/.axiom/axiom-secrets/`.
- Do not set up an outbound reverse tunnel to a third-party relay: it is out of
  scope and likely outside the platform's acceptable use.
- Do not report any DSW number as a funded-GCP or official-image result.
- Do not mark HotCRP #27 ready.

验证命令:
```bash
python3 -m unittest discover -s chia_loop/tests -v
bash -n scripts/dsw_remote_driver.sh
python3 scripts/modelscope_timing_probe.py --dry-run
sha256sum results/modelscope_timing_probe.json
git diff --check && git status -sb
```

风险/回滚:
- The free CPU instance closes after roughly one hour of inactivity and has a
  hard 8-hour per-instance cap; long jobs must live in `tmux` with NAS logs, and
  every run must be resumable from `/mnt/workspace`.
- The container filesystem is rebuilt on restart; only `/mnt/workspace` is
  persistent, so work directories, logs, and results must never live elsewhere.
- Disk: the NAS volume is quota-limited and the previous build tree may already
  consume it; check free space before any trace download.
- Shared third-party compute runs downloaded code: the build and run commands
  are shown to the user before launch, and the source remains the already pinned
  DPC4-ChampSim commit rather than a moving target.
- Cookie or auth-code reuse from a browser session may fail or expire; if the
  local path fails, degrade to the broker path instead of widening scope.
- Rollback: stop the tmux driver, delete nothing on the NAS, leave the instance
  running for inspection, and record the abort reason in the operations log.

## Execution Steps

1. Complete the Aliyun login and capture the gateway base URL and instance id.
2. Probe the channel: REST round trip with a SHA-256-verified file.
3. Probe the instance: recovered previous-job state, shape, disk, Docker, and
   the pinned build tree.
4. Generate one real candidate locally with retained provenance; run the unit
   test seam for the candidate contract before uploading.
5. Confirm the trace source and size against upstream documentation, then
   download one trace that is not the 5,000-instruction smoke trace.
6. Launch the queued timing job under `tmux`: build once, run twice, record
   instructions, cycles, IPC, and wall clock.
7. Download the result JSON, verify hashes locally, and write the grid go/no-go
   statement from the measured rate.
8. Update the operations log, commit, and push to both remotes.

## Findings from the first probe (2026-09-22)

These are measured facts, so later steps are constrained by them rather than by
the assumptions above.

- Channel: the gateway session cookie is httpOnly and cannot be exported, and
  unauthenticated local requests return 302 to Aliyun login. Execution therefore
  goes through the authenticated tab as a same-origin REST broker against base
  path `/dsw-2201946/` (`/api/kernels` + websocket `execute_request`). The
  browser bridge caps one call at ~15s, so anything long-running must be launched
  detached and polled through `/api/contents`.
- Persistent volume: intact. The earlier "probe files were lost to a container
  rebuild" reading was an artifact of the wrong API base path returning 400.
- Instance: same container, 8 vCPU, 30 GiB, `/mnt/workspace` NAS with ~1 PiB
  free, tmux present, Docker CLI present but no daemon, so the official image
  path stays out of scope here.
- Previous job root cause: `curl (35) connection reset` to
  `release-assets.githubusercontent.com` during vcpkg bootstrap, and
  `raw.githubusercontent.com` now also stalls. Step 3's build must avoid GitHub
  release assets.
- Real traces (step 5 resolved): the DPC-4 collection is public on Cloudflare R2
  (`pub-c31f67d79d1b4cd28ff320612b1a9f84.r2.dev`, manifest-indexed; the
  documented `dpc4-all-traces` GCS bucket is not anonymously listable). 92
  SPEC17 traces, 25.3 MB to 1.33 GB compressed, 31.2 GB in total. Measured
  instance-side throughput is only ~182 KB/s, and the default Python user agent
  is rejected with 403, so downloads must use curl and stay in the 25-50 MB
  range. Consequence: the "large trace" grid is not feasible on this instance;
  the timing probe must state which trace and instruction count it used.

## Findings from the second round (2026-09-22)

All numbers below were produced on the local machine inside the official
`ghcr.io/ucb-bar/chia-champsim:latest` image, which is where the compute was
moved once round 1 showed the DSW instance cannot host a Docker daemon.

- Plan deviations, recorded: `scripts/dsw_remote_driver.sh` and
  `scripts/modelscope_timing_probe.py` listed in the contract were never
  created. The same-origin REST broker replaced the queued-file driver, and the
  broker plus direct `docker exec` replaced the local-side driver, so a queue
  protocol would have been dead weight. The candidate generator was created as
  specified; `results/modelscope_timing_probe.json` was not, because the timing
  evidence landed in the control script's JSONL output instead.
- Transfer bridge (step 7): the authenticated tab's own origin serves
  `/dsw-2201946/files/<path>?download=1`, so a NAS file lands on this machine by
  clicking a link the page renders. No dataset publish, no token, no third-party
  relay, no new dependency. Chrome only honours the first page-initiated
  download; the remaining two landed after replacing the DOM with a single
  visible link and issuing a real click. The earlier "browser download produced
  no local file" reading was wrong: this desktop uses `~/下载`, not `~/Downloads`.
- Throughput correction: instance-side pulls from the public R2 bucket run at
  ~662 KB/s, not the ~182 KB/s recorded in round 1. That round-1 figure came
  from a 74 KB manifest fetch, which is latency-dominated, so it understated the
  steady-state rate by ~3.6x.
- Traces (step 5 done): three DPC-4 traces with behavioural spread, all
  non-smoke, byte-verified against the R2 manifest MD5.

  | trace | bytes | md5 (manifest-verified) |
  | --- | --- | --- |
  | `SPEC17-649.fotonik3d_s-1B` | 25,294,572 | `a9ee5d35387f0ceb530b39a79efdb93e` |
  | `ligra_BFSCC.com-lj.ungraph...length_250M` | 74,092,232 | `8df5a66937966db41932c4ea60b57051` |
  | `638.imagick_s-4128B` | 50,679,132 | `ed67c3d3df7889c508f11b0837f96b8c` |

  SHA-256 of the local copies is recorded in the operations log. DPC4-ChampSim
  reads `.xz` natively (`src/tracereader.cc:42` branches on the suffix into an
  lzma inflator), so no decompression staging is needed and the traces mount
  read-only.
- Real candidates (step 4 done): five candidates from
  `Pro/deepseek-ai/DeepSeek-V3` through an OpenAI-compatible endpoint, each with
  prompt text, prompt SHA-256, raw response, latency, token usage, parse verdict,
  normalizations and warnings retained. Seed and prompt both change the artifact
  (distinct prompt SHA-256 per cell), so NO-GO item 3 no longer holds.
- Measurement validity (Critical, and the reason no ranking claim survives the
  pre-compaction scorecard): with the previous `incremental=True` default,
  `build_champsim` returns the image's prebuilt binary unchanged. Three different
  module names, three different sources, one identical binary:

  ```text
  noop / next_line / gen_default_s0  ->  binary_sha256 688278205d6c9fa4
  image's shipped bin/champsim       ->  688278205d6c9fa4  (same bytes, 37,861,176)
  strings bin/champsim | grep -c probe_noop        -> 0
  strings bin/champsim | grep -c gen_default_s0    -> 0
  strings bin/champsim | grep -c ip_stride         -> 424
  ```

  Mechanism, read from the installed `chia/simulators/champsim.py`: the
  incremental branch runs `make -j$(nproc)` and deliberately skips `config.sh`,
  so the generated `module_inst_N.cc.inc` never names the new module, so make
  rebuilds nothing. The docstring's own precondition ("module name ... stay
  constant") is violated by any loop that gives each candidate a distinct module
  name, which is exactly what the candidate contract requires. Consequence: every
  cycles/IPC number gathered through that path measures the image default, not
  the candidate.
- Fix and its proof: `incremental` now defaults to `False` in
  `chia_loop/sim/backends.py`, and the adapter memoises binaries keyed by
  (module name, SHA-256 of the source) so a design is built once and reused
  across traces and repeats. A real cold build produces a different binary and
  different cycles:

  ```json
  {"design":"noop_cold","incremental":false,"build_success":true,"build_s":1440.0,
   "binary_sha256":"8a4884c11c4995dc","binary_bytes":37855336,
   "base_rev":"164fdb1e...","run_s":13.9,"success":true,
   "instructions":2000001,"cycles":1138748,"ipc":1.7563157081285763}
  ```

  against `688278205d6c9fa4` / 1,129,305 cycles for the stale binary.

The complete control run (`results/module_effect_control_2026-09-22.jsonl`, one
real trace, 1M warmup + 2M simulation, 2,000,001 instructions measured):

| design | incremental | build_s | binary sha256 | cycles |
| --- | --- | --- | --- | --- |
| noop | yes | 1.9 | `688278205d6c9fa4` | 1,129,305 |
| next_line | yes | 0.8 | `688278205d6c9fa4` | 1,129,305 |
| llm candidate | yes | 0.9 | `688278205d6c9fa4` | 1,129,305 |
| noop | no (cold) | 1,440.0 | `8a4884c11c4995dc` | 1,138,748 |
| next_line | no (cold) | 1,390.2 | `bee5b5b60c6f4437` | 1,129,305 |
| noop, after the next_line build | yes | 0.7 | `bee5b5b60c6f4437` | 227,700 |

Three things follow from that table. The last row is the defect in its purest
form: a build labelled "noop" delivered the binary that the previous
`next_line` build left in the tree. The two cold rows show the backend does
respond to the design (1,138,748 vs 1,129,305 cycles, a 0.83% spread in the
direction a next-line prefetcher should help). And the image's own prebuilt
binary scores exactly like `next_line`, which is what the DPC4 default
configuration is expected to do, so the stale numbers were not noise: they were
one fixed machine measured three times.
- Timing (step 6, the reason this plan exists): cold build 1,440 s per design;
  one run at 1,000,000 warmup + 2,000,000 simulation instructions (2,000,001
  measured) 13.9 s.
- Wall-clock constraint found, not worked around: the build command is
  `make -j$(nproc)`, and inside a Ray actor `nproc` prints 1 because Ray exports
  `OMP_NUM_THREADS=1` for a 1-CPU actor. The container sees 12 cores; the build
  uses one. Leaving it alone keeps us inside the audited CHIA contract, and the
  sizing below uses the measured single-core number.
- Separate defect, worked around in config, code untouched:
  `audit_repro._apply_overrides` forwards `--simulation-instructions` to the
  `champsim_node` block but never `--warmup-instructions`, so warmup must be set
  in the config JSON or it silently stays at the 5,000,000 default.
- Grid go/no-go (step 7), sized by the measurements above: 4 candidates (2
  prompts x 2 seeds) x 3 traces x 2 repeats. Builds dominate: 4 cold builds x
  1,440 s = 96 min, since the memo makes one build serve all traces and repeats.
  Runs: 24 x ~28 s at 1M/4M = ~11 min. Total ~1.8 h of wall clock on this
  machine, which fits well inside the deadline, so the grid is GO on cost. It is
  NOT yet GO on evidence: the gate is "a real candidate compiles and moves the
  cycle count", and that measurement is what the parallel control is producing.

## Compile screening (steps 4-5, 2026-09-22)

Evidence file: `results/candidate_compile_screening_2026-09-22.jsonl`, one JSON
line per design produced by `scripts/module_effect_control.py --candidate <dir>`
with `incremental=False` on the real fotonik3d trace (1M warmup + 2M simulation).
Every design below is a real LLM response retained with its raw prompt and
response under `.tmp/cand*/`; the generator is
`scripts/real_candidate_generate.py` against an OpenAI-compatible endpoint.

Compile rate per prompt contract, measured, not estimated:

| contract | what changed in the brief | designs screened | compiled | failures |
| --- | --- | --- | --- | --- |
| v1 | module API skeleton only | 5 | 1 (`gen_fill_only_conservative_s0`) | 4 |
| v2 | + hard typed-address constraints | 6 | 1 (`gen_default_s0`) | 5 |
| v2 + repair | v2 brief plus the failing compiler output | 3 | 1 (`gen_aggressive_offset_s1_r1`) | 2 |
| v3 | + corrected `prefetch_line` signature | 3 | 3 | 0 |

Overall: 6 of 17 designs compile (35%). The cost is strongly asymmetric, which
is what makes screening affordable: every failure dies inside the candidate
translation unit in 47.3-54.5 s, while a success costs a full cold build
(1,411-1,674 s). 11 failures cost 9.1 min summed; 6 successes cost 2.6 h summed
build seconds, which is not wall-clock because designs were screened in parallel
containers. The three v3 designs, launched as one wave of three containers, sit
at the top of the range (1,644-1,674 s) against 1,411-1,417 s for two of the
solo builds; the artifact records no timestamps, so attributing that ~17% to
concurrency is an inference from the launch waves, not a measurement.

Reading the table above: the 17 rows are 17 distinct generated sources (the four
module names `gen_aggressive_offset_s0/s1`, `gen_default_s0/s1` were each
generated twice, once per contract, and their `prefetcher_source` differ), but
the screening artifact carries no contract or prompt-sha column, so which of two
same-named rows belongs to v1 and which to v2 is established only by the
per-wave container logs in `.tmp/`, not by the committed file.

The v3 rate is not comparable to v1 or v2 and must not be read as proof that the
signature fix works: v3 was screened only on the `fill_only_conservative` brief
family, which had already compiled once under v1, and it used three fresh seeds.
Two variables moved at once (brief contract and prompt family).

The failures we can attribute are one family: the model treats ChampSim's typed
address as an integer. Attribution is limited by the artifact itself - the
screening keeps `build_diagnostics[-1500:]`, the *last* 1,500 characters, so on a
verbose error the primary `error:` line is cut and only trailing `note:`
candidates survive; 4 of the 11 failing rows retain no `error:` line at all.
Counting failing designs (a design can appear under more than one message) whose
surviving text does name one: `cannot convert` x3 (e.g. `LOG2_BLOCK_SIZE` of type
`const unsigned int` to `champsim::data::bits`), `no match for 'operator%'` x2,
`no match for 'operator>>'` x2, `invalid 'static_cast'` from
`champsim::address` x1, `no match for 'operator&'` x1, `no match for
'operator!='` x1, and `prefetch_line` called with the wrong argument list x1.
Pinning the constraints into the brief (v2) did not move the rate: 1/5 versus
1/6, which on this sample size is not a measurable effect, so no claim is made
for it.

Two findings that the screening produced by accident and that change the plan:

- The generator's own brief contained a false API statement. Its skeleton comment
  read `call prefetch_line(addr, metadata, in)`, while
  `/home/ray/champsim/inc/modules.h:104` declares
  `bool prefetch_line(champsim::address pf_addr, bool fill_this_level,
  uint32_t prefetch_metadata) const`. One candidate hit exactly that
  (`no matching function for call to ...::prefetch_line(champsim::address&,
  champsim::address..., ...)`) because it followed the comment rather than the
  constraint list. Fixed in `scripts/real_candidate_generate.py`; that fix is
  what defines contract v3, so v3 rates are not comparable to v1/v2 rates as a
  single-variable change.
- Compiling is not the same as being measured. Against the cold `noop` control on
  the same trace and budget (1,138,748 cycles) and the `next_line` control
  (1,129,305 cycles), the six compiling designs split three ways:
  `gen_default_s0` and `gen_aggressive_offset_s1_r1` land on 1,138,748 - a
  distinct binary digest that reproduces the no-op timing exactly - while
  `gen_fill_only_conservative_s0/s1/s3` reach 1,129,706 / 1,129,110 / 1,129,110
  and `s2` 1,132,568. Three different binaries sharing the no-op count, and two
  different binaries sharing 1,129,110, are also a determinism datapoint: the
  backend is bit-reproducible, which is what makes an equal count a statement
  about the design rather than about noise. Consequence for the gate: "compiles"
  is a weak criterion, so `scripts/check_grid_evidence.py` requires the cycle
  count to differ from the no-op reference on the same trace.

Grid sizing updated from these numbers (supersedes the cost paragraph above):
the grid runs the designs that compile inside one contract, because directory
mode would otherwise mix briefs. `scripts/make_grid_config.py` groups compiled
designs by a contract key derived from the retained prompt text (everything
before the cell-specific brief, with module names normalised out), refuses to mix
contracts, excludes repair-round designs from the one-shot grid, stages only the
selected rectangle so the pool cannot leak a wrong design, and refuses to start
below 3 cells. On this evidence it selected contract `39fb3caf1be1` at
`fill_only_conservative` x seeds {1,2,3} and dropped the other three compiled
designs as foreign contracts; the grid started at 19:10.

Because a compiling design can still be behaviourally null, `scripts/
baseline_probe.py` measures the no-op and next-line references on every trace in
the grid at the same instruction budget (1M warmup + 4M simulation). A ChampSim
binary is trace independent, so the script builds each reference once and runs
that binary across all three traces: 2 cold builds and 6 runs instead of 6
builds. Its unit test pins exactly that (1 build per design, the same binary for
every trace) and fails against a build-per-trace variant. The launcher keeps a
second cold build off the host until memory is free again, because the machine has
15.8 GiB and each build container holds ~2.3 GiB while four ran at once.

Reference designs measured, on all three grid traces at 1M warmup + 4M
simulation (`results/reference_designs_2026-09-22.jsonl`, container exited rc=0
at 19:59:52):

| trace | noop cycles | next_line cycles | gap |
| --- | --- | --- | --- |
| `SPEC17-649.fotonik3d_s-1B` | 2,261,770 | 2,252,330 | 0.42% |
| `ligra_BFSCC.com-lj.ungraph...length_250M` | 7,183,123 | 5,520,026 | 23.15% |
| `638.imagick_s-4128B` | 1,561,323 | 1,496,885 | 4.13% |

Each reference is its own cold binary (`b49ebf8858bedd46`, `476f7ee0b9cfc286`),
neither of them the image default, built in 1,380.3 s and 1,348.4 s while the
grid container was building alongside, and one binary served all three traces as
intended. Three consequences:

- The traces are not equally discriminative. `ligra_BFSCC` separates the two
  canonical designs by 23%, while `fotonik3d` separates them by 0.42% - the same
  order as the spread already seen between compiling candidates on that trace
  (1,129,110 to 1,132,568 of 1,138,748, i.e. up to 0.85%). A ranking that only
  moves on fotonik3d is therefore weak evidence, and the grid must be read per
  trace rather than averaged.
- `instructions` reports the simulated window only (4,000,00x), so the
  1,000,000-instruction smoke floor is a floor on the simulation budget, not on
  warmup plus simulation.
- Run cost at this budget is trace dependent: 23.6 s on fotonik3d, 56.2 s on
  ligra_BFSCC and 16.5 s on imagick per repeat, which is the input the grid cost
  projection uses.

Follow-ups opened by this freeze, not done in it:

- The screening artifact should carry the contract key (or `prompt_sha256`) and a
  digest of `prefetcher_source` per row, so the 6/17 rate and the per-contract
  split are re-derivable from the committed file alone.
- Closed while promoting the builder to `scripts/make_grid_config.py`: the
  duplicate-module-name hazard needs no name-level refusal. A rectangle is drawn
  from one contract at a time and two designs claiming one cell are already
  refused, so a name collision can only sit in the dropped remainder - which is
  tonight's case (`gen_default_s0` exists under v1 and v2, neither selected). A
  stricter guard was written, tested, and removed after it was shown to reject
  this exact valid input.

## Third round: is the DSW instance actually able to run this workload? (2026-09-22 20:55-21:20)

Round 1 ended with "the DSW instance cannot host a Docker daemon", and round 2
therefore moved the compute into the official image. That inference was recorded
before the instance had been measured for the thing it was being dismissed for,
so this round re-opened the instance and tested it directly, because it is the
only other place that already holds all three grid traces.

Answer: **no, not for this evidence, and the two blockers are independent of the
instance's shape.** The shape is adequate; the environment is not.

Channel (facts): the instance id had been recycled, so the round-2 path
`/dsw-2201946/...` now serves the ModelScope SPA; the live instance is
`dsw-2203230`. Its Jupyter server answers cross-origin requests carrying
`credentials: 'include'` from the already-authenticated `www.modelscope.cn` tab,
and kernel code runs over the websocket at `/api/kernels/<id>/channels` (there is
no `/connect` route, and forcing the `v1.kernel.jupyter.org` subprotocol fails).
Replies arrive synchronously now - the round-2 "fire and poll" fallback was
working around the stale instance path, not the channel.

Adequate shape (facts, read inside the instance):

- The instance is a Kubernetes pod (`/proc/self/cgroup` puts it under
  `kubepods/burstable/pod<uid>/<container-id>`, both elided here) using cgroup v1,
  so the v2 files
  `cpu.max` and `memory.max` do not exist there. Reading the v1 knobs:
  `cpu/cpu.cfs_quota_us` = 800000 over `cpu/cpu.cfs_period_us` = 100000 = **8
  usable cores** while `nproc` reports 64, `cpu/cpu.shares` = 8192, and
  `memory/memory.limit_in_bytes` = 30,064,771,072 B = **28.0 GiB** (`free -g`
  agrees: 28 total, 27 available). `cpu/cpu.stat` shows `nr_throttled 5` with
  `throttled_time 12447165363` ns, so the quota has been enforced at some
  point since the pod started (these counters are cumulative, so they do not
  attribute that time to any one run). The
  session runs as root, so apt needs no sudo. Consequence for CHIA:
  `make -j$(nproc)` would ask for 64 jobs against an 8-core quota.
- `g++ (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0`, the same compiler series as the
  image, with Python 3.11.11 where the image has 3.10.19.
- All three grid traces are on the NAS, and `SPEC17-649.fotonik3d_s-1B.champsimtrace.xz`
  measures 25,294,572 B with sha256 starting `ecdc1feb586b6362`, which is the same
  digest as the copy the grid is running against (checked below), so trace
  identity is not a confound between the two machines.
- The tree at `/root/dswb` is the pinned commit
  `164fdb1ed01185a21a39c292937bf26bb7f4c694`, and its `config.sh`
  (`41d2025cb69ec01e...`) and `Makefile` (`65603ae87509ac7c...`) are byte-identical
  to the ones in the official image, so a build difference cannot be blamed on the
  sources or the build scripts.

Blocker 1 - no Docker daemon (fact, unchanged from round 1): the `docker` CLI is
installed (Client: Docker Engine - Community 28.1.0) but `docker info` answers
`Cannot connect to the Docker daemon at unix:///var/run/docker.sock`, and neither
`/run/docker.sock` nor `/dev/docker*` exists. The contract names the official
image, and it cannot be pulled or started there. Even a successful
from-source build would produce a hand-configured binary that cannot be pooled
with tonight's reference designs, which were measured in the image.

Blocker 2 - the from-source build cannot complete, for two separable reasons
(fact). The first is pinned to one token: the tree's `vcpkg` submodule is empty,
so `config.sh` writes
`absolute.options` with no dependency include directory. The two files compared
byte-for-byte:

```
image  -I/home/ray/champsim/inc -isystem /home/ray/champsim/vcpkg_installed/x64-linux/include
dsw    -I/root/dswb/inc -isystem <newline>   # dangling: -isystem is the last token
```

Every ChampSim compile rule is `g++ @global.options @absolute.options -MM -MT ... `,
so the empty argument makes `-isystem` swallow the following `-MM`. cc1plus then
rejects the command line for every translation unit:
`error: to generate dependencies you must specify either '-M' or '-MM'`, and
`make` exits 2 within seconds without producing `bin/`.

A second, independent cause is entangled with it, and the two must not be merged
into one explanation. On a tree whose `.csconfig/` has genuinely just been deleted,
the core translation units start before the generated-file rule at Makefile:93/201
has written `.csconfig/module_decl.inc`, so `inc/cache.h:232` fails with
`fatal error: module_decl.inc: No such file or directory` even though `make` had
printed `Building .csconfig/module_decl.inc with modules` for exactly that build.
Building the two generated files first does not dodge it: `make .csconfig/module_decl.inc
.csconfig/legacy_bridge.h` returned 0 with both files on disk (81 B and 71 B, and
reported "already up to date" on the follow-up), and the next `make -j8` still
failed on the same missing include, so the full build does not keep those files
alive long enough for the compiles that need them. The generated files themselves
are fine: `module_decl.inc` and `legacy_bridge.h` are 3 lines in both trees, so the
empty guard body is normal, not a symptom.

The official image never hits either cause, because `make clean` leaves the `.inc`
files from the image's own build in place and `vcpkg_installed/` is populated, so
CHIA's `make clean && config.sh && make -j$(nproc)` runs against a pre-populated
`.csconfig` and a complete include list. That is the same mechanism that made
`incremental=True` return the image's prebuilt digest instead of a fresh build.
Judgement, not fact: the surviving `module_decl.inc` ordering hazard is worth
reporting upstream independently of this instance, since a first build of a clean
checkout is the normal case everywhere else.

Judgement, stated as judgement: both blockers are environment, not hardware, so
the instance is not permanently unfit. Populating `vcpkg_installed/` (or pointing
`-isystem` at the apt-provided headers) removes the swallowed `-MM` in minutes; the
generated-include lifetime needs a separate fix, most likely a serial first pass
over `.csconfig/module_decl.inc` and `legacy_bridge.h` before the core objects.
Neither is worth doing before the deadline, because the result still would not be
an official-image binary and so could not be pooled with tonight's references.

Residual risk this leaves open, and it is the one worth naming: tonight's grid is
single-source evidence, one machine and one container. If that container is lost,
the fallback is not the DSW instance but a re-pull of the same image on this host.

Artifacts left on the instance by this round, in `/mnt/workspace` (NAS, so they
survive a recycle) and `/root` (container-local): the probe drivers
`probe3.py`, `probe5.py`, `probe6.py`, `probe7.py`, `dsw_build_test.py`,
`dsw_equiv.py`, `dsw_equiv2.py`, `dsw_coldbuild.py`, `dsw_wa.py`, `dsw_serial.py`,
the header `probe_noop.h` (671 B, sha256 `d7e9ef0b5fbcf1df...`, verified identical
to the local copy after upload), their result files
`chia_probe_out.json`, `chia_probe3.json`, `chia_probe5.json`, `chia_probe6.json`,
`chia_probe7.json`, `dsw_build_result.json`, `dsw_equiv.json`, `dsw_equiv2.json`,
`dsw_coldbuild.json`, `dsw_workaround.json`, `dsw_serial.json`, `dsw_serial2.log`,
`dsw_serial3.log`, `dsw_run.log`, the build trees `/root/dswb`, `/root/dswb2`,
`/root/dswb3`, and
two idle Jupyter kernels. None of them hold credentials. They are kept rather than
deleted so the numbers above can be re-derived; deleting them costs nothing once
this section has been checked against them.

## The grid ran (2026-09-22 19:10:11 - 21:35:57, contract `39fb3caf1be1`)

`chia-grid` exited 0 after 8,746.7 s. The rectangle was 3 seeds x 1 prompt x
3 traces with `n_repeat=2`, i.e. 9 cells and 18 runs, behind 3 cold builds
(binary ready at 19:32:27, 20:30:50, 20:59:51). Artifacts:
`results/grid_v6/{raw.json,audit_report.json,dblind_report.json,scorecard.txt,env_pin.json,provenance.json}`;
`provenance.json` carries what `raw.json` does not - image digest, the container
command, the three trace SHA-256s, and the build timeline.

Median cycles per cell, against the two reference designs measured on the same
trace and the same 1M+4M budget:

| seed | image digest (binary) | fotonik3d | ligra_BFSCC | imagick |
| --- | --- | --- | --- | --- |
| noop reference | `b49ebf8858bedd46` | 2,261,770 | 7,183,123 | 1,561,323 |
| next_line reference | `476f7ee0b9cfc286` | 2,252,330 | 5,520,026 | 1,496,885 |
| 1 | `11791ea33a696b76` | 2,252,142 (-0.43%) | 95,624,440 (+1231%) | 1,526,689 (-2.22%) |
| 2 | `28e80600e04c016a` | 2,255,590 (-0.27%) | 6,420,195 (-10.62%) | **1,561,323 (+0.00%)** |
| 3 | `46a3c00dde193bff` | 2,252,142 (-0.43%) | 95,624,440 (+1231%) | 1,526,689 (-2.22%) |

`scripts/check_grid_evidence.py` says `passed: false`, with one failure:
`moves_cycles_vs_reference - fill_only_conservative/2 on imagick equals noop at
1.56132e+06`. Three things follow, and they are the reason this grid is worth
more than the 18 cells it contains.

1. **Two seeds produced one algorithm.** Seeds 1 and 3 differ only in the struct
   name and in the continuation indentation of two parameter lines; their
   `prefetcher_source` digests (`b542624faf6a`, `529a404042b5`), design digests
   (`fe657c63be72`, `94327c7d3d51`) and binary digests are all different, while
   every one of the three traces returns bit-identical cycles. So "the seed
   changes the artifact" holds and "the seed changes the design" does not: at
   this prompt the generator's seed moved only cosmetics. Both implement
   prefetch-on-every-fill, which is not next-line: on BFSCC it costs 13.3x the
   no-op cycle count and about 19x its wall clock (17.5 min per run against the
   reference's 56.2 s on that trace), because every fill queues another line and
   the graph workload has almost no locality to exploit.
2. **A candidate can be inert on one trace and strong on another.** Seed 2 keeps
   a 16-entry fill history and prefetches only when a recorded block sits exactly
   one line ahead, so on imagick it issues nothing and reproduces the no-op
   cycle count to the unit while on ligra it is 10.6% faster than no-op and 16.3%
   faster than next_line. The checker flags the equality, which is right as a
   warning and wrong as a gate: the design is not globally null, so per-trace
   inertness and design-level inertness have to stay separate claims. Judgement,
   not fact: imagick's streaming access pattern is the plausible reason a
   history-match prefetcher never fires.
3. **The reproducibility verdict on this rectangle is NON-REPRODUCIBLE, and the
   cause is now visible rather than assumed.** `scorecard.txt`: max cross-seed CV
   78.16% against a 5% gate, max trace CV 163.33%, trace top-1 stability 0.667,
   Kendall tau 0.556, publish gate BLOCKED on `reproducibility_threshold`. The
   cross-seed spread is entirely seed 2 against seeds 1 and 3, which agree with
   each other exactly. Repeated-run CV is 0.0000%: all 9 cells gave bit-identical
   cycles across their two trials, each trial its own process, so the simulator
   is deterministic at this budget - but N=2 is below the N>=5 cross-session bar
   this project sets for a determinism claim, so no such claim is made here.

What this does and does not license. Gate 2's compile half is met: three generated
modules each produced their own binary, none equal to the image's prebuilt
`688278205d6c9fa4`, with `incremental=False`. Gate 3 is met (runs complete on
three traces). Gate 4 is met only because `provenance.json` was written after the
fact: `raw.json` alone has no image digest and no trace hashes, and its `git_sha`
is HEAD at write time rather than at stage entry - it reads `d3033f5`, while the
code that ran was that of `675abf8` and only documentation commits landed in
between. No ranking claim is supportable from these three designs: two are the
same program and the third is inert on a third of the traces.

Follow-ups opened by the run, none done in it:

- `stage_run` writes `raw.json` once at the end, so a single run timeout discards
  every completed cell. The BFSCC runs took ~17.5 min against `run_timeout_s`
  1800 s, i.e. 1.7x margin, so that was one slower design away from losing the
  whole grid; per-design output plus a caught build/run failure is the fix.
- The checker should report design-level and cell-level nullity separately, and
  grid cells should retain per-run wall seconds the way the reference probe does.
- The screening artifact still needs the contract key and a per-row source digest,
  so 6/17 and the per-contract split are re-derivable from the committed file.
