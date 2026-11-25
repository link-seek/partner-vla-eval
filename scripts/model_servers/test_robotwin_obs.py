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
from robotwin_obs import (  # noqa: E402
    RESIZE_WH, build_policy_obs, flat_joint_state, resize_bilinear, to_chw01,
)

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
    imgs_320 = {k: np.zeros((240, 320, 3), dtype=np.uint8) for k in ("head_camera", "left_camera", "right_camera")}
    imgs = {
        "head_camera": np.zeros((480, 640, 3), np.uint8),
        "left_camera": np.zeros((480, 640, 3), np.uint8),
        "right_camera": np.zeros((480, 640, 3), np.uint8),
    }
    act = build_policy_obs(imgs, list(range(14)), "act")
    check("act 键位", set(act) == {"head_cam", "left_cam", "right_cam", "qpos"}, str(sorted(act)))
    check("act qpos 是 list", isinstance(act["qpos"], list))
    dp = build_policy_obs(imgs, np.arange(14, dtype=np.float32), "dp")
    check("dp 键位只有 head_cam + agent_pos", set(dp) == {"head_cam", "agent_pos"}, str(sorted(dp)))
    check("dp agent_pos 是 ndarray", isinstance(dp["agent_pos"], np.ndarray))

    try:
        build_policy_obs({"head_camera": imgs["head_camera"]}, list(range(14)), "act")
        check("缺相机应报错", False, "未抛错")
    except KeyError:
        check("缺相机应报错", True)

    # ---- resize：考场 D435 是 320x240，官方要求 640x480（2026-11-25 实测 0/1 的真因）----
    small = np.random.default_rng(0).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    big = resize_bilinear(small, *RESIZE_WH)
    check("320x240 HWC uint8 → 480x640x3", big.shape == (480, 640, 3), f"{big.shape}")
    check("resize 保持 uint8 与值域", big.dtype == np.uint8 and big.min() >= 0 and big.max() <= 255)
    const = np.full((240, 320, 3), 77, dtype=np.uint8)
    check("常量图 resize 后仍是 77", int(resize_bilinear(const, 640, 480).max()) == 77)
    chw_in = np.random.default_rng(1).integers(0, 255, (3, 240, 320), dtype=np.uint8)
    chw_out = resize_bilinear(chw_in, 640, 480)
    check("CHW 输入保持 CHW", chw_out.shape == (3, 480, 640), f"{chw_out.shape}")
    same = resize_bilinear(small, 320, 240)
    check("尺寸相同则原样返回", np.array_equal(same, small))
    o2 = build_policy_obs(imgs_320, np.zeros(14, dtype=np.float32), "act")
    check("act 输出 3x480x640（已 resize）",
          all(v.shape == (3, 480, 640) for k, v in o2.items() if k in ("head_cam", "left_cam", "right_cam")))
    # DP 契约：只 head_cam，保持原生 240x320（ckpt shape_meta 决定的，不能 resize）
    o3 = build_policy_obs(imgs_320, np.zeros(14, dtype=np.float32), "dp")
    check("dp 只送 head_cam", set(o3) == {"head_cam", "agent_pos"}, str(sorted(o3)))
    check("dp head_cam 保持 3x240x320（不 resize）", o3["head_cam"].shape == (3, 240, 320),
          str(o3["head_cam"].shape))

    # 回归：numpy 数组作为 joint_state 时不得触发"真值歧义"
    arr_js = np.zeros(14, dtype=np.float32)
    o = build_policy_obs(imgs, arr_js, "dp")
    check("numpy joint_state 不炸（真值歧义回归）", o["agent_pos"].size == 14)

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
