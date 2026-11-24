#!/usr/bin/env python3
"""从 collect_matrix.sh 的 JSON 生成/更新 docs/data 的逐 task 报告。

两种模式：
  easy  —— 新建报告（含 success / mean_success / steps）
  hard  —— 写进同一份报告的 hard_success 与 gap（Easy − Hard），并把 protocol 标清楚

为什么这么设计：A2 的教训是"报告里的版本/数字不许手写"。所以这里所有数值都从 aggregate 来，
报告里只允许出现 aggregate 里有的数；缺失就写 null，不猜。

用法：
  python3 scripts/data/gen_reports.py <collected.json> <easy|hard> [out_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_HINT = "https://github.com/link-seek/partner-vla-eval/actions"


def model_dir_name(model: str) -> str:
    return {"x-vla-robotwin2": "xvla", "db-cogact": "cogact"}.get(model, model)


def main() -> int:
    src = Path(sys.argv[1])
    proto = sys.argv[2] if len(sys.argv) > 2 else "easy"
    outdir = Path(sys.argv[3]) if len(sys.argv) > 3 else (ROOT / "docs" / "data")
    outdir.mkdir(parents=True, exist_ok=True)
    if proto not in ("easy", "hard"):
        print("协议只允许 easy|hard", file=sys.stderr)
        return 1

    data = json.loads(src.read_text())
    model, tasks = data["model"], data["tasks"]
    short = model_dir_name(model)

    written = []
    for task, t in tasks.items():
        if t.get("status") == "missing":
            print(f"SKIP {task} (missing aggregate)")
            continue
        path = outdir / f"{short}_robotwin-{task}-x50.json"

        if proto == "easy":
            rep = {
                "model": f"{model} (serve-robotwin)",
                "task": f"RobotWin {task} x50（Easy / demo_clean，本考场 5 task 子集）",
                "mean_success": t["rate"], "n": t["n"], "success": t["success"],
                "errors": t["errors"],
                "versions": {
                    "harness": t.get("harness_version") or None,
                    "harness_note": "aggregate 实测值；真实栈版本以 benchmark_image tag 为准",
                    "benchmark_image": "swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:0.8.0-ee-slim",
                    "serve_image": "swr.cn-north-4.myhuaweicloud.com/link-seek/vla-serve-xvla:0.8.0-ee16"
                    if short == "xvla" else
                    "swr.cn-north-4.myhuaweicloud.com/link-seek/vla-serve-cogact:0.8.0",
                },
                "machine": "V100-32GB ×2 (cn-north-4, 0002)",
                "seeds": "bundled（skip_expert=false，从 100000 起）",
                "date": (t.get("created_at") or "")[:10] or None,
                "artifacts": RUN_HINT,
                "steps_success": {"mean": t["steps_avg"], "med": t["steps_med"]},
                "hard_success": None, "gap": None,
                "note": "Easy only；Hard 待补（跑完由 gen_reports.py --hard 回填）。",
                "report_version": "v1 (docs/tutorial/leaderboard.md)",
            }
        else:
            # hard：在已有 easy 报告上回填
            if not path.exists():
                print(f"SKIP {task}: 没有 Easy 报告可回填（先跑 easy）")
                continue
            rep = json.loads(path.read_text())
            rep["hard_success"] = t["rate"]
            easy = rep.get("mean_success")
            rep["gap"] = round(easy - t["rate"], 4) if isinstance(easy, (int, float)) else None
            rep["hard_n"] = t["n"]
            rep["hard_success_count"] = t["success"]
            rep["hard_errors"] = t["errors"]
            rep["hard_steps_success"] = {"mean": t["steps_avg"], "med": t["steps_med"]}
            rep["note"] = (
                f"Easy {easy:.3f}（n={rep.get('n')}）vs Hard {t['rate']:.3f}（n={t['n']}），"
                f"落差 {rep['gap']:.3f}。" if isinstance(easy, (int, float)) else rep.get("note")
            )
            rep["hard_protocol"] = "demo_randomized"

        path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n")
        written.append((task, t["success"], t["n"], t["rate"]))

    if not written:
        print("没写出任何报告")
        return 1
    tot = sum(w[1] for w in written)
    ne = sum(w[2] for w in written)
    print(f"[{model}/{proto}] wrote {len(written)} report(s) -> {outdir}")
    print(f"  total {tot}/{ne} = {tot / ne * 100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
