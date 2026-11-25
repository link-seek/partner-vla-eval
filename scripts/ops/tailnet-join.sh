#!/bin/bash
# action=tailnet-join：让 V100 重新加入 tailnet。
# 原 ts-join-v100.yml：经 hw41 跳板（V100 入网前不可直连），key 现场 mint、只在命令行传、不落盘。
set -uo pipefail
. "$(dirname "$0")/common.sh"
require_env V100_SSH_PASS TS_API_KEY
setup_ssh
HN="${TAILNET_HOSTNAME:-v100-0002}"

if is_dry; then
  plan "action=tailnet-join hostname=$HN"
  plan "跳板 hw41=$HW41_JUMP tcp 22: $(tcp_check "$HW41_JUMP" 22)"
  plan "目标 V100=$V100_0002 tcp 22: $(tcp_check "$V100_0002" 22)"
  plan "TS_API_KEY 在位（长度 ${#TS_API_KEY}）；dry-run 不 mint key、不执行 tailscale up"
  plan "将执行的命令：ssh root@$HW41_JUMP \"ssh root@$V100_0002 'tailscale up --authkey=<minted> --hostname=$HN ...'\""
  plan "dry-run 结束"
  exit 0
fi

echo "[ops] 1/3 预检：V100 22 是否可达（经 hw41 跳板）"
"$OPS_SSH_DIR/ssh.sh" "root@$HW41_JUMP" \
  "(echo > /dev/tcp/$V100_0002/22) 2>/dev/null && echo v100-22-OPEN || { echo v100-22-CLOSED; exit 1; }"

echo "[ops] 2/3 现场 mint reusable key（90 天）"
RESP=$(mktemp)
CODE=$(curl -sS -m 30 -o "$RESP" -w '%{http_code}' -X POST \
  -u "$TS_API_KEY:" -H 'Content-Type: application/json' \
  -d '{"capabilities":{"devices":{"create":{"reusable":true,"ephemeral":false,"preauthorized":true}}},"expirySeconds":7776000}' \
  https://api.tailscale.com/api/v2/tailnet/-/keys || true)
case "$CODE" in
  200|201) ;;
  *) echo "[ops] FAIL: mint HTTP $CODE"; head -c 300 "$RESP"; rm -f "$RESP"; exit 1 ;;
esac
KEY=$(python3 -c "import json;print(json.load(open('$RESP')).get('key',''))")
rm -f "$RESP"
[ -n "$KEY" ] || { echo "[ops] FAIL: mint 返回空 key" >&2; exit 1; }
mask "$KEY"

echo "[ops] 3/3 经 hw41 跳板执行 tailscale up（key 只在命令行，不落 V100 盘）"
"$OPS_SSH_DIR/ssh.sh" "root@$HW41_JUMP" \
  "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes root@$V100_0002 \
   'tailscale up --authkey=$KEY --hostname=$HN --ssh --accept-routes=false --accept-dns=false && tailscale ip -4'"
rc=$?
echo "[ops] tailnet-join exit=$rc"
exit $rc
