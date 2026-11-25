#!/usr/bin/env python3
"""第 2 类基础设施的登记门禁。

规则来源：CONTRIBUTING.md 第三节。

为什么需要（2026-11-25 的真实教训）：
  - 仓里攒了 7 个"只做一次"的 workflow（诊断/探针/一次性修复），
    它们没有可执行引用、30 天没动，却会一直占着 Actions 目录、消耗 review 注意力；
  - 同时有一批配置是**靠参数引用**的（`run_yaml` / `serve_yaml` / build-arg），
    grep 看起来"零引用"，差点被当成垃圾删掉（`run-libero-spatial50.yaml` 就是）。

所以判定不能靠 grep，必须有一张登记表：
  workflows: kind ∈ {routine, rare}（**one-off 禁止进 main**，见 CONTRIBUTING 第二节）
  configs:   靠参数引用的登记为 option，永不按时间删

本门禁只做静态校验，不需要 GPU / 网络。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
INV = ROOT / "scripts" / "gates" / "infra-inventory.json"
WF_DIR = ROOT / ".github" / "workflows"
ALLOWED_KINDS = {"routine", "rare"}

fails: list[str] = []
warns: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


def main() -> int:
    inv = json.loads(INV.read_text())
    declared: dict = inv.get("workflows") or {}

    actual = {p.stem: p for p in WF_DIR.glob("*.yml")}
    print(f"[workflows] 实际 {len(actual)} 个，登记 {len(declared)} 个")

    unregistered = sorted(set(actual) - set(declared))
    check("每个 workflow 都已登记", not unregistered,
          f"未登记 {unregistered} → 在 scripts/gates/infra-inventory.json 里加 kind")

    stale = sorted(set(declared) - set(actual))
    check("清单里没有已删除的条目", not stale,
          f"残留 {stale} → 删掉这些条目（清单腐化会让门禁失效）")

    bad_kind = {k: v.get("kind") for k, v in declared.items()
                if v.get("kind") not in ALLOWED_KINDS}
    check("kind 只有 routine / rare", not bad_kind,
          f"{bad_kind}（one-off 请放分支，不要进 main）")

    no_owner = {k: v for k, v in declared.items()
                if v.get("kind") == "rare" and not (v.get("owner") and v.get("when"))}
    check("rare 类必须有 owner + when（否则没人知道何时用）", not no_owner, str(list(no_owner)))

    print("[workflows] 每个文件必须有 name:")
    noname = [n for n, p in actual.items()
              if not re.search(r"^name:\s*\S", p.read_text(errors="ignore"), re.M)]
    check("workflow 都有 name", not noname, str(noname))

    print("[configs] 选项型配置（靠参数引用，不许按时间删）")
    options: dict = (inv.get("configs") or {}).get("option") or {}
    missing = [p for p in options if not (ROOT / p).exists()]
    check("登记的 option 配置都存在", not missing, f"不存在 {missing}")

    # 规模哨兵：登记数暴增/骤降通常意味着有人绕过流程直接塞东西
    check("workflow 数量在合理区间（<= 40）", len(actual) <= 40, f"当前 {len(actual)}")

    for w in warns:
        print(f"  WARN {w}")

    if fails:
        print(f"\nINFRA FAIL: {len(fails)} 项")
        return 1
    print(f"\nINFRA OK（workflow {len(actual)}：routine "
          f"{sum(1 for v in declared.values() if v.get('kind') == 'routine')} / rare "
          f"{sum(1 for v in declared.values() if v.get('kind') == 'rare')}；option 配置 {len(options)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
