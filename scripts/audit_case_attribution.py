"""审计每个语义用例的源文件归属：用例里存的源码，是否就是产生该测量的那个文件。

触发点：sem-esc-01 的 design_source_sha256 指向 .tmp/cand/gen_default_s0.json，
而那份源码在钉死镜像里根本编译不过；真正编译成功并测出 1,138,748 的是
.tmp/cand2 的同名文件。也就是说标注者读到的是 A 文件的源码，
而"测量说等价"说的是 B 文件。

这个脚本对所有 semantic / semantic_fact 用例做同一检查：
1) 用例内嵌源码的 sha256 是否等于它自己声明的 evidence 哈希；
2) 该源码是否能在仓库的候选目录里找到同名但**不同内容**的另一份（名字冲突）。
"""
import glob
import hashlib
import json
import os
import sys
from collections import defaultdict

REPO = "/mnt/d/chia-repo-audit-from-linux-20260922/chia-repo-audit"

# 每个模块名在各候选目录里对应的源码摘要
by_module = defaultdict(dict)
for path in glob.glob(os.path.join(REPO, ".tmp", "cand*", "*.json")):
    if "generation-log" in path:
        continue
    try:
        c = json.load(open(path, encoding="utf-8"))
    except Exception:
        continue
    src = (c.get("design") or {}).get("prefetcher_source") if isinstance(c.get("design"), dict) \
        else c.get("source") or c.get("code")
    mod = c.get("module_name") or c.get("candidate_id")
    if not src or not mod:
        continue
    tag = os.path.basename(os.path.dirname(path))
    by_module[mod][hashlib.sha256(src.encode()).hexdigest()] = tag

bad_selfhash = []
collisions = []
checked = 0
for case_dir in ("chia_loop/semantic", "chia_loop/semantic_fact"):
    for path in sorted(glob.glob(os.path.join(REPO, case_dir, "*.json"))):
        case = json.load(open(path, encoding="utf-8"))
        ev = case.get("evidence", {})
        for side in ("design", "reference"):
            body = case.get(side) or {}
            src = body.get("prefetcher_source")
            declared = ev.get(f"{side}_source_sha256")
            if not src or not declared:
                continue
            checked += 1
            actual = hashlib.sha256(src.encode()).hexdigest()
            if actual != declared:
                bad_selfhash.append((case["id"], side, declared[:16], actual[:16]))
            mod = body.get("module_name", "")
            variants = by_module.get(mod, {})
            if len(variants) > 1 and actual in variants:
                others = {h[:16]: t for h, t in variants.items() if h != actual}
                if others:
                    collisions.append((case["id"], side, mod, variants[actual], others))

print(f"checked {checked} (case, side) source-hash assertions")
print(f"\nself-inconsistent (embedded source != declared hash): {len(bad_selfhash)}")
for row in bad_selfhash:
    print("   ", row)

print(f"\nname collisions where the SAME module name has several distinct sources: "
      f"{len(collisions)}")
seen = set()
for case_id, side, mod, own, others in collisions:
    key = (mod, own)
    if key in seen:
        continue
    seen.add(key)
    print(f"    {mod}: case uses {own}, other copies {others}")

if bad_selfhash:
    sys.exit(1)
