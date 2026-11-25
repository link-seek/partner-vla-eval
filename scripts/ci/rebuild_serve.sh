#!/bin/bash
# 重打 serve 镜像 → 推 SWR → 把**真实 manifest digest** 写回 registry，一条命令做完。
#
# 为什么不让人手工抄 digest（2026-11-25 已踩过两次）：
#   1) `docker manifest inspect` 里既有 manifest digest 也有 config.digest，长得都像 sha256:…，
#      我第一次抄的是 config.digest → `FROM image@digest` 直接报
#      "unexpected media type application/octet-stream"，镜像根本起不来；
#   2) 适配器每改一次，digest 就变一次，registry 不跟着改就等于"声称的行为版本"和实际不符。
# 所以 digest 只能由**构建这条链路自己**写回，且必须来自 `docker inspect .RepoDigests`（manifest digest），
# 不能来自任何需要人眼判断的输出。
#
# 必须跑在有 docker + 已登录 SWR 的机器上（基座本地有缓存时约 10 秒/个）。
#
# 用法：
#   bash scripts/ci/rebuild_serve.sh                 # 重打 act + dp
#   bash scripts/ci/rebuild_serve.sh act             # 只重打 act
#   bash scripts/ci/rebuild_serve.sh --dry-run       # 只打印计划
set -uo pipefail
cd "$(dirname "$0")/../.."
WORK="$PWD"

REG="swr.cn-north-4.myhuaweicloud.com/link-seek"
REGISTRY="configs/registry/model-registry.json"
DOCKERFILE="docker/Dockerfile.serve-robotwin"
TAG="0.8.0"

TARGETS=(); DRY=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    act|dp) TARGETS+=("$a") ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数 $a（可用 act / dp / --dry-run）" >&2; exit 2 ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=(act dp)

# 自检：Dockerfile 的基座必须等于 registry 里的 bench_image_digest（防"改了基座忘了改账"）
BENCH_DIG=$(python3 -c "import json;print(json.load(open('$REGISTRY'))['exam']['bench_image_digest'])")
grep -q "$BENCH_DIG" "$DOCKERFILE" || {
  echo "FAIL: $DOCKERFILE 的基座不是 registry 里的 $BENCH_DIG" >&2; exit 1; }
echo "[rebuild] 基座一致：${BENCH_DIG:0:22}…"

if [ "$DRY" = "1" ]; then
  for t in "${TARGETS[@]}"; do
    echo "[rebuild][dry] docker build --build-arg POLICY=$t -f $DOCKERFILE -t $REG/vla-serve-robotwin-$t:$TAG . && push"
  done
  exit 0
fi

declare -A NEW
for t in "${TARGETS[@]}"; do
  echo "[rebuild] 构建 $t …"
  docker build -q -f "$DOCKERFILE" --build-arg "POLICY=$t" \
    -t "$REG/vla-serve-robotwin-$t:$TAG" . >/dev/null || { echo "FAIL: 构建 $t 失败" >&2; exit 1; }
  docker push -q "$REG/vla-serve-robotwin-$t:$TAG" >/dev/null 2>&1 || { echo "FAIL: 推送 $t 失败（SWR 登录？）" >&2; exit 1; }
  # 标准取法：buildx 直接问 registry 要 manifest digest。
  # 不用 `docker inspect .RepoDigests | sed`，也不用 `docker manifest inspect` 里的 config.digest
  # （后者是配置层 blob，拿去做 FROM image@digest 会报 unexpected media type）。
  dig=$(docker buildx imagetools inspect --format '{{.Manifest.Digest}}' \
          "$REG/vla-serve-robotwin-$t:$TAG" 2>/dev/null)
  case "$dig" in
    sha256:????????????????????????????????????????????????????????????????) NEW[$t]="$dig" ;;
    *) echo "FAIL: 取不到 $t 的 manifest digest（拿到 ${dig:-空}）" >&2; exit 1 ;;
  esac
  echo "[rebuild]   ${t}: ${dig:0:22}…"
done

# 写回 registry（键 = act-baseline / dp-baseline）
python3 - "$REGISTRY" "$(printf '%s\n' "${!NEW[@]}")" "$(printf '%s\n' "${NEW[@]}")" <<'PY'
import json, sys
path, keys, digs = sys.argv[1], sys.argv[2].split("\n"), sys.argv[3].split("\n")
d = json.load(open(path))
changed = []
for k, dig in zip(keys, digs):
    entry = d["models"].get(f"{k}-baseline")
    if entry is None:
        print(f"WARN: registry 没有 {k}-baseline，跳过", file=sys.stderr); continue
    old = entry.get("serve_image_digest")
    if old != dig:
        entry["serve_image_digest"] = dig
        changed.append((k, old, dig))
json.dump(d, open(path, "w"), ensure_ascii=False, indent=2)
open(path, "a").write("\n")
for k, old, dig in changed:
    print(f"[rebuild] {k}: {(old or '无')[:22]}… → {dig[:22]}…")
print(f"[rebuild] registry 更新 {len(changed)} 项（幂等：digest 未变则不写）")
PY

python3 scripts/gates/check_registry.py || { echo "FAIL: 写完 registry 后门禁不过" >&2; exit 1; }
echo "[rebuild] 完成。别忘了：改了适配器 → 用过旧 digest 的结果要在报告里注明版本。"
