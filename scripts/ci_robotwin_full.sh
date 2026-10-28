#!/bin/bash
# RobotWin 全量（分块）：host 编排 serve(DB-CogACT 关节口径) + run_sharded.sh 多分片。
# X-VLA 是 EE 口径，benchmark 只要关节，已记债 park（serve-robotwin.yaml 留档）。
# 输入（环境变量，workflow 透传）：
#   RW_TASKS     逗号分隔 task 名（默认首块 5 个）
#   RW_EPISODES  每 task 集数（默认 50；验证用小值）
#   RW_SHARDS    分片数（默认 8；EE 默认 4，见下）
#   RW_VIDEO     1=录像，默认 0（全量关录像省时间/空间）
# 输出：results/robotwin-<chunk>/aggregate.json + recording sqlite，OBS 按块累积。
set -e
cd "$(dirname "$0")/.."
WORK="$PWD"
source "$WORK/scripts/lib/common.sh"
HARNESS_REF="${HARNESS_REF:-v0.8.0}"
ROBOTWIN_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:${RW_BENCH_TAG:-0.8.0}"
VERIFY_IMAGE="pi0-molmo-verify:0.1"
RW_TASKS="${RW_TASKS:-grab_roller,adjust_bottle,click_bell,handover_block,stack_blocks_two}"
RW_EPISODES="${RW_EPISODES:-50}"
# EE 默认 4 分片：fast_init=false 全量 planner + SAPIEN 抢显存，8 分片 OOM（10-27 实测 3/10 env_start）。
# qpos 保持 8（已验证吞吐）。
if [ -z "${RW_SHARDS:-}" ]; then
  if [ "${RW_ACTION_TYPE:-}" = "ee" ]; then RW_SHARDS=4; else RW_SHARDS=8; fi
fi
RW_VIDEO="${RW_VIDEO:-0}"
CHUNK_TAG=$(echo "$RW_TASKS" | tr ',' '+' | cut -c1-60)
OUTDIR="results/robotwin-${CHUNK_TAG}-x${RW_EPISODES}"
results_fresh  # 全清（smoke 同口径；10-23 教训：只清自家 OUTDIR 会把上轮 libero 残留打进 artifact）
# 注意：mkdir OUTDIR 必须在 results_root_wipe 之后（wipe 清 results/* 会连 OUTDIR 一起扬掉）

echo "[0/6] workspace 属主修复 + 缓存目录预建"
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
results_root_wipe "$ROBOTWIN_IMAGE"
mkdir -p "$OUTDIR"  # wipe 之后建（见上注释）

echo "[4/6] 预热权重（默认 DB-CogACT 按 task 子目录；RW_PREWARM=none 跳过，如 X-VLA 由 serve 镜像自理）"
# 资产初始化（仅外置资产）：update_embodiment_config_path.py 把 _tmp 模板渲染成真正的
# curobo_*.yml（写进挂载目录，幂等）。entrypoint 被 outer 的 --entrypoint bash 绕过，
# 这里显式跑一次（rw 挂载）；主跑保持 :ro。
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

if [ -n "${ASSETS_MOUNT:-}" ]; then
  echo "[4b/6] 资产初始化（_tmp 模板→真正的 curobo_*.yml，rw 跑一次，幂等）"
  docker run --rm --entrypoint bash \
    -v "${ASSETS_MOUNT%:ro}:rw" \
    "$ROBOTWIN_IMAGE" \
    -c "cd /app/RoboTwin && conda run --no-capture-output -n robotwin python script/update_embodiment_config_path.py" \
    || { echo "assets init FAILED"; exit 1; }
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
# 资产挂载通道（10-26 定稿，以实测为准）：
# - eval 跑在 harness 起的 sibling 容器里（与外层隔离；铁证：outer 挂了资产 eval 照样 FileNotFound）。
# - RW_VOLUMES（yaml docker.volumes）：唯一有效通道（sibling 挂载）。EE/planner/curobo 必需。
# - ASSETS_MOUNT（outer -v）：只进外层（entrypoint 跑 config-path 用）；对 eval 无效，但无害、保留。
# - 相对路径 assets/...（相对 CWD=/workspace）：靠镜像内 /workspace/assets 软链解析。
# - place_empty_cup 能跑是因为它不读外部资产（无 clutter、无 planner）；grab_roller 两样都要。
MOUNT_FLAGS=()
if [ -n "${ASSETS_MOUNT:-}" ]; then
  IFS=';' read -ra VLIST <<< "$ASSETS_MOUNT"
  for v in "${VLIST[@]}"; do
    [ -n "$v" ] && MOUNT_FLAGS+=(-v "$v")
  done
fi
# 追踪仓拉取（议题 H）：run_sharded 与 P2 补丁一律从 fork 按 REF 取，本仓不 vendoring
# P2/分片脚本：烘在统一镜像 /opt/patches（构建时从追踪仓拉；V100 出境不认 raw 域名，运行时现拉必死）。
# 统一镜像 entrypoint 按 STATE_PATCH 环境变量激活补丁；stock 镜像无此机制（4→1 后 stock 退役）。
if [ "${RW_STATE_PATCH:-}" = "robotwin" ]; then
  echo "state-patch: robotwin（镜像内激活）"
fi
# 通用外层挂载（P2 补丁等）：RW_EXTRA_MOUNTS 形如 "host:container:ro;..."，与资产挂载同通道
if [ -n "${RW_EXTRA_MOUNTS:-}" ]; then
  IFS=';' read -ra VLIST <<< "$RW_EXTRA_MOUNTS"
  for v in "${VLIST[@]}"; do
    [ -n "$v" ] && MOUNT_FLAGS+=(-v "$v")
  done
fi
if [ "${RW_FAST_INIT:-true}" = "false" ] && [ -z "${RW_VOLUMES:-}" ] && [ -z "${ASSETS_MOUNT:-}" ]; then
  echo "REFUSE: fast_init=false 要走 planner，必须给资产挂载（RW_VOLUMES 或 ASSETS_MOUNT 至少一个）" >&2
  exit 1
fi
echo "ASSETS_MOUNT=${ASSETS_MOUNT:-<未用outer挂载>}"
echo "outer -v flags: ${MOUNT_FLAGS[*]:-<无>}"
docker run --rm --gpus all --network host --entrypoint bash \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  "${MOUNT_FLAGS[@]}" \
  -e CUDA_VISIBLE_DEVICES=1 \
  -e STATE_PATCH="${RW_STATE_PATCH:-}" \
  "$ROBOTWIN_IMAGE" \
  -c "conda run --no-capture-output -n robotwin bash /opt/patches/run_sharded.sh -c /work/configs/run-robotwin-chunk.yaml -n $RW_SHARDS -o /work/$OUTDIR $VIDEO_FLAG" 2>&1 | tee "$OUTDIR/shard.log"
CODE=${PIPESTATUS[0]}
set -e
docker logs cogact-serve > "$OUTDIR/cogact-serve.log" 2>&1 || true
docker rm -f cogact-serve 2>/dev/null || true
ls -lh "$OUTDIR" || true
echo "chunk_exit=$CODE"
exit $CODE
