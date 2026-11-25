#!/bin/bash
# 从 matrix/ 汇总某模型某协议的逐 task 结果，输出紧凑 JSON（供 gen_reports.py 生成报告）
#
# 用法：bash scripts/data/collect_matrix.sh <model_key> <easy|hard> [matrix_root]
#   model_key   registry key，如 x-vla-robotwin2
#   协议        easy → matrix/<model>/<task>；hard → matrix/<model>/<task>-hard
# 输出：stdout 一份 JSON；stderr 打合计。
#
# 为什么要有这个脚本：2026-11-24 之前这段逻辑只存在于 /tmp，机器一关就没了，不可复现。
set -euo pipefail

MODEL="${1:?用法: collect_matrix.sh <model> <easy|hard> [matrix_root] [replicate]}"
PROTO="${2:?用法: collect_matrix.sh <model> <easy|hard> [matrix_root]}"
ROOT="${3:-matrix}"
REPLICATE="${4:-}"   # A5：重复轮标签（r2/r3…）

case "$PROTO" in
  easy) SUFFIX="" ;;
  hard) SUFFIX="-hard" ;;
  *) echo "协议只允许 easy|hard（实际 $PROTO）" >&2; exit 1 ;;
esac
if [ -n "$REPLICATE" ]; then SUFFIX="${SUFFIX}-${REPLICATE}"; fi

# task 清单从 registry.exam.tasks 取（唯一真源，见 scripts/data/bench_config.py 注释）
CFG_TASKS=$(python3 "$(dirname "$0")/bench_config.py" tasks)

python3 - "$ROOT" "$MODEL" "$SUFFIX" "$PROTO" "$REPLICATE" "$CFG_TASKS" <<'PY'
import json, pathlib, sys

root, model, suffix, proto, replicate = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
base = pathlib.Path(root) / model
tasks = [t for t in sys.argv[6].split(",") if t]

# 目录里有、但清单里没有的：多数是别的考场或改名残留，提醒但不收（避免混进报告）
if base.is_dir():
    known = set(tasks)
    extra = sorted({d.name.split("-hard")[0].replace("-r2", "") for d in base.iterdir() if d.is_dir()} - known)
    if extra:
        print(f"[collect] 注意：{model} 下有不属于 exam.tasks 的目录，已跳过：{extra}", file=sys.stderr)

out = {"model": model, "protocol": proto, "replicate": replicate or None, "tasks": {}}
for task in tasks:
    # 目录名 = <task> 或 <task>-hard；早期产物没有 -hard 后缀，两种都试
    cands = [base / f"{task}{suffix}", base / task]
    p = None
    for d in cands:
        f = d / f"{task}_aggregate.json"
        if f.exists():
            p = f
            break
    if p is None:
        out["tasks"][task] = {"status": "missing"}
        continue
    d = json.load(open(p))
    t = d.get("tasks", [d])[0]
    eps = t.get("episodes", [])
    ok = sum(1 for e in eps if (e.get("metrics") or {}).get("success"))
    errs = sum(1 for e in eps if e.get("error"))
    steps = [e.get("steps", 0) for e in eps] or [0]
    out["tasks"][task] = {
        "n": len(eps), "success": ok,
        "rate": round(ok / max(1, len(eps)), 4),
        "errors": errs,
        "steps_avg": round(sum(steps) / max(1, len(steps)), 1),
        "steps_med": sorted(steps)[len(steps) // 2] if steps else 0,
        "created_at": d.get("created_at"),
        "harness_version": d.get("harness_version"),
    }

json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
print()

done = {k: v for k, v in out["tasks"].items() if v.get("status") != "missing"}
tot = sum(v["success"] for v in done.values())
ne = sum(v["n"] for v in done.values())
print(f"[{model}/{proto}] {tot}/{ne} = {tot / max(1, ne) * 100:.1f}% over {len(done)} task(s)", file=sys.stderr)
for k, v in out["tasks"].items():
    print(f"  {k}: " + (f"{v['success']}/{v['n']} = {v['rate'] * 100:.0f}%" if v.get("status") != "missing" else "MISSING"), file=sys.stderr)
PY
