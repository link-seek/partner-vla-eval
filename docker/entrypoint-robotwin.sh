#!/bin/bash
# RobotWin 统一镜像 entrypoint：资产就绪（update_embodiment_config_path 幂等）后 exec vla-eval。
# P2 已退役（归档 tag 见 versions.yaml）：不再向 site-packages 复制补丁。
set -e
if [ -d /app/RoboTwin/assets ]; then
  cd /app/RoboTwin && python script/update_embodiment_config_path.py >/dev/null 2>&1 || true
fi
exec conda run --no-capture-output -n robotwin vla-eval "$@"
