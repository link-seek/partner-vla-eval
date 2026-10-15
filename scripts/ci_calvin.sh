#!/bin/bash
# CALVIN smoke: host 编排 serve(DB-CogACT) + run(SWR calvin 镜像当 client)。
# serve 用 configs/serve-cogact-calvin.yaml（Dexmal/calvin-db-cogact 单仓，chunk 7）。
# 5 sequences，只验链路。
set -e
cd "$(dirname "$0")/.."
WORK="$PWD"
SERVE_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-serve-cogact:0.7.0"
VERIFY_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-verify:0.1"
CALVIN_IMAGE="${CALVIN_IMAGE:-swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-calvin:0.8.0}"
mkdir -p results

echo "[0/4] workspace 属主修复 + 缓存目录预建"
docker run --rm -v "$WORK":/w python:3.12-slim chown -R 1001:1001 /w 2>/dev/null || \
  sudo chown -R "$(id -u):$(id -g)" "$WORK" 2>/dev/null || true
mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" 2>/dev/null || sudo mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" || true
sudo chown -R "$(id -u):$(id -g)" "$WORK/.cache" 2>/dev/null || true

echo "[1/4] 拉镜像（SWR 内网）"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$CALVIN_IMAGE"
docker pull "$SERVE_IMAGE"
docker pull "$VERIFY_IMAGE"

echo "[2/4] 预热 CALVIN 权重（单仓，mirror）"
for i in 1 2 3; do
  if docker run --rm --network host \
    -v "$WORK/.cache/hf":/root/.cache/huggingface \
    -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
    -e HF_TOKEN="${HF_TOKEN:-}" -e HF_HUB_DISABLE_XET=1 \
    "$VERIFY_IMAGE" hf-download download Dexmal/calvin-db-cogact > /tmp/calvin-prewarm.log 2>&1; then
    echo "weights ok"; break
  fi
  tail -n 5 /tmp/calvin-prewarm.log 2>/dev/null || true
  sleep 15
  [ "$i" = "3" ] && exit 1
done

echo "[3/4] 启动 CogACT serve (GPU0, 后台；烘焙镜像 + UV_OFFLINE)"
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
  vla-eval serve -c /work/configs/serve-cogact-calvin.yaml
for i in $(seq 1 120); do
  [ "$(docker inspect -f '{{.State.Running}}' cogact-serve 2>/dev/null)" = "true" ] || { echo "serve 容器退出"; docker logs cogact-serve 2>&1 | tail -n 15; exit 1; }
  if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then echo "serve UP"; break; fi
  [ "$i" = "120" ] && { echo "serve 超时"; docker logs cogact-serve 2>&1 | tail -n 15; exit 1; }
  sleep 10
done

echo "[4/4] 跑 CALVIN smoke (5 sequences)"
set +e
docker run --rm --gpus all --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK/configs":/work/configs:ro \
  -v "$WORK/results":/work/results \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=0 \
  "$CALVIN_IMAGE" \
  run --config /work/configs/run-calvin-smoke.yaml --server-url ws://localhost:8000 --output-dir /work/results/calvin-smoke 2>&1 | tee results/calvin-smoke.log
CODE=${PIPESTATUS[0]}
set -e
docker logs cogact-serve > results/cogact-calvin-serve.log 2>&1 || true
docker rm -f cogact-serve 2>/dev/null || true
ls -lh results/ || true
echo "smoke_exit=$CODE"
exit $CODE
