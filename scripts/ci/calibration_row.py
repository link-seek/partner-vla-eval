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


def read_aggregate(path: Path) -> tuple[int, int, int]:
    """返回 (success, n, errors)。兼容 mean_success 无量级 success 的报告。"""
    d = json.loads(path.read_text())
    n = int(d.get("n") or 0)
    success = d.get("success")
    if success is None:
        mean = d.get("mean_success")
        if mean is None or not n:
            raise SystemExit(f"{path} 里没有 success 也没有 mean_success+n")
        success = round(float(mean) * n)
    return int(success), n, int(d.get("errors") or 0)


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
        check("mean_success 反推 success", read_aggregate(p) == (29, 50, 0), read_aggregate(p))
        p.write_text(json.dumps({"success": 31, "n": 50, "errors": 2}))
        check("显式 success 优先", read_aggregate(p) == (31, 50, 2), read_aggregate(p))

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
    if a.aggregate:
        success, n, errors = read_aggregate(a.aggregate)
    elif a.success is not None and a.n:
        success, n = a.success, a.n
    else:
        ap.error("需要 --aggregate 或 --success + --n")

    row, delta = fmt_row(a.task, success, n, official, errors, a.band)
    print(row)
    print()
    print(json.dumps({
        "entry": a.entry, "model": display, "task": a.task, "difficulty": a.difficulty,
        "ours": round(100.0 * success / n, 2) if n else None,
        "official": official, "delta_pp": round(delta, 2),
        "success": success, "n": n, "errors": errors,
        "outlier": abs(delta) > a.band, "band_pp": a.band,
        "snapshot": str(a.snapshot.relative_to(ROOT)) if a.snapshot.is_relative_to(ROOT) else str(a.snapshot),
        "board_updated": snap["board"]["updated"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
