#!/usr/bin/env python3
"""S1 数据校验：RoboTwin 2.0 训练数据（Aloha-AgileX）结构与统计。

为什么要有：
  `prepare_robotwin_data.sh` 只数了 `*.hdf5` 个数。个数对不代表能用——
  维度错、相机缺、rgb 解不开、episode 长度 0，都会在 6–7 天训练跑完后才暴露。
  这个脚本在训练前把"能不能训"验掉。

用法（在有 h5py 的环境里跑，例如 robotwin 镜像）：
  python3 scripts/data/check_robotwin_data.py --root /data/robotwin-train --sample 5

判据（每个 task × kind 抽样）：
  - joint_action/vector 存在且第二维 = 14
  - left_arm/right_arm (T,6)，两个 gripper (T,)
  - head/left/right 三路相机存在，rgb 帧数 = T
  - 至少抽 1 帧尝试解码（有 cv2 时）；解不开算失败
  - 同一文件内关节与相机的 T 一致
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h5py
import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None

CAMS = ("head_camera", "left_camera", "right_camera")


def pick_even(paths: list[Path], n: int) -> list[Path]:
    if len(paths) <= n:
        return paths
    idx = np.linspace(0, len(paths) - 1, n).round().astype(int)
    return [paths[i] for i in sorted(set(idx.tolist()))]


def check_file(p: Path, decode: bool) -> list[str]:
    errs: list[str] = []
    with h5py.File(p, "r") as h:
        for key in ("joint_action/vector", "joint_action/left_arm", "joint_action/right_arm",
                    "joint_action/left_gripper", "joint_action/right_gripper"):
            if key not in h:
                errs.append(f"缺 {key}")
        if errs:
            return errs
        vec = h["joint_action/vector"]
        T = int(vec.shape[0])
        if T <= 0:
            errs.append("T=0")
        if vec.shape[1] != 14:
            errs.append(f"joint_action/vector 维度 {vec.shape} != (T,14)")
        if h["joint_action/left_arm"].shape != (T, 6) or h["joint_action/right_arm"].shape != (T, 6):
            errs.append("左右臂形状不是 (T,6)")
        if h["joint_action/left_gripper"].shape != (T,) or h["joint_action/right_gripper"].shape != (T,):
            errs.append("gripper 形状不是 (T,)")
        for cam in CAMS:
            k = f"observation/{cam}/rgb"
            if k not in h:
                errs.append(f"缺相机 {cam}")
                continue
            rgb = h[k]
            if int(rgb.shape[0]) != T:
                errs.append(f"{cam} 帧数 {rgb.shape[0]} != T={T}")
            if decode and rgb.shape[0] > 0:
                buf = bytes(rgb[0])
                if not buf:
                    errs.append(f"{cam} 首帧为空")
                elif cv2 is not None:
                    img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
                    if img is None:
                        errs.append(f"{cam} 首帧解码失败")
                    elif img.ndim != 3 or img.shape[2] != 3:
                        errs.append(f"{cam} 首帧不是三通道 {img.shape}")
    return errs


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/data/robotwin-train")
    ap.add_argument("--sample", type=int, default=5)
    ap.add_argument("--decode", type=int, default=1)
    a = ap.parse_args(argv)

    root = Path(a.root) / "data"
    if not root.is_dir():
        print(f"没有数据目录：{root}")
        return 2

    total, bad = 0, 0
    print(f"[S1] root={a.root} sample={a.sample}/group decode={bool(a.decode)} cv2={cv2 is not None}")
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for kind in ("clean_50", "randomized_500"):
            gdir = task_dir / kind
            files = sorted(gdir.rglob("*.hdf5")) if gdir.is_dir() else []
            if not files:
                print(f"  {task_dir.name:20s} {kind:15s} MISSING")
                bad += 1
                continue
            sample = pick_even(files, a.sample)
            lens = []
            group_errs = []
            for f in sample:
                total += 1
                errs = check_file(f, bool(a.decode))
                if errs:
                    group_errs.append((f.name, errs))
                else:
                    with h5py.File(f, "r") as h:
                        lens.append(int(h["joint_action/vector"].shape[0]))
            status = "OK" if not group_errs else f"FAIL({len(group_errs)})"
            rng = f"T={min(lens)}..{max(lens)}" if lens else ""
            print(f"  {task_dir.name:20s} {kind:15s} n={len(files):3d} sample={len(sample):2d} {status} {rng}")
            for name, errs in group_errs:
                bad += 1
                print(f"      - {name}: {'; '.join(errs[:3])}")
    print(f"\n[S1] 抽样 {total} 个文件，失败组 {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
