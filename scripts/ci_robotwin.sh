#!/bin/bash
# RobotWin smoke: host 编排 serve(DB-CogACT 双臂, GPU0) + run(SWR robotwin 镜像当 client)。
# serve 用自研 configs/serve-robotwin.yaml（上游 robotwin2.yaml 口径：chunk 16 + 三相机）。
# V100 适配（同 molmo smoke 教训）：
# - xvla.py header 打补丁：torch==2.6.0（cu126 源）+ requires-python 放宽；
# - uv 装包走 PIP_INDEX_URL=cu126 + EXTRA=pypi。
set -e
cd "$(dirname "$0")/.."
WORK="$PWD"
HARNESS_REF="${HARNESS_REF:-v0.7.0}"
ROBOTWIN_IMAGE="swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:0.7.0"
VERIFY_IMAGE="pi0-molmo-verify:0.1"
mkdir -p results

echo "[0/5] workspace 属主修复"
docker run --rm -v "$WORK":/w python:3.12-slim chown -R 1001:1001 /w 2>/dev/null || \
  sudo chown -R "$(id -u):$(id -g)" "$WORK" 2>/dev/null || true
mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" 2>/dev/null || sudo mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" || true
sudo chown -R "$(id -u):$(id -g)" "$WORK/.cache" 2>/dev/null || true

echo "[1/5] harness 源码 (host 侧 clone)"
LEROBOT_URL="https://github.com/huggingface/lerobot.git"
[ -n "${GITHUB_TOKEN:-}" ] && LEROBOT_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/huggingface/lerobot.git"
if [ ! -f harness/pyproject.toml ]; then
  rm -rf harness
  CLONE_URL="https://github.com/allenai/vla-evaluation-harness.git"
  [ -n "${GITHUB_TOKEN:-}" ] && CLONE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/allenai/vla-evaluation-harness.git"
  for i in 1 2 3 4 5; do
    if git clone --depth 1 --branch "$HARNESS_REF" "$CLONE_URL" harness 2>&1 | tail -n 1; then break; fi
    echo "clone 失败, 重试 $i..."; rm -rf harness; sleep 20
    [ "$i" = "5" ] && exit 128
  done
else
  echo "harness 已存在, 跳过 clone"
fi

echo "[1b/5] xvla header 打补丁 (torch 钉 2.6.0/cu126 + python 放宽，同 molmo 教训)"
XVLA=harness/src/vla_eval/model_servers/xvla.py
if ! grep -q '"torch==2.6.0"' "$XVLA"; then
  sed -i 's|"torch>=2.2"|"torch==2.6.0"|' "$XVLA"
fi
if ! grep -q 'requires-python = ">=3.11"' "$XVLA"; then
  sed -i 's|requires-python = "~=3.11"|requires-python = ">=3.11"|' "$XVLA"
fi
grep -nE '"torch==|requires-python' "$XVLA" | head -n 5

echo "[2/5] robotwin 镜像 (SWR 内网拉取)"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$ROBOTWIN_IMAGE"
docker images | grep -E 'robotwin' || true

echo "[3/5] 构建 verify 镜像 (host 缓存)"
docker build -f docker/Dockerfile.verify -t "$VERIFY_IMAGE" .

echo "[4/5] 预热 X-VLA 权重 (单仓共享权重, mirror, 带重试)"
for i in 1 2 3; do
  if SNAP=$(docker run --rm --network host \
    -v "$WORK/.cache/hf":/root/.cache/huggingface \
    -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
    -e HF_TOKEN="${HF_TOKEN:-}" -e HF_HUB_DISABLE_XET=1 \
    "$VERIFY_IMAGE" python -c "from huggingface_hub import snapshot_download; print(snapshot_download('2toINF/X-VLA-WidowX', max_workers=4))" 2>&1 | tee /tmp/prewarm.log | tail -n 1) && [ -n "$SNAP" ]; then
    echo "snapshot: $SNAP"; break
  fi
  echo "prewarm 输出尾:"; tail -n 5 /tmp/prewarm.log 2>/dev/null || true
  echo "checkpoint 预热失败, 重试 $i..."; sleep 15
  [ "$i" = "3" ] && exit 1
done
echo "[4a/5] 生成 serve 配置 (X-VLA 单仓权重，直接指 snapshot 本地路径，免重复下载)"
sed "s|model_path: .*|model_path: $SNAP|" "$WORK/configs/serve-robotwin.yaml" > "$WORK/configs/serve-robotwin-local.yaml"
grep -n "model_path" "$WORK/configs/serve-robotwin-local.yaml"

echo "[4b/5] 启动 X-VLA serve (GPU0, 后台)"
docker rm -f xvla-serve 2>/dev/null || true
start_serve() {
docker run -d --name xvla-serve --gpus '"device=0"' --network host \
  -v "$WORK":/work -w /work/harness \
  -v "$WORK/.cache/uv":/root/.cache/uv \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e PIP_INDEX_URL=https://download.pytorch.org/whl/cu126 \
  -e PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
  -e HF_HUB_DISABLE_XET=1 \
  -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
  -e HF_TOKEN="${HF_TOKEN:-}" \
  "$VERIFY_IMAGE" \
  vla-eval serve -c /work/configs/serve-robotwin-local.yaml
}
wait_serve() {
  for i in $(seq 1 120); do
    if [ "$(docker inspect -f '{{.State.Running}}' xvla-serve 2>/dev/null)" != "true" ]; then return 1; fi
    if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then echo "serve UP"; return 0; fi
    if [ "$i" = "120" ]; then return 2; fi
    sleep 10
  done
}
SERVE_OK=0
for attempt in 1 2 3; do
  echo "serve 启动尝试 $attempt/3"
  docker rm -f xvla-serve 2>/dev/null || true
  start_serve
  sleep 15
  if wait_serve; then SERVE_OK=1; break; fi
  echo "serve 未起来 (尝试 $attempt), 尾日志:"; docker logs xvla-serve 2>&1 | tail -n 15
  docker rm -f xvla-serve 2>/dev/null || true
  sleep 10
done
[ "$SERVE_OK" = "1" ] || { echo "serve 3次都起不来"; exit 1; }

echo "[5/5] 跑 RobotWin smoke (grab_roller 1ep, 用 robotwin 镜像当 client)"
set +e
docker run --rm --gpus all --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK":/work -w /work \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=0 \
  "$ROBOTWIN_IMAGE" \
  run --config /work/configs/run-robotwin-smoke.yaml 2>&1 | tee results/robotwin-smoke.log
CODE=${PIPESTATUS[0]}
set -e
echo "[5b/5] 收 serve 日志"
docker logs xvla-serve > results/xvla-serve.log 2>&1 || true
docker rm -f xvla-serve 2>/dev/null || true
ls -lh results/ || true
echo "smoke_exit=$CODE"
exit $CODE
