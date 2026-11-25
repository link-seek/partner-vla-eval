#!/usr/bin/env python3
"""校准行生成器：把「我们的 aggregate」和「官方榜单快照」拼成一行可入表的对照。

为什么要有：
  ④ 校准跑出来的数要并进 docs/decks/calibration-2026-11-25.md。手工抄有三类错——
  抄错官方值、算错差值、漏标离群。这三件都是机械动作，就该由脚本做。

用法：
  # 从 aggregate 读（推荐：跑完直接生成，不碰手抄）
  python3 scripts/ci/calibration_row.py --entry sft:ACT --task click_bell \
      --aggregate /root/r01/act50/results/act/click_bell_aggregate.json

  # 手给 K/N
  python3 scripts/ci/calibration_row.py --entry sft:ACT --task click_bell --success 29 --n 50

  # 只看官方值（对齐/查数用）
  python3 scripts/ci/calibration_row.py --entry sft:ACT --task click_bell --official-only

  # 自检（进 run_all.py 的 calibration 门）
  python3 scripts/ci/calibration_row.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = ROOT / "docs/data/official/robotwin_leaderboard_2026-11-20.json"
BAND_PP = 4.0  # n=50 的噪声带（见校准表第四节）：超出标"离群"


def load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text())


def official_task_name(task: str, tasks: list[str]) -> str:
    """click_bell -> Click Bell（官方用标题格式）。找不到就报错，不猜。"""
    want = task.strip().lower().replace("_", " ")
    for t in tasks:
        if t.lower().replace("_", " ") == want:
            return t
    raise SystemExit(f"官方榜单里没有 task {task!r}；候选：{tasks[:8]} …")


def official_value(snap: dict, entry_id: str, task: str, difficulty: str = "easy") -> tuple[float, str]:
    entries = {e["id"]: e for e in snap["entries"]}
    if entry_id not in entries:
        ids = ", ".join(sorted(entries)[:6])
        raise SystemExit(f"榜单里没有 entry {entry_id!r}；例如：{ids} …")
    e = entries[entry_id]
    name = official_task_name(task, snap["tasks"])
    idx = snap["tasks"].index(name)
    series = e.get(difficulty)
    if not series or idx >= len(series):
        raise SystemExit(f"{entry_id} 的 {difficulty} 列缺 {name}")
    return float(series[idx]), e["name"]


def read_aggregate(path: Path, require_distinct_seeds: bool = True) -> dict:
    """读 aggregate，返回 success/n/errors/seed 数，并拒绝"重复种子的假 n"。

    兼容两种格式：
      - harness aggregate：{tasks:[{episodes:[{seed,metrics,...}], num_errors}]}
      - 报告摘要：{mean_success, n}（没有逐集信息，无法校验种子）

    2026-11-25 实测：episodes_per_task=50 + test_num=1 会把同一集跑 50 次，
    aggregate 照样给 mean_success=1.0，看起来像 50/50。种子数就是判据。
    """
    d = json.loads(path.read_text())
    seeds: list = []
    tasks = d.get("tasks")
    if isinstance(tasks, list):
        if len(tasks) != 1:
            raise SystemExit(f"{path} 含 {len(tasks)} 个 task；校准行只接受单 task aggregate")
        t = tasks[0]
        eps = t.get("episodes") or []
        n = int(t.get("num_episodes") or len(eps))
        success = sum(1 for e in eps if (e.get("metrics") or {}).get("success"))
        errors = int(t.get("num_errors") or 0) or sum(
            1 for e in eps if e.get("failure_reason") or e.get("failure_detail"))
        seeds = [e.get("seed") for e in eps if e.get("seed") is not None]
        if eps and n != len(eps):
            raise SystemExit(f"{path}: num_episodes={n} 与 episodes={len(eps)} 不一致")
    else:
        n = int(d.get("n") or 0)
        success = d.get("success")
        if success is None:
            mean = d.get("mean_success")
            if mean is None or not n:
                raise SystemExit(f"{path} 里没有 success 也没有 mean_success+n")
            success = round(float(mean) * n)
        success = int(success)
        errors = int(d.get("errors") or 0)
        seeds = [x for x in (d.get("seeds") or []) if x is not None]

    uniq = len(set(seeds))
    if require_distinct_seeds and seeds and uniq < n:
        raise SystemExit(
            f"{path}: 只有 {uniq} 个不同种子，却有 n={n} 集——"
            "同一集被重复跑（test_num/episodes_per_task 配反的典型症状）。"
            "确认后用 --allow-repeated-seeds 才能继续。")
    return {"success": success, "n": n, "errors": errors, "seeds": uniq,
            "seed_checked": bool(seeds)}


def fmt_row(task: str, success: int, n: int, official: float, errors: int, band: float) -> tuple[str, float]:
    ours = 100.0 * success / n if n else 0.0
    delta = ours - official
    flag = ""
    if abs(delta) > band:
        flag = " ← 离群" if delta < 0 else " ← 离群"
    note = f"{success}/{n}"
    if errors:
        note += f"，{errors} error"
    row = (f"| {task} | {ours:.0f}%（{note}） | {official:.0f}% | "
           f"**{delta:+.0f}pp**{flag} |")
    return row, delta


def selftest() -> int:
    snap = load_snapshot(DEFAULT_SNAPSHOT)
    fails = []

    def check(name, cond, detail=""):
        print(f"  {'ok  ' if cond else 'FAIL'} {name} {'' if cond else detail}")
        if not cond:
            fails.append(name)

    print("[官方快照锚点]")
    act, _ = official_value(snap, "sft:ACT", "click_bell")
    dp, _ = official_value(snap, "sft:DP", "click_bell")
    xv, _ = official_value(snap, "cotrain:X_VLA", "click_bell")
    check("ACT click_bell = 58", act == 58.0, f"实际 {act}")
    check("DP  click_bell = 54", dp == 54.0, f"实际 {dp}")
    check("X-VLA click_bell = 100", xv == 100.0, f"实际 {xv}")
    xvla = {e["id"]: e for e in snap["entries"]}["cotrain:X_VLA"]
    check("X-VLA easy_mean = 67.96", abs(xvla["easy_mean"] - 67.96) < 1e-9, xvla["easy_mean"])
    check("50 个 task", len(snap["tasks"]) == 50, len(snap["tasks"]))

    print("[任务名映射]")
    check("click_bell → Click Bell", official_task_name("click_bell", snap["tasks"]) == "Click Bell")
    check("place_phone_stand → Place Phone Stand",
          official_task_name("place_phone_stand", snap["tasks"]) == "Place Phone Stand")
    try:
        official_task_name("not_a_task", snap["tasks"])
        check("未知 task 应报错", False, "没抛")
    except SystemExit:
        check("未知 task 应报错", True)

    print("[行生成与离群标注]")
    row, d1 = fmt_row("click_bell", 29, 50, act, 0, BAND_PP)
    check("行含 58% 与 +0pp", "58%" in row and "+0pp" in row, row)
    check("29/50 与官方 58 差 ~0", abs(d1) < 1.0, d1)
    row2, d2 = fmt_row("place_empty_cup", 8, 50, 28.0, 0, BAND_PP)
    check("16 vs 28 标离群", "离群" in row2 and d2 == -12.0, row2)

    print("[aggregate 解析]")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.json"
        p.write_text(json.dumps({"mean_success": 0.58, "n": 50, "errors": 0}))
        a = read_aggregate(p)
        check("mean_success 反推 success", (a["success"], a["n"], a["errors"]) == (29, 50, 0), a)
        p.write_text(json.dumps({"success": 31, "n": 50, "errors": 2}))
        a = read_aggregate(p)
        check("显式 success 优先", (a["success"], a["n"], a["errors"]) == (31, 50, 2), a)

        def harness(seeds):
            return {"tasks": [{"episodes": [
                {"seed": s, "metrics": {"success": i % 2 == 0}} for i, s in enumerate(seeds)
            ], "num_errors": 0}]}

        p.write_text(json.dumps(harness([100000, 100001])))
        a = read_aggregate(p)
        check("harness 格式逐集统计", (a["success"], a["n"], a["seeds"]) == (1, 2, 2), a)

        p.write_text(json.dumps(harness([100000, 100000])))
        try:
            read_aggregate(p)
            check("重复种子必须拒绝", False, "没抛")
        except SystemExit as e:
            check("重复种子必须拒绝", "不同种子" in str(e), str(e))
        a = read_aggregate(p, require_distinct_seeds=False)
        check("允许时才放行", a["seeds"] == 1, a)

    if fails:
        print(f"\nFAILED: {len(fails)} -> {fails}")
        return 1
    print("\nALL OK")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", help="官方 entry id，如 sft:ACT / sft:DP / cotrain:X_VLA")
    ap.add_argument("--task", help="我们的 task id，如 click_bell")
    ap.add_argument("--success", type=int)
    ap.add_argument("--n", type=int)
    ap.add_argument("--aggregate", type=Path)
    ap.add_argument("--errors", type=int, default=0)
    ap.add_argument("--difficulty", default="easy", choices=["easy", "hard"])
    ap.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    ap.add_argument("--band", type=float, default=BAND_PP)
    ap.add_argument("--allow-small-n", action="store_true",
                    help="默认拒绝 n<10 的 aggregate（区间太宽，不能进表）")
    ap.add_argument("--allow-repeated-seeds", action="store_true",
                    help="默认拒绝「不同种子数 < 集数」的 aggregate（假 n）")
    ap.add_argument("--official-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.entry or not a.task:
        ap.error("--entry 和 --task 必填（或 --selftest）")

    snap = load_snapshot(a.snapshot)
    official, display = official_value(snap, a.entry, a.task, a.difficulty)
    if a.official_only:
        print(f"{display} · {a.task} · {a.difficulty} = {official:.0f}% "
              f"(board {snap['board']['updated']})")
        return 0

    errors = a.errors
    agg = None
    if a.aggregate:
        agg = read_aggregate(a.aggregate, require_distinct_seeds=not a.allow_repeated_seeds)
        success, n, errors = agg["success"], agg["n"], agg["errors"]
    elif a.success is not None and a.n:
        success, n = a.success, a.n
    else:
        ap.error("需要 --aggregate 或 --success + --n")

    if n < 10 and not a.allow_small_n:
        raise SystemExit(
            f"n={n} 太小（95% 区间半宽 >20pp），不作分数结论；"
            "确认只是查链路就用 --allow-small-n。")

    row, delta = fmt_row(a.task, success, n, official, errors, a.band)
    print(row)
    print()
    print(json.dumps({
        "entry": a.entry, "model": display, "task": a.task, "difficulty": a.difficulty,
        "ours": round(100.0 * success / n, 2) if n else None,
        "official": official, "delta_pp": round(delta, 2),
        "success": success, "n": n, "errors": errors,
        "distinct_seeds": (agg or {}).get("seeds"),
        "outlier": abs(delta) > a.band, "band_pp": a.band,
        "snapshot": str(a.snapshot.relative_to(ROOT)) if a.snapshot.is_relative_to(ROOT) else str(a.snapshot),
        "board_updated": snap["board"]["updated"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
