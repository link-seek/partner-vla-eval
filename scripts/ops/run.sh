#!/bin/bash
# ops 唯一入口：把原先 4 个一次性 workflow（audit-v100 / repair-v100 / repair-v100-0001 /
# ts-join-v100）收敛成一个常驻能力，action 用参数选择。
#
# 为什么这么改（CONTRIBUTING 第二/三节）：
#   main 上只放"常驻能力"，不放"一次性事件"。这四件事都会反复发生（机器重装、跑飞了要审计），
#   所以它们是能力；但四份 workflow 各自带凭证拼装逻辑，改一处要改四处 → 收敛成一个入口 + 脚本。
#
# 用法：
#   workflow_dispatch: action=audit|repair-0002|repair-0001|tailnet-join
#   本地：ACTION=audit V100_SSH_PASS=... bash scripts/ops/run.sh
set -uo pipefail
cd "$(dirname "$0")"

ACTION="${ACTION:?ACTION 必填：audit | repair-0002 | repair-0001 | tailnet-join}"

case "$ACTION" in
  audit)         exec bash ./audit.sh ;;
  repair-0002)   exec bash ./repair-0002.sh ;;
  repair-0001)   exec bash ./repair-0001.sh ;;
  tailnet-join)  exec bash ./tailnet-join.sh ;;
  *) echo "[ops] 未知 action: $ACTION（只允许 audit|repair-0002|repair-0001|tailnet-join）" >&2; exit 2 ;;
esac
