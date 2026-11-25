#!/bin/bash
# 基模评测矩阵：按 configs/registry/model-registry.json 逐模型 × 逐 task 调 ci_robotwin_full.sh，
# 每 task 一轮独立 chunk（CogACT 一头一 task），产物收拢到 matrix/<model>/<task>/ 后整包传 OBS。
# 输入（环境变量）：
#   MM_MODELS   逗号分隔模型名（registry key）
#   MM_TASKS    逗号分隔 task
#   MM_EPISODES 每 task 集数（默认 50，考场口径）
#   MM_SHARDS   分片数（默认 8）
#   MM_VIDEO    1=录像（默认 0）
#   MODEL_REGISTRY 默认 configs/registry/model-registry.json
# 约定：matrix/ 独立于 results/（results/ 每轮会被 results_fresh 清空）。
set -e
cd "$(dirname "$0")/../.."
WORK="$PWD"
REG="${MODEL_REGISTRY:-configs/registry/model-registry.json}"
MODELS="${MM_MODELS:?MM_MODELS 必填（逗号分隔 registry key）}"
TASKS="${MM_TASKS:?MM_TASKS 必填（逗号分隔 task）}"
EP="${MM_EPISODES:-50}"
SH="${MM_SHARDS:-8}"
VID="${MM_VIDEO:-0}"
PROTO="${MM_PROTOCOL:-easy}"   # easy=demo_clean | hard=demo_randomized
REPLICATE="${MM_REPLICATE:-}"  # A5：重复轮标签（r2/r3…），空=首轮
RESUME="${MM_RESUME:-0}"       # 1=保留 results/ 与 sqlite（续跑/救援）

[ -f "$REG" ] || { echo "registry 不存在: $REG" >&2; exit 1; }

field() {  # field <model> <key>
  python3 - "$REG" "$1" "$2" <<'PY'
import json, sys
reg, model, key = sys.argv[1], sys.argv[2], sys.argv[3]
m = json.load(open(reg))["models"][model]
print(m.get(key, "") if not isinstance(m.get(key, ""), (list, dict)) else "")
PY
}

mkdir -p matrix
for model in ${MODELS//,/ }; do
  echo "================ [$model] ================"
  SERVE_IMAGE_V="$(field "$model" serve_image)"
  SERVE_YAML_V="$(field "$model" serve_yaml)"
  PREWARM_V="$(field "$model" prewarm)"
  ACTION_V="$(field "$model" action_type)"
  SKIP_V="$(field "$model" skip_expert)"
  BENCH_V="$(field "$model" bench_tag)"
  FAST_V="$(field "$model" fast_init)"
  CKPT_REPO_V="$(field "$model" ckpt_repo)"
  CKPT_REV_V="$(field "$model" ckpt_revision)"
  [ -z "$CKPT_REPO_V" ] && CKPT_REPO_V="$(field "$model" ckpt)"
  # A1：verified 模型必须有 revision，否则拒绝跑（否则永远拉 main，复现必翻车）
  if [ "$(field "$model" status)" = "verified" ] && [ -z "$CKPT_REV_V" ]; then
    echo "REFUSE: $model status=verified 但缺 ckpt_revision（weights 无法钉版本）" >&2
    exit 1
  fi

  if [ -z "$SERVE_IMAGE_V" ]; then
    echo "SKIP $model：registry 里没有 serve_image（适配未就绪，status=$(field "$model" status)）" >&2
    continue
  fi

  case "$PROTO" in
    easy) TASK_CFG="demo_clean" ;;
    hard) TASK_CFG="demo_randomized" ;;
    *) echo "MM_PROTOCOL 只允许 easy|hard（实际 $PROTO）" >&2; exit 1 ;;
  esac
  for task in ${TASKS//,/ }; do
    echo "---------------- [$model] $task x$EP ($PROTO) ----------------"
    SUFFIX="$PROTO"
    if [ -n "$REPLICATE" ]; then SUFFIX="$PROTO-$REPLICATE"; fi
    rm -rf "matrix/$model/$task" "matrix/$model/$task-$SUFFIX"
    RW_TASKS="$task" RW_EPISODES="$EP" RW_SHARDS="$SH" RW_VIDEO="$VID" \
      SERVE_IMAGE="$SERVE_IMAGE_V" RW_SERVE_YAML="$SERVE_YAML_V" RW_PREWARM="$PREWARM_V" \
      RW_ACTION_TYPE="$ACTION_V" RW_SKIP_EXPERT="$SKIP_V" RW_BENCH_TAG="$BENCH_V" RW_FAST_INIT="$FAST_V" \
      RW_CKPT_REPO="$CKPT_REPO_V" RW_CKPT_REV="$CKPT_REV_V" RW_TASK_CONFIG="$TASK_CFG" \
      RW_REPLICATE="$REPLICATE" RW_RESUME="$RESUME" \
      bash scripts/ci/ci_robotwin_full.sh
    mkdir -p matrix/"$model"
    if ! ls -d results/robotwin-* >/dev/null 2>&1; then
      echo "MISSING results/robotwin-*（$model/$task 没产物，停）" >&2
      exit 1
    fi
    cp -r results/robotwin-* "matrix/$model/$task-$SUFFIX"
    echo "collected: matrix/$model/$task-$SUFFIX"
  done
done

echo "=== matrix 汇总 ==="
find matrix -name "*_aggregate.json" | sort
