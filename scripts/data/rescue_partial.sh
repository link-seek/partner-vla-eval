#!/bin/bash
# 部分结果救援：从 recording sqlite 增量导出 aggregate（不重跑评测）。
#
# 背景：`vla-eval export --help` 明确支持 "Rerun to include subsequently recorded
# episodes"。但我们每轮开跑前 `results_fresh` 会把 results/ 连 sqlite 一起删，
# 于是 run 中途崩掉就全丢。这个脚本把"已有的那部分"捞回来。
#
# 用法：
#   bash scripts/data/rescue_partial.sh <sqlite> [输出目录]
#
# 会在宿主机（有 docker 的那台）上跑，用 robotwin 镜像执行 vla-eval export。
# 输出：<outdir>/aggregate.json + 每集 jsonl；并打印 已完成/目标 集数。
set -euo pipefail

SQLITE="${1:?用法: rescue_partial.sh <recording-*.sqlite> [outdir]}"
OUT="${2:-$(dirname "$SQLITE")/rescue}"
IMG="${ROBOTWIN_IMAGE:-swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:0.8.0-ee-slim}"
TARGET="${TARGET_EPISODES:-50}"

[ -f "$SQLITE" ] || { echo "找不到 sqlite: $SQLITE" >&2; exit 1; }
mkdir -p "$OUT"

# 一致性快照：sqlite 正在被写时，直接 cp 可能读到半页。有 sqlite3 就 .backup，
# 没有就退化成 cp（export 本身对损坏容忍度较低，但 cp 通常也能读）。
SNAP="$OUT/snapshot.sqlite"
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$SQLITE" ".backup '$SNAP'" && echo "[rescue] 用 sqlite3 .backup 取快照"
else
  cp -f "$SQLITE" "$SNAP" && echo "[rescue] 无 sqlite3，退化为 cp 快照"
fi

echo "[rescue] 导出中（镜像 $IMG）"
docker run --rm --entrypoint bash \
  -v "$(dirname "$SQLITE")":"$(dirname "$SQLITE")" \
  -v "$OUT":"$OUT" \
  "$IMG" -c "cd /work 2>/dev/null || cd /; conda run --no-capture-output -n robotwin vla-eval export '$SNAP' -o '$OUT' 2>&1 | tail -6" \
  || { echo "[rescue] export 失败（sqlite 可能损坏或格式不符）" >&2; exit 1; }

echo "[rescue] 产物："
ls -lh "$OUT" | tail -6

python3 - "$OUT" "$TARGET" <<'PY'
import json, glob, sys, pathlib
out, target = pathlib.Path(sys.argv[1]), int(sys.argv[2])
aggs = list(out.glob("*aggregate*.json")) + list(out.glob("aggregate.json"))
if not aggs:
    print("[rescue] 没找到 aggregate.json"); raise SystemExit(0)
d = json.loads(aggs[0].read_text())
tasks = d.get("tasks", [d])
tot = 0
for t in tasks:
    eps = t.get("episodes", [])
    ok = sum(1 for e in eps if (e.get("metrics") or {}).get("success"))
    tot += len(eps)
    pct = len(eps) / target * 100 if target else 0
    flag = "部分" if len(eps) < target else "完整"
    print(f"[rescue] {t.get('task','?')}: {ok}/{len(eps)} 完成度 {len(eps)}/{target} ({pct:.0f}%) [{flag}]")
print(f"[rescue] 合计 {tot} 集；目标每 task {target} 集")
if tot < target:
    print("[rescue] 注意：这是部分结果，只能进附录，不能当正式数（榜单门禁按 n 判断）")
PY
