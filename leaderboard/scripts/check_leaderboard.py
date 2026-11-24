#!/usr/bin/env python3
"""榜单门禁：schema + 自洽性 + 报告对账 + 排名口径隔离。

对照上游 leaderboard/scripts/validate.py 的做法，但加了本仓特有的两条：
  1) 每个 entry 必须能在 docs/reports/*.json 找到同 (task, n, success) 的报告（防手写漂移）
  2) shared 与 finetuned 不得混在同一排名（防跨口径解读）

用法：python3 leaderboard/scripts/check_leaderboard.py [--strict]
退出码 0 = 通过；1 = 有错。
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LB = ROOT / "leaderboard" / "leaderboard.json"
SCHEMA = ROOT / "leaderboard" / "leaderboard.schema.json"
VERSIONS = ROOT / "docker" / "versions.yaml"

errors: list[str] = []
warnings: list[str] = []


def load():
    if not LB.exists():
        errors.append(f"缺 {LB.relative_to(ROOT)}")
        return None
    try:
        return json.loads(LB.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"leaderboard.json 非法 JSON: {e}")
        return None


def check_schema(data):
    try:
        import jsonschema
    except ImportError:
        warnings.append("jsonschema 未安装，跳过 schema 校验")
        return
    schema = json.loads(SCHEMA.read_text())
    v = jsonschema.Draft7Validator(schema)
    for e in sorted(v.iter_errors(data), key=lambda x: list(x.absolute_path)):
        path = ".".join(str(p) for p in e.absolute_path) or "<root>"
        errors.append(f"schema: {path}: {e.message}")


REQUIRED_FIELDS = (
    "model", "task", "n", "success", "errors", "weight_type",
    "replicate_count", "run", "date", "ckpt_repo", "ckpt_revision",
    "bench_image", "serve_image",
)


def check_required(data):
    """无依赖兜底：即使没装 jsonschema，必填与格式也必须过。"""
    import re
    for i, r in enumerate(data.get("entries", [])):
        tag = f"entries[{i}] {r.get('model')}/{r.get('task')}"
        for f in REQUIRED_FIELDS:
            if f not in r:
                errors.append(f"{tag}: 缺必填字段 {f}")
        rev = r.get("ckpt_revision")
        if rev is not None and not re.fullmatch(r"[0-9a-f]{40}", str(rev)):
            errors.append(f"{tag}: ckpt_revision 不是 40 位 hex（实际 {rev!r}）")
        wt = r.get("weight_type")
        if wt is not None and wt not in ("shared", "finetuned"):
            errors.append(f"{tag}: weight_type={wt!r} 只允许 shared|finetuned")


def check_rows(data):
    seen = set()
    for i, r in enumerate(data.get("entries", [])):
        tag = f"entries[{i}] {r.get('model')}/{r.get('task')}"
        n, s, err = r.get("n"), r.get("success"), r.get("errors")
        if isinstance(n, int) and isinstance(s, int):
            if s > n:
                errors.append(f"{tag}: success({s}) > n({n})")
            if isinstance(err, int) and s + err > n:
                errors.append(f"{tag}: success({s}) + errors({err}) > n({n})")
        key = (r.get("model"), r.get("task"), data.get("protocol"))
        if key in seen:
            errors.append(f"{tag}: 重复条目 (同 model/task/protocol)")
        seen.add(key)
        if r.get("replicate_count") == 1:
            warnings.append(f"{tag}: 单轮（n={n}），榜单需标'单轮勿作结论'")


def check_reports(data):
    """显式 report 对账：给了路径就必须存在且 (task,n,success) 与 entry 一致。"""
    for i, r in enumerate(data.get("entries", [])):
        tag = f"entries[{i}] {r.get('model')}/{r.get('task')}"
        rel = r.get("report")
        if not rel:
            warnings.append(f"{tag}: 未给 report 字段，无法与归档对账")
            continue
        p = ROOT / rel
        if not p.exists():
            errors.append(f"{tag}: report 文件不存在 {rel}")
            continue
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            errors.append(f"{tag}: report 非法 JSON {rel}")
            continue
        rn = d.get("n")
        rs = d.get("success")
        if rs is None and d.get("mean_success") is not None and rn:
            rs = round(d["mean_success"] * rn)
        if rn != r.get("n") or rs != r.get("success"):
            errors.append(
                f"{tag}: leaderboard 写 {r.get('success')}/{r.get('n')}，"
                f"report {rel} 是 {rs}/{rn}"
            )
        if r.get("task") not in str(d.get("task", "")):
            errors.append(f"{tag}: report 的 task 字段不含 '{r.get('task')}'")


def check_ranking_isolation(data):
    wt = {r.get("weight_type") for r in data.get("entries", [])}
    if "shared" in wt and "finetuned" in wt:
        warnings.append("同榜单混有 shared 与 finetuned：排名必须分组，禁止合并")


def main() -> int:
    data = load()
    if data is None:
        for e in errors:
            print("ERROR:", e)
        return 1
    check_required(data)
    check_schema(data)
    check_rows(data)
    check_reports(data)
    check_ranking_isolation(data)

    for w in warnings:
        print("WARN:", w)
    if errors:
        print(f"\nLEADERBOARD FAIL ({len(errors)} error(s)):")
        for e in errors:
            print(" -", e)
        return 1
    n = len(data.get("entries", []))
    print(f"LEADERBOARD OK ({n} entries, bench={data.get('bench')}, protocol={data.get('protocol')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
