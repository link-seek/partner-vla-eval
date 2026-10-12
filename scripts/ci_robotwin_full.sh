#!/bin/bash
# RobotWin 全量（分块）：host 编排 serve(DB-CogACT 关节口径) + run_sharded.sh 多分片。
# X-VLA 是 EE 口径，benchmark 只要关节，已记债 park（serve-robotwin.yaml 留档）。
# 输入（环境变量，workflow 透传）：
#   RW_TASKS     逗号分隔 task 名（默认首块 5 个）
#   RW_EPISODES  每 task 集数（默认 50；验证用小值）
#   RW_SHARDS    分片数（默认 8）
#   RW_VIDEO     1=录像，默认 0（全量关录像省时间/空间）
# 输出：results/robotwin-<chunk>/aggregate.json + recording sqlite，OBS 按块累积。
set -e
cd "$(dirname "$0")/.."
WORK="$PWD"
HARNESS_REF="${HARNESS_REF:-v0.7.0}"
ROBOTWIN_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:0.7.0"
VERIFY_IMAGE="pi0-molmo-verify:0.1"
RW_TASKS="${RW_TASKS:-grab_roller,adjust_bottle,click_bell,handover_block,stack_blocks_two}"
RW_EPISODES="${RW_EPISODES:-50}"
RW_SHARDS="${RW_SHARDS:-8}"
RW_VIDEO="${RW_VIDEO:-0}"
CHUNK_TAG=$(echo "$RW_TASKS" | tr ',' '+' | cut -c1-60)
OUTDIR="results/robotwin-${CHUNK_TAG}-x${RW_EPISODES}"
mkdir -p "$OUTDIR"

echo "[0/6] workspace 属主修复 + 缓存目录预建"
docker run --rm -v "$WORK":/w python:3.12-slim chown -R 1001:1001 /w 2>/dev/null || \
  sudo chown -R "$(id -u):$(id -g)" "$WORK" 2>/dev/null || true
mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" 2>/dev/null || sudo mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" || true
sudo chown -R "$(id -u):$(id -g)" "$WORK/.cache" 2>/dev/null || true

SERVE_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-serve-cogact:0.7.0"
VERIFY_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-verify:0.1"

echo "[1/6] harness 代码已烘进 serve 镜像，无 clone（V100 离线要求）"

echo "[2/6] 生成本块 run 配置（每 task 一个 entry）"
GEN="$WORK/configs/run-robotwin-chunk.yaml"
{
echo "# 自动生成：chunk [$RW_TASKS] x $RW_EPISODES"
echo "server:"
echo "  url: \"ws://localhost:8000\""
echo "  timeout: 600.0"
echo ""
echo "docker:"
echo "  image: $ROBOTWIN_IMAGE"
echo "  user: host"
echo ""
echo "output_dir: \"./$OUTDIR\""
echo ""
echo "benchmarks:"
IFS=',' read -ra TLIST <<< "$RW_TASKS"
for t in "${TLIST[@]}"; do
echo "  - benchmark: \"vla_eval.benchmarks.robotwin.benchmark:RoboTwinBenchmark\""
echo "    name: $t"
echo "    episodes_per_task: 1"
echo "    params:"
echo "      task_name: $t"
echo "      task_config: demo_clean"
echo "      seed: 0"
echo "      instruction_type: seen"
echo "      test_num: $RW_EPISODES"
echo "      skip_expert_check: false"
echo "    action_dim: 14"
done
} > "$GEN"
grep -c "task_name:" "$GEN"

echo "[3/6] 拉镜像（SWR 内网：benchmark + serve 烘焙版，不本地构建）"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$ROBOTWIN_IMAGE"
docker pull "$SERVE_IMAGE"
docker pull "$VERIFY_IMAGE"

