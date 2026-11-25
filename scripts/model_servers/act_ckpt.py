#!/usr/bin/env python3
"""ACT 权重路径解析：官方只认 policy_last.ckpt，找不到会静默留随机权重。

为什么单独成模块：
  这段判断踩过一次真坑（2026-11-25）：挂进去的是 `policy_epoch_6000_seed_100.ckpt`，
  官方加载器只打一行 Warning 就继续跑——400 步、零 error、分数全 0。
  抽成纯函数才能单测，也才能在"接第三个策略"时复用同一套 fail-closed 语义。

返回约定（None 表示"官方自己会加载 policy_last.ckpt"）：
  - ckpt_file 给定            → 返回该路径（适配器显式 torch.load + 严格断言）
  - 目录里有 policy_last.ckpt → 返回 None（官方负责加载）
  - 目录里只有单个 *.ckpt     → **报错**，并给出该文件名（提示软链或传 ckpt_file）
  - 目录里什么都没有          → 报错
"""
from __future__ import annotations

import glob
import os


def resolve_act_ckpt(ckpt_dir: str | None, ckpt_file: str | None = None) -> str | None:
    if ckpt_file:
        if not os.path.exists(ckpt_file):
            raise ValueError(f"ckpt_file 不存在：{ckpt_file}")
        return ckpt_file
    if not ckpt_dir:
        raise ValueError("ACT 需要 ckpt_dir 或 ckpt_file（缺了会用随机权重）")
    last = os.path.join(ckpt_dir, "policy_last.ckpt")
    if os.path.exists(last):
        return None
    found = sorted(glob.glob(os.path.join(ckpt_dir, "*.ckpt")))
    if found:
        names = [os.path.basename(x) for x in found]
        raise ValueError(
            f"官方 ACT 只认 {last}，目录里是 {names}；"
            "不修会静默用随机权重（跑满也不报错，分数全 0）。"
            f"传 ckpt_file={found[0]}，或把该文件软链成 policy_last.ckpt。")
    raise ValueError(f"目录里没有 .ckpt：{ckpt_dir}（官方会静默用随机权重）")
