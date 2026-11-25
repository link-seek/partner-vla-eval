#!/usr/bin/env python3
"""从 collect_matrix.sh 的 JSON 生成/更新 docs/data 的逐 task 报告。

两种模式：
  easy  —— 新建报告（含 success / mean_success / steps）
  hard  —— 写进同一份报告的 hard_success 与 gap（Easy − Hard），并把 protocol 标清楚

为什么这么设计：A2 的教训是"报告里的版本/数字不许手写"。所以这里所有数值都从 aggregate 来，
报告里只允许出现 aggregate 里有的数；缺失就写 null，不猜。

两种模式之外还有一个维护模式：
  --backfill —— 给历史报告补 stats/hard_stats（只由报告自带的 success/n 推出，幂等）

用法：
  python3 scripts/data/gen_reports.py <collected.json> <easy|hard> [out_dir]
  python3 scripts/data/gen_reports.py --backfill [glob]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_HINT = "https://github.com/link-seek/partner-vla-eval/actions"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stats import summarize  # noqa: E402


def protocol_version() -> str:
    """协议版本唯一真源：registry.exam.protocol_version。"""
    reg = json.loads((ROOT / "configs" / "registry" / "model-registry.json").read_text())
    return reg["exam"]["protocol_version"]


def model_dir_name(model: str) -> str:
    return {"x-vla-robotwin2": "xvla", "db-cogact": "cogact"}.get(model, model)


def backfill(argv: list[str]) -> int:
    """给历史报告补 stats / hard_stats（幂等；数值只由 success/n 推出，不猜）。"""
    pattern = argv[0] if argv else "docs/data/*.json"
    files = sorted(ROOT.glob(pattern))
    changed = skipped = 0
    for p in files:
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            skipped += 1
            continue
        todo = []
        if not d.get("protocol_version"):
            # robotwin 报告属于主协议；libero/calvin 的临时 smoke 不是版本化协议，标 adhoc（诚实而非编造）
            d["protocol_version"] = protocol_version() if "robotwin" in p.name else "adhoc"
            todo.append(("protocol_version", None))
        if isinstance(d.get("success"), int) and isinstance(d.get("n"), int) and not d.get("stats"):
            todo.append(("stats", d["success"]))
        if isinstance(d.get("hard_success"), (int, float)) and isinstance(d.get("n"), int) and not d.get("hard_stats"):
            todo.append(("hard_stats", round(d["hard_success"] * d["n"])))
        if not todo:
            continue
        for key, k in todo:
            if key == "protocol_version":
                continue          # 上面已直接写入
            d[key] = summarize(k, d["n"])
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        changed += 1
        print(f"  补 {'/'.join(t[0] for t in todo):12s} {p.name}")
    print(f"[backfill] 补 {changed} 份，跳过 {skipped} 份（幂等：已有 stats 不动）")
    return 0


def main() -> int:
    if sys.argv[1:2] == ["--backfill"]:
        return backfill(sys.argv[2:])
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
                "stats": summarize(t["success"], t["n"]),
                "hard_success": None, "gap": None,
                "note": "Easy only；Hard 待补（跑完由 gen_reports.py --hard 回填）。",
                "report_version": "v1 (docs/tutorial/leaderboard.md)",
                "protocol_version": protocol_version(),
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
            rep["hard_stats"] = summarize(t["success"], t["n"])
            if rep.get("protocol_version") != protocol_version():
                # 若旧报告没有版本字段，按当前协议补；已有且不同则保留（说明是不同协议的历史结果）
                rep.setdefault("protocol_version", protocol_version())
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
