#!/usr/bin/env python3
"""从 collect_matrix.sh 的 JSON 生成榜单文件（easy / hard 各一份）。

为什么要有脚本而不是手写：榜单里每一条都要带 ckpt_revision / run / n / success，
手写必然漏（2026-11-24 就出现过 leaderboard 写 45/50 而报告是 39/50）。
所有值都从"collected JSON + registry"取，取不到就拒绝生成。

用法：
  python3 scripts/data/make_leaderboard.py <collected.json> <easy|hard> \
      --run <run_id> [--out leaderboard/leaderboard.hard.json] [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "configs" / "registry" / "model-registry.json"

BENCH_IMAGE = "swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:0.8.0-ee-slim"
SHORT = {"x-vla-robotwin2": "xvla", "db-cogact": "cogact"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="+", help="一份或多份 collected JSON（多份=重复轮）")
    ap.add_argument("protocol", choices=["easy", "hard"])
    ap.add_argument("--run", required=True, help="GitHub Actions run id")
    ap.add_argument("--out", default=None)
    ap.add_argument("--date", default=str(date.today()))
    a = ap.parse_args()

    runs = [json.loads(Path(p).read_text()) for p in a.src]
    models = {r["model"] for r in runs}
    if len(models) != 1:
        print(f"多份输入必须是同一模型（拿到 {sorted(models)}）", file=sys.stderr)
        return 1
    model = runs[0]["model"]
    short = SHORT.get(model, model)

    reg = json.loads(REG.read_text())["models"].get(model)
    if reg is None:
        print(f"registry 里没有模型 {model}", file=sys.stderr)
        return 1
    rev = reg.get("ckpt_revision")
    if not rev or len(str(rev)) != 40:
        print(f"{model}: registry 缺 ckpt_revision（40-hex），拒绝生成榜单", file=sys.stderr)
        return 1

    proto_label = "easy-demo_clean" if a.protocol == "easy" else "hard-demo_randomized"
    out = {"last_updated": a.date, "bench": "robotwin", "protocol": proto_label, "entries": []}

    skipped = []
    all_tasks = sorted({t for r in runs for t in r["tasks"]})
    for task in all_tasks:
        per_run = [r["tasks"][task] for r in runs if r["tasks"].get(task, {}).get("status") != "missing"]
        if not per_run:
            skipped.append(task)
            continue
        if len(per_run) != len(runs):
            print(f"WARN {task}: 只有 {len(per_run)}/{len(runs)} 轮有数", file=sys.stderr)
        # 重复轮：合并样本（success/n 相加），并记录轮间极差
        n_sum = sum(x["n"] for x in per_run)
        ok_sum = sum(x["success"] for x in per_run)
        rates = [x["rate"] for x in per_run]
        t = {
            "n": n_sum, "success": ok_sum,
            "rate": round(ok_sum / max(1, n_sum), 4),
            "errors": sum(x["errors"] for x in per_run),
            "steps_avg": round(sum(x["steps_avg"] * x["n"] for x in per_run) / max(1, n_sum), 1),
            "steps_med": per_run[0]["steps_med"],
            "created_at": per_run[0].get("created_at"),
            "harness_version": per_run[0].get("harness_version"),
        }
        out["entries"].append({
            "model": model,
            "task": task,
            "n": t["n"],
            "success": t["success"],
            "errors": t["errors"],
            "weight_type": reg.get("weight_type", "shared"),
            "replicate_count": len(per_run),
            "run": str(a.run),
            "date": (t.get("created_at") or a.date)[:10],
            "ckpt_repo": (reg.get("ckpt_repo") or reg.get("ckpt") or "").split("/<")[0],
            "ckpt_revision": rev,
            "bench_image": BENCH_IMAGE,
            "serve_image": reg.get("serve_image", ""),
            "harness_version": t.get("harness_version") or None,
            "rate_min": min(rates) if len(rates) > 1 else None,
            "rate_max": max(rates) if len(rates) > 1 else None,
            "report": f"docs/data/{short}_robotwin-{task}-x50.json",
            **({"regime": reg["regime"]} if reg.get("regime") else {}),
        })

    if not out["entries"]:
        print("没有可用 task，拒绝生成空榜单（schema 要求 minItems=1）", file=sys.stderr)
        return 1

    dest = Path(a.out) if a.out else (ROOT / "leaderboard" / f"leaderboard.{a.protocol}.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")

    n = len(out["entries"])
    tot = sum(e["success"] for e in out["entries"])
    ne = sum(e["n"] for e in out["entries"])
    print(f"wrote {dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest} "
          f"({n} entries, {tot}/{ne} = {tot / ne * 100:.1f}%)")
    if skipped:
        print(f"  skipped (no aggregate): {','.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
