#!/usr/bin/env python3
"""S1 统计校验：按 task × 口径计算 qpos 的 mean/std/min/max。

为什么要有：
  R01 的口径 A/B 必须**各自独立**算统计量（复用会引入口径污染）。
  训练脚本启动时也会重算，但那时已经在烧 GPU；先在 CPU 上算一遍可以：
    1. 验证 A/B 分布确实不同（randomized 的方差应更大）；
    2. 把结果留档，训练时对得上；
    3. 发现坏数据（NaN/维度错/长度 0）。

用法（robotwin 镜像内）：
  python3 scripts/data/robotwin_data_stats.py --root /data/robotwin-train \
      --out /data/robotwin-train/stats.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np


def one_group(gdir: Path) -> dict:
    files = sorted(gdir.rglob("*.hdf5"))
    n = 0
    s = np.zeros(14, dtype=np.float64)
    ss = np.zeros(14, dtype=np.float64)
    lo = np.full(14, np.inf)
    hi = np.full(14, -np.inf)
    lens: list[int] = []
    bad: list[str] = []
    for f in files:
        try:
            with h5py.File(f, "r") as h:
                a = np.asarray(h["joint_action/vector"], dtype=np.float64)
        except Exception as e:  # 坏文件不应中断整组
            bad.append(f"{f.name}: {type(e).__name__}")
            continue
        if a.ndim != 2 or a.shape[1] != 14 or a.shape[0] == 0:
            bad.append(f"{f.name}: shape={a.shape}")
            continue
        if not np.isfinite(a).all():
            bad.append(f"{f.name}: 含 NaN/Inf")
            continue
        s += a.sum(axis=0)
        ss += (a * a).sum(axis=0)
        lo = np.minimum(lo, a.min(axis=0))
        hi = np.maximum(hi, a.max(axis=0))
        n += a.shape[0]
        lens.append(a.shape[0])
    if n == 0:
        return {"files": len(files), "frames": 0, "bad": bad}
    mean = s / n
    var = np.maximum(ss / n - mean * mean, 0.0)
    return {
        "files": len(files),
        "frames": n,
        "episodes_T_min": min(lens) if lens else 0,
        "episodes_T_max": max(lens) if lens else 0,
        "qpos_mean": [round(float(x), 5) for x in mean],
        "qpos_std": [round(float(x), 5) for x in np.sqrt(var)],
        "qpos_min": [round(float(x), 4) for x in lo],
        "qpos_max": [round(float(x), 4) for x in hi],
        "std_mean": round(float(np.sqrt(var).mean()), 5),
        "bad": bad[:5],
        "bad_count": len(bad),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/data/robotwin-train")
    ap.add_argument("--out", default="/data/robotwin-train/stats.json")
    a = ap.parse_args(argv)
    root = Path(a.root) / "data"
    out: dict = {"source": "TianxingChen/RoboTwin2.0", "tasks": {}}
    bad_total = 0
    print(f"{'task':20s} {'regime':15s} {'files':>5s} {'frames':>7s} {'T':>9s} {'std_mean':>9s} bad")
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        out["tasks"][tdir.name] = {}
        for kind in ("clean_50", "randomized_500"):
            g = tdir / kind
            if not g.is_dir():
                continue
            r = one_group(g)
            out["tasks"][tdir.name][kind] = r
            bad_total += r.get("bad_count", 0)
            T = f"{r.get('episodes_T_min',0)}..{r.get('episodes_T_max',0)}"
            print(f"{tdir.name:20s} {kind:15s} {r['files']:5d} {r['frames']:7d} {T:>9s} "
                  f"{r.get('std_mean',0):9.4f} {r.get('bad_count',0)}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n[S1] stats -> {a.out}；坏文件 {bad_total}")
    return 0 if bad_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
