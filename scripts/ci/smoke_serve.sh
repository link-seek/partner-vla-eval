#!/bin/bash
# RobotWin serve+run 的 smoke 驱动：把 2026-11-25 踩过的四类「接缝错误」变成前置断言。
#
# 为什么要有这个脚本（都是真实事故，不是假设）：
#   1) 路径双写 → output_dir 写成 /work/run/smoke2/results，而挂载是 <host>:​/work/run，
#      结果落到 <host>/smoke2/results，跑成功但写偏了，最后 `find` 找不到还以为没跑。
#   2) serve 端口配错 → 写成 yaml 顶层 `server.port`，harness 只认 `args.port`
#      （或 --address），于是去绑 8000，撞上别的容器 → address already in use。
#   3) 适配器 CLI 缺参数 → `unrecognized arguments: --args.left_arm_dim=6`
#      （jsonargparse 按类签名生成，**必须**在 __init__ 显式声明）。
#   4) 长跑日志丢失 → 整段管道接 `| tail`，中途零输出，外层 timeout 一掐就没诊断。
#
# 本脚本的对应约束：
#   - 路径映射只有一处定义（HOST_WD → /work/run），并断言没有重复段
#   - 端口用 --address 显式覆盖，启动前先断言端口空闲
#   - serve 起不来/端口不开 → 立刻打日志退出，不"继续跑客户端"
#   - 全程 tee 到 $HOST_WD/run.log；每阶段各自 timeout
#   - 结束后断言 aggregate 落在**预期宿主机路径**，否则非零退出
#
# 用法：
#   bash scripts/ci/smoke_serve.sh --image <img> --policy act|dp --ckpt-host <path> \
#        [--task click_bell] [--port 8021] [--workdir /root/r01/smoke] [--dry-run]
set -uo pipefail

IMAGE=""; POLICY=""; CKPT_HOST=""; TASK="click_bell"; PORT="8021"
WORKDIR="/root/r01/smoke"; DRY=0; ASSETS="${ASSETS:-/data/robotwin-assets/c3ddfa8}"
EPISODES=1; GPU=0; TIMEOUT="${TIMEOUT:-900}"
while [ $# -gt 0 ]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --policy) POLICY="$2"; shift 2 ;;
    --ckpt-host) CKPT_HOST="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --workdir) WORKDIR="$2"; shift 2 ;;
    --assets) ASSETS="$2"; shift 2 ;;
    --episodes) EPISODES="$2"; shift 2 ;;
    --gpu) GPU="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "未知参数 $1" >&2; exit 2 ;;
  esac
done

die() { echo "[smoke] FAIL: $*" >&2; exit 1; }
ok()  { echo "[smoke] ok: $*"; }

[ -n "$IMAGE" ] || die "--image 必填"
[ "$POLICY" = "act" ] || [ "$POLICY" = "dp" ] || die "--policy 只允许 act|dp"
[ -n "$CKPT_HOST" ] || die "--ckpt-host 必填"

# ---------------------------------------------------------------- 路径映射（唯一真源）
CTR_WD="/work/run"
CTR_RESULTS="$CTR_WD/results/$POLICY"
HOST_RESULTS="$WORKDIR/results/$POLICY"

echo "[smoke] 路径映射："
printf '  %-22s %s\n' "host workdir"      "$WORKDIR"
printf '  %-22s %s\n' "container workdir" "$CTR_WD"
printf '  %-22s %s\n' "output_dir (ctr)"  "$CTR_RESULTS"
printf '  %-22s %s\n' "output_dir (host)" "$HOST_RESULTS"

