#!/usr/bin/env python3
"""覆盖检查：registry 的 covered_tasks ∩ 考场 tasks，缺格即拒跑。

背景（真实事故）：CogACT 公开仓只发 4 个头（无 click_bell / handover_block），
我们按 5 task 排期，跑到第 3 个 task 才因为预热"Fetching 0 files"发现。
本脚本把这一步前置到 dispatch，缺格直接非 0 退出，不烧卡。

用法：
  python3 scripts/gates/check_coverage.py --models db-cogact --tasks grab_roller,click_bell
  python3 scripts/gates/check_coverage.py --models db-cogact,x-vla-robotwin2 --tasks a,b,c

退出码：0 全覆盖；2 部分缺格（默认拒跑，--allow-partial 放行但打印缺失）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "configs" / "registry" / "model-registry.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="逗号分隔 registry key")
    ap.add_argument("--tasks", required=True, help="逗号分隔考场 task")
    ap.add_argument("--registry", default=str(REG))
    ap.add_argument("--allow-partial", action="store_true",
                    help="缺格仍放行（只打印，用于考古/补跑）")
    a = ap.parse_args()

    reg = json.loads(Path(a.registry).read_text())
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    tasks = [t.strip() for t in a.tasks.split(",") if t.strip()]
    exam = set(reg.get("exam", {}).get("tasks", []))
    partial = False

    for name in models:
        m = reg.get("models", {}).get(name)
        if not m:
            print(f"ERROR: registry 里没有模型 {name}", file=sys.stderr)
            return 2
        covered = m.get("covered_tasks")
        public = m.get("public_tasks") or []
        if not covered:
            # 未声明 covered_tasks：视为全覆盖，但提示补声明
            print(f"WARN: {name} 未声明 covered_tasks，按全覆盖处理（建议补）", file=sys.stderr)
            covered = tasks
        # 可跑 task = 考场覆盖 ∪ 公开权重里但不在考场的 task（如 CogACT 的 place_empty_cup）
        cov = set(covered) | set(public)
        missing = [t for t in tasks if t not in cov]
        not_in_exam = [t for t in tasks if t not in exam]
        if not_in_exam:
            print(f"WARN: {name}: {not_in_exam} 不在考场 task 集内", file=sys.stderr)
        if missing:
            partial = True
            print(f"COVERAGE {len(cov & set(tasks))}/{len(tasks)} "
                  f"missing={','.join(missing)}  model={name}")
        else:
            print(f"COVERAGE {len(tasks)}/{len(tasks)}  model={name} OK")

    if partial and not a.allow_partial:
        print("\nREFUSE: 存在缺格模型。补 ckpt 或改 tasks；"
              "确需部分跑请加 --allow-partial。", file=sys.stderr)
        return 2
    print("COVERAGE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
