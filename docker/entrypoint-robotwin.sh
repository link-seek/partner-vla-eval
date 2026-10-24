#!/bin/bash
# RobotWin 统一镜像 entrypoint：资产就绪 + P2 补丁激活（STATE_PATCH=robotwin），再 exec vla-eval。
# P2 文件烘在 /opt/patches（构建时从追踪仓拉，V100 出境只认 github.com，raw 域名不通，只能烘不能现拉）。
set -e
if [ -d /app/RoboTwin/assets ]; then
  cd /app/RoboTwin && python script/update_embodiment_config_path.py >/dev/null 2>&1 || true
fi
if [ "${STATE_PATCH:-}" = "robotwin" ]; then
  SP=$(conda run --no-capture-output -n robotwin python -c "import vla_eval.benchmarks.robotwin.benchmark as m; print(m.__file__)")
  cp /opt/patches/robotwin_benchmark_state.py "$SP"
  echo "state-patch activated: robotwin ($(basename "$SP"))" >&2
fi
exec conda run --no-capture-output -n robotwin vla-eval "$@"