# 断言：不得出现 <workdir>/<basename(workdir)>/... 这种重复段（事故 1 的形态）
WD_BASE="$(basename "$WORKDIR")"
case "$HOST_RESULTS" in
  "$WORKDIR"/*) ok "输出目录在 workdir 内" ;;
  *) die "输出目录不在 workdir 内：$HOST_RESULTS（路径映射接错了）" ;;
esac
case "$HOST_RESULTS" in
  "$WORKDIR/$WD_BASE"/*) die "输出目录出现重复段 $WD_BASE/$WD_BASE（就是把 /work/run/xxx 又拼了一次）" ;;
esac

# ---------------------------------------------------------------- 前置检查
[ -f "$CKPT_HOST" ] || [ -d "$CKPT_HOST" ] || die "ckpt 不存在：$CKPT_HOST"
ok "ckpt 存在：$CKPT_HOST"
if [ ! -d "$ASSETS" ]; then
  # dry-run 常用于 CI/本机（没有 SUT 资产），只告警；真跑必须存在
  if [ "$DRY" = "1" ]; then echo "[smoke] warn: SUT assets 不在本机：$ASSETS（dry-run 忽略）"
  else die "SUT assets 不存在：$ASSETS"; fi
fi

if [ "$DRY" = "1" ]; then
  echo "[smoke] dry-run：前置检查通过（未启动容器）"
  exit 0
fi

command -v docker >/dev/null || die "没有 docker"
docker image inspect "$IMAGE" >/dev/null 2>&1 || die "镜像不在本地：$IMAGE"
ok "镜像在本地：$IMAGE"

# 端口空闲检查（事故 2 的形态：静默去绑 8000，撞上别人）
if (exec 3<>/dev/tcp/127.0.0.1/"$PORT") 2>/dev/null; then
  who="$(docker ps --format '{{.Names}} {{.Ports}}' | grep -F ":$PORT->" | head -1)"
  die "端口 $PORT 已被占用${who:+（$who）}——换 --port，或先停掉那个容器"
fi
ok "端口 $PORT 空闲"

mkdir -p "$HOST_RESULTS" "$WORKDIR"
LOG="$WORKDIR/run.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1     # 全程留档（事故 4）

# ---------------------------------------------------------------- 渲染 yaml
SERVE_YAML="$WORKDIR/${POLICY}-serve.yaml"
RUN_YAML="$WORKDIR/${POLICY}-run.yaml"

if [ "$POLICY" = "act" ]; then
  cat > "$SERVE_YAML" <<YML
script: "/opt/serve/robotwin_policy.py"
args:
  policy: act
  ckpt_dir: /ckpt
  action_dim: 14
  chunk_size: 50
  kl_weight: 10.0
  temporal_agg: false
  device: cuda:0
YML
  # 宿主机 ckpt 目录挂到 /ckpt，ACT 的 ckpt_dir 用容器内路径
  SERVE_CWD="/opt/serve"
  EXTRA_MOUNT=(-v "$CKPT_HOST:/ckpt:ro")
else
  # DP 官方 get_model 用相对路径 ./policy/DP/checkpoints/<task>-<setting>-<num>-<seed>/<num>.ckpt
  # 官方布局：<task>-<ckpt_setting>-<expert_data_num>/<seed>/<ckpt>.ckpt（HF 上只有前 3 段）
  NAME="$(basename "$(dirname "$CKPT_HOST")")"                   # 例：100（= expert_data_num = seed）
  SETTING_FULL="$(basename "$(dirname "$(dirname "$CKPT_HOST")")")"  # 例：click_bell-demo_clean-100
  # 从 "<task>-<setting>-<num>" 里剥出 setting（不能简单 -%%-*-*，那样会把 demo_clean 切掉）
  _t="${SETTING_FULL#"$TASK"-}"; SETTING="${_t%-"$NAME"}"
  [ -n "$SETTING" ] || { echo "[smoke] FAIL: 无法从 $SETTING_FULL 推出 ckpt_setting（用 --ckpt-setting 显式给）" >&2; exit 1; }
  CTR_CKPT="/app/RoboTwin/policy/DP/checkpoints/${SETTING_FULL}-${NAME}/$(basename "$CKPT_HOST")"
  cat > "$SERVE_YAML" <<YML
script: "/opt/serve/robotwin_policy.py"
args:
  policy: dp
  task_name: $TASK
  ckpt_setting: $SETTING
  expert_data_num: $NAME
  seed: $NAME
  checkpoint_num: $(basename "$CKPT_HOST" .ckpt)
  action_dim: 14
  left_arm_dim: 6
  right_arm_dim: 6
  device: cuda:0
YML
  SERVE_CWD="/app/RoboTwin"
  EXTRA_MOUNT=(-v "$CKPT_HOST:$CTR_CKPT:ro")
fi

cat > "$RUN_YAML" <<YML
server:
  url: "ws://127.0.0.1:$PORT"
  timeout: 600.0
output_dir: "$CTR_RESULTS"
benchmarks:
  - benchmark: "vla_eval.benchmarks.robotwin.benchmark:RoboTwinBenchmark"
    name: $TASK
    episodes_per_task: $EPISODES
    params:
      task_name: $TASK
      task_config: demo_clean
      seed: 0
      instruction_type: seen
      test_num: 1
      skip_expert_check: true
      fast_init: false
      action_type: qpos
    action_dim: 14
YML

# ---------------------------------------------------------------- serve
CTR_NAME="smoke-${POLICY}-$$"
docker rm -f "$CTR_NAME" >/dev/null 2>&1 || true
# 端口走 --address 显式覆盖：yaml 里没有 server.port 这个概念（见 --help）
# 就绪判定用 Docker 原生 HEALTHCHECK（标准原语），不再手写 TCP 轮询循环。
# 探针必须打**服务自己的 HTTP 端点** `/config`（serve 日志会打印它，实测 200）。
# 教训（2026-11-25）：别用 `/dev/tcp` —— HEALTHCHECK 由容器里的 /bin/sh(dash) 执行，
# /dev/tcp 是 bash 专有特性，dash 下报 "cannot create /dev/tcp/...: Directory nonexistent"，
# 于是健康检查永远 unhealthy，看起来像"服务起不来"，其实服务好得很。
docker run -d --name "$CTR_NAME" --gpus "\"device=$GPU\"" --network host --entrypoint bash \
  --health-cmd "curl -fsS -o /dev/null http://127.0.0.1:$PORT/config || exit 1" \
  --health-interval=5s --health-timeout=3s --health-retries=40 --health-start-period=15s \
  -v "$WORKDIR:$CTR_WD:ro" "${EXTRA_MOUNT[@]}" \
  -e CUDA_VISIBLE_DEVICES=$GPU -e HF_HUB_OFFLINE=1 \
  "$IMAGE" -lc "cd $SERVE_CWD && conda run --no-capture-output -n robotwin vla-eval serve -c $CTR_WD/$(basename "$SERVE_YAML") --address 0.0.0.0:$PORT" >/dev/null

docker_wait_healthy() {   # 标准做法：轮询 docker 自己的健康状态
  local deadline=$((SECONDS + 300))
  while [ $SECONDS -lt $deadline ]; do
    case "$(docker inspect --format '{{.State.Health.Status}}' "$CTR_NAME" 2>/dev/null)" in
      healthy) return 0 ;;
      unhealthy) return 1 ;;
    esac
    docker ps --format '{{.Names}}' | grep -qx "$CTR_NAME" || return 1
    sleep 3
  done
  return 1
}
if ! docker_wait_healthy; then
  echo "[smoke] serve 未就绪（health=$(docker inspect --format '{{.State.Health.Status}}' "$CTR_NAME" 2>/dev/null)），日志尾部："
  docker logs "$CTR_NAME" 2>&1 | tail -30
  docker rm -f "$CTR_NAME" >/dev/null 2>&1
  die "serve 未通过健康检查（见上面的日志）"
fi
ok "serve 健康检查通过（docker health=healthy，端口 $PORT）"

# ---------------------------------------------------------------- run
echo "[smoke] 跑 $EPISODES 集（GPU$GPU）"
timeout "$TIMEOUT" docker run --rm --gpus "\"device=$GPU\"" --network host --entrypoint bash \
  -v "$WORKDIR:$CTR_WD" -v "$ASSETS:/app/RoboTwin/assets:ro" \
  -e CUDA_VISIBLE_DEVICES=$GPU \
  "$IMAGE" -lc "cd /app/RoboTwin && conda run --no-capture-output -n robotwin vla-eval run -c $CTR_WD/$(basename "$RUN_YAML")" \
  2>&1 | grep -viE '^\s*[0-9]+%|it/s|B/s'
RC=${PIPESTATUS[0]}

echo "[smoke] serve 日志（完整落盘 + 摘要）"
docker logs "$CTR_NAME" > "$WORKDIR/serve.log" 2>&1
grep -aiE '\[dbg\]|loaded|error|traceback' "$WORKDIR/serve.log" | tail -15
docker rm -f "$CTR_NAME" >/dev/null 2>&1

# ---------------------------------------------------------------- 后置断言
AGG="$HOST_RESULTS/${TASK}_aggregate.json"
[ "$RC" = "0" ] || die "客户端退出码 $RC（日志：$LOG）"
[ -f "$AGG" ] || die "没找到 aggregate：$AGG（输出写偏了？见 $LOG）"
ok "aggregate 落在预期路径：$AGG"
# 断言对齐 aggregate 的真源字段：task.num_errors + 每集 failure_reason/failure_detail。
# 2026-11-25 教训：之前只看 e["error"]（aggregate 根本没有这个键）→ 明明 1 集报错还判 PASS。
python3 - "$AGG" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
t = d.get("tasks", [d])[0]
eps = t.get("episodes", [])
ok = sum(1 for e in eps if (e.get("metrics") or {}).get("success"))
err = int(t.get("num_errors") or 0) or sum(
    1 for e in eps if e.get("failure_reason") or e.get("failure_detail"))
print(f"[smoke] {t.get('task')}: {ok}/{len(eps)} success, num_errors={err}")
if err:
    for e in eps:
        if e.get("failure_reason") or e.get("failure_detail"):
            print(f"[smoke] FAIL {e.get('failure_reason')}: {str(e.get('failure_detail'))[-600:]}")
    sys.exit(1)
sys.exit(0)
PY
ASSERT_RC=$?
[ "$ASSERT_RC" = "0" ] || die "后置断言未通过（aggregate 里有报错，见上）"
echo "[smoke] PASS（日志：$LOG）"
