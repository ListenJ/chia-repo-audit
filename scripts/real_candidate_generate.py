#!/usr/bin/env python3
"""Generate real LLM cache-design candidates with inspectable provenance.

Each emitted JSON satisfies the directory-mode contract consumed by
``chia_loop/loops/audit_repro.py`` and the ChampSimNode backend:
``design.prefetcher_source`` plus ``design.module_name``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://api.siliconflow.cn/v1"
CHAT_ENDPOINT = API_BASE + "/chat/completions"
CREDENTIAL_PATH = Path.home() / ".axiom/axiom-secrets/siliconflow.credentials"

MODULE_SPEC = """\
Target simulator: ChampSim (the fork shipped in ghcr.io/ucb-bar/chia-champsim,
base revision 164fdb1ed01185a21a39c292937bf26bb7f4c694).

The module must be one C++ struct that derives from the prefetcher module API:

  #include <cstdint>
  #include "address.h"
  #include "modules.h"

  struct <NAME> : public champsim::modules::prefetcher {
    using prefetcher::prefetcher;

    uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip,
                                       uint8_t cache_hit, bool useful_prefetch,
                                       access_type type, uint32_t metadata_in) {
      // called on every core-cache access; the real signature is
      // prefetch_line(champsim::address pf_addr, bool fill_this_level, uint32_t prefetch_metadata)
      return metadata_in;
    }

    uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way,
                                    uint8_t prefetch, champsim::address evicted_addr,
                                    uint32_t metadata_in) {
      // called on a fill into the cache being modelled
      return metadata_in;
    }
  };

Constraints: standard library only, no external packages, no template
parameters, no file or network I/O, state kept in plain member fields.

Hard API constraints for this revision. Each of these was a real compiler error
observed in a generated candidate, so re-read the code for them before answering:

- champsim::address is a typed bit-slice, not an integer. static_cast<int64_t>(addr),
  addr + 1 and addr >> n all fail to compile.
- Convert once, at the top of the callback: champsim::block_number blk{addr};
  All line arithmetic happens on blk, which is an integer-like type.
- Convert back when issuing a prefetch:
  prefetch_line(champsim::address{blk + 1}, true, metadata_in);
- Distance between two lines uses champsim::offset(a, b) on block_number
  operands, and yields champsim::block_number::difference_type (signed).
- LOG2_BLOCK_SIZE is an unsigned int, so it cannot shift an address; shift
  plain integers only.
- Key tables on champsim::address or champsim::block_number values, which
  support == and <. There is no address-to-integer conversion to hash with.
- champsim::block_number is not an integer either: it supports ==, <, ++, and
  addition/subtraction of a difference_type, but there is no operator%, operator/
  or operator>> on it, so you cannot index an array with an address or mask off
  region bits. To reason about a region, hold a champsim::block_number base and
  take champsim::offset(base, blk), which returns a signed line count you can
  compare or use as an offset. Track a small fixed set of registers, or a
  std::vector of entries scanned with ==, instead of an address-indexed table.
