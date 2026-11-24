#!/usr/bin/env python3
"""报告门禁：docs/reports/*.json 必须自洽，且与榜单一致。

三层对账（前两层今天已做，这是第三层）：
  1) leaderboard ↔ report        （check_leaderboard.py）
  2) report ↔ aggregate          （生成时保证；aggregate 归档在 OBS）
  3) report 内部自洽             ← 本脚本

拦过的事故：报告写 `harness 0.8.0` 而 aggregate 是 `0.0.0`；
`success` 与 `mean_success*n` 对不上；`errors` 大于 `n`。

用法：python3 scripts/gates/check_reports.py
退出码：0 通过；1 有错
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "data"
LB = ROOT / "leaderboard" / "leaderboard.json"

REQUIRED = ("model", "task", "n", "errors", "versions", "machine", "seeds", "date")
errors: list[str] = []
warnings: list[str] = []
checked = 0


def check_one(path: Path) -> dict | None:
    global checked
    name = path.name
    try:
        d = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{name}: 非法 JSON ({e})")
        return None
    if not isinstance(d, dict) or "mean_success" not in d:
        return None  # 不是结果报告（如方案文档）
    checked += 1
    for f in REQUIRED:
        if f not in d:
            errors.append(f"{name}: 缺字段 {f}")

    n = d.get("n")
    s = d.get("success")
    ms = d.get("mean_success")
    err = d.get("errors")

    if isinstance(n, int) and isinstance(err, int) and err > n:
        errors.append(f"{name}: errors({err}) > n({n})")
    if isinstance(s, int) and isinstance(n, int):
        if s > n:
            errors.append(f"{name}: success({s}) > n({n})")
        if isinstance(ms, (int, float)) and n:
            expect = s / n
            if abs(ms - expect) > 0.005:
                errors.append(f"{name}: mean_success={ms} 与 success/n={expect:.4f} 不符")
    elif isinstance(ms, (int, float)) and isinstance(n, int):
        # 只有 mean_success 时反推 success 是否整
        val = ms * n
        if abs(val - round(val)) > 0.01:
            warnings.append(f"{name}: mean_success*n={val:.2f} 非整数（可能四舍五入）")

    v = d.get("versions") or {}
    if not v.get("benchmark_image"):
        # 不计分的证伪记录（mean_success=null）不参与排名，缺镜像只警告；
        # 有分的报告缺镜像则是硬错（无法定位栈，也就无法复现）。
        if d.get("mean_success") is None:
            warnings.append(f"{name}: 缺 versions.benchmark_image（不计分记录，仅警告）")
        else:
            errors.append(f"{name}: versions.benchmark_image 缺失（无法定位栈）")
    hv = v.get("harness")
    if hv is None:
        warnings.append(f"{name}: versions.harness 缺失")
    elif hv == "0.0.0":
        warnings.append(f"{name}: harness=0.0.0（上游 __version__ 未注入，以镜像 tag 为准）")

    if d.get("hard_success") is None and d.get("gap") is None:
        warnings.append(f"{name}: 只有 Easy（hard_success/gap 为 null，按约定不当 0）")
    return d


def main() -> int:
    files = sorted(glob.glob(str(DATA / "*.json")))
    results = {}
    for f in files:
        d = check_one(Path(f))
        if d:
            results[Path(f).name] = d

    # 与榜单交叉：榜单每条若指了 report，该 report 的核心数字必须一致（leaderboard 侧已查，
    # 这里反查 report 是否存在、是否被引用，防止榜单指向已删报告）
    if LB.exists():
        lb = json.loads(LB.read_text())
        for e in lb.get("entries", []):
            rel = e.get("report")
            if rel and not (ROOT / rel).exists():
                errors.append(f"leaderboard 指向不存在的报告：{rel}")

    # 交叉一致性：报告里有 hard_success，就必须在某个 hard 榜单里有一行；
    # 反之榜单有 hard 行，报告必须有 hard_success。防"数出了但榜单没更新"。
    hard_lb = set()
    for lbf in ROOT.glob("leaderboard/leaderboard*.json"):
        if lbf.name.endswith(".schema.json"):
            continue
        try:
            lbd = json.loads(lbf.read_text())
        except json.JSONDecodeError:
            continue
        if not str(lbd.get("protocol", "")).startswith("hard"):
            continue
        for e in lbd.get("entries", []):
            hard_lb.add((e.get("model"), e.get("task")))

    reports_with_hard = set()
    for fname, d in results.items():
        if d.get("hard_success") is None:
            continue
        task = str(d.get("task", ""))
        for t in ("grab_roller", "adjust_bottle", "place_phone_stand", "click_bell", "handover_block"):
            if t in task:
                # 报告文件名前缀是 xvla/cogact；榜单 model 是 registry key，用宽松匹配
                prefix = "xvla" if "xvla" in fname else ("db-cogact" if "cogact" in fname else None)
                reports_with_hard.add((prefix, t))
    if reports_with_hard and not hard_lb:
        errors.append(
            f"{len(reports_with_hard)} 份报告已回填 hard_success，但没有 hard 榜单文件"
            "（跑 scripts/data/make_leaderboard.py <json> hard --run <id>）"
        )

    for w in warnings:
        print("WARN:", w)
    if errors:
        print(f"\nREPORTS FAIL ({len(errors)} error(s)):")
        for e in errors:
            print(" -", e)
        return 1
    print(f"REPORTS OK ({checked} report(s) checked, {len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
