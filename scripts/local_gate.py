#!/usr/bin/env python3
"""Validate the local GPU and official CHIA ChampSim path before GCP."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")
STRATEGIES = ("next_line", "stride", "no_prefetch")


def run(
    command: list[str],
    *,
    timeout_s: int,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout_s,
    )


def check_gpu(gpu_python: Path) -> dict:
    code = """
import json, time, torch
available = torch.cuda.is_available()
result = {"available": available}
if available:
    a = torch.randn((1024, 1024), device="cuda")
    b = torch.randn((1024, 1024), device="cuda")
    torch.cuda.synchronize()
    started = time.time()
    for _ in range(5):
        c = a @ b
    torch.cuda.synchronize()
    result.update({
        "device": torch.cuda.get_device_name(0),
        "cuda_version": torch.version.cuda,
        "matmul_5x_1024_seconds": time.time() - started,
        "checksum": float(c.sum()),
    })
print(json.dumps(result))
"""
    errors = []
    for attempt in range(2):
        completed = run([str(gpu_python), "-c", code], timeout_s=60)
        if completed.returncode == 0:
            return json.loads(completed.stdout)
        errors.append((completed.stdout + completed.stderr)[-1200:])
        if attempt == 0:
            time.sleep(2)
    raise RuntimeError("GPU retry failed: " + "\n".join(errors))


def check_local_model(llama_bin: Path, model: Path) -> dict:
    prompt = (
        "Answer one token only: next_line, stride, or no_prefetch.\n"
    )
    started = time.time()
    completed = run(
        [
            str(llama_bin),
            "-m",
            str(model),
            "-c",
            "512",
            "-ngl",
            "0",
        ],
        timeout_s=60,
        input_text=prompt,
    )
    output = ANSI_RE.sub("", completed.stdout + completed.stderr)
    lines = [
        line.strip().lstrip("> ").strip()
        for line in output.splitlines()
        if line.strip().lstrip("> ").strip()
        and set(line.strip().lstrip("> ").strip()) != {"."}
    ]
    final_line = lines[-1] if lines else ""
    selected = final_line if final_line in STRATEGIES else None
    return {
        "status": "ok" if completed.returncode == 0 and selected else "warning",
        "selected_strategy": selected,
        "final_line": final_line,
        "elapsed_seconds": time.time() - started,
        "returncode": completed.returncode,
        "output_tail": output[-1000:],
    }


def check_champsim_node(
    *,
    image: str,
    repo_root: Path,
    output_path: Path,
) -> dict:
    completed = run(
        [
            "docker",
            "run",
            "--rm",
            "--shm-size=2g",
            "-v",
            f"{repo_root}:/workspace",
            "-w",
            "/workspace",
            image,
            "python3",
            "scripts/champsim_node_smoke.py",
            "--start-ray",
            "--output",
            "/workspace/results/local_champsim_node_result.json",
        ],
        timeout_s=600,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stdout + completed.stderr)[-4000:])
    if not output_path.is_file():
        raise RuntimeError("ChampSimNode did not write its result file")
    return json.loads(output_path.read_text())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        default="ghcr.io/ucb-bar/chia-champsim:latest",
    )
    parser.add_argument(
        "--gpu-python",
        type=Path,
        default=Path("/home/listen/predict chemical/.venv-gpu/bin/python"),
    )
    parser.add_argument(
        "--llama-bin",
        type=Path,
        default=Path(
            "/home/listen/Omini/omnimem-cpp/build-det/bin/llama-simple-chat"
        ),
    )
    parser.add_argument(
        "--llama-model",
        type=Path,
        default=Path(
            "/home/listen/Omini/models/Qwen3.5-0.8B-GGUF/"
            "Qwen3.5-0.8B-Q4_K_M.gguf"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "results" / "local_gate.json",
    )
    return parser.parse_args()


def main() -> dict:
    args = parse_args()
    failures = []
    warnings = []

    try:
        image_id = run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", args.image],
            timeout_s=30,
        ).stdout.strip()
        repo_digest = run(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "{{index .RepoDigests 0}}",
                args.image,
            ],
            timeout_s=30,
        ).stdout.strip()
    except Exception as exc:
        image_id = None
        repo_digest = None
        failures.append(f"image inspection failed: {exc}")

    gpu = {"available": False}
    try:
        gpu = check_gpu(args.gpu_python)
        if not gpu.get("available"):
            failures.append("CUDA is not available to PyTorch")
    except Exception as exc:
        failures.append(f"GPU check failed: {exc}")

    model = {"status": "skipped"}
    try:
        model = check_local_model(args.llama_bin, args.llama_model)
        if model["status"] != "ok":
            warnings.append("local model did not return a valid strategy token")
    except Exception as exc:
        warnings.append(f"local model check failed: {exc}")

    champsim_node = {}
    try:
        champsim_node = check_champsim_node(
            image=args.image,
            repo_root=REPO_ROOT,
            output_path=(
                REPO_ROOT / "results" / "local_champsim_node_result.json"
            ),
        )
    except Exception as exc:
        failures.append(f"ChampSimNode gate failed: {exc}")

    result = {
        "timestamp": time.time(),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "warnings": warnings,
        "image": {
            "name": args.image,
            "image_id": image_id,
            "repo_digest": repo_digest,
        },
        "gpu": gpu,
        "local_model": model,
        "champsim_node": champsim_node,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    try:
        result = main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0 if result["status"] == "PASS" else 1)
