#!/usr/bin/env python3
"""门禁：task 清单不许再硬编码回脚本 / workflow。

背景：2026-11-25 实测发现同一个 5 task 清单存在两份且已漂移
  - scripts/ci/ci_robotwin_full.sh 默认：grab_roller,adjust_bottle,click_bell,handover_block,stack_blocks_two
  - scripts/data/collect_matrix.sh 写死：grab_roller,adjust_bottle,place_phone_stand,click_bell,handover_block
两份都“跑得通”，所以没人发现；后果是少跑一格或收不到一格，报告里就是 MISSING。

现在唯一真源是 configs/registry/model-registry.json 的 exam.tasks，
统一经 scripts/data/bench_config.py 读取。

本门禁规则：一行里出现 ≥3 个 exam.tasks 的 task 名（逗号/空格分隔的清单形态）即判红。
单个 task 名的正常使用（如 `RW_TASKS="$task"`、目录名）不拦。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "configs" / "registry" / "model-registry.json"

SCAN_DIRS = ["scripts", ".github/workflows"]
SUFFIXES = {".sh", ".bash", ".yml", ".yaml", ".py"}
# 允许保留字面量的地方：门禁自身、读取入口、registry 文件
ALLOW = {ROOT / "scripts/gates/check_task_list.py", ROOT / "scripts/data/bench_config.py"}


def main() -> int:
    tasks = json.loads(REGISTRY.read_text())["exam"]["tasks"]
    if len(tasks) < 3:
        print(f"TASK-LIST: exam.tasks 只有 {len(tasks)} 个，门禁无法判断", file=sys.stderr)
        return 1

    errors: list[str] = []
    for d in SCAN_DIRS:
        for f in sorted((ROOT / d).rglob("*")):
            if f.suffix not in SUFFIXES or not f.is_file() or f in ALLOW:
                continue
            try:
                lines = f.read_text(errors="ignore").splitlines()
            except OSError:
                continue
            for no, line in enumerate(lines, 1):
                hit = sum(1 for t in tasks if re.search(rf"\b{re.escape(t)}\b", line))
                if hit >= 3:
                    errors.append(
                        f"{f.relative_to(ROOT)}:{no} 硬编码了 {hit} 个 task 名 → "
                        f"改成 python3 scripts/data/bench_config.py tasks"
                    )

    if errors:
        print(f"TASK-LIST FAIL ({len(errors)} 处硬编码清单):")
        for e in errors:
            print(" -", e)
        print("\n唯一真源是 registry.exam.tasks；脚本/workflow 一律经 bench_config.py 读取。")
        return 1

    print(f"TASK-LIST OK (exam.tasks={len(tasks)} 个，无脚本硬编码清单)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
