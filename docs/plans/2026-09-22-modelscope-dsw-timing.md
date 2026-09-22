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
| v2 + repair | v2 brief plus the failing compiler output | 1 so far | 0 | 1 |
| v3 | + corrected `prefetch_line` signature | 3 (in flight) | - | - |

Overall so far: 2 of 12 designs compile. The cost is strongly asymmetric, which
is what makes screening affordable: every failure dies inside the candidate
translation unit in 47.3-52.8 s, while a success costs a full cold build
(1,411.2 s and 1,417.1 s measured). 10 failures cost 8.5 min of machine time in
total; 2 successes cost 47 min.

All 10 failures are the same family: the model treats ChampSim's typed address as
an integer. Distinct compiler errors observed, with counts: `invalid 'static_cast'
from type 'champsim::address'` x2, `no match for 'operator%'` on
`champsim::block_number` x2, `no match for 'operator>>'` x2 (once on `address`,
once on `block_number`), `no match for 'operator&'` x1, `no match for
'operator!='` x1, no matching `prefetch_line` overload x1, `cannot convert
'champsim::address'` x1. Pining the constraints into the brief (v2) did not move
the rate: 1/5 versus 1/6, which on this sample size is not a measurable effect,
so no claim is made for it.

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
- Compiling is not the same as being measured. `gen_default_s0` builds to a
  binary digest (`cc0477f0e1ee0187`) that differs from the image default
  (`688278205d6c9fa4`) and from both controls, so it genuinely entered the
  simulated machine - and its cycle count, 1,138,748, is *identical* to the cold
  `noop` control. Same for the two binaries' determinism: two different designs
  that issue no effective prefetch produce bit-identical timing, which is a
  reproducibility datapoint, not a result. `gen_fill_only_conservative_s0`
  (1,129,706 cycles) is the only design so far that both compiles and moves the
  cycle count. Consequence for the gate: "compiles" is a weak criterion, and the
  grid must be judged against the noop baseline per trace, not against zero.

Grid sizing updated from these numbers (supersedes the cost paragraph above):
the grid runs the designs that compile inside one contract, because directory
mode would otherwise mix briefs. `.tmp/make_grid_config.py` groups compiled
designs by a contract key derived from the retained prompt text (everything
before the cell-specific brief, with module names normalised out), refuses to mix
contracts, excludes repair-round designs from the one-shot grid, stages only the
selected rectangle so the pool cannot leak a wrong design, and refuses to start
below 3 cells. Under those rules the current evidence blocks the grid (2 compiled
designs, 1 cell per contract), which is why contract v3 is being screened in
three parallel containers at ~24 min each.

