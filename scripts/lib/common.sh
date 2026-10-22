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
  rm -rf results/*  # 跨 run 累积污染 artifact；每轮 OBS+artifact 已留档，清掉重来
}
