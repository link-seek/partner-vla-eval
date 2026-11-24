#!/usr/bin/env python3
"""RoboTwin 策略的观测转换（纯函数，不依赖 harness / GPU / 机器人环境）。

抽出来的原因：`robotwin_policy.py` 顶部 import 了 `vla_eval`，在本机跑不了；
而"观测转换错"是 B3 最可能的失败点（runbook 里"动作全程不动"就是它）。
所以把这段做成零依赖模块，配 `test_robotwin_obs.py` 单测，进 lint。

官方 `encode_obs()` 的要求（policy/ACT|DP/deploy_policy.py）：
  - 三相机 RGB 转成 CHW 且归一到 0..1
  - ACT 用键 `qpos`（list），DP 用键 `agent_pos`（ndarray）
  - 关节向量 14 维（aloha-agilex：左右各 6 关节 + 各 1 夹爪）
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np

CAMERAS = ("head_camera", "left_camera", "right_camera")
SHORT = {"head_camera": "head_cam", "left_camera": "left_cam", "right_camera": "right_cam"}


def to_chw01(img: np.ndarray) -> np.ndarray:
    """任意常见布局 → CHW float32，值域 0..1。

    支持 HWC(H,W,3|4) uint8 / HWC float(0..1 或 0..255) / CHW 原样。
    用 `max() > 1.5` 判是否 0-255：比 `dtype==uint8` 更稳（有些链路会先转 float 再给）。
    """
    a = np.asarray(img)
    if a.ndim != 3:
        raise ValueError(f"图像维度应为 3（HWC 或 CHW），拿到 shape={a.shape}")
    # HWC：最后一维是通道
    if a.shape[-1] in (1, 3, 4):
        a = a[..., :3] if a.shape[-1] > 1 else np.repeat(a, 3, axis=-1)
        a = np.moveaxis(a, -1, 0)
    elif a.shape[0] not in (1, 3, 4):
        raise ValueError(f"无法识别的图像布局 shape={a.shape}（既不是 HWC 也不是 CHW）")

    if a.dtype != np.float32:
        a = a.astype(np.float32)
    if a.max(initial=0.0) > 1.5:
        a = a / 255.0
    return np.ascontiguousarray(a)


def flat_joint_state(js: Any, action_dim: int = 14) -> np.ndarray:
    """关节向量 → 一维 float32，并校验维度。"""
    a = np.asarray(js, dtype=np.float32).reshape(-1)
    if a.size != action_dim:
        raise ValueError(f"joint_state 维度 {a.size} 与 action_dim {action_dim} 不符")
    return a


def build_policy_obs(
    images: Mapping[str, Any],
    joint_state: Any,
    policy: str,
    action_dim: int = 14,
) -> dict[str, Any]:
    """拼接官方 `encode_obs()` 期望的 dict。

    policy='act' → 额外键 `qpos`（list，官方走 list 相加）
    policy='dp'  → 额外键 `agent_pos`（ndarray）
    """
    policy = policy.lower()
    if policy not in ("act", "dp"):
        raise ValueError(f"policy 只允许 act|dp（实际 {policy!r}）")

    out: dict[str, Any] = {}
    for name in CAMERAS:
        if name not in images:
            raise KeyError(f"观测缺相机 {name}（拿到 {sorted(images)}）")
        out[SHORT[name]] = to_chw01(images[name])

    js = flat_joint_state(joint_state, action_dim)
    if policy == "act":
        out["qpos"] = js.tolist()
    else:
        out["agent_pos"] = js
    return out
