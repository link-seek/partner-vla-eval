#!/usr/bin/env python3
"""所有门禁的唯一入口：一条命令跑完，输出一张表。

为什么要有：门禁散在 6 个文件 + 3 个测试里，CI 里也是一步一步列（lint.yml 十几步），
结果"哪道门现在红了"要翻日志。这里统一：谁红、红在哪、怎么修，一眼看到。

用法：
  python3 scripts/gates/run_all.py              # 全跑
  python3 scripts/gates/run_all.py --only paths,contracts
  python3 scripts/gates/run_all.py --list
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (name, 命令, 说明)  —— 顺序按"改了东西最先想知道"排
GATES: list[tuple[str, list[str], str]] = [
    ("paths",      ["python3", "scripts/gates/check_paths.py"],
     "文档/脚本里的路径必须存在（防引用已删文件）"),
    ("contracts",  ["python3", "scripts/gates/check_contracts.py"],
     "task 清单不硬编码 + serve yaml 契约（不需要 GPU）"),
    ("registry",   ["python3", "scripts/gates/check_registry.py"],
     "模型真源可复现（verified 必须钉 digest/revision）"),
    ("infra",      ["python3", "scripts/gates/check_infra_inventory.py"],
     "基础设施登记（workflow kind / 选项配置，禁 one-off 进 main）"),
    ("versions",   ["python3", "scripts/gates/check_versions.py"],
     "Dockerfile/versions.yaml 的 pin 不许漂移"),
    ("reports",    ["python3", "scripts/gates/check_reports.py"],
     "报告自洽（mean_success vs success/n、stats、图片）"),
    ("coverage",   ["python3", "scripts/gates/check_coverage.py",
                    "--models", "db-cogact", "--tasks", "__from_registry__"],
     "缺格模型必须拒跑（CogACT 3/5）"),
    ("leaderboard", ["python3", "leaderboard/scripts/check_leaderboard.py"],
     "榜单 schema + 与报告对账 + n==协议集数"),
    ("stats",      ["python3", "scripts/data/test_stats.py"],
     "bootstrap/Wilson 统计函数（含锚点）"),
    ("collect",    ["python3", "scripts/data/test_collect_matrix.py"],
     "采集器三种目录命名 + 禁止跨协议/跨轮回落"),
    ("adapter",    ["python3", "scripts/model_servers/test_robotwin_obs.py"],
     "观测转换（通道/resize/真值歧义）"),
]


def tasks_from_registry() -> str:
    import json
    d = json.loads((ROOT / "configs/registry/model-registry.json").read_text())
    return ",".join(d["exam"]["tasks"])


def main(argv: list[str]) -> int:
    only = None
    if "--list" in argv:
        for n, _, desc in GATES:
            print(f"  {n:12s} {desc}")
        return 0
    for i, a in enumerate(argv):
        if a == "--only" and i + 1 < len(argv):
            only = {x.strip() for x in argv[i + 1].split(",") if x.strip()}

    rows, failed = [], []
    for name, cmd, desc in GATES:
        if only and name not in only:
            continue
        cmd = [tasks_from_registry() if c == "__from_registry__" else c for c in cmd]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        ok = r.returncode == 0
        # 兼容 check_coverage 的"拒跑即通过"语义
        if name == "coverage":
            ok = r.returncode == 2
        tail = (r.stdout.strip().splitlines() or [r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ""])[-1]
        rows.append((name, "PASS" if ok else "FAIL", tail[:88]))
        if not ok:
            failed.append((name, r.stdout, r.stderr))

    print(f"{'门禁':12s} {'结果':5s} 摘要")
    print("-" * 78)
    for name, st, tail in rows:
        print(f"{name:12s} {st:5s} {tail}")

    if failed:
        print("\n失败详情：")
        for name, out, err in failed:
            print(f"\n--- {name} ---")
            print((out or err).strip()[-2000:])
        return 1
    print(f"\nALL GATES PASS ({len(rows)} 项)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
