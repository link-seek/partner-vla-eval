#!/usr/bin/env python3
"""action_queue 单测（纯 Python，直接跑，进 lint）。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_queue import ActionQueue  # noqa: E402

fails: list[str] = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


print("[单步策略：ACT]")
q = ActionQueue(14)
a = q.pop_or_fill(np.arange(14, dtype=np.float32))
check("单步直接吐出", a.shape == (14,))
check("吐完队列空", q.pending == 0)

print("[分块策略：DP]")
q = ActionQueue(14)
chunk = np.arange(6 * 14, dtype=np.float32).reshape(6, 14)
first = q.pop_or_fill(chunk)
check("首步取块首行", float(first[0]) == 0.0)
check("剩余 5 步在队列", q.pending == 5)
second = q.pop_or_fill(None)     # 队列非空时 chunk 传 None（=不推理）
check("第二步取第 2 行", float(second[0]) == 14.0)
check("剩余 4 步", q.pending == 4)

print("[reset 清空，防跨集串动作]")
q.clear()
check("clear 后为空", q.pending == 0)
try:
    q.pop()
    check("空队列 pop 应报错", False, "未抛错")
except IndexError:
    check("空队列 pop 应报错", True)

print("[边界]")
try:
    ActionQueue(0)
    check("action_dim=0 应报错", False, "未抛错")
except ValueError:
    check("action_dim=0 应报错", True)
try:
    ActionQueue(14).push(np.zeros(15, dtype=np.float32))
    check("维度不整除应报错", False, "未抛错")
except ValueError:
    check("维度不整除应报错", True)
try:
    ActionQueue(14).push(np.zeros(0, dtype=np.float32))
    check("空动作应报错", False, "未抛错")
except ValueError:
    check("空动作应报错", True)

print("[drain]")
q = ActionQueue(3); q.push(np.arange(6, dtype=np.float32))
check("drain 出 2 步", len(list(q.drain())) == 2)
check("drain 后为空", q.pending == 0)

if fails:
    print(f"\nFAILED: {len(fails)} -> {fails}")
    sys.exit(1)
print("\nALL OK")
