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
  # docker 写出的文件属主是 root，runner 直接 rm 会 Permission denied（10-23 calvin smoke 翻车）；
  # 先清属主再删，两种手段都不行才报错（不用裸 sudo，避免 runner 无 sudo 权限时挂）。
  rm -rf results/* 2>/dev/null || {
    local _w="${WORK:-$PWD}"
    docker run --rm -v "$_w/results":/r python:3.12-slim chown -R 1001:1001 /r 2>/dev/null || \
      sudo chown -R "$(id -u):$(id -g)" "$_w/results" 2>/dev/null || true
    rm -rf "$_w"/results/*
  }
}
