#!/usr/bin/env python3
"""协议版本门禁：让"这个数属于哪一版"由机器判定，不靠人记。

背景（2026-11-25）：
  · 仓库 0 tag / 0 release，`protocol` 字段有**三种写法**（`easy-demo_clean` /
    `demo_clean / seed 0` / `demo_clean / seed 0 / 400 steps`）
  · 报告的 `harness` 全是 `0.0.0`（上游没注入），等于没有版本
  → 于是"这 48/50 是哪套题集、哪个镜像、哪版权重跑出来的"只能靠翻 run 日志。

规则：
  1. 唯一真源 = `registry.exam.protocol_version`
  2. 每份报告、每个榜单（顶层 + 每条）都必须带 `protocol_version`
  3. robotwin 报告/榜单必须等于真源；其他考场标 `adhoc`（不是版本化协议，如实标注）
  4. 版本号变更条件写在 `registry.exam.protocol_version_rules`（bump 就冻结旧结果）
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = Path = pathlib.Path(__file__).resolve().parents[2]
REG = ROOT / "configs" / "registry" / "model-registry.json"
DATA = ROOT / "docs" / "data"
LB = ROOT / "leaderboard"
VER_RE = re.compile(r"^[a-z0-9]+-\d+\.\d+(\.\d+)?$|^adhoc$")

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


def main() -> int:
    exam = json.loads(REG.read_text())["exam"]
    pv = exam.get("protocol_version") or ""
    print("[真源] protocol_version =", pv or "(缺失)")
    check("registry 有 protocol_version", bool(pv))
    check("版本号格式合法", bool(VER_RE.match(pv)), pv)
    check("写了 bump 条件", bool(exam.get("protocol_version_rules")),
          "缺 protocol_version_rules（否则没人知道什么时候该升版本）")

    print("[报告] docs/data/*.json")
    reports = sorted(DATA.glob("*.json"))
    missing, mismatch = [], []
    for f in reports:
        d = json.loads(f.read_text())
        v = d.get("protocol_version")
        if not v:
            missing.append(f.name)
        elif "robotwin" in f.name and v != pv:
            mismatch.append(f"{f.name}: {v}")
        elif "robotwin" not in f.name and v != "adhoc":
            mismatch.append(f"{f.name}: 非 robotwin 应为 adhoc，实际 {v}")
    check(f"{len(reports)} 份报告都带 protocol_version", not missing, str(missing[:4]))
    check("robotwin 报告版本与真源一致（其他考场为 adhoc）", not mismatch, str(mismatch[:4]))

    print("[榜单] leaderboard/*.json（不含 schema）")
    lbs = [p for p in sorted(LB.glob("*.json")) if not p.name.endswith(".schema.json")]
    for f in lbs:
        d = json.loads(f.read_text())
        check(f"{f.name}: 顶层版本一致", d.get("protocol_version") == pv,
              f"实际 {d.get('protocol_version')!r}")
        bad = [e.get("task") or e.get("model") for e in d.get("entries", [])
               if e.get("protocol_version") != pv]
        check(f"{f.name}: 每条 entry 版本一致", not bad, str(bad[:4]))

    print("[附录] leaderboard/partial/*.json")
    for f in sorted((LB / "partial").glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("partial") is True and not d.get("protocol_version"):
            print(f"  WARN {f.name}: partial 未标 protocol_version（附录不强制，但建议补）")

    if fails:
        print(f"\nPROTOCOL FAIL: {len(fails)} 项")
        return 1
    print(f"\nPROTOCOL OK（{len(reports)} 报告 / {len(lbs)} 榜单，真源 {pv}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
