#!/usr/bin/env python3
"""registry 门禁：verified 模型必须可复现（权重 pin revision、覆盖声明齐全）。

背景：`configs/registry/model-registry.json` 是全仓唯一模型真源，但此前没有任何结构校验。
表现过的两个事故：
  1) ckpt 只写 repo 名 → 预热永远拉 main，别人复现不出同一份权重
  2) 没有 covered_tasks → 按 5 task 排期，跑到第 3 个才发现只有 3 个头

用法：python3 scripts/check_registry.py
退出码：0 通过；1 有错
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "configs" / "registry" / "model-registry.json"

REQUIRED = ("family", "ckpt", "action_spec", "precision", "status", "bench_tag")
STATUSES = ("verified", "pending", "dropped", "blocked")
HEX40 = re.compile(r"^[0-9a-f]{40}$")

errors: list[str] = []
warnings: list[str] = []


def main() -> int:
    if not REG.exists():
        print(f"ERROR: 缺 {REG}", file=sys.stderr)
        return 1
    d = json.loads(REG.read_text())
    exam = d.get("exam", {})
    exam_tasks = exam.get("tasks") or []
    models = d.get("models") or {}
    if not models:
        errors.append("models 为空")

    for name, m in models.items():
        tag = f"models.{name}"
        for f in REQUIRED:
            if f not in m:
                errors.append(f"{tag}: 缺必填字段 {f}")
        st = m.get("status")
        if st is not None and st not in STATUSES:
            errors.append(f"{tag}: status={st!r} 不在 {STATUSES}")

        rev = m.get("ckpt_revision")
        if st == "verified":
            # 核心规则：verified（本仓已跑出数）必须能钉住权重
            if not rev:
                errors.append(f"{tag}: status=verified 但缺 ckpt_revision（weights 无法复现）")
            elif not HEX40.match(str(rev)):
                errors.append(f"{tag}: ckpt_revision 不是 40 位 hex（{rev!r}）")
            if not m.get("covered_tasks"):
                warnings.append(f"{tag}: verified 但未声明 covered_tasks（覆盖无法前置检查）")
            else:
                outside = [t for t in m["covered_tasks"] if t not in exam_tasks]
                if outside:
                    warnings.append(f"{tag}: covered_tasks 含考场外 task {outside}")
        else:
            if rev is not None and not HEX40.match(str(rev)):
                errors.append(f"{tag}: ckpt_revision 格式错（{rev!r}）")

    for w in warnings:
        print("WARN:", w)
    if errors:
        print(f"\nREGISTRY FAIL ({len(errors)} error(s)):")
        for e in errors:
            print(" -", e)
        return 1
    v = sum(1 for m in models.values() if m.get("status") == "verified")
    print(f"REGISTRY OK ({len(models)} models, {v} verified, exam tasks={len(exam_tasks)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
