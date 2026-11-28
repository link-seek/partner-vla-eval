#!/usr/bin/env bash
# R01 S3：ACT 10 个 ckpt 顺序训练（失败即停，已有 ckpt 自动跳过）
# 用法：bash scripts/r01/s3_act_chain.sh [--gpu 0] [--data-root ...] [--ckpt-root ...]
set -euo pipefail

GPU=0
DATA_ROOT=/data/robotwin-train
CKPT_ROOT=/root/r01/r01-ckpt
while [ $# -gt 0 ]; do
  case "$1" in
    --gpu) GPU="$2"; shift 2 ;;
    --data-root) DATA_ROOT="$2"; shift 2 ;;
    --ckpt-root) CKPT_ROOT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
LOG="$CKPT_ROOT/logs/act_chain.log"
mkdir -p "$CKPT_ROOT/logs"
say(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

TASKS="$(python3 "$HERE/../data/bench_config.py" tasks)"
for t in $TASKS; do
  for r in clean_50 randomized_500; do
    OUT="$CKPT_ROOT/$t-$r-s0"
    if [ -f "$OUT/policy_last.ckpt" ]; then say "SKIP ACT $t/$r (exists)"; continue; fi
    say "START ACT $t/$r"
    if ! "$HERE/s3_train_act.sh" --task "$t" --regime "$r" --gpu "$GPU" \
         --data-root "$DATA_ROOT" --ckpt-root "$CKPT_ROOT"; then
      say "FAIL ACT $t/$r"; exit 1
    fi
    say "DONE ACT $t/$r"
  done
done
say "ACT ALL DONE"
