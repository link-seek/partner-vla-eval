#!/usr/bin/env python3
"""给历史报告补 `stats` / `hard_stats`（幂等，数值只由报告自带的 success/n 推出）。

背景：2026-11-25 起 gen_reports.py 会给新报告写 bootstrap stderr + Wilson CI，
但之前生成的 19 份没有，check_reports.py 一直告警。这个脚本只做「按已有
success/n 补算统计量」，不改变任何原始数字，也不猜任何缺失值：
  - 有 success 与 n 才补；缺任一则跳过并说明
  - 已有 stats 的条目原样保留（幂等，可重复跑）

用法：
  python3 scripts/data/backfill_stats.py [--dry] [glob]
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "data"))
from stats import summarize  # noqa: E402


def keys_for(p: pathlib.Path) -> list[str]:
    return ["stats"]


def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    pattern = next((a for a in argv[1:] if not a.startswith("-")), "docs/data/*.json")
    files = sorted(ROOT.glob(pattern))
    if not files:
        print(f"没匹配到文件：{pattern}")
        return 1

    changed, skipped, kept = [], [], []
    for p in files:
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            skipped.append((p.name, "非法 JSON"))
            continue

        todo = []
        if isinstance(d.get("success"), int) and isinstance(d.get("n"), int) and not d.get("stats"):
            todo.append(("stats", d["success"], d["n"]))
        if isinstance(d.get("hard_success"), (int, float)) and isinstance(d.get("n"), int) and not d.get("hard_stats"):
            # hard_success 是比例（0..1）→ 反推成功集数；浮点误差用 round 消掉
            k = round(d["hard_success"] * d["n"])
            todo.append(("hard_stats", k, d["n"]))

        if not todo:
            if d.get("stats"):
                kept.append(p.name)
            else:
                skipped.append((p.name, "缺 success/n，无法补"))
            continue

        for key, k, n in todo:
            d[key] = summarize(k, n)
        if not dry:
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        changed.append((p.name, [t[0] for t in todo]))

    for name, keys in changed:
        print(f"  {'[dry] ' if dry else ''}补 {'/'.join(keys):12s} {name}")
    for name, why in skipped:
        print(f"  skip {name}: {why}")
    print(f"\n合计：补 {len(changed)} 份，已有 {len(kept)} 份，跳过 {len(skipped)} 份")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
