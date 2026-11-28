#!/usr/bin/env bash
# R01 S3：单 task × 单口径的 DP 训练（可重复，可干跑）
#
# 用法：
#   bash scripts/r01/s3_train_dp.sh --task grab_roller --regime clean_50
#   bash scripts/r01/s3_train_dp.sh --task grab_roller --regime clean_50 --epochs 1 --dry-run
#
# 与 ACT 的差异（2026-11-28 实测）：
#   1. 依赖 wandb（模块级 import）→ vla-robotwin-train-dp 构建期装
#   2. ckpt 只在 `(epoch+1) % checkpoint_every == 0` 时保存；没有 end-of-run 保存
#      → 取 checkpoint_every = num_epochs，保证最后一步落盘
#   3. 保存名是 `checkpoints/<zarr-stem>-<seed>/<epoch>.ckpt`，serve 期望
#      `<task>-<setting>-<num>-<seed>/<num>.ckpt` → 训练后复制成 serve 布局
#   4. 容器仍需 --ipc=host
set -euo pipefail

TASK=""; REGIME="clean_50"; GPU=0; STEPS=40000; SEED=0; EPOCHS=""; DRY=0
DATA_ROOT=/data/robotwin-train
CKPT_ROOT=/root/r01/r01-ckpt
IMAGE=vla-robotwin-train-dp:dev
BATCH=128

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

# 2026-11-28 实测：50 集 ≈ 29 batch/epoch（batch=128, num_workers=0）
BATCHES=$(( (N * 58 + 99) / 100 ))
[ "$BATCHES" -gt 0 ] || BATCHES=1
if [ -z "$EPOCHS" ]; then
  EPOCHS=$(( (STEPS + BATCHES - 1) / BATCHES ))
fi
RUN_NAME="${TASK}-${REGIME}-dp-s${SEED}"
OUT="$CKPT_ROOT/$RUN_NAME"
SERVE_OUT="$CKPT_ROOT/serve/$TASK-$REGIME-$N-$SEED"
mkdir -p "$OUT" "$CKPT_ROOT/logs"
LOG="$CKPT_ROOT/logs/$RUN_NAME.log"

echo "[S3-DP] task=$TASK regime=$REGIME N=$N batch/epoch≈$BATCHES epochs=$EPOCHS steps≈$((EPOCHS*BATCHES))"
echo "[S3-DP] image=$IMAGE gpu=$GPU ckpt=$OUT"

docker run --rm --ipc=host --gpus "\"device=$GPU\"" \
  -v "$DATA_ROOT":/data \
  -v "$CKPT_ROOT":/out \
  -e WANDB_MODE=offline \
  --entrypoint bash "$IMAGE" -lc "
set -e
mkdir -p /app/RoboTwin/data/$TASK
ln -sfn /data/data/$TASK/$REGIME/aloha-agilex_$REGIME /app/RoboTwin/data/$TASK/$REGIME
cd /app/RoboTwin/policy/DP
echo '[S3-DP] process_data'
conda run -n robotwin python process_data.py $TASK $REGIME $N >/tmp/process.log 2>&1
tail -2 /tmp/process.log
echo '[S3-DP] train'
conda run -n robotwin python train.py --config-name=robot_dp_14.yaml \
  task.name=$TASK task.dataset.zarr_path=data/$TASK-$REGIME-$N.zarr \
  training.debug=False training.seed=$SEED training.device=cuda:0 \
  exp_name=$RUN_NAME logging.mode=offline setting=$REGIME \
  expert_data_num=$N head_camera_type=D435 \
  training.num_epochs=$EPOCHS training.checkpoint_every=$EPOCHS \
  hydra.run.dir=/out/$RUN_NAME 2>&1 \
  | grep --line-buffered -E 'Training epoch|Validation|Error|Traceback|out of memory'
# save_checkpoint 的 path 是相对 CWD（policy/DP），不在 hydra.run.dir 下
CK=\$(find /app/RoboTwin/policy/DP/checkpoints -name '*.ckpt' | tail -1)
[ -n \"\$CK\" ] || { echo '没找到 DP ckpt'; exit 4; }
mkdir -p /out/serve/$TASK-$REGIME-$N-$SEED
cp \"\$CK\" /out/serve/$TASK-$REGIME-$N-$SEED/$N.ckpt
ls -lh /out/serve/$TASK-$REGIME-$N-$SEED/$N.ckpt
" 2>&1 | tee "$LOG"

python3 - "$SERVE_OUT/$N.ckpt" "$TASK" "$REGIME" "$N" "$EPOCHS" "$SEED" <<'PY'
import json, os, sys, pathlib
ck, task, regime, n, epochs, seed = sys.argv[1:7]
man = {"task": task, "regime": regime, "episodes": int(n), "epochs": int(epochs),
       "seed": int(seed), "ckpt": ck, "exists": os.path.exists(ck)}
pathlib.Path(ck).parent.mkdir(parents=True, exist_ok=True)
pathlib.Path(ck).parent.joinpath("run.json").write_text(json.dumps(man, ensure_ascii=False, indent=2))
print("[S3-DP] manifest ->", pathlib.Path(ck).parent / "run.json")
PY

[ "$DRY" = "1" ] && echo "[S3-DP] dry-run 完成（epochs=$EPOCHS）"
echo "[S3-DP] OK $RUN_NAME"
