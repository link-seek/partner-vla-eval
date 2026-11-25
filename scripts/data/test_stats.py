#!/usr/bin/env python3
"""stats.py 单测（直接 python3 跑；进 lint）。

校验点：
  1) 全对/全错时标准误为 0，区间贴边
  2) bootstrap 与解析式 sqrt(p(1-p)/n) 量级一致（相对差 < 25%）
  3) 已知数值锚点：49/50 的标准误约 0.028，Wilson 下界约 0.895
  4) 与文档里已有的 Wilson 数值一致（xvla grab_roller 49/50 → [89.5, 99.6]）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stats import bootstrap_stderr, mean_stderr, summarize, wilson_ci  # noqa: E402

fails: list[str] = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


print("[边界]")
check("全对 → stderr=0", bootstrap_stderr([1] * 50) == 0.0)
check("全错 → stderr=0", bootstrap_stderr([0] * 50) == 0.0)
check("单样本 → stderr=0", bootstrap_stderr([1]) == 0.0)
lo, hi = wilson_ci(50, 50)
check("全对 Wilson 上界=1.0", abs(hi - 1.0) < 1e-9, f"hi={hi}")

print("[已知锚点]")
lo, hi = wilson_ci(49, 50)
check("49/50 Wilson ≈ [0.895, 0.996]",
      abs(lo - 0.895) < 0.002 and abs(hi - 0.996) < 0.002, f"[{lo:.3f},{hi:.3f}]")
# p=0.98, n=50 → sqrt(0.98*0.02/50) = 0.0198（不是 0.028，那是 p=0.96）
se_a = mean_stderr([1] * 49 + [0])
check("49/50 解析 stderr ≈ 0.0198", abs(se_a - 0.0198) < 0.001, f"{se_a:.4f}")
se_b = mean_stderr([1] * 48 + [0] * 2)
check("48/50 解析 stderr ≈ 0.0277", abs(se_b - 0.0277) < 0.001, f"{se_b:.4f}")

print("[bootstrap vs 解析]")
for k, n in ((48, 50), (39, 50), (8, 50)):
    flags = [1] * k + [0] * (n - k)
    b, a = bootstrap_stderr(flags, iters=4000, seed=1), mean_stderr(flags)
    rel = abs(b - a) / max(a, 1e-9)
    check(f"{k}/{n} bootstrap≈解析（rel={rel:.2f}）", rel < 0.25 and a > 0)

print("[summarize 结构]")
s = summarize(48, 50)
check("含 n/success/mean/stderr/ci95",
      all(k in s for k in ("n", "success", "mean_success", "stderr", "ci95")))
check("mean_success=0.96", abs(s["mean_success"] - 0.96) < 1e-9)
check("ci95 两端都在 [0,1]", 0 <= s["ci95"][0] <= s["ci95"][1] <= 1)
s0 = summarize(0, 0)
check("n=0 → mean_success=None", s0["mean_success"] is None and s0["stderr"] is None)

if fails:
    print(f"\nFAILED: {len(fails)} -> {fails}")
    sys.exit(1)
print("\nALL OK")
