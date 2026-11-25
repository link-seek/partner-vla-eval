#!/bin/bash
# action=repair-0002：重配 0002 上的两个 agent（/data/gh-runner、/data/gh-runner2）。
# 原 repair-v100.yml。凭证用预置 org 注册 token（V100_REG_TOKEN），用完即弃。
#
# 注：token 通过远端命令的参数传入（与改造前一致）。它已 add-mask，不进日志；
# 不落 V100 磁盘（只在进程环境里）。
set -uo pipefail
. "$(dirname "$0")/common.sh"
require_env V100_SSH_PASS PROD_GH_TOKEN
setup_ssh

# 2026-11-25 实测：原来依赖手动设置的 V100_REG_TOKEN，该 secret 已不存在 →
# 这个修复能力在重构前就已经不可用了。改成与 repair-0001 一致：现场 mint。
if [ -n "${V100_REG_TOKEN:-}" ]; then
  REG_TOKEN="$V100_REG_TOKEN"
  echo "[ops] 用预置 V100_REG_TOKEN"
else
  if is_dry; then
    REG_TOKEN="<dry-run-minted>"
    plan "将通过 PROD_GH_TOKEN 现场 mint 注册 token（dry-run 不真的 mint）"
  else
    RESP=$(curl -sS -m 30 -X POST -H "Authorization: Bearer $PROD_GH_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      https://api.github.com/orgs/link-seek/actions/runners/registration-token)
    REG_TOKEN=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('token',''))")
    [ -n "$REG_TOKEN" ] || { echo "[ops] FAIL: mint 失败 $(echo "$RESP" | head -c 200)" >&2; exit 1; }
  fi
fi
mask "$REG_TOKEN"

read -r -d '' REMOTE <<'REMOTE'
set -euo pipefail
for pair in "gh-runner:ecs-0002-org" "gh-runner2:ecs-0002-pi0"; do
  dir="/data/${pair%%:*}"; name="${pair##*:}"
  echo "== $name ($dir) =="
  cd "$dir"
  ./svc.sh stop || true
  ./svc.sh uninstall || true
  # agent 文件属 runner 用户：config 必须以 runner 身份跑；svc 启停/安装 root 做
  su -s /bin/bash runner -c "cd '$dir' && ./config.sh remove --token '$REG_TOKEN' || true"
  su -s /bin/bash runner -c "cd '$dir' && ./config.sh --unattended --url https://github.com/link-seek --token '$REG_TOKEN' --name '$name' --labels V100,V100-pi0 --work _work"
  ./svc.sh install runner
  ./svc.sh start
done
echo "== status =="
systemctl is-active "actions.runner.link-seek.ecs-0002-org.service" || true
sleep 15
echo "listener 进程数: $(ps aux | grep -c '[R]unner.Listener')"
REMOTE

if is_dry; then
  plan "action=repair-0002 target=root@$V100_0002"
  plan "tcp 22: $(tcp_check "$V100_0002" 22)"
  plan "token: $([ "$REG_TOKEN" = "<dry-run-minted>" ] && echo '将现场 mint（未执行）' || echo "已注入，长度 ${#REG_TOKEN}")"
  plan "将执行的远端脚本："
  printf '%s\n' "$REMOTE" | sed 's/^/[ops][dry]   /'
  plan "dry-run 结束（未改动任何 agent）"
  exit 0
fi

"$OPS_SSH_DIR/ssh.sh" "root@$V100_0002" "REG_TOKEN='$REG_TOKEN' bash -s" <<< "$REMOTE"
rc=$?
echo "[ops] repair-0002 exit=$rc"
exit $rc
