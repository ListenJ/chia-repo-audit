#!/usr/bin/env python3
"""sim/backends.py — 仿真后端抽象。

CHIA hackathon loop 的仿真层。两种后端：
  - StubBackend：本地确定性桩（无外部依赖，跑通循环逻辑）
  - ChampSimBackend：真实 trace-driven 微架构仿真（09-21 短期算力到账后启用）

切换方式：CONFIG["backend"] = "stub" | "champsim"（在 audit_repro.py 的 CONFIG）。

【诚实核验清单】ChampSimBackend 依赖 CHIA 捆绑的 ChampSim 环境，下列项在算力到账后
需按 CHIA 文档/环境核对，本文以最常用形式给出并标为可配置：
  - 构建脚本与产物路径（build_champsim.sh 的签名 / bin 产物布局）
  - 轨迹文件位置与命名（.champsimtrace.xz）
  - 运行旗标（--warmup_instructions / --simulation_instructions）
  - 输出解析（IPC / 缓存命中率的 stdout 措辞）
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol


# ── 结果结构 ──────────────────────────────────────────────────
@dataclass
class SimResult:
    cycles: float
    ipc: float
    l1_miss_rate: float
    seed: int
    prompt: str
    trace: str
    design: dict = field(default_factory=dict)
    backend: str = "stub"
    binary_sha256: str = ""
    instructions: float = float("nan")

    def asdict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "cycles", "ipc", "l1_miss_rate", "seed", "prompt", "trace", "design",
            "backend", "binary_sha256", "instructions")}


# ── 后端协议 ──────────────────────────────────────────────────
class SimBackend(Protocol):
    name: str

    def run(
        self,
        seed: int,
        prompt: str,
        trace: str,
        design: dict,
        run_index: int = 0,
    ) -> SimResult: ...


# ── Stub 后端 ─────────────────────────────────────────────────
class StubBackend:
    """确定性桩：注入受 (seed, prompt, design) 影响的伪指标，保证循环逻辑可测。

    桩故意引入跨 seed 噪声 + 提示词/设计偏差，使同一套审计代码能验证
    「方差检测真的会报警」。真实数据须由 ChampSimBackend 产出。
    """
    name = "stub"

    def run(
        self,
        seed: int,
        prompt: str,
        trace: str,
        design: dict,
        run_index: int = 0,
    ) -> SimResult:
        key = json_dumps_stable({
            "seed": seed,
            "prompt": prompt,
            "trace": trace,
            "design": design,
            "run_index": run_index,
        })
        h = hashlib.sha256(key.encode()).hexdigest()
        rnd = random.Random(int(h[:8], 16))
        base = 1000 + seed * 37 + len(trace) * 3
        prompt_bias = {"default": 0.0, "cot": 2.1, "adversarial": -3.7}[prompt]
        # design 影响：llc_replacement 不同策略给不同基线（模拟真实设计差异）
        repl_bias = {"lru": 0.0, "mru": 4.0, "fifo": 2.0, "srrip": 1.0}.get(
            design.get("llc_replacement", "lru"), 0.0)
        noise = rnd.gauss(0, 1.2)
        cycles = base + prompt_bias + repl_bias + noise
        return SimResult(
            cycles=cycles,
            ipc=1.0 / (1.0 + abs(prompt_bias + repl_bias) / 100.0 + abs(noise) / 200.0),
            l1_miss_rate=0.05 + abs(noise) / 400.0,
            seed=seed, prompt=prompt, trace=trace, design=design, backend="stub",
        )


def json_dumps_stable(obj) -> str:
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


# ── ChampSim 后端 ─────────────────────────────────────────────
class ChampSimBackend:
    """真实 trace-driven 微架构仿真后端（09-21 算力到账后启用）。

    把 design（llc_replacement / branch_predictor 等）映射为 ChampSim 构建参数，
    构建二进制 → 以 trace 运行 → 解析 stdout 得 cycles / IPC / L1 miss rate。

    【核验清单（首次在算力环境运行时逐项确认）】
    1. CHIA 捆绑 ChampSim 的构建脚本与产物路径（本类默认 build_champsim.sh + bin/）
    2. 轨迹文件：CHIA 文档给出的 trace 目录 / .champsimtrace.xz 命名
    3. 运行旗标默认值（warmup/simulation instructions）
    4. stdout 解析正则与 CHIA 实际输出措辞对齐
    """
    name = "champsim"

    def __init__(
        self,
        chia_root: str = "",
        build_script: str = "build_champsim.sh",
        bin_dir: str = "bin",
        traces_dir: str = "",
        warmup_instructions: int = 10_000_000,
        simulation_instructions: int = 10_000_000,
        num_cores: int = 1,
    ):
        self.chia_root = Path(chia_root) if chia_root else None
        self.build_script = build_script
        self.bin_dir = bin_dir
        self.traces_dir = Path(traces_dir) if traces_dir else None
        self.warmup = warmup_instructions
        self.sim = simulation_instructions
        self.num_cores = num_cores

    # design → ChampSim build 参数映射（分支预测 / L1D/L2C/LLC 预取 / LLC 替换 / 核数）
    def _build_args(self, design: dict) -> list[str]:
        llc_repl = design.get("llc_replacement", "lru")
        branch = design.get("branch_predictor", "bimodal")
        return [
            branch,
            design.get("l1d_prefetcher", "no"),
            design.get("l2c_prefetcher", "no"),
            design.get("llc_prefetcher", "no"),
            llc_repl,
            str(self.num_cores),
        ]

    def build(self, design: dict) -> Path:
        """构建 ChampSim 二进制。返回产物路径。"""
        if self.chia_root is None:
            raise RuntimeError("ChampSimBackend 需 chia_root（CHIA 捆绑 ChampSim 的根目录）")
        args = self._build_args(design)
        cmd = ["bash", str(self.chia_root / self.build_script), *args]
        subprocess.run(cmd, cwd=str(self.chia_root), check=True, capture_output=True, text=True)
        # 产物名：<branch>-<l1d>-<l2c>-<llc_pref>-<llc_repl>-<n>core（ChampSim 惯例）
        name = "-".join(args[:-1]) + f"-{self.num_cores}core"
        return self.chia_root / self.bin_dir / name

    def _trace_path(self, trace: str) -> Path:
        if self.traces_dir is None:
            raise RuntimeError("ChampSimBackend 需 traces_dir（轨迹目录）")
        return self.traces_dir / f"{trace}.champsimtrace.xz"

    def run(
        self,
        seed: int,
        prompt: str,
        trace: str,
        design: dict,
        run_index: int = 0,
    ) -> SimResult:
        """Run one deterministic ChampSim measurement.

        ChampSim does not consume Python's ``run_index``. It is accepted so the
        backend conforms to the audit protocol; repeated simulations should be
        bit-identical unless the executable, inputs, or environment changed.
        """
        binary = self.build(design)
        trace_path = self._trace_path(trace)
        cmd = [
            str(binary),
            "--warmup-instructions", str(self.warmup),
            "--simulation-instructions", str(self.sim),
            str(trace_path),
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        return self._parse(out, seed, prompt, trace, design)

    def _parse(self, stdout: str, seed, prompt, trace, design) -> SimResult:
        """解析 ChampSim stdout。措辞随版本可能变化——首次运行核验并调正则。"""
        cycles = self._re(stdout, r"cumulative (?:IPCs|cycles)[^0-9]*([0-9.eE+-]+)")
        ipc = self._re(stdout, r"CPU\s*\d+\s*cumulative IPC:\s*([0-9.]+)")
        l1_miss = self._re(stdout, r"L1D\s+TOTAL.*?(?:MISS|miss).*?([0-9.]+)")
        return SimResult(
            cycles=cycles, ipc=ipc, l1_miss_rate=l1_miss,
            seed=seed, prompt=prompt, trace=trace, design=design, backend="champsim",
        )

    @staticmethod
    def _re(text: str, pattern: str) -> float:
        m = re.search(pattern, text, re.I)
        return float(m.group(1)) if m else float("nan")


class ChampSimNodeBackend:
    """Adapter for CHIA's official ChampSimNode build/run contract.

    The runner callables are injected so the adapter can be unit-tested
    without Ray. In a live CHIA cluster, the default callables dispatch
    ``ChampSimNode.build_champsim`` and ``ChampSimNode.run_champsim``.
    """

    name = "champsim_node"

    def __init__(
        self,
        champsim_root: str,
        traces_dir: str,
        warmup_instructions: int = 5_000_000,
        simulation_instructions: int = 25_000_000,
        cache_level: str = "L2C",
        build_timeout_s: int = 1800,
        run_timeout_s: int = 3600,
        incremental: bool = False,
        build_runner: Callable[..., object] | None = None,
        run_runner: Callable[..., object] | None = None,
    ):
        self.champsim_root = champsim_root
        self.traces_dir = Path(traces_dir)
        self.warmup = warmup_instructions
        self.sim = simulation_instructions
        self.cache_level = cache_level
        self.build_timeout_s = build_timeout_s
        self.run_timeout_s = run_timeout_s
        self.incremental = incremental
        # A cached (incremental) build returns whatever binary the tree already
        # holds, so it silently measures the same design for every candidate.
        self._binaries: dict[tuple[str, str], bytes] = {}
        self.build_runner = build_runner or _default_build_runner
        self.run_runner = run_runner or _default_run_runner

    def run(
        self,
        seed: int,
        prompt: str,
        trace: str,
        design: dict,
        run_index: int = 0,
    ) -> SimResult:
        source = design.get("prefetcher_source")
        module_name = design.get("module_name")
        if not source or not module_name:
            raise ValueError(
                "ChampSimNodeBackend requires design.prefetcher_source and "
                "design.module_name"
            )

        key = (module_name, hashlib.sha256(source.encode()).hexdigest())
        binary = self._binaries.get(key)
        if binary is None:
            build = self.build_runner(
                self.champsim_root,
                source,
                module_name,
                cache_level=self.cache_level,
                timeout_s=self.build_timeout_s,
                incremental=self.incremental,
            )
            if not getattr(build, "success", False):
                diagnostics = getattr(build, "build_diagnostics", "")
                raise RuntimeError(f"CHIA ChampSim build failed: {diagnostics}")
            binary = getattr(build, "binary", b"")
            self._binaries[key] = binary

        result = self.run_runner(
            binary,
            self.traces_dir / trace,
            warmup_instructions=self.warmup,
            simulation_instructions=self.sim,
            timeout_s=self.run_timeout_s,
        )
        if not getattr(result, "success", False):
            diagnostics = getattr(result, "stdout_tail", "")
            raise RuntimeError(f"CHIA ChampSim run failed: {diagnostics}")

        return SimResult(
            cycles=float(getattr(result, "cycles", float("nan"))),
            ipc=float(getattr(result, "ipc", float("nan"))),
            l1_miss_rate=float("nan"),
            seed=seed,
            prompt=prompt,
            trace=trace,
            design=design,
            backend=self.name,
            binary_sha256=hashlib.sha256(binary).hexdigest()[:16],
            instructions=float(getattr(result, "instructions", float("nan"))),
        )


def _default_build_runner(
    champsim_root: str,
    prefetcher_source: str,
    module_name: str,
    **kwargs,
):
    from chia.base.ChiaFunction import get
    from chia.simulators.champsim import ChampSimNode

    return get(
        ChampSimNode.build_champsim.chia_remote(
            champsim_root,
            prefetcher_source,
            module_name,
            **kwargs,
        )
    )


def _default_run_runner(binary: bytes, trace: Path, **kwargs):
    from chia.base.ChiaFunction import get
    from chia.simulators.champsim import ChampSimNode

    return get(
        ChampSimNode.run_champsim.chia_remote(
            binary=binary,
            trace=str(trace),
            **kwargs,
        )
    )


# ── 工厂 ─────────────────────────────────────────────────────
def get_backend(cfg: dict) -> SimBackend:
    name = cfg.get("backend", "stub")
    if name == "champsim":
        return ChampSimBackend(**cfg.get("champsim", {}))
    if name == "champsim_node":
        return ChampSimNodeBackend(**cfg.get("champsim_node", {}))
    return StubBackend()
