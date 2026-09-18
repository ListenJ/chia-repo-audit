# Short-Term Compute Window Runbook

Status updated: 2026-09-18

## Confirmation

The organizers confirmed by email that this project will receive a short-term
funded account. No additional confirmation action is required. Account details
will follow on Sunday, 2026-09-20 in the evening PDT.

The account is new, so old GCP projects, credentials, API keys, and local
`gcloud` configurations must not be reused.

## Time Window

- Account delivery: Sunday 2026-09-20 evening PDT.
- Usage starts: Monday 2026-09-21.
- Usage ends: Wednesday 2026-09-23 23:59 PT.
- Local end time: Thursday 2026-09-24 14:59 Shanghai.
- Paper/submission deadline: Friday 2026-09-25 19:59 Shanghai (Sep 24 AoE).

The funding window does not include a confirmation deadline. Treat the email
as final approval and use the remaining time for readiness work.

## Before Credentials Arrive

Complete these locally on Sep 18-20:

1. Run the stub audit and unit tests from the repository root:

   ```bash
   python3 chia_loop/loops/audit_repro.py --version 5
   python3 -m unittest discover -s chia_loop/tests -v
   ```

2. Install and verify the local toolchain:

   ```bash
   bash scripts/preflight_compute.sh
   ```

3. Pull and smoke-test the official ChampSim image locally:

   ```bash
   docker pull ghcr.io/ucb-bar/chia-champsim:latest
   ```

   If the image is still unavailable, Kaggle can validate the pinned
   source-build path without Docker:

   ```bash
   python3 scripts/kaggle_champsim_smoke.py --dry-run
   ```

   See `KAGGLE_VALIDATION.md` for the supported and unsupported claims.

4. Prepare one or more ChampSim traces and record their SHA-256 hashes.

5. Prepare a clean CHIA Python environment. CHIA currently documents Python
   3.10 for its Docker-matched environment.

6. Freeze the exact commands and expected outputs for one minimal smoke run.

The checked-in source-build smoke already completed locally and is stored in
`results/kaggle_champsim_smoke_result.json`. Kaggle is now an optional
portability check, not a blocker for entering the GCP window.

## First 30 Minutes With the New Account

Do not start a distributed run before completing these checks:

1. Authenticate against the new account:

   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project "$GCP_PROJECT"
   ```

2. Verify identity and project:

   ```bash
   gcloud auth list
   gcloud config list
   gcloud projects describe "$GCP_PROJECT"
   ```

3. Enable the required APIs and inspect quota:

   ```bash
   gcloud services enable compute.googleapis.com
   gcloud compute regions describe "$GCP_REGION"
   ```

4. Check whether the requested machine types and disk quotas are available in
   the selected zone.

5. Run the official image smoke test before the grid:

   ```bash
   docker run --rm ghcr.io/ucb-bar/chia-champsim:latest \
     python3 -c 'import chia; print(chia.__path__)'
   ```

   Then run the repository smoke path through CHIA and verify the parsed
   cycles/IPC before scaling out.

6. Record the project ID, region, zone, service-account identity, and quota
   limits in the run log. Never commit private keys or API keys.

## Environment Variables

The checked-in `chia_loop/cluster.gcp.yaml` is a template. Set variables
instead of editing secrets into the file:

```bash
export HEAD_IP="<head machine IP or hostname>"
export GCP_PROJECT="<new project id>"
export GCP_REGION="<region>"
export GCP_ZONE="<zone>"
export GCP_PRIVATE_KEY_PATH="$HOME/.ssh/id_ed25519"
export CHAMPSIM_TRACE_DIR="<absolute local trace directory>"
```

Use a new SSH key or upload the existing public key to the new account. Do not
reuse an old project service-account key.

## Run Order

Stop and inspect after every stage. Do not launch the next stage until the
previous stage has produced usable evidence.

| Stage | Scope | Intended output | Abort condition |
| --- | --- | --- | --- |
| 0 | Local stub; checked-in source smoke; optional Kaggle portability run | Reproducible v4 scorecard and pinned ChampSim smoke result | Tests/build fail |
| 1 | One image build | ChampSim binary and build log | Build exceeds 20 minutes |
| 2 | One trace, one run | Parsed cycles/IPC plus raw stdout | No structured metrics |
| 3 | Three traces, one candidate | Per-trace result table | More than one trace fails |
| 4 | Three traces, multiple seeds/candidates | Sensitivity table | Budget or quota exhaustion |
| 5 | One repeated core cell | Repeatability estimate | Results cannot be attributed to environment changes |
| 6 | Gold/adversarial audit | Kappa and publish gate | Any adversarial case missed |

The first real result matters more than the largest grid. Preserve a small,
valid dataset and report negative results honestly.

## Budget and Lifecycle Controls

- Keep one cluster active at a time.
- Run a one-minute smoke instance before any long job.
- Prefer a small initial machine type, then scale only after the smoke passes.
- Use `chia down` immediately after each stage if jobs are complete.
- Check the GCP billing console and quota pages before long runs.
- Do not run distributed work merely to fill the funding window.
- Keep raw logs and hashes; these cost little and make the artifact credible.

## Evidence Checklist

For every real run, record:

- Git commit SHA and dirty/clean state.
- Container image name and digest.
- GCP project, zone, machine type, and VM identity.
- ChampSim build revision and build command.
- Trace filename and SHA-256 hash.
- Warmup and simulation instruction counts.
- Full stdout/stderr or a preserved tail.
- Parsed metrics and the parser version/commit.
- Wall-clock time and approximate compute cost.

## Fallbacks

If account details arrive late:

- Run the same smoke path locally with the official image.
- Freeze the paper's stub-validation numbers as a pilot result.
- State clearly which claims are not supported by real hardware measurement.

If quota is too small:

- Use one candidate and three traces.
- Reduce simulation instructions for the smoke only.
- Keep the core result and omit the sensitivity grid.

If build or trace resolution fails:

- Use CHIA's documented `ChampSimNode` and the upstream smoke trace.
- Do not claim that the hand-written adapter is a verified backend.
