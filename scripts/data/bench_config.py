#!/usr/bin/env python3
"""考场配置的唯一读取入口：registry 里的 exam 段就是真源。

为什么要有这个文件：task 清单此前硬编码在三处
  - scripts/ci/ci_robotwin_full.sh  (默认含 stack_blocks_two)
  - scripts/data/collect_matrix.sh  (含 place_phone_stand)
  - .github/workflows/model-matrix.yml (又一份)
2026-11-25 实测发现前两者已经漂移（一个有 stack_blocks_two，一个有 place_phone_stand）。
加 task 要改三处、漏一处就少跑一格，还查不出来。现在统一从这里读。

用法（shell 里直接调用）：
  python3 scripts/data/bench_config.py tasks              # grab_roller,adjust_bottle,...
  python3 scripts/data/bench_config.py task_config hard   # demo_randomized
  python3 scripts/data/bench_config.py label hard         # Hard
  python3 scripts/data/bench_config.py episodes           # 50
  python3 scripts/data/bench_config.py json               # exam 段原样输出

registry 是 JSON，所以不依赖 PyYAML，任何有 python3 的地方都能跑。
"""
from __future__ import annotations

import json
import pathlib
import sys

REGISTRY = pathlib.Path(__file__).resolve().parents[2] / "configs" / "registry" / "model-registry.json"


def exam() -> dict:
    return json.loads(REGISTRY.read_text())["exam"]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    e = exam()

    if cmd == "tasks":
        print(",".join(e["tasks"]))
        return 0
    if cmd == "episodes":
        print(int(e["episodes"]))
        return 0
    if cmd == "json":
        print(json.dumps(e, ensure_ascii=False, indent=2))
        return 0
    if cmd in ("task_config", "label"):
        if len(argv) < 3:
            print(f"用法: bench_config.py {cmd} <easy|hard>", file=sys.stderr)
            return 2
        proto = argv[2]
        protos = e.get("protocols") or {}
        if proto not in protos:
            print(f"未知协议 {proto!r}，可选：{sorted(protos)}", file=sys.stderr)
            return 2
        print(protos[proto][cmd])
        return 0

    print(f"未知子命令 {cmd!r}（可用 tasks/episodes/task_config/label/json）", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
