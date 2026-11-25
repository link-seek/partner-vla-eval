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
# 两个官方策略对图像的契约**不同**（2026-11-25 实测，别再统一处理）：
#   ACT: 官方 encode_obs 把三相机 resize 到 (w=640, h=480)
#   DP : ckpt 里的 shape_meta 是 {'head_cam': (3, 240, 320), 'agent_pos': (14,)}
#        —— 只用 head_cam，且是考场 D435 原生尺寸，**不 resize**
#        （DP 的 MultiImageObsEncoder 直接 assert img.shape[1:] == key_shape_map[key]）
# 之前对两者都 resize 并送三路相机 → DP 报 AssertionError（空消息，极难查）。
# 官方 `encode_obs()` 把三相机统一 resize 到 (w=640, h=480) 再送进策略。
# 考场 D435 相机实际是 320x240（task_config/demo_clean.yml: head_camera_type: D435），
# 2026-11-25 实测：不做这步 resize 时 ACT 整集 0/1——模型按 640x480 训练，喂半分辨率就是分布外。
RESIZE_WH = (640, 480)
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


def resize_bilinear(img: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """双线性 resize，保持 HWC/CHW 布局与 dtype 语义（对齐 cv2.resize INTER_LINEAR）。

    为什么自己写：本模块是零依赖纯函数（只 numpy），不想为了一个 resize 把 cv2 拖进单测。
    对齐的是"尺寸与插值方式"，不追求与 cv2 逐比特一致。
    """
    a = np.asarray(img)
    if a.ndim != 3:
        raise ValueError(f"图像维度应为 3，拿到 shape={a.shape}")
    chw = a.shape[0] in (1, 3, 4) and a.shape[-1] not in (1, 3, 4)
    hwc = np.moveaxis(a, 0, -1) if chw else a
    h, w = hwc.shape[0], hwc.shape[1]
    if (w, h) == (out_w, out_h):
        return a

    ys = (np.arange(out_h, dtype=np.float64) + 0.5) * (h / out_h) - 0.5
    xs = (np.arange(out_w, dtype=np.float64) + 0.5) * (w / out_w) - 0.5
    ys = np.clip(ys, 0, h - 1)
    xs = np.clip(xs, 0, w - 1)
    y0 = np.floor(ys).astype(np.int64); y1 = np.minimum(y0 + 1, h - 1)
    x0 = np.floor(xs).astype(np.int64); x1 = np.minimum(x0 + 1, w - 1)
    wy = (ys - y0)[:, None, None]
    wx = (xs - x0)[None, :, None]

    src = hwc.astype(np.float64)
    top = src[y0][:, x0] * (1 - wx) + src[y0][:, x1] * wx
    bot = src[y1][:, x0] * (1 - wx) + src[y1][:, x1] * wx
    out = top * (1 - wy) + bot * wy

    if np.issubdtype(a.dtype, np.integer):
        out = np.clip(np.rint(out), 0, 255).astype(a.dtype)
    else:
        out = out.astype(a.dtype)
    return np.ascontiguousarray(np.moveaxis(out, -1, 0) if chw else out)


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
    if policy == "act":
        # 三路相机 + resize 到图片训练尺寸 640x480
        for name in CAMERAS:
            if name not in images:
                raise KeyError(f"观测缺相机 {name}（拿到 {sorted(images)}）")
            out[SHORT[name]] = to_chw01(resize_bilinear(images[name], *RESIZE_WH))
    else:
        # DP：DPRunner 的 get_action 里**显式读三路相机**（head_cam/left_cam/right_cam）
        # + agent_pos，缺任一路就 KeyError；但 encoder 的 rgb_keys 只有 head_cam，
        # 且其 key_shape_map 是 (3, 240, 320) → **不 resize**（考场 D435 原尺寸正好就是它）。
        # 所以：三路都送，全部保持原生尺寸。
        for name in CAMERAS:
            if name not in images:
                raise KeyError(f"DP 观测缺相机 {name}（拿到 {sorted(images)}）")
            out[SHORT[name]] = to_chw01(images[name])

    js = flat_joint_state(joint_state, action_dim)
    if policy == "act":
        out["qpos"] = js.tolist()
    else:
        out["agent_pos"] = js
    return out
