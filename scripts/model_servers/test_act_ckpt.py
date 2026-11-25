#!/usr/bin/env python3
"""act_ckpt 单测：锁死"静默随机权重"这条坑，纯 Python 直接跑（进 lint + run_all）。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from act_ckpt import resolve_act_ckpt  # noqa: E402

fails: list[str] = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


def expect_error(name, fn, needle=""):
    try:
        fn()
    except ValueError as e:
        check(name, needle in str(e), f"错误信息缺 {needle!r}: {e}")
    else:
        check(name, False, "未抛错")


with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    epoch = d / "policy_epoch_6000_seed_100.ckpt"
    epoch.write_bytes(b"x")

    print("[显式 ckpt_file 优先]")
    check("返回给定 file", resolve_act_ckpt(str(d), str(epoch)) == str(epoch))
    expect_error("file 不存在报错", lambda: resolve_act_ckpt(str(d), str(d / "no.ckpt")), "不存在")

    print("[目录里只有 epoch 权重：必须报错而不是静默]")
    expect_error("单 epoch ckpt 报错", lambda: resolve_act_ckpt(str(d)), "policy_last.ckpt")
    try:
        resolve_act_ckpt(str(d))
    except ValueError as e:
        check("报错里带真实文件名", "policy_epoch_6000_seed_100.ckpt" in str(e))
        check("报错里给出修法", "ckpt_file=" in str(e))

    print("[标准布局：policy_last.ckpt 在，交给官方加载]")
    (d / "policy_last.ckpt").write_bytes(b"x")
    check("返回 None", resolve_act_ckpt(str(d)) is None)

    print("[空目录 / 缺参数]")
    empty = d / "empty"
    empty.mkdir()
    expect_error("空目录报错", lambda: resolve_act_ckpt(str(empty)), "没有 .ckpt")
    expect_error("ckpt_dir 与 ckpt_file 都缺", lambda: resolve_act_ckpt(None), "ckpt_dir")

print("[多份 epoch 权重也不猜]")
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    (d / "a.ckpt").write_bytes(b"x")
    (d / "b.ckpt").write_bytes(b"x")
    expect_error("多份候选报错", lambda: resolve_act_ckpt(str(d)), "policy_last.ckpt")

if fails:
    print(f"\nFAILED: {len(fails)} -> {fails}")
    sys.exit(1)
print("\nALL OK")
