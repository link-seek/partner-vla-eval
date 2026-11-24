#!/usr/bin/env python3
"""robotwin_obs 单测（零依赖，直接 python3 跑，不需要 pytest）。

进 lint：`python3 scripts/model_servers/test_robotwin_obs.py`
覆盖 B3 最可能的失败点：
  - HWC uint8 0..255 → CHW float 0..1
  - HWC float 0..1   → 不被二次除 255
  - CHW 输入原样保留
  - RGBA 4 通道截成 3
  - 缺相机 / 维度不符 必须抛错（静默通过最危险）
  - act 用 qpos(list)、dp 用 agent_pos(ndarray)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from robotwin_obs import build_policy_obs, flat_joint_state, to_chw01  # noqa: E402

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        fails.append(name)


def main() -> int:
    print("[to_chw01]")
    hwc_u8 = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
    out = to_chw01(hwc_u8)
    check("HWC uint8 → CHW", out.shape == (3, 480, 640), f"shape={out.shape}")
    check("归一化到 0..1", 0.0 <= out.min() and out.max() <= 1.0, f"range={out.min()}..{out.max()}")
    check("与 /255 一致", np.allclose(out, np.moveaxis(hwc_u8, -1, 0).astype(np.float32) / 255.0, atol=1e-6))

    hwc_f = hwc_u8.astype(np.float32) / 255.0
    out2 = to_chw01(hwc_f)
    check("HWC float(0..1) 不被二次归一", np.allclose(out2, np.moveaxis(hwc_f, -1, 0), atol=1e-6), f"max={out2.max()}")

    chw = np.random.rand(3, 224, 224).astype(np.float32)
    check("CHW 原样保留", np.allclose(to_chw01(chw), chw))

    rgba = np.random.randint(0, 256, (240, 320, 4), dtype=np.uint8)
    check("RGBA → 3 通道", to_chw01(rgba).shape == (3, 240, 320), f"shape={to_chw01(rgba).shape}")

    for bad, why in ((np.zeros((10, 10)), "2 维"), (np.zeros((5, 5, 5)), "5 通道")):
        try:
            to_chw01(bad)
            check(f"{why} 应报错", False, "未抛错")
        except ValueError:
            check(f"{why} 应报错", True)

    print("[flat_joint_state]")
    check("14 维通过", flat_joint_state(list(range(14))).size == 14)
    try:
        flat_joint_state(list(range(15)))
        check("15 维应报错", False, "未抛错")
    except ValueError:
        check("15 维应报错", True)

    print("[build_policy_obs]")
    imgs = {
        "head_camera": np.zeros((480, 640, 3), np.uint8),
        "left_camera": np.zeros((480, 640, 3), np.uint8),
        "right_camera": np.zeros((480, 640, 3), np.uint8),
    }
    act = build_policy_obs(imgs, list(range(14)), "act")
    check("act 键位", set(act) == {"head_cam", "left_cam", "right_cam", "qpos"}, str(sorted(act)))
    check("act qpos 是 list", isinstance(act["qpos"], list))
    dp = build_policy_obs(imgs, np.arange(14, dtype=np.float32), "dp")
    check("dp 键位", set(dp) == {"head_cam", "left_cam", "right_cam", "agent_pos"}, str(sorted(dp)))
    check("dp agent_pos 是 ndarray", isinstance(dp["agent_pos"], np.ndarray))

    try:
        build_policy_obs({"head_camera": imgs["head_camera"]}, list(range(14)), "act")
        check("缺相机应报错", False, "未抛错")
    except KeyError:
        check("缺相机应报错", True)

    try:
        build_policy_obs(imgs, list(range(14)), "pi0")
        check("未知 policy 应报错", False, "未抛错")
    except ValueError:
        check("未知 policy 应报错", True)

    if fails:
        print(f"\nFAILED: {len(fails)} 项 -> {fails}")
        return 1
    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
