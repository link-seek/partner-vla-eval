#!/bin/bash
# RobotWin 全量（分块）：host 编排 serve(X-VLA 双臂) + run_sharded.sh 多分片。
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

echo "[1/6] harness + xvla header（幂等补丁，smoke 已验证过直接复用逻辑）"
if [ ! -f harness/pyproject.toml ]; then
  rm -rf harness
  CLONE_URL="https://github.com/allenai/vla-evaluation-harness.git"
  [ -n "${GITHUB_TOKEN:-}" ] && CLONE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/allenai/vla-evaluation-harness.git"
  for i in 1 2 3 4 5; do
    if git clone --depth 1 --branch "$HARNESS_REF" "$CLONE_URL" harness 2>&1 | tail -n 1; then break; fi
    rm -rf harness; sleep 20
    [ "$i" = "5" ] && exit 128
  done
fi
XVLA=harness/src/vla_eval/model_servers/xvla.py
grep -q '"torch==2.6.0"' "$XVLA" || sed -i 's|"torch>=2.2"|"torch==2.6.0"|' "$XVLA"
grep -q 'requires-python = ">=3.11"' "$XVLA" || sed -i 's|requires-python = "~=3.11"|requires-python = ">=3.11"|' "$XVLA"

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
echo "      skip_expert_check: true"
echo "    action_dim: 14"
done
} > "$GEN"
grep -c "task_name:" "$GEN"

echo "[3/6] robotwin 镜像 + verify 镜像"
LOGIN_KEY=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
echo "$LOGIN_KEY" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
docker pull "$ROBOTWIN_IMAGE"
docker build -f docker/Dockerfile.verify -t "$VERIFY_IMAGE" .

echo "[4/6] 预热 X-VLA 权重"
for i in 1 2 3; do
  if SNAP=$(docker run --rm --network host \
    -v "$WORK/.cache/hf":/root/.cache/huggingface \
    -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
    -e HF_TOKEN="${HF_TOKEN:-}" -e HF_HUB_DISABLE_XET=1 \
    "$VERIFY_IMAGE" python -c "from huggingface_hub import snapshot_download; print(snapshot_download('2toINF/X-VLA-WidowX', max_workers=4))" 2>&1 | tee /tmp/prewarm.log | tail -n 1) && [ -n "$SNAP" ]; then
    echo "snapshot: $SNAP"; break
  fi
  tail -n 5 /tmp/prewarm.log 2>/dev/null || true
  sleep 15
  [ "$i" = "3" ] && exit 1
done
sed "s|model_path: .*|model_path: $SNAP|" "$WORK/configs/serve-robotwin.yaml" > "$WORK/configs/serve-robotwin-local.yaml"

echo "[5/6] 启动 X-VLA serve (GPU0, 后台)"
docker rm -f xvla-serve 2>/dev/null || true
docker run -d --name xvla-serve --gpus '"device=0"' --network host \
  -v "$WORK":/work -w /work/harness \
  -v "$WORK/.cache/uv":/root/.cache/uv \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e PIP_INDEX_URL=https://download.pytorch.org/whl/cu126 \
  -e PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
  -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_VERBOSITY=warning \
  -e HF_TOKEN="${HF_TOKEN:-}" -e HF_HUB_DISABLE_XET=1 \
  "$VERIFY_IMAGE" \
  vla-eval serve -c /work/configs/serve-robotwin-local.yaml
for i in $(seq 1 120); do
  [ "$(docker inspect -f '{{.State.Running}}' xvla-serve 2>/dev/null)" = "true" ] || { echo "serve 容器退出"; docker logs xvla-serve 2>&1 | tail -n 15; exit 1; }
  if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then echo "serve UP"; break; fi
  [ "$i" = "120" ] && { echo "serve 超时"; docker logs xvla-serve 2>&1 | tail -n 15; exit 1; }
  sleep 10
done

echo "[6/6] run_sharded 全块跑（分片 $RW_SHARDS，录像=$RW_VIDEO，cpu 软渲染）"
VIDEO_FLAG="--no-record-video"
[ "$RW_VIDEO" = "1" ] && VIDEO_FLAG="--record-video"
set +e
# run_sharded.sh 在 0.7.0 镜像里缺失（tag 里有，镜像构建早），从 host 的 harness clone 挂进去用
# 分片跑在卡1：serve 独占卡0，8 分片同卡 SAPIEN 会 hang（watchdog 全杀，见 run 38186912836）。
# V100 双32G，卡1空闲给渲染。
docker run --rm --gpus all --network host --entrypoint bash \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORK":/work \
  -v "$WORK/harness/scripts":/opt/harness-scripts:ro \
  -v "$WORK/.cache/hf":/root/.cache/huggingface \
  -e CUDA_VISIBLE_DEVICES=1 \
  "$ROBOTWIN_IMAGE" \
  -c "conda run --no-capture-output -n robotwin bash /opt/harness-scripts/run_sharded.sh -c /work/configs/run-robotwin-chunk.yaml -n $RW_SHARDS -o /work/$OUTDIR $VIDEO_FLAG" 2>&1 | tee "$OUTDIR/shard.log"
CODE=${PIPESTATUS[0]}
set -e
docker logs xvla-serve > "$OUTDIR/xvla-serve.log" 2>&1 || true
docker rm -f xvla-serve 2>/dev/null || true
ls -lh "$OUTDIR" || true
echo "chunk_exit=$CODE"
exit $CODE
