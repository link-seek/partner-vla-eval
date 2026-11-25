#!/usr/bin/env python3
"""镜像打包门禁：适配器的本地依赖必须都被 COPY 进 serve 镜像。

为什么要有（2026-11-25 实测）：
  抽出 action_queue.py / act_ckpt.py 后，Dockerfile 仍然只 COPY robotwin_policy.py + robotwin_obs.py。
  构建期自检只 import robotwin_obs，所以 **镜像能构建成功**，但运行时
  `from action_queue import ActionQueue` 会 ModuleNotFoundError —— 要等 smoke 才炸。

判据（不靠记忆）：
  1. robotwin_policy.py 里 `from <mod> import ...`，若 scripts/model_servers/<mod>.py 存在，
     则 Dockerfile 必须有一行 `COPY scripts/model_servers/<mod>.py /opt/serve/...`
  2. Dockerfile 必须有一个构建期 `import robotwin_policy` 自检
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts/model_servers"
DOCKERFILE = ROOT / "docker/Dockerfile.serve-robotwin"
ADAPTER = SRC / "robotwin_policy.py"

fails: list[str] = []


def main() -> int:
    dockerfile = DOCKERFILE.read_text()
    copied = set(re.findall(r"COPY\s+scripts/model_servers/([A-Za-z0-9_]+\.py)\s+/opt/serve/", dockerfile))

    adapter = ADAPTER.read_text()
    local_modules = []
    for mod in re.findall(r"^from\s+([A-Za-z0-9_]+)\s+import\s", adapter, re.M):
        if (SRC / f"{mod}.py").is_file():
            local_modules.append(f"{mod}.py")

    print(f"[扫描] 适配器本地依赖：{sorted(set(local_modules))}")
    print(f"[扫描] Dockerfile 已 COPY：{sorted(copied)}")

    for f in sorted(set(local_modules)):
        if f not in copied:
            fails.append(f"{f} 被适配器 import，但没被 COPY 进 /opt/serve")

    if "import robotwin_policy" not in dockerfile:
        fails.append("Dockerfile 缺少构建期 `import robotwin_policy` 自检（只 import robotwin_obs 抓不到这类问题）")

    if fails:
        print("\nFAIL:")
        for f in fails:
            print(f"  - {f}")
        print("\n修法：在 docker/Dockerfile.serve-robotwin 补 COPY / 自检，再重打镜像。")
        return 1
    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