- Include what you use: <vector>, <algorithm>, <cstddef> are available; anything
  else is not."""

PROMPTS = {
    "default": (
        "Design a novel L2 software-transparent prefetcher that trains on demand "
        "accesses and issues at most one prefetch per access."
    ),
    "aggressive_offset": (
        "Design a spatial-offset prefetcher that issues prefetches more than one "
        "cache line ahead, keeps a per-region confidence counter, and suppresses "
        "issue when confidence is low."
    ),
    "fill_only_conservative": (
        "Design a conservative prefetcher that never trains on demand misses: it "
        "issues prefetches only from cache-fill feedback, at most one line ahead."
    ),
}

STRUCT_DECL = re.compile(
    r"struct\s+([A-Za-z_]\w*)\s*(?:final\s*)?:\s*public\s+champsim::modules::prefetcher"
)
FENCE = re.compile(r"```(?:cpp|c\+\+|cc|C\+\+)?[^\n]*\n(.*?)```", re.DOTALL)


def module_name_for(prompt: str, seed: int) -> str:
    slug = re.sub(r"\W+", "_", prompt).strip("_").lower()
    return f"gen_{slug[:24]}_s{int(seed)}"


def build_prompt(prompt_name: str, seed: int) -> str:
    brief = PROMPTS[prompt_name]
    module = module_name_for(prompt_name, seed)
    return (
        f"{MODULE_SPEC}\n\n"
        f"Name the struct exactly `{module}`.\n\n"
        f"Design brief (seed {seed}): {brief}\n\n"
        "Return only one ```cpp fenced block holding the complete module, including "
        "the three #include lines. No prose, no comments describing the plan."
    )


def build_repair_prompt(prompt_name: str, seed: int, previous_source: str,
                        diagnostics: str, module: str) -> str:
    """Prompt for one compile-feedback round.

    Repaired candidates stay a separate protocol: the record carries
    ``repair_round`` and the module they were repaired from, so a repaired
    design can never be counted as a one-shot generation.
    """
    return (
        f"{build_prompt(prompt_name, seed)}\n\n"
        f"Your previous answer for this brief was:\n\n```cpp\n{previous_source}\n```\n\n"
        "It failed to compile. Compiler output:\n\n"
        f"```\n{diagnostics[-4000:]}\n```\n\n"
        f"Name the struct exactly `{module}`. Keep the design idea and change only "
        "what the compiler requires. Return only the corrected ```cpp block."
    )


def _match_bare_struct(raw: str) -> str:
    decl = STRUCT_DECL.search(raw)
    if not decl:
        raise ValueError("no champsim::modules::prefetcher struct found")
    start = raw.index("{", decl.end())
    depth = 0
    for index in range(start, len(raw)):
        if raw[index] == "{":
            depth += 1
        elif raw[index] == "}":
            depth -= 1
            if depth == 0:
                return raw[decl.start(): index + 1] + ";"
    raise ValueError("unbalanced braces in candidate module")


def parse_candidate_source(raw: str, *, module_name: str) -> dict:
    """Extract one compilable prefetcher module from a raw model reply."""
    fenced = FENCE.search(raw)
    if fenced and STRUCT_DECL.search(fenced.group(1)):
        source, parse = fenced.group(1).strip(), "fenced_cpp"
    elif STRUCT_DECL.search(raw):
        source, parse = _match_bare_struct(raw), "bare_struct"
    else:
        raise ValueError("model reply contains no prefetcher module")

    normalizations, warnings = [], []
    declared = STRUCT_DECL.search(source).group(1)
    if declared != module_name:
        source = re.sub(rf"\b{declared}\b", module_name, source)
        normalizations.append(f"struct_rename:{declared}->{module_name}")
    if "prefetcher_cache_operate" not in source:
        warnings.append("missing_prefetcher_cache_operate")
    if "prefetch_line" not in source:
        warnings.append("never_calls_prefetch_line")

    return {
        "parse": parse,
        "module_name": module_name,
        "source": source + "\n",
        "normalizations": normalizations,
        "warnings": warnings,
    }


def build_candidate_record(*, model: str, prompt_name: str, seed: int, prompt_text: str,
                           raw_response: str, parsed: dict, api_base: str,
                           latency_s: float, usage: dict, extra: dict | None = None) -> dict:
    module = parsed["module_name"]
    return {
        "candidate_id": module,
        "generator_seed": seed,
        "prompt": prompt_name,
        "module_name": module,
        "design": {
            "module_name": module,
            "prefetcher_source": parsed["source"],
            "cache_level": "L2C",
        },
        "provenance": {
            "model": model,
            "api_base": api_base,
            "endpoint": "/chat/completions",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latency_s": latency_s,
            "usage": usage,
            "prompt_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
            "prompt_text": prompt_text,
            "raw_response": raw_response,
            "parse": parsed["parse"],
            "normalizations": parsed["normalizations"],
            "warnings": parsed["warnings"],
            "credential_source": str(CREDENTIAL_PATH) + " (value not stored)",
            **(extra or {}),
        },
    }


def read_api_key(path: Path = CREDENTIAL_PATH) -> str:
    return path.read_text().strip().splitlines()[0]


def call_chat(prompt_text: str, *, model: str, api_key: str, seed: int,
              temperature: float, max_tokens: int, timeout_s: int,
              api_base: str = API_BASE) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": temperature,
        "seed": seed,
        "max_tokens": max_tokens,
    }).encode()
    request = urllib.request.Request(
        api_base + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + api_key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        payload = json.load(response)
    return {
        "text": payload["choices"][0]["message"]["content"],
        "usage": payload.get("usage", {}),
    }


def repo_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--cells", default="default:0,aggressive_offset:0,default:1",
                        help="comma separated prompt:seed pairs")
    parser.add_argument("--model", default="Pro/deepseek-ai/DeepSeek-V3")
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--credential-path", type=Path, default=CREDENTIAL_PATH)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true",
                        help="print prompts without contacting any API")
    parser.add_argument("--repair-from", type=Path,
                        help="screening JSONL from scripts/module_effect_control.py; "
                             "one repair turn is generated for each build failure")
    parser.add_argument("--source-dir", type=Path,
                        help="directory holding the candidate JSONs named by that log")
    args = parser.parse_args()

    cells = []
    for token in args.cells.split(","):
        name, _, seed = token.partition(":")
        name = name.strip()
        if name not in PROMPTS:
            parser.error(f"unknown prompt variant {name!r}; have {sorted(PROMPTS)}")
        cells.append((name, int(seed or 0)))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.out_dir / "generation-log.jsonl"
    api_key = "" if args.dry_run else read_api_key(args.credential_path)
    written, failures = 0, []

    failed, previous = {}, {}
    if args.repair_from:
        for line in args.repair_from.read_text().splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("build_success") is False:
                failed[record["module"]] = record.get("diagnostics_tail", "")
        for path in sorted((args.source_dir or args.out_dir).glob("*.json")):
            try:
                record = json.loads(path.read_text())
            except ValueError:
                continue
            if "design" in record:
                previous[record["design"]["module_name"]] = record

    for name, seed in cells:
        prompt_text = build_prompt(name, seed)
        module = module_name_for(name, seed)
        extra = None
        if args.repair_from:
            diagnostics = failed.get(module)
            if diagnostics is None or module not in previous:
                continue
            extra = {"repair_round": 1, "repaired_from": module,
                     "diagnostics_sha256":
                         hashlib.sha256(diagnostics.encode()).hexdigest()}
            prompt_text = build_repair_prompt(
                name, seed, previous[module]["design"]["prefetcher_source"],
                diagnostics, f"{module}_r1")
            module += "_r1"
        entry = {"cell": f"{name}/{seed}", "module_name": module, "model": args.model,
                 "generator_repo_sha": repo_sha(), "prompt_sha256":
                     hashlib.sha256(prompt_text.encode()).hexdigest()}
        if args.dry_run:
            entry.update({"state": "dry_run", "prompt_chars": len(prompt_text)})
            print(json.dumps(entry, ensure_ascii=False))
            with log_path.open("a") as log:
                log.write(json.dumps(entry, ensure_ascii=False) + "\n")
            continue

        started = time.monotonic()
        try:
            reply = call_chat(prompt_text, model=args.model, api_key=api_key, seed=seed,
                              temperature=args.temperature, max_tokens=args.max_tokens,
                              timeout_s=args.timeout_s, api_base=args.api_base)
            parsed = parse_candidate_source(reply["text"], module_name=module)
        except (urllib.error.URLError, KeyError, ValueError, OSError) as error:
            failures.append({"cell": entry["cell"], "error": f"{type(error).__name__}: {error}"[:400]})
            entry.update({"state": "failed", "error": str(error)[:400]})
            with log_path.open("a") as log:
                log.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[fail] {entry['cell']}: {type(error).__name__} {str(error)[:160]}")
            continue

        record = build_candidate_record(
            model=args.model, prompt_name=name, seed=seed, prompt_text=prompt_text,
            raw_response=reply["text"], parsed=parsed, api_base=args.api_base,
            latency_s=round(time.monotonic() - started, 2), usage=reply.get("usage", {}),
            extra=extra,
        )
        record["provenance"]["generator_repo_sha"] = repo_sha()
        path = args.out_dir / f"{module}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
        entry.update({"state": "written", "path": str(path),
                      "parse": parsed["parse"], "warnings": parsed["warnings"],
                      "latency_s": record["provenance"]["latency_s"]})
        with log_path.open("a") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        written += 1
        print(f"[ok] {module} parse={parsed['parse']} {record['provenance']['latency_s']}s "
              f"warnings={parsed['warnings'] or 'none'}")

    print(f"candidates_written={written} cells={len(cells)} failures={len(failures)}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
