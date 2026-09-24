#!/usr/bin/env python3
"""Emit a self-contained, blind annotation page and its separate answer key.

Why a generator rather than a hand-written page: the point of the page is that a human
answers the same contract the models answered, so it must show exactly what
`scripts/independent_audit.py` shows. That module already owns the allowlist, so this
imports it instead of copying it -- a second copy of a leak guard is how a guard stops
being a guard.

Two leaks this closes that a naive page would not:

1. Field leak. `annotator_payload` allows only id/design/reference. Anything else in a
   case record (expected_verdict, planting, evidence, taxonomy_note) is the answer.
   Every payload is re-checked after construction and the build refuses if a forbidden
   key survived, so the guard is exercised rather than trusted.

2. Identity leak. Case ids are not neutral: `sem-esc-01` says "this is a simulator
   escape", which is the thing under test. So the page shows opaque slots (Q1..Qn) in a
   seeded shuffle, and the slot -> case mapping is written to a SEPARATE key file that
   the page never references. Without that, a rater who has read the ops log is not
   blind and the resulting agreement statistic means nothing.

The export echoes the shuffle seed and the digest of the rendered prompt set. That is
what lets a later reader tell that a submitted answer file belongs to this display and
was not assembled after the key was consulted.

The page is not tamper-proof -- it is a local file, and the rater here is the person who
built the cases. So the export records that fact as a field (`rater_role`,
`authored_cases`) and `scripts/score_human_annotations.py` refuses to call the result an
inter-rater reliability estimate when the rater authored the cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from independent_audit import (FORBIDDEN_KEYS, VISIBLE_KEYS,  # noqa: E402
                               RUBRIC, annotator_payload)

SETS = {
    "spec10": ["chia_loop/gold", "chia_loop/adversarial"],
    "measured6": ["chia_loop/semantic"],
    "fact36": ["chia_loop/semantic_fact"],
}
# Re-read from substrate_probe.py's own source at build time rather than trusting this
# dict. substrate_probe imports torch at module scope, so it cannot be imported here to
# share the constant, and a silently-diverging copy of "which files are which case set"
# would let the human annotate one set while the scorer compares it against another.
def declared_sets() -> dict:
    import ast
    src = (REPO / "scripts/substrate_probe.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "SETS" for t in node.targets):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                paths = []
                for e in v.elts:
                    # each element is `REPO / "chia_loop/gold"`, i.e. a BinOp whose
                    # right operand is the string we want
                    right = getattr(e, "right", e)
                    paths.append(ast.literal_eval(right))
                out[k.value] = paths
            return out
    raise SystemExit("SETS not found in substrate_probe.py; refusing to guess case dirs")


def load_cases(dirs: list[Path]) -> list[dict]:
    out = []
    for d in dirs:
        for p in sorted(Path(d).glob("*.json")):
            if p.name == "answer-key.json":
                continue
            rec = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(rec, dict) or "id" not in rec:
                continue
            rec["_path"] = str(p.relative_to(REPO)).replace("\\", "/")
            out.append(rec)
    return out


def build_page(cases: list[dict], seed: int, out_html: Path, out_key: Path) -> int:
    payload, key = [], []
    order = list(range(len(cases)))
    random.Random(seed).shuffle(order)
    for slot, idx in enumerate(order, start=1):
        case = cases[idx]
        vis = annotator_payload(case)          # raises if a forbidden key leaked in
        blob = json.dumps(vis, indent=2)
        leak = [k for k in FORBIDDEN_KEYS if k in blob]
        if leak:
            raise SystemExit(f"slot Q{slot} leaks {leak} after allowlisting")
        if str(case.get("expected_verdict")) in blob:
            raise SystemExit(f"slot Q{slot} contains the expected verdict verbatim")
        sid = f"Q{slot}"
        payload.append({"slot": sid, "rubric": RUBRIC, "case": vis})
        key.append({"slot": sid, "case_id": case["id"], "path": case["_path"],
                    "expected_verdict": case.get("expected_verdict"),
                    "expected_errors": case.get("expected_errors")})

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    display_sha = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False)) \
                   .replace("__SEED__", str(seed)) \
                   .replace("__SHA__", display_sha) \
                   .replace("__N__", str(len(payload))) \
                   .replace("__BUILT__", datetime.now(timezone.utc).isoformat())
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_bytes(html.encode("utf-8"))
    out_key.write_bytes((json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "shuffle_seed": seed,
        "display_sha256": display_sha,
        "n_slots": len(payload),
        "visible_keys_shown": list(VISIBLE_KEYS),
        "forbidden_keys_gated": list(FORBIDDEN_KEYS),
        "slots": key,
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"wrote {out_html.relative_to(REPO)} ({len(html)} bytes, {len(payload)} slots)")
    print(f"wrote {out_key.relative_to(REPO)}")
    print(f"display_sha256 {display_sha}")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Blind annotation - CHIA audit</title>
<style>
body{font:15px/1.6 system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1a1c20}
header{position:sticky;top:0;background:#1a1c20;color:#fff;padding:12px 20px;z-index:5}
header b{font-size:16px} header span{opacity:.75;font-size:13px;margin-left:12px}
main{max-width:960px;margin:0 auto;padding:20px}
.card{background:#fff;border:1px solid #d8dbe0;border-radius:8px;padding:16px;margin-bottom:14px}
.card h2{margin:0 0 4px;font-size:16px}
.rubric{white-space:pre-wrap;background:#f0f2f5;border-left:3px solid #98a1ad;
 padding:10px;font-size:12.5px;max-height:150px;overflow:auto;color:#3c424b}
pre{white-space:pre-wrap;background:#fbfbfc;border:1px solid #e3e6ea;border-radius:6px;
 padding:10px;font-size:12.5px;max-height:340px;overflow:auto;margin:6px 0}
label{display:inline-block;margin-right:14px;font-size:14px}
input[type=text]{width:100%;box-sizing:border-box;padding:7px;border:1px solid #cfd4da;
 border-radius:6px;font-size:14px}
.row{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:8px}
button{background:#2f6f4f;color:#fff;border:0;border-radius:6px;padding:10px 16px;
 font-size:14px;cursor:pointer}
button.sec{background:#4a515c}
.done .card{opacity:.55;border-color:#2f6f4f}
#prog{font-variant-numeric:tabular-nums}
.note{font-size:12.5px;color:#5c636e;margin-top:6px}
</style></head><body>
<header><b>Blind annotation</b><span id="prog"></span>
 <span>seed __SEED__ · display __SHA__ · __N__ slots</span></header>
<main>
<div class="card" id="meta">
 <h2>Before you start</h2>
 <p>You will see <b>__N__</b> candidate/reference pairs of C++ prefetcher source, in an
 order that is not the repository order and under labels (Q1..Q__N__) that do not
 identify where a case came from. Nothing here names the simulator result.</p>
 <div class="row">
  <label>Rater name or handle <input type="text" id="rater"></label>
  <label><input type="checkbox" id="authored"> I constructed or co-constructed some of these cases</label>
 </div>
 <div class="row">
  <label><input type="checkbox" id="attest"> I have not consulted the answer key or the
   measurement records for any case during this session</label>
 </div>
 <p class="note">Both boxes are recorded in the export as data, not as prose. The
 scorer refuses to describe the result as an inter-rater reliability estimate if the
 rater authored the cases, because that is the failure mode this repository is about.</p>
</div>
<div id="cases"></div>
<div class="card"><div class="row">
 <button id="dl">Download answer file</button>
 <button class="sec" id="js">Copy JSON</button>
 <span id="warn" class="note"></span>
</div></div>
</main>
<script>
const DATA = __DATA__;
const SEED = __SEED__, SHA = "__SHA__";
const box = document.getElementById("cases");
DATA.forEach(d => {
  const el = document.createElement("div");
  el.className = "card"; el.id = "c-" + d.slot;
  const errs = ["E1","E2","E3","E4"].map(e =>
    `<label><input type="checkbox" data-slot="${d.slot}" data-err="${e}"> ${e}</label>`).join("");
  el.innerHTML = `<h2>${d.slot}</h2>
   <details><summary class="note">task rubric</summary><div class="rubric">${d.rubric}</div></details>
   <h3 class="note">candidate</h3><pre>${esc(JSON.stringify(d.case.design, null, 2))}</pre>
   <h3 class="note">reference</h3><pre>${esc(JSON.stringify(d.case.reference, null, 2))}</pre>
   <div class="row">
     <label><input type="radio" name="v-${d.slot}" value="equivalent"> equivalent</label>
     <label><input type="radio" name="v-${d.slot}" value="not_equivalent"> not equivalent</label>
   </div>
   <div class="row">${errs}</div>
   <div class="row" style="width:100%"><input type="text" id="r-${d.slot}"
     placeholder="one sentence rationale"></div>`;
  box.appendChild(el);
});
function esc(s){const n=document.createElement("div");n.textContent=s;return n.innerHTML;}
function collect(){
  const out = {schema:"chia-human-annotation/1", generated_utc:
      new Date().toISOString(), shuffle_seed:SEED, display_sha256:SHA,
      rater: document.getElementById("rater").value.trim(),
      rater_authored_cases: document.getElementById("authored").checked,
      attested_blind: document.getElementById("attest").checked, labels: []};
  DATA.forEach(d => {
    const v = document.querySelector(`input[name="v-${d.slot}"]:checked`);
    const e = Array.from(document.querySelectorAll(
        `input[data-slot="${d.slot}"][data-err]:checked`)).map(x=>x.dataset.err);
    out.labels.push({slot:d.slot, verdict: v ? v.value : null,
                     errors: e, rationale: document.getElementById("r-"+d.slot).value.trim()});
    if (v) document.getElementById("c-"+d.slot).classList.add("done");
  });
  return out;
}
function progress(){
  const n = DATA.filter(d => document.querySelector(`input[name="v-${d.slot}"]:checked`)).length;
  document.getElementById("prog").textContent = `${n} / ${DATA.length} answered`;
  return n;
}
document.addEventListener("change", () => { progress();
  document.getElementById("warn").textContent = ""; });
progress();
function dl(){
  const done = progress(), o = collect();
  if (done < DATA.length) { document.getElementById("warn").textContent =
      `${DATA.length - done} slots still unanswered`; return; }
  if (!o.rater) { document.getElementById("warn").textContent = "rater name required"; return; }
  if (!o.attested_blind) { document.getElementById("warn").textContent =
      "the blind attestation box is required"; return; }
  const b = new Blob([JSON.stringify(o, null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b); a.download = "annotator_result.json"; a.click();
}
document.getElementById("dl").onclick = dl;
document.getElementById("js").onclick = () =>
  navigator.clipboard.writeText(JSON.stringify(collect(), null, 2));
</script></body></html>
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--out", default="web/annotator.html")
    ap.add_argument("--key", default="results/annotator_human_key.json")
    ap.add_argument("--sets", nargs="*", default=["measured6", "spec10"],
                    help="which registered case sets to show; `all` takes every one")
    ap.add_argument("--dirs", nargs="*", default=None,
                    help="ad-hoc directories, bypassing the registered-set check")
    opts = ap.parse_args(argv)

    want = sorted(SETS) if opts.sets == ["all"] else opts.sets
    if opts.dirs:
        dirs = [REPO / d for d in opts.dirs]
    else:
        decl = declared_sets()
        for name in want:
            if name not in decl:
                raise SystemExit(f"set {name!r} is not declared in substrate_probe.py")
            if decl[name] != SETS[name]:
                raise SystemExit(f"SETS[{name!r}] disagrees with substrate_probe.py: "
                                 f"{SETS[name]} vs {decl[name]}")
        dirs = [REPO / d for name in want for d in SETS[name]]
    cases = load_cases(dirs)
    if not cases:
        raise SystemExit("no cases found in " + ", ".join(str(d) for d in dirs))
    print(f"sets {want}: {len(cases)} cases from {len(dirs)} directories")
    return build_page(cases, opts.seed, REPO / opts.out, REPO / opts.key)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
