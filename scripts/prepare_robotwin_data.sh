#!/bin/bash
# S1：取 RoboTwin 2.0 训练数据子集（R01 口径）
#   clean_50        = 口径 A（50 条 clean demos）
#   randomized_500  = 口径 B 的增量（与 clean_50 合并成 550 条）
# 数据从 hf-mirror 直拉（V100 出境不通，走镜像站），解包后出 manifest 供训练脚本核对。
# 用法：TASKS=grab_roller,... DATA_ROOT=/root/robotwin-train bash scripts/prepare_robotwin_data.sh
set -euo pipefail

TASKS="${TASKS:-grab_roller,adjust_bottle,place_phone_stand,click_bell,handover_block}"
DATA_ROOT="${DATA_ROOT:-/data/robotwin-train}"
BASE="${HF_MIRROR:-https://hf-mirror.com}/datasets/TianxingChen/RoboTwin2.0/resolve/main/dataset"

mkdir -p "$DATA_ROOT"/{raw,data}
echo "[S1] 目标目录 $DATA_ROOT  任务：$TASKS"

for task in ${TASKS//,/ }; do
  for kind in clean_50 randomized_500; do
    zip="aloha-agilex_${kind}.zip"
    raw="$DATA_ROOT/raw/$task/$zip"
    out="$DATA_ROOT/data/$task/$kind"
    mkdir -p "$(dirname "$raw")"
    if [ ! -s "$raw" ]; then
      echo "[S1] 下载 $task/$zip"
      curl -fL --retry 5 --retry-delay 10 -o "$raw.part" "$BASE/$task/$zip"
      mv "$raw.part" "$raw"
    else
      echo "[S1] 已存在 $task/$zip（$(du -h "$raw" | cut -f1)）"
    fi
    if [ ! -d "$out" ] || [ -z "$(find "$out" -name '*.hdf5' -print -quit)" ]; then
      echo "[S1] 解包 $task/$kind"
      mkdir -p "$out"
      unzip -q -o "$raw" -d "$out"
    fi
    n=$(find "$out" -name '*.hdf5' | wc -l)
    echo "[S1] $task/$kind -> $n episodes"
  done
done

python3 - "$DATA_ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
man = {"source": "TianxingChen/RoboTwin2.0", "embodiment": "aloha-agilex", "tasks": {}}
for task_dir in sorted((root / "data").iterdir()):
    if not task_dir.is_dir():
        continue
    entry = {}
    for kind in ("clean_50", "randomized_500"):
        d = task_dir / kind
        n = len(list(d.rglob("*.hdf5"))) if d.is_dir() else 0
        entry[kind] = n
    entry["regime_A"] = entry["clean_50"]
    entry["regime_B"] = entry["clean_50"] + entry["randomized_500"]
    man["tasks"][task_dir.name] = entry
(root / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2))
print("[S1] manifest ->", root / "manifest.json")
for t, e in man["tasks"].items():
    print(f"  {t}: A={e['regime_A']}  B={e['regime_B']}")
PY
