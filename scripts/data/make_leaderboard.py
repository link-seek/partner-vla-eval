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
    ap.add_argument("src")
    ap.add_argument("protocol", choices=["easy", "hard"])
    ap.add_argument("--run", required=True, help="GitHub Actions run id")
    ap.add_argument("--out", default=None)
    ap.add_argument("--date", default=str(date.today()))
    a = ap.parse_args()

    data = json.loads(Path(a.src).read_text())
    model = data["model"]
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
    for task, t in data["tasks"].items():
        if t.get("status") == "missing":
            skipped.append(task)
            continue
        out["entries"].append({
            "model": model,
            "task": task,
            "n": t["n"],
            "success": t["success"],
            "errors": t["errors"],
            "weight_type": reg.get("weight_type", "shared"),
            "replicate_count": 1,
            "run": str(a.run),
            "date": (t.get("created_at") or a.date)[:10],
            "ckpt_repo": (reg.get("ckpt_repo") or reg.get("ckpt") or "").split("/<")[0],
            "ckpt_revision": rev,
            "bench_image": BENCH_IMAGE,
            "serve_image": reg.get("serve_image", ""),
            "harness_version": t.get("harness_version") or None,
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
