#!/bin/bash
# RW_VIDEO=1 时录像（诊断用，默认关）。
# RobotWin smoke: host 编排 serve(DB-CogACT 双臂, GPU0) + run(SWR robotwin 镜像当 client)。
# serve 用 SWR 烘焙镜像（与全量同口径，UV_OFFLINE 零下载）；host 侧 clone 已删（V100 出境限速）。
# V100 适配（历史记录，現已烘进镜像）：
# - torch==2.6.0 cu126 + transformers 4.46.3 + fp16（见 serve-cogact Dockerfile）。
set -e
cd "$(dirname "$0")/.."
WORK="$PWD"
ROBOTWIN_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:${RW_BENCH_TAG:-0.8.0-ee-slim}"
ASSETS_MOUNT="${ASSETS_MOUNT:-/data/robotwin-assets/c3ddfa8:/app/RoboTwin/assets:ro}"
VERIFY_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-verify:0.1"
SERVE_IMAGE="${SERVE_IMAGE:-swr.cn-north-4.myhuaweicloud.com/link-seek/vla-serve-cogact:0.8.0}"
source "$WORK/scripts/lib/common.sh"
results_fresh
workspace_fix "0/5"

# serve 走 SWR 烘焙镜像（与全量同口径，UV_OFFLINE 零下载）；
# 历史 host 侧 clone（harness/dexbotic + sed）已删：V100 出境限速下现场下源码必挂。

echo "[2/5] bench + serve 镜像 (SWR 内网拉取)"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$ROBOTWIN_IMAGE"
docker pull "$SERVE_IMAGE"
docker images | grep -E 'robotwin|serve-cogact' || true
results_root_wipe "$ROBOTWIN_IMAGE"

echo "[3/5] verify 镜像 (SWR 拉取，与 libero/calvin 同口径，不本地构建)"
docker pull "$VERIFY_IMAGE"

echo "[4/5] 预热 DB-CogACT 权重 (grab_roller 头, mirror, 带重试)"
for i in 1 2 3; do
  if docker run --rm --network host \
    -v "$WORK/.cache/hf":/root/.cache/huggingface \
    -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
    -e HF_TOKEN="${HF_TOKEN:-}" -e HF_HUB_DISABLE_XET=1 \
    "$VERIFY_IMAGE" hf-download download Dexmal/robotwin-db-cogact --include "grab_roller/*" > /tmp/prewarm.log 2>&1; then
    SNAP_HOST=$(ls -dt "$WORK/.cache/hf/hub/models--Dexmal--robotwin-db-cogact/snapshots/"*/ 2>/dev/null | head -n 1)
    if [ -n "$SNAP_HOST" ] && [ -d "${SNAP_HOST}grab_roller" ]; then
      SNAP="/root/.cache/huggingface/hub/models--Dexmal--robotwin-db-cogact/snapshots/$(basename "$SNAP_HOST")"
      echo "snapshot: $SNAP"; break
    fi
    echo "snapshot 目录异常"; ls "$WORK/.cache/hf/hub/models--Dexmal--robotwin-db-cogact/snapshots/" 2>/dev/null || true
  fi
  echo "prewarm 输出尾:"; tail -n 5 /tmp/prewarm.log 2>/dev/null || true
  echo "checkpoint 预热失败, 重试 $i..."; sleep 15
  [ "$i" = "3" ] && exit 1
done
echo "[4a/5] 生成本地路径 serve 配置 (from_pretrained 不认三段式 repo/subdir，只能本地路径)"
sed "s|model_path: .*|model_path: $SNAP/grab_roller|" "$WORK/configs/serve-robotwin-cogact.yaml" > "$WORK/configs/serve-robotwin-local.yaml"
grep -n "model_path" "$WORK/configs/serve-robotwin-local.yaml"

echo "[4b/5] 启动 DB-CogACT serve (GPU0, 后台)"
docker rm -f cogact-serve 2>/dev/null || true
start_serve() {
docker run -d --name cogact-serve --gpus '"device=0"' --network host \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -w /work/harness \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e UV_OFFLINE=1 \
  -e HF_HUB_DISABLE_XET=1 \
  -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
  -e HF_TOKEN="${HF_TOKEN:-}" \
  "$SERVE_IMAGE" \
  vla-eval serve -c /work/configs/serve-robotwin-local.yaml
}
wait_serve() {
  for i in $(seq 1 120); do
    if [ "$(docker inspect -f '{{.State.Running}}' cogact-serve 2>/dev/null)" != "true" ]; then return 1; fi
    if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then echo "serve UP"; return 0; fi
    if [ "$i" = "120" ]; then return 2; fi
    sleep 10
  done
}
SERVE_OK=0
for attempt in 1 2 3; do
  echo "serve 启动尝试 $attempt/3"
  docker rm -f cogact-serve 2>/dev/null || true
  start_serve
  sleep 15
  if wait_serve; then SERVE_OK=1; break; fi
  echo "serve 未起来 (尝试 $attempt), exit=$(docker inspect -f '{{.State.ExitCode}}' cogact-serve 2>/dev/null), 尾日志:"; docker logs cogact-serve 2>&1 | tail -n 15; docker logs cogact-serve 2>&1 | head -n 80 > results/serve-debug-attempt$attempt.log || true
  docker rm -f cogact-serve 2>/dev/null || true
  sleep 10
done
[ "$SERVE_OK" = "1" ] || { echo "serve 3次都起不来"; exit 1; }

echo "[5/5] 跑 RobotWin smoke (grab_roller 1ep, 用 robotwin 镜像当 client)"
set +e
docker run --rm --gpus all --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK":/work -w /work \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  ${ASSETS_MOUNT:+-v "$ASSETS_MOUNT"} \
  -e CUDA_VISIBLE_DEVICES=0 \
  "$ROBOTWIN_IMAGE" \
  run --config /work/configs/run-robotwin-smoke.yaml ${RW_VIDEO:+--record-video} 2>&1 | tee results/robotwin-smoke.log
CODE=${PIPESTATUS[0]}
set -e
echo "[5b/5] 收 serve 日志"
docker logs cogact-serve > results/cogact-serve.log 2>&1 || true
docker rm -f cogact-serve 2>/dev/null || true
ls -lh results/ || true
echo "smoke_exit=$CODE"
exit $CODE
