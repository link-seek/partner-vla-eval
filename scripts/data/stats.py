#!/usr/bin/env python3
"""统计工具：二值成功率的区间与标准误（零依赖，除 numpy 外无外部包）。

为什么需要：报告目前只给点估计（如 48/50 = 96%），跨模型比较时缺误差口径。
lm-evaluation-harness 用 bootstrap_stderr；我们也补上，并同时给 Wilson 区间
（小样本比例更稳，两者并列，读者自行取舍）。

参考：
- Wilson (1927) score interval
- Efron & Tibshirani, An Introduction to the Bootstrap（percentile method）
"""
from __future__ import annotations

import numpy as np


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 区间（95%）。n=0 时返回 (0, 1)? 不——返回 (0.0, 0.0) 并让调用方判空。"""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(max(0.0, c - m)), float(min(1.0, c + m)))


def bootstrap_stderr(flags, iters: int = 2000, seed: int = 0) -> float:
    """二值序列的成功率标准误（非参数 bootstrap 百分位法）。

    flags: 0/1 序列（或 bool）。少于 2 个样本返回 0.0。
    """
    a = np.asarray(flags, dtype=np.float64).reshape(-1)
    n = a.size
    if n < 2:
        return 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(iters, n))
    means = a[idx].mean(axis=1)
    return float(means.std(ddof=1))


def mean_stderr(flags) -> float:
    """解析标准误 sqrt(p(1-p)/n)，用作 bootstrap 的交叉校验。"""
    a = np.asarray(flags, dtype=np.float64).reshape(-1)
    n = a.size
    if n < 2:
        return 0.0
    p = a.mean()
    return float(np.sqrt(p * (1 - p) / n))


def summarize(k: int, n: int, seed: int = 0) -> dict:
    """一次给出报告需要的全部统计量。"""
    if n <= 0:
        return {"n": 0, "success": k, "mean_success": None,
                "stderr": None, "ci95": None, "ci95_method": "wilson"}
    flags = [1] * k + [0] * (n - k)
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "success": k,
        "mean_success": round(k / n, 6),
        "stderr": round(bootstrap_stderr(flags, seed=seed), 6),
        "stderr_method": "bootstrap(2000)",
        "stderr_analytic": round(mean_stderr(flags), 6),
        "ci95": [round(lo, 4), round(hi, 4)],
        "ci95_method": "wilson",
    }
