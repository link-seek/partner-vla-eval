#!/bin/bash
# action=audit：V100 本机只读审计。经 SSH 在 V100 上执行（原 audit-v100.yml 是直接跑在 V100 runner 上）。
# 只读禁令：只用 du / docker images / docker system df / ls，不动系统。
set -uo pipefail
. "$(dirname "$0")/common.sh"
require_env V100_SSH_PASS
setup_ssh

cat > /tmp/ops-audit.sh <<'REMOTE'
set -uo pipefail
echo "=== disk ==="; df -h / /data 2>/dev/null
echo "=== /data top ==="; du -sh /data/* 2>/dev/null | sort -rh | head -n 20
echo "=== docker images ==="; docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' 2>/dev/null | sort -k2 -rh | head -n 25
echo "=== docker disk ==="; docker system df 2>/dev/null
echo "=== workspace caches ==="; du -sh /data/gh-runner/_work/*/ 2>/dev/null | sort -rh | head -n 10
echo "=== gpu ==="; nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null
REMOTE

run_remote "$V100_0002" /tmp/ops-audit.sh
