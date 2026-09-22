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
