#!/usr/bin/env python3
"""collect_matrix.sh 回归测试（直接 python3 跑，进 lint）。

为什么值得测：这段逻辑 2026-11-25 实测踩了两个静默坑——
  1) A5 的 easy r2 目录是 `<task>-easy-r2`，脚本只认 `<task>`/`<task>-hard` → 收 0 个 task；
  2) 修完后如果不收紧，收 hard 会回落到裸名 `<task>`（那是 easy 的目录），
     收 r2 会回落到 r1 —— 两者都会在没人察觉的情况下产出**错标/重复**的数据。
这类错误不会报错，只会让报告数字变成假的，所以必须由测试钉住。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "data" / "collect_matrix.sh"

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


def make_agg(root: Path, model: str, dirname: str, task: str, ok: int, n: int) -> None:
    d = root / model / dirname
    d.mkdir(parents=True, exist_ok=True)
    eps = [{"metrics": {"success": i < ok}, "steps": 50} for i in range(n)]
    (d / f"{task}_aggregate.json").write_text(
        json.dumps({"tasks": [{"task": task, "num_episodes": n, "episodes": eps, "steps": 50}]})
    )


def run(root: Path, proto: str, replicate: str = "") -> dict:
    cmd = ["bash", str(SCRIPT), "m", proto, str(root)] + ([replicate] if replicate else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:])
        raise SystemExit(f"collect_matrix 退出码 {r.returncode}")
    return json.loads(r.stdout)


def task_state(data: dict, task: str) -> str:
    t = data["tasks"].get(task, {})
    if t.get("status") == "missing":
        return "missing"
    return f"{t.get('success')}/{t.get('n')}"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # 三种命名各放一份
        make_agg(root, "m", "grab_roller", "grab_roller", 2, 2)              # legacy easy 裸名
        make_agg(root, "m", "click_bell-hard", "click_bell", 1, 2)           # legacy hard
        make_agg(root, "m", "adjust_bottle-hard-r2", "adjust_bottle", 2, 2)  # 重复轮
        make_agg(root, "m", "place_phone_stand-easy", "place_phone_stand", 2, 2)  # 新命名 easy

        print("[easy：裸名 + <task>-easy 都能收，且不回落到 hard/r2]")
        e = run(root, "easy")
        check("grab_roller（裸名）收到 2/2", task_state(e, "grab_roller") == "2/2", task_state(e, "grab_roller"))
        check("place_phone_stand（-easy）收到 2/2", task_state(e, "place_phone_stand") == "2/2", task_state(e, "place_phone_stand"))
        check("click_bell（-hard）不混进 easy", task_state(e, "click_bell") == "missing", task_state(e, "click_bell"))

        print("[hard：只认 -hard，绝不回落到裸名]")
        h = run(root, "hard")
        check("click_bell（-hard）收到 1/2", task_state(h, "click_bell") == "1/2", task_state(h, "click_bell"))
        check("grab_roller（裸名= easy）不得被当 hard", task_state(h, "grab_roller") == "missing", task_state(h, "grab_roller"))

        print("[r2：只认 -<proto>-r2，绝不回落 r1]")
        r2 = run(root, "hard", "r2")
        check("adjust_bottle（-hard-r2）收到 2/2", task_state(r2, "adjust_bottle") == "2/2", task_state(r2, "adjust_bottle"))
        check("click_bell（r1 的 -hard）不得被当 r2", task_state(r2, "click_bell") == "missing", task_state(r2, "click_bell"))
        check("输出的 replicate 字段为 r2", r2.get("replicate") == "r2", str(r2.get("replicate")))

        print("[新命名 easy-r2]")
        make_agg(root, "m", "handover_block-easy-r2", "handover_block", 2, 2)
        e2 = run(root, "easy", "r2")
        check("handover_block（-easy-r2）收到 2/2", task_state(e2, "handover_block") == "2/2", task_state(e2, "handover_block"))

    if fails:
        print(f"\nFAILED: {len(fails)} -> {fails}")
        return 1
    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