echo "[4/6] 预热 DB-CogACT 权重（按块内 task 子目录）"
# CogACT 一 task 一头：块内 task 必须同属一头，战役按 1 task/轮打。
FIRST_TASK=$(echo "${RW_TASKS:-grab_roller}" | cut -d, -f1)
for i in 1 2 3; do
  # 纯 CLI 预热：huggingface-cli 下载 + ls 定位 snapshot（不写 python）
  INC=()
  IFS=',' read -ra TLIST <<< "${RW_TASKS:-grab_roller}"
  for t in "${TLIST[@]}"; do
    t=$(echo "$t" | tr -d '[:space:]')
    [ -n "$t" ] && INC+=(--include "$t/*")
  done
  if docker run --rm --network host \
    -v "$WORK/.cache/hf":/root/.cache/huggingface \
    -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
    -e HF_TOKEN="${HF_TOKEN:-}" -e HF_HUB_DISABLE_XET=1 \
    "$VERIFY_IMAGE" hf-download download Dexmal/robotwin-db-cogact "${INC[@]}" > /tmp/prewarm.log 2>&1; then
    # snapshot 即缓存下最新子目录（宿主/容器同挂载，路径对应）
    SNAP_HOST=$(ls -dt "$WORK/.cache/hf/hub/models--Dexmal--robotwin-db-cogact/snapshots/"*/ 2>/dev/null | head -n 1)
    if [ -n "$SNAP_HOST" ] && [ -d "$SNAP_HOST$FIRST_TASK" ]; then
      SNAP="/root/.cache/huggingface/hub/models--Dexmal--robotwin-db-cogact/snapshots/$(basename "$SNAP_HOST")"
      echo "snapshot: $SNAP"; break
    fi
    echo "snapshot 目录异常"; ls "$WORK/.cache/hf/hub/models--Dexmal--robotwin-db-cogact/snapshots/" 2>/dev/null || true
  fi
  tail -n 5 /tmp/prewarm.log 2>/dev/null || true
  sleep 15
  [ "$i" = "3" ] && exit 1
done
# from_pretrained 不认 repo/subdir，用本地子目录绝对路径。
sed "s|model_path: .*|model_path: $SNAP/$FIRST_TASK|" "$WORK/configs/serve-robotwin-cogact.yaml" > "$WORK/configs/serve-robotwin-local.yaml"
grep -n "model_path" "$WORK/configs/serve-robotwin-local.yaml"

echo "[5/6] 启动 DB-CogACT serve (GPU0, 后台；烘焙镜像 + UV_OFFLINE，零下载)"
docker rm -f cogact-serve 2>/dev/null || true
docker run -d --name cogact-serve --gpus '"device=0"' --network host \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -w /work/harness \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e UV_OFFLINE=1 \
  -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
  -e HF_TOKEN="${HF_TOKEN:-}" -e HF_HUB_DISABLE_XET=1 \
  "$SERVE_IMAGE" \
  vla-eval serve -c /work/configs/serve-robotwin-local.yaml
for i in $(seq 1 120); do
  [ "$(docker inspect -f '{{.State.Running}}' cogact-serve 2>/dev/null)" = "true" ] || { echo "serve 容器退出"; docker logs cogact-serve 2>&1 | tail -n 15; exit 1; }
  if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then echo "serve UP"; break; fi
  [ "$i" = "120" ] && { echo "serve 超时"; docker logs cogact-serve 2>&1 | tail -n 15; exit 1; }
  sleep 10
done

echo "[6/6] run_sharded 全块跑（分片 $RW_SHARDS，录像=$RW_VIDEO，gpu 渲染）"
VIDEO_FLAG="--no-record-video"
[ "$RW_VIDEO" = "1" ] && VIDEO_FLAG="--record-video"
set +e
# run_sharded.sh vendoring 在本仓（scripts/upstream，0.7.0 镜像里缺失）
# 分片跑在卡1：serve 独占卡0，8 分片同卡 SAPIEN 会 hang（watchdog 全杀，见 run 38186912836）。
# V100 双32G，卡1空闲给渲染。
docker run --rm --gpus all --network host --entrypoint bash \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$WORK/scripts/upstream":/opt/harness-scripts:ro \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=1 \
  "$ROBOTWIN_IMAGE" \
  -c "conda run --no-capture-output -n robotwin bash /opt/harness-scripts/run_sharded.sh -c /work/configs/run-robotwin-chunk.yaml -n $RW_SHARDS -o /work/$OUTDIR $VIDEO_FLAG" 2>&1 | tee "$OUTDIR/shard.log"
CODE=${PIPESTATUS[0]}
set -e
docker logs cogact-serve > "$OUTDIR/cogact-serve.log" 2>&1 || true
docker rm -f cogact-serve 2>/dev/null || true
ls -lh "$OUTDIR" || true
echo "chunk_exit=$CODE"
exit $CODE
