#!/bin/bash
# 公共头：workspace 修复 + 缓存目录 + SWR 登录 + results 清理。
# 用法（调用方先 cd 到仓库根并设好 WORK）：
#   source "$WORK/scripts/lib/common.sh"
#   workspace_fix "0/4"
#   swr_login
#   results_fresh
# 注意：OBS_AK/OBS_SK 由 workflow secrets 注入；不要回显密钥。
workspace_fix() {
  local tag="${1:-[0]}"
  echo "[$tag] workspace 属主修复 + 缓存目录预建"
  docker run --rm -v "$WORK":/w python:3.12-slim chown -R 1001:1001 /w 2>/dev/null || \
    sudo chown -R "$(id -u):$(id -g)" "$WORK" 2>/dev/null || true
  mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" 2>/dev/null || sudo mkdir -p "$WORK/.cache/uv" "$WORK/.cache/hf" || true
  sudo chown -R "$(id -u):$(id -g)" "$WORK/.cache" 2>/dev/null || true
}
swr_login() {
  echo "[swr] 登录私仓（HMAC 派生口令，不落盘不回显）"
  local key
  key=$(printf "${OBS_AK:?}" | openssl dgst -binary -sha256 -hmac "${OBS_SK:?}" | od -An -vtx1 | sed 's/[ \n]//g' | sed 'N;s/\n//')
  echo "$key" | docker login -u "cn-north-4@${OBS_AK}" --password-stdin swr.cn-north-4.myhuaweicloud.com
}
results_fresh() {
  mkdir -p results
  # 先清能清的；root 属主的清不掉（docker 落盘）→ 留给 results_root_wipe（借已拉取镜像删）。
  # 10-23 教训：docker 拉公共镜像/sudo 在 V100 上都不可用，fallback 必须走业务镜像。
  rm -rf results/* 2>/dev/null || true
  if [ -n "$(ls -A results 2>/dev/null)" ]; then
    echo "[results] 有 root 残留，待 post-pull 清场（results_root_wipe）"
  fi
}
# root 文件清场：借已拉取的业务镜像当 root 身份删（V100 唯一可行路）。
# 调用点：各 ci 脚本 docker pull 之后。删不掉就 loud fail，不许带 stale 跑。
results_root_wipe() {
  local img="$1"
  [ -n "$(ls -A results 2>/dev/null)" ] || return 0
  echo "[results] root 残留清场（image: $img）"
  docker run --rm --entrypoint bash -v "${WORK:-$PWD}/results":/r "$img" -c 'rm -rf /r/*' \
    || { echo "root wipe FAILED"; exit 1; }
  [ -z "$(ls -A results 2>/dev/null)" ] || { echo "root wipe INCOMPLETE"; exit 1; }
  echo "[results] clean"
}
