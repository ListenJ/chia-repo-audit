# Kaggle Preliminary Validation Review

Reviewed: 2026-09-18

## Decision

**Judgment:** Kaggle is suitable for a CPU-only ChampSim source-build smoke
test and parser/repeatability validation. It is not a substitute for the
official CHIA Docker/Ray cluster or the funded GCP run.

Use Kaggle to de-risk the following before the compute window:

- Clone and build the pinned DPC4-ChampSim revision.
- Run the upstream 10,000-instruction smoke trace.
- Parse the Simulation phase into instructions, cycles, and IPC.
- Repeat the same run and verify identical parsed metrics.

Do not use Kaggle to claim that the CHIA cluster path, GCP provisioning, or a
full trace grid has been validated.

## Platform Facts

Source: <https://www.kaggle.com/docs/notebooks>

- Kaggle Notebooks run inside a managed Docker container.
- Internet can be enabled in session options, and packages/source can be
  installed for the current notebook.
- Up to 20 GB of output may be saved under `/kaggle/working`.
- CPU, GPU, and TPU accelerators are session options.

Source: <https://www.kaggle.com/docs/efficient-gpu-usage>

- Free GPU quota is approximately 30 hours/week and may be higher depending on
  demand and resources.
- Kaggle states that GPUs do not accelerate most non-deep-learning workflows.

Source: <https://www.kaggle.com/docs/tpu>

- Free TPU quota is up to 20 hours/week and up to 9 hours per session.
- TPUs are specialized for TensorFlow/JAX-style tensor workloads.

**Judgment:** ChampSim is a CPU-bound trace-driven simulator. Selecting a GPU
or TPU consumes scarce accelerator quota without accelerating the simulation.
Use a CPU session.

## What Kaggle Can Validate

| Check | Kaggle CPU | Official CHIA image | GCP cluster |
| --- | --- | --- | --- |
| Python audit loop and unit tests | Yes | Yes | Yes |
| Pinned ChampSim source build | Yes, if dependencies fit | Yes | Yes |
| Smoke trace execution | Yes | Yes | Yes |
| Structured cycles/IPC parsing | Yes | Yes | Yes |
| Repeated-run determinism | Yes | Yes | Yes |
| CHIA `ChampSimNode` | No | Yes | Yes |
| Docker/Ray worker scheduling | No | Yes | Yes |
| GCP provisioning, quota, cost | No | No | Yes |
| Full multi-trace experiment | Not recommended | Yes | Yes |

Kaggle runs inside a container. Treat nested Docker and multi-node Ray as
unsupported unless separately proven in a live session.

## Pinned Build Inputs

These match CHIA's official `ChampSimDockerfile`, but this path does not use
the Docker image:

- DPC4-ChampSim repository: `https://github.com/raghav-g13/DPC4-ChampSim.git`
- Branch: `incremental-compilation`
- Commit: `164fdb1ed01185a21a39c292937bf26bb7f4c694`
- Smoke trace source: `ucb-bar/chia` at
  `16c35e92aaaf9511c6453bf94cd5cf589698f4e3`
- Smoke trace SHA-256:
  `3516e79d7523a1b2c88a5abd364be8704b4d7de117f4820724b15002bd8428e8`

Source:
<https://github.com/ucb-bar/chia/blob/main/dockerfiles/ChampSimDockerfile>

## Kaggle Procedure

1. Create a new Kaggle Notebook.
2. Select `Accelerator: None` and enable `Internet`.
3. Clone the public artifact repository:

   ```bash
   !git clone https://github.com/ListenJ/chia-repo-audit.git
   %cd chia-repo-audit
   ```

4. Run the smoke test:

   ```bash
   !python3 scripts/kaggle_champsim_smoke.py \
     --work-dir /kaggle/temp/champsim-smoke \
     --output /kaggle/working/kaggle_champsim_smoke_result.json
   ```

5. Treat build/install time as the main risk. The script pins the source and
   trace, captures every command, and fails loudly on dependency or parsing
   errors.
6. Save the result JSON as a Kaggle Notebook output before the session ends.

## Expected Result

A successful run produces:

- `champsim_commit` equal to the pinned commit.
- Simulation instructions and cycles greater than zero.
- A finite IPC value.
- Two repeated runs with identical parsed metrics.
- A result JSON containing the exact commands and trace digest.

This is evidence for source-build and parser readiness. It remains preliminary
evidence until the same inputs run through the official CHIA image on GCP.

## Local Pre-Validation Result

The same script was run on the local Linux host on 2026-09-18. The first vcpkg
attempt was interrupted by a network download failure; a second invocation
resumed the downloads and completed the build. This is now a known failure
mode, and the script retries `vcpkg install` automatically.

Observed result:

```text
Pinned ChampSim commit: 164fdb1ed01185a21a39c292937bf26bb7f4c694
Trace SHA-256: 3516e79d7523a1b2c88a5abd364be8704b4d7de117f4820724b15002bd8428e8
Simulation instructions: 5003
Simulation cycles: 40459
IPC: 0.12365604686225562
Repeated runs identical: true
```

The machine-readable result is committed at
`results/kaggle_champsim_smoke_result.json`.

**Judgment:** Kaggle CPU feasibility is now high because the pinned build and
smoke path completed on a generic Linux host. A live Kaggle run is still
recommended before relying on it, because Kaggle's container packages,
network policy, and session limits remain unobserved.

## Alternatives

- **Local Docker:** best fallback because it can use CHIA's actual image and
  `ChampSimNode`, but the image is roughly 1.8 GB compressed and the current
  local link is slow.
- **Google Colab, Codespaces, or another CPU container:** acceptable only for
  the same source-build smoke test. They do not validate CHIA's worker image.
- **GCP short-term account:** authoritative environment for final evidence and
  cluster-level claims.

## Recommendation

Run Kaggle once if the official image is not ready before Sep 21. Use the
result to catch build, trace, and parser failures early. Regardless of the
Kaggle outcome, run the official CHIA Docker smoke test first inside the GCP
window before starting the experiment grid.
