#!/usr/bin/env bash
# R01 S3：单 task × 单口径的 ACT 训练（可重复，可干跑）
#
# 用法：
#   bash scripts/r01/s3_train_act.sh --task click_bell --regime clean_50
#   bash scripts/r01/s3_train_act.sh --task click_bell --regime clean_50 --epochs 1 --dry-run
#
# 设计要点（都是 2026-11-25 实测踩过的）：
#   1. 训练镜像必须是 vla-robotwin-train（einops + dm_control 构建期装）
#   2. 训练容器必须 --ipc=host（默认 64MB /dev/shm 会让 DataLoader worker 崩）
#   3. 原始数据先经 process_data.py 转成训练格式；布局用软链补齐
#   4. 40k 优化步按 batch=8 换算成 epochs（A=50 集 / B=550 集步数不同）
#   5. 产物必须是 policy_last.ckpt + dataset_stats.pkl（serve 契约）
set -euo pipefail

TASK=""; REGIME="clean_50"; GPU=0; STEPS=40000; SEED=0; EPOCHS=""; DRY=0
DATA_ROOT=/data/robotwin-train
CKPT_ROOT=/root/r01/r01-ckpt
IMAGE=vla-robotwin-train:dev
BATCH=8
SAVE_FREQ=2000

while [ $# -gt 0 ]; do
  case "$1" in
    --task) TASK="$2"; shift 2 ;;
    --regime) REGIME="$2"; shift 2 ;;
    --gpu) GPU="$2"; shift 2 ;;
    --steps) STEPS="$2"; shift 2 ;;
    --epochs) EPOCHS="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --data-root) DATA_ROOT="$2"; shift 2 ;;
    --ckpt-root) CKPT_ROOT="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$TASK" ] || { echo "--task 必填" >&2; exit 2; }
case "$REGIME" in clean_50|randomized_500) ;; *) echo "--regime 只允许 clean_50|randomized_500" >&2; exit 2 ;; esac

SRC="$DATA_ROOT/data/$TASK/$REGIME/aloha-agilex_$REGIME"
[ -d "$SRC/data" ] || { echo "数据不存在：$SRC/data" >&2; exit 3; }
N=$(find "$SRC/data" -name '*.hdf5' | wc -l)
[ "$N" -gt 0 ] || { echo "没有 hdf5：$SRC/data" >&2; exit 3; }

BATCHES=$(( (N + BATCH - 1) / BATCH ))
if [ -z "$EPOCHS" ]; then
  EPOCHS=$(( (STEPS + BATCHES - 1) / BATCHES ))
fi
RUN_NAME="${TASK}-${REGIME}-s${SEED}"
OUT="$CKPT_ROOT/$RUN_NAME"
LOG_DIR="$CKPT_ROOT/logs"
mkdir -p "$OUT" "$LOG_DIR"
LOG="$LOG_DIR/$RUN_NAME.log"

echo "[S3] task=$TASK regime=$REGIME N=$N batches/epoch=$BATCHES epochs=$EPOCHS steps≈$((EPOCHS*BATCHES))"
echo "[S3] image=$IMAGE gpu=$GPU ckpt=$OUT"
echo "[S3] log=$LOG"

docker run --rm --ipc=host --gpus "\"device=$GPU\"" \
  -v "$DATA_ROOT":/data \
  -v "$CKPT_ROOT":/out \
  --entrypoint bash "$IMAGE" -lc "
set -e
mkdir -p /app/RoboTwin/data/$TASK
ln -sfn /data/data/$TASK/$REGIME/aloha-agilex_$REGIME /app/RoboTwin/data/$TASK/$REGIME
cd /app/RoboTwin/policy/ACT
echo '[S3] process_data'
conda run -n robotwin python process_data.py $TASK $REGIME $N >/tmp/process.log 2>&1
tail -2 /tmp/process.log
echo '[S3] train'
conda run -n robotwin python imitate_episodes.py \
  --task_name sim-$TASK-$REGIME-$N \
  --ckpt_dir /out/$RUN_NAME \
  --policy_class ACT --kl_weight 10 --chunk_size 50 \
  --hidden_dim 512 --batch_size $BATCH --dim_feedforward 3200 \
  --num_epochs $EPOCHS --lr 1e-5 --save_freq $SAVE_FREQ \
  --state_dim 14 --seed $SEED 2>&1 | tail -6
test -f /out/$RUN_NAME/policy_last.ckpt
test -f /out/$RUN_NAME/dataset_stats.pkl
ls -lh /out/$RUN_NAME/policy_last.ckpt /out/$RUN_NAME/dataset_stats.pkl
" 2>&1 | tee "$LOG"

python3 - "$OUT" "$TASK" "$REGIME" "$N" "$EPOCHS" "$SEED" <<'PY'
import json, os, sys, pathlib
out, task, regime, n, epochs, seed = sys.argv[1:7]
man = {"task": task, "regime": regime, "episodes": int(n), "epochs": int(epochs),
       "seed": int(seed), "ckpt": str(pathlib.Path(out) / "policy_last.ckpt"),
       "has_stats": (pathlib.Path(out) / "dataset_stats.pkl").exists()}
(pathlib.Path(out) / "run.json").write_text(json.dumps(man, ensure_ascii=False, indent=2))
print("[S3] manifest ->", pathlib.Path(out) / "run.json")
PY

[ "$DRY" = "1" ] && echo "[S3] dry-run 完成（epochs=$EPOCHS），产物仅供链路验证"
echo "[S3] OK $RUN_NAME"
