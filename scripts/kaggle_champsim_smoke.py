#!/usr/bin/env python3
"""Build and smoke-test the pinned ChampSim revision on a CPU-only host.

This is intended for Kaggle CPU notebooks and other temporary Linux
environments where nested Docker is unavailable. It validates the source
build, smoke trace execution, JSON-stat parsing, and repeated-run stability.
It does not replace the official CHIA Docker worker smoke test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


CHAMPSIM_REPO = "https://github.com/raghav-g13/DPC4-ChampSim.git"
CHAMPSIM_BRANCH = "incremental-compilation"
CHAMPSIM_COMMIT = "164fdb1ed01185a21a39c292937bf26bb7f4c694"

CHIA_TRACE_COMMIT = "16c35e92aaaf9511c6453bf94cd5cf589698f4e3"
SMOKE_TRACE_URL = (
    "https://raw.githubusercontent.com/ucb-bar/chia/"
    f"{CHIA_TRACE_COMMIT}/chia/simulators/tests/traces/"
    "smoke.champsimtrace.gz"
)
SMOKE_TRACE_SHA256 = (
    "3516e79d7523a1b2c88a5abd364be8704b4d7de117f4820724b15002bd8428e8"
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {expected}, got {actual}"
        )


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(str(part) for part in command)
    print(f"+ {printable}", flush=True)
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: "
            f"{printable}\n"
            f"stdout tail:\n{completed.stdout[-4000:]}\n"
            f"stderr tail:\n{completed.stderr[-4000:]}"
        )
    return completed


def run_command_with_retries(
    command: list[str],
    *,
    cwd: Path | None = None,
    attempts: int = 3,
) -> subprocess.CompletedProcess[str]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return run_command(command, cwd=cwd)
        except RuntimeError as exc:
            last_error = exc
            if attempt == attempts:
                break
            print(
                f"Retrying command after failure "
                f"({attempt}/{attempts}): {command[0]}",
                flush=True,
            )
            time.sleep(min(2 ** (attempt - 1), 10))
    if last_error is None:
        raise RuntimeError("command retry loop ended without an error")
    raise last_error


def ensure_commands() -> None:
    required = ["git", "python3", "make", "cmake", "g++"]
    missing = [command for command in required if shutil.which(command) is None]
    if missing:
        raise RuntimeError(
            "Missing required commands: " + ", ".join(sorted(missing))
        )


def download_trace(destination: Path) -> None:
    if destination.exists():
        verify_sha256(destination, SMOKE_TRACE_SHA256)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {SMOKE_TRACE_URL}", flush=True)
    with urllib.request.urlopen(SMOKE_TRACE_URL, timeout=120) as response:
        destination.write_bytes(response.read())
    verify_sha256(destination, SMOKE_TRACE_SHA256)


def ensure_champsim(work_dir: Path) -> Path:
    champsim_root = work_dir / "DPC4-ChampSim"
    if not (champsim_root / ".git").is_dir():
        run_command(
            [
                "git",
                "clone",
                "--branch",
                CHAMPSIM_BRANCH,
                "--single-branch",
                CHAMPSIM_REPO,
                str(champsim_root),
            ]
        )

    run_command(
        ["git", "fetch", "origin", CHAMPSIM_BRANCH],
        cwd=champsim_root,
    )
    run_command(
        ["git", "checkout", CHAMPSIM_COMMIT],
        cwd=champsim_root,
    )
    run_command(
        ["git", "submodule", "update", "--init"],
        cwd=champsim_root,
    )
    return champsim_root


def build_champsim(
    work_dir: Path,
    champsim_root: Path,
    *,
    download_retries: int,
) -> None:
    bootstrap = champsim_root / "vcpkg" / "bootstrap-vcpkg.sh"
    vcpkg = champsim_root / "vcpkg" / "vcpkg"
    if not bootstrap.is_file():
        raise FileNotFoundError(f"Missing vcpkg bootstrap script: {bootstrap}")

    run_command(["bash", str(bootstrap)], cwd=champsim_root)
    run_command_with_retries(
        [str(vcpkg), "install"],
        cwd=champsim_root,
        attempts=download_retries,
    )

    config_path = work_dir / "champsim_config.json"
    config_path.write_text(json.dumps({
        "executable_name": "champsim",
        "L2C": {"prefetcher": "evolved_pf"},
    }))
    run_command(
        [
            "python3",
            str(champsim_root / "config.sh"),
            "--no-compile-all-modules",
            str(config_path),
        ],
        cwd=champsim_root,
    )
    run_command(
        ["make", f"-j{os.cpu_count() or 1}"],
        cwd=champsim_root,
    )


def _find_l2c_stats(stats: list[dict]) -> dict:
    simulation = _simulation_phase(stats)
    roi = simulation.get("roi", {})
    for key, value in roi.items():
        if "L2C" in str(key) and isinstance(value, dict):
            return value
    return {}


def _simulation_phase(stats: list[dict]) -> dict:
    if not stats:
        raise ValueError("ChampSim JSON output is empty")
    return next(
        (phase for phase in stats if phase.get("name") == "Simulation"),
        stats[-1],
    )


def parse_simulation_metrics(stats: list[dict]) -> dict:
    simulation = _simulation_phase(stats)
    cores = simulation.get("roi", {}).get("cores", [])
    if not cores:
        raise ValueError("ChampSim JSON output has no simulation cores")

    instructions = int(cores[0].get("instructions", 0))
    cycles = int(cores[0].get("cycles", 0))
    if instructions <= 0 or cycles <= 0:
        raise ValueError(
            f"Invalid simulation counters: instructions={instructions}, "
            f"cycles={cycles}"
        )

    l2c = _find_l2c_stats(stats)
    return {
        "instructions": instructions,
        "cycles": cycles,
        "ipc": instructions / cycles,
        "l2c_prefetch_requested": int(l2c.get("prefetch requested", 0)),
        "l2c_prefetch_issued": int(l2c.get("prefetch issued", 0)),
        "l2c_useful_prefetch": int(l2c.get("useful prefetch", 0)),
        "l2c_useless_prefetch": int(l2c.get("useless prefetch", 0)),
    }


def run_smoke(
    *,
    champsim_root: Path,
    trace_path: Path,
    work_dir: Path,
    warmup_instructions: int,
    simulation_instructions: int,
    repetitions: int,
) -> tuple[list[dict], list[dict]]:
    binary = champsim_root / "bin" / "champsim"
    if not binary.is_file():
        raise FileNotFoundError(f"ChampSim binary not found: {binary}")

    metrics_runs = []
    commands = []
    for run_index in range(repetitions):
        stats_path = work_dir / f"smoke_stats_{run_index + 1}.json"
        command = [
            str(binary),
            "--warmup-instructions",
            str(warmup_instructions),
            "--simulation-instructions",
            str(simulation_instructions),
            "--json",
            str(stats_path),
            str(trace_path),
        ]
        run_command(command, cwd=champsim_root)
        metrics_runs.append(
            parse_simulation_metrics(json.loads(stats_path.read_text()))
        )
        commands.append(" ".join(command))
    return metrics_runs, commands


def dry_run_plan(
    *,
    work_dir: Path,
    warmup_instructions: int,
    simulation_instructions: int,
    repetitions: int,
) -> list[str]:
    champsim_root = work_dir / "DPC4-ChampSim"
    trace_path = work_dir / "smoke.champsimtrace.gz"
    config_path = work_dir / "champsim_config.json"
    binary = champsim_root / "bin" / "champsim"

    commands = [
        (
            "git clone --branch "
            f"{CHAMPSIM_BRANCH} --single-branch {CHAMPSIM_REPO} "
            f"{champsim_root}"
        ),
        f"git -C {champsim_root} fetch origin {CHAMPSIM_BRANCH}",
        f"git -C {champsim_root} checkout {CHAMPSIM_COMMIT}",
        f"git -C {champsim_root} submodule update --init",
        f"bash {champsim_root / 'vcpkg' / 'bootstrap-vcpkg.sh'}",
        f"{champsim_root / 'vcpkg' / 'vcpkg'} install",
        (
            f"python3 {champsim_root / 'config.sh'} "
            f"--no-compile-all-modules {config_path}"
        ),
        f"make -j{os.cpu_count() or 1}",
    ]
    for run_index in range(repetitions):
        commands.append(
            " ".join([
                str(binary),
                "--warmup-instructions",
                str(warmup_instructions),
                "--simulation-instructions",
                str(simulation_instructions),
                "--json",
                str(work_dir / f"smoke_stats_{run_index + 1}.json"),
                str(trace_path),
            ])
        )
    return commands


def default_work_dir() -> Path:
    if Path("/kaggle/temp").is_dir():
        return Path("/kaggle/temp/champsim-smoke")
    return Path(tempfile.gettempdir()) / "champsim-smoke"


def default_output_path() -> Path:
    if Path("/kaggle/working").is_dir():
        return Path("/kaggle/working/kaggle_champsim_smoke_result.json")
    return REPO_ROOT / "results" / "kaggle_champsim_smoke_result.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, default=default_work_dir())
    parser.add_argument("--output", type=Path, default=default_output_path())
    parser.add_argument("--warmup-instructions", type=int, default=1000)
    parser.add_argument("--simulation-instructions", type=int, default=5000)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--download-retries", type=int, default=3)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    if args.repetitions < 1:
        raise ValueError("--repetitions must be at least 1")

    work_dir = args.work_dir.resolve()
    commands = dry_run_plan(
        work_dir=work_dir,
        warmup_instructions=args.warmup_instructions,
        simulation_instructions=args.simulation_instructions,
        repetitions=args.repetitions,
    )
    if args.dry_run:
        result = {
            "dry_run": True,
            "champsim_repo": CHAMPSIM_REPO,
            "champsim_branch": CHAMPSIM_BRANCH,
            "champsim_commit": CHAMPSIM_COMMIT,
            "trace_url": SMOKE_TRACE_URL,
            "trace_sha256": SMOKE_TRACE_SHA256,
            "work_dir": str(work_dir),
            "commands": commands,
        }
        print(json.dumps(result, indent=2))
        return result

    ensure_commands()
    work_dir.mkdir(parents=True, exist_ok=True)
    trace_path = work_dir / "smoke.champsimtrace.gz"
    download_trace(trace_path)

    if args.skip_build:
        champsim_root = work_dir / "DPC4-ChampSim"
    else:
        champsim_root = ensure_champsim(work_dir)
        build_champsim(
            work_dir,
            champsim_root,
            download_retries=args.download_retries,
        )

    started = time.time()
    metrics_runs, run_commands = run_smoke(
        champsim_root=champsim_root,
        trace_path=trace_path,
        work_dir=work_dir,
        warmup_instructions=args.warmup_instructions,
        simulation_instructions=args.simulation_instructions,
        repetitions=args.repetitions,
    )
    elapsed = time.time() - started

    result = {
        "dry_run": False,
        "champsim_repo": CHAMPSIM_REPO,
        "champsim_branch": CHAMPSIM_BRANCH,
        "champsim_commit": CHAMPSIM_COMMIT,
        "trace_url": SMOKE_TRACE_URL,
        "trace_sha256": SMOKE_TRACE_SHA256,
        "warmup_instructions": args.warmup_instructions,
        "simulation_instructions": args.simulation_instructions,
        "repetitions": args.repetitions,
        "elapsed_seconds": elapsed,
        "metrics": metrics_runs[0],
        "all_metrics": metrics_runs,
        "repeated_runs_identical": all(
            metrics == metrics_runs[0] for metrics in metrics_runs[1:]
        ),
        "commands": run_commands,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
