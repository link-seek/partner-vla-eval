#!/bin/bash
# RobotWin smoke: host 编排 serve(DB-CogACT 双臂, GPU0) + run(SWR robotwin 镜像当 client)。
# serve 用自研 configs/serve-robotwin.yaml（上游 robotwin2.yaml 口径：chunk 16 + 三相机）。
# V100 适配（同 molmo smoke 教训）：
# - cogact.py header 打补丁：torch==2.6.0（cu126 源）+ requires-python 放宽到 3.11+；
# - dexbotic host 侧 clone（serve 容器内 github 不通），header 改本地 path；
# - uv 装包走 PIP_INDEX_URL=cu126 + EXTRA=pypi。
set -e
cd "$(dirname "$0")/.."
WORK="$PWD"
HARNESS_REF="${HARNESS_REF:-v0.7.0}"
DEXBOTIC_REV="42f72859dfe48bb4c30a09ab151a018c2ca0700a"
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

echo "[1b/5] dexbotic 源码 (host 侧 clone)"
if [ ! -f dexbotic-src/pyproject.toml ]; then
  rm -rf dexbotic-src
  DEX_URL="https://github.com/MilkClouds/dexbotic.git"
  [ -n "${GITHUB_TOKEN:-}" ] && DEX_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/MilkClouds/dexbotic.git"
  for i in 1 2 3; do
    if git clone "$DEX_URL" dexbotic-src 2>&1 | tail -n 1 && (cd dexbotic-src && git checkout -q "$DEXBOTIC_REV"); then break; fi
    echo "dexbotic clone 失败, 重试 $i..."; rm -rf dexbotic-src; sleep 20
    [ "$i" = "3" ] && exit 128
  done
else
  echo "dexbotic-src 已存在, 跳过 clone"
fi

echo "[1c/5] cogact header 打补丁 (torch 钉 2.6.0 + dexbotic 本地 path + python 放宽)"
COG=harness/src/vla_eval/model_servers/dexbotic/cogact.py
if ! grep -q '/work/dexbotic-src' "$COG"; then
  sed -i 's|dexbotic = { git = "https://github.com/MilkClouds/dexbotic.git", rev = "42f72859dfe48bb4c30a09ab151a018c2ca0700a" }|dexbotic = { path = "/work/dexbotic-src" }|' "$COG"
fi
if ! grep -q '"torch==2.6.0"' "$COG"; then
  sed -i 's|"torch>=2.0"|"torch==2.6.0"|' "$COG"
fi
if ! grep -q '"transformers==4.46.3"' "$COG"; then
  # 官方复现要求：v5.x 有 meta device 问题，钉 4.46.3（见 dexbotic.md）
  sed -i 's|"transformers>=4.40,<5"|"transformers==4.46.3"|' "$COG"
fi
if ! grep -q 'requires-python = ">=3.11"' "$COG"; then
  sed -i 's|requires-python = "~=3.11"|requires-python = ">=3.11"|' "$COG"
fi
grep -nE 'torch==|dexbotic =|requires-python' "$COG" | head -n 5

echo "[2/5] robotwin 镜像 (SWR 内网拉取)"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$ROBOTWIN_IMAGE"
docker images | grep -E 'robotwin' || true

echo "[3/5] 构建 verify 镜像 (host 缓存)"
docker build -f docker/Dockerfile.verify -t "$VERIFY_IMAGE" .

echo "[4/5] 预热 DB-CogACT 权重 (grab_roller 头, mirror, 带重试)"
for i in 1 2 3; do
  if SNAP=$(docker run --rm --network host \
    -v "$WORK/.cache/hf":/root/.cache/huggingface \
    -e HF_ENDPOINT=https://hf-mirror.com \
    "$VERIFY_IMAGE" python -c "from huggingface_hub import snapshot_download; print(snapshot_download('Dexmal/robotwin-db-cogact', allow_patterns=['grab_roller/*'], max_workers=4))" 2>/dev/null | tail -n 1) && [ -n "$SNAP" ]; then
    echo "snapshot: $SNAP"; break
  fi
  echo "checkpoint 预热失败, 重试 $i..."; sleep 15
  [ "$i" = "3" ] && exit 1
done
echo "[4a/5] 生成本地路径 serve 配置 (from_pretrained 不认三段式 repo/subdir，只能本地路径)"
sed "s|model_path: .*|model_path: $SNAP/grab_roller|" "$WORK/configs/serve-robotwin.yaml" > "$WORK/configs/serve-robotwin-local.yaml"
grep -n "model_path" "$WORK/configs/serve-robotwin-local.yaml"

echo "[4b/5] 启动 DB-CogACT serve (GPU0, 后台)"
docker rm -f cogact-serve 2>/dev/null || true
start_serve() {
docker run -d --name cogact-serve --gpus '"device=0"' --network host \
  -v "$WORK":/work -w /work/harness \
  -v "$WORK/.cache/uv":/root/.cache/uv \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e PIP_INDEX_URL=https://download.pytorch.org/whl/cu126 \
  -e PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
  -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
  -e HF_TOKEN="${HF_TOKEN:-}" \
  "$VERIFY_IMAGE" \
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
  echo "serve 未起来 (尝试 $attempt), 尾日志:"; docker logs cogact-serve 2>&1 | tail -n 15
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
  -e CUDA_VISIBLE_DEVICES=0 \
  "$ROBOTWIN_IMAGE" \
  run --config /work/configs/run-robotwin-smoke.yaml 2>&1 | tee results/robotwin-smoke.log
CODE=${PIPESTATUS[0]}
set -e
echo "[5b/5] 收 serve 日志"
docker logs cogact-serve > results/cogact-serve.log 2>&1 || true
docker rm -f cogact-serve 2>/dev/null || true
ls -lh results/ || true
echo "smoke_exit=$CODE"
exit $CODE
