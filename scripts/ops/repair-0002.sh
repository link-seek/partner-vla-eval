#!/bin/bash
# action=repair-0002：重配 0002 上的两个 agent（/data/gh-runner、/data/gh-runner2）。
# 原 repair-v100.yml。凭证用预置 org 注册 token（V100_REG_TOKEN），用完即弃。
#
# 注：token 通过远端命令的参数传入（与改造前一致）。它已 add-mask，不进日志；
# 不落 V100 磁盘（只在进程环境里）。
set -uo pipefail
. "$(dirname "$0")/common.sh"
require_env V100_SSH_PASS V100_REG_TOKEN
mask "$V100_REG_TOKEN"
setup_ssh

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

"$OPS_SSH_DIR/ssh.sh" "root@$V100_0002" "REG_TOKEN='$V100_REG_TOKEN' bash -s" <<< "$REMOTE"
rc=$?
echo "[ops] repair-0002 exit=$rc"
exit $rc
