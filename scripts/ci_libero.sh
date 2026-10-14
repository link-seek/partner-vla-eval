#!/bin/bash
# LIBERO smoke: host 编排 serve(pi05) + run(SWR libero 镜像当 client)。
# serve 用 configs/serve-pi05-libero.yaml，1 task x 1ep，只验链路。
set -e
cd "$(dirname "$0")/.."
WORK="$PWD"
LIBERO_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-libero:0.7.0"
VERIFY_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-verify:0.1"
mkdir -p results

echo "[0/4] workspace 属主修复 + 缓存目录预建"
docker run --rm -v "$WORK":/w python:3.12-slim chown -R 1001:1001 /w 2>/dev/null || \
  sudo chown -R "$(id -u):$(id -g)" "$WORK" 2>/dev/null || true
mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" 2>/dev/null || sudo mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" || true
sudo chown -R "$(id -u):$(id -g)" "$WORK/.cache" 2>/dev/null || true

echo "[1/4] 拉镜像（SWR 内网）"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$LIBERO_IMAGE"
docker pull "$VERIFY_IMAGE"

echo "[2/4] 预热 pi05 权重（V100 盘已有缓存则秒过）"
for i in 1 2 3; do
  if docker run --rm --network host \
    -v "$WORK/.cache/hf":/root/.cache/huggingface \
    -e HF_ENDPOINT=https://hf-mirror.com \
    "$VERIFY_IMAGE" hf-download download lerobot/pi05_libero_finetuned > /tmp/pi05-prewarm.log 2>&1; then break; fi
  echo "checkpoint 预热失败, 重试 $i..."; sleep 15
  [ "$i" = "3" ] && exit 1
done

echo "[3/4] 启动 pi05 serve (GPU0, 后台)"
docker rm -f pi05-serve 2>/dev/null || true
docker run -d --name pi05-serve --gpus '"device=0"' --network host \
  -v "$WORK":/work -w /work/harness \
  -v "$WORK/.cache/uv":/root/.cache/uv \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=0 -e COMPILE_MODEL=false \
  -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
  -e HF_TOKEN="${HF_TOKEN:-}" \
  "$VERIFY_IMAGE" \
  vla-eval serve -c /work/configs/serve-pi05-libero.yaml
for i in $(seq 1 120); do
  [ "$(docker inspect -f '{{.State.Running}}' pi05-serve 2>/dev/null)" = "true" ] || { echo "serve 容器退出"; docker logs pi05-serve 2>&1 | tail -n 15; exit 1; }
  if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then echo "serve UP"; break; fi
  [ "$i" = "120" ] && { echo "serve 超时"; docker logs pi05-serve 2>&1 | tail -n 15; exit 1; }
  sleep 10
done

echo "[4/4] 跑 LIBERO smoke (spatial 1 task x 1ep)"
set +e
docker run --rm --gpus all --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=0 \
  "$LIBERO_IMAGE" \
  run --config /work/configs/run-libero-smoke.yaml --server-url ws://localhost:8000 --output-dir /work/results/libero-smoke 2>&1 | tee results/libero-smoke.log
CODE=${PIPESTATUS[0]}
set -e
docker logs pi05-serve > results/pi05-serve.log 2>&1 || true
docker rm -f pi05-serve 2>/dev/null || true
ls -lh results/ || true
echo "smoke_exit=$CODE"
exit $CODE
