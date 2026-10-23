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
HARNESS_REF="${HARNESS_REF:-v0.8.0}"
ROBOTWIN_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:${RW_BENCH_TAG:-0.8.0}"
VERIFY_IMAGE="pi0-molmo-verify:0.1"
RW_TASKS="${RW_TASKS:-grab_roller,adjust_bottle,click_bell,handover_block,stack_blocks_two}"
RW_EPISODES="${RW_EPISODES:-50}"
RW_SHARDS="${RW_SHARDS:-8}"
RW_VIDEO="${RW_VIDEO:-0}"
CHUNK_TAG=$(echo "$RW_TASKS" | tr ',' '+' | cut -c1-60)
OUTDIR="results/robotwin-${CHUNK_TAG}-x${RW_EPISODES}"
rm -rf "$OUTDIR"  # 同名块跨 run 累积污染 artifact；OBS 已留档
mkdir -p "$OUTDIR"

echo "[0/6] workspace 属主修复 + 缓存目录预建"
source "$WORK/scripts/lib/common.sh"
workspace_fix "0/6"

SERVE_IMAGE="${SERVE_IMAGE:-swr.cn-north-4.myhuaweicloud.com/link-seek/vla-serve-cogact:0.8.0}"
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
if [ -n "${RW_VOLUMES:-}" ]; then
  echo "  volumes:"
  IFS=';' read -ra VLIST <<< "$RW_VOLUMES"
  for v in "${VLIST[@]}"; do
    echo "    - \"$v\""
  done
fi
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
echo "      skip_expert_check: ${RW_SKIP_EXPERT:-true}  # 0.7.0 无 bundled seeds 必须 true；0.8.0 探 false 走自带种子+oracle"
if [ -n "${RW_ACTION_TYPE:-}" ]; then
echo "      action_type: ${RW_ACTION_TYPE}  # 仅 EE 镜像认；stock 镜像未知参数会炸，故缺省不发"
fi
echo "      fast_init: ${RW_FAST_INIT:-true}  # EE 必须 false：fast-path 禁 plan_path，而 EE 靠它做 IK"
echo "    action_dim: 14"
done
} > "$GEN"
grep -c "task_name:" "$GEN"
echo "--- generated docker block ---"
grep -A6 "^docker:" "$GEN" | head -n 10
echo "--- end docker block ---"

echo "[3/6] 拉镜像（SWR 内网：benchmark + serve 烘焙版，不本地构建）"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$ROBOTWIN_IMAGE"
docker pull "$SERVE_IMAGE"
docker pull "$VERIFY_IMAGE"

echo "[4/6] 预热权重（默认 DB-CogACT 按 task 子目录；RW_PREWARM=none 跳过，如 X-VLA 由 serve 镜像自理）"
# CogACT 一 task 一头：块内 task 必须同属一头，战役按 1 task/轮打。
SERVE_YAML="${RW_SERVE_YAML:-serve-robotwin-cogact.yaml}"
if [ "${RW_PREWARM:-cogact}" = "none" ]; then
  echo "prewarm skipped"
else
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
fi
# 非 CogACT 路（RW_PREWARM=none，如 X-VLA）：serve 配置直用 $SERVE_YAML，不生成 local。
if [ "${RW_PREWARM:-cogact}" = "none" ]; then
  cp "$WORK/configs/$SERVE_YAML" "$WORK/configs/serve-robotwin-local.yaml"
fi

echo "[5/6] 启动 serve (GPU${SERVE_CUDA:-0}，后台；烘焙镜像 + UV_OFFLINE，零下载；配置 $SERVE_YAML)"
docker rm -f cogact-serve 2>/dev/null || true
docker run -d --name cogact-serve --gpus "\"device=${SERVE_CUDA:-0}\"" --network host \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -w /work/harness \
  -e CUDA_VISIBLE_DEVICES=${SERVE_CUDA:-0} \
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
# run_sharded.sh 从追踪仓按 REF 拉取（见下方拉取块），0.8.0 镜像未烘 scripts，挂载保留
# 分片跑在卡1：serve 独占卡0，8 分片同卡 SAPIEN 会 hang（watchdog 全杀，见 run 38186912836）。
# V100 双32G，卡1空闲给渲染。
# 资产/代码外置挂载挂在这里（外层容器），不是 yaml 里——分片是容器内本地进程，
# yaml 的 docker.volumes 只对 harness 自己起的 sibling 容器有效（阴性对照已证）。
# ASSETS_MOUNT 形如 /data/robotwin-assets/c3ddfa8:/app/RoboTwin/assets:ro（空=不用）。
MOUNT_FLAGS=()
if [ -n "${ASSETS_MOUNT:-}" ]; then
  IFS=';' read -ra VLIST <<< "$ASSETS_MOUNT"
  for v in "${VLIST[@]}"; do
    [ -n "$v" ] && MOUNT_FLAGS+=(-v "$v")
  done
fi
# 追踪仓拉取（议题 H）：run_sharded 与 P2 补丁一律从 fork 按 REF 取，本仓不 vendoring
_PB=$(grep -E '^harness_patch_base:' "$WORK/docker/versions.yaml" | sed -E 's/.*: *"([^"]+)".*/\1/')
_PR=$(grep -E '^harness_patch_ref:' "$WORK/docker/versions.yaml" | sed -E 's/.*: *"([^"]+)".*/\1/')
_PD="$WORK/.cache/patches/$_PR"
mkdir -p "$_PD"
[ -f "$_PD/run_sharded.sh" ] || curl -fsSL "$_PB/$_PR/scripts/run_sharded.sh" -o "$_PD/run_sharded.sh" || { echo "run_sharded fetch FAILED"; exit 1; }
chmod +x "$_PD/run_sharded.sh"
# P2 状态补丁（RW_STATE_PATCH=robotwin）：同源拉取，按需挂载
if [ "${RW_STATE_PATCH:-}" = "robotwin" ]; then
  [ -f "$_PD/robotwin_benchmark_state.py" ] || curl -fsSL "$_PB/$_PR/src/vla_eval/benchmarks/robotwin/benchmark.py" -o "$_PD/robotwin_benchmark_state.py" || { echo "patch fetch FAILED"; exit 1; }
  MOUNT_FLAGS+=(-v "$_PD/robotwin_benchmark_state.py:/workspace/src/vla_eval/benchmarks/robotwin/benchmark.py:ro")
  echo "state-patch fetched from fork @${_PR:0:8}: robotwin"
fi
# 通用外层挂载（P2 补丁等）：RW_EXTRA_MOUNTS 形如 "host:container:ro;..."，与资产挂载同通道
if [ -n "${RW_EXTRA_MOUNTS:-}" ]; then
  IFS=';' read -ra VLIST <<< "$RW_EXTRA_MOUNTS"
  for v in "${VLIST[@]}"; do
    [ -n "$v" ] && MOUNT_FLAGS+=(-v "$v")
  done
fi
echo "ASSETS_MOUNT=${ASSETS_MOUNT:-<内置>}"
echo "outer -v flags: ${MOUNT_FLAGS[*]:-<无>}"
docker run --rm --gpus all --network host --entrypoint bash \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$_PD/run_sharded.sh:/opt/harness-scripts/run_sharded.sh:ro" \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  "${MOUNT_FLAGS[@]}" \
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
