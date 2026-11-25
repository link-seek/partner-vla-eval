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
LB_GLOB = "leaderboard/leaderboard*.json"   # easy / hard 各一份，逐个校验
PARTIAL_GLOB = "leaderboard/partial/*.json"  # 未跑满的结果，只进附录
REGISTRY = ROOT / "configs" / "registry" / "model-registry.json"
PROTO_EXPECT = {"leaderboard.json": None}   # 文件名 → 期望 protocol 前缀（None=不校验）
SCHEMA = ROOT / "leaderboard" / "leaderboard.schema.json"
VERSIONS = ROOT / "docker" / "versions.yaml"

errors: list[str] = []
warnings: list[str] = []

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


def check_schema(data):
    """JSON Schema 校验（装了 jsonschema 才做；没装由 check_required 兜底）。"""
    try:
        import jsonschema
    except ImportError:
        warnings.append("jsonschema 未安装，跳过 schema 校验（check_required 已兜底必填）")
        return
    schema = json.loads(SCHEMA.read_text())
    v = jsonschema.Draft7Validator(schema)
    for e in sorted(v.iter_errors(data), key=lambda x: list(x.absolute_path)):
        path = ".".join(str(p) for p in e.absolute_path) or "<root>"
        errors.append(f"schema: {path}: {e.message}")


def expected_n() -> int:
    """协议目标集数（registry.exam.episodes）。榜单必须满格才进排名。"""
    try:
        return int(json.loads(REGISTRY.read_text())["exam"]["episodes"])
    except Exception:
        return 50


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
        exp = expected_n()
        if isinstance(n, int) and n != exp and not data.get("allow_partial"):
            errors.append(
                f"{tag}: n={n} 不等于协议目标 {exp}（未跑满的结果只能放 leaderboard/partial/，"
                "并标 partial: true；否决理由见 decisions-retention-partial-regression.md 决策 2）"
            )

        rc = r.get("replicate_count")
        if rc == 1:
            warnings.append(f"{tag}: 单轮（n={n}），榜单需标'单轮勿作结论'")
        elif isinstance(rc, int) and rc > 1:
            # A5：多轮必须有轮间极差，否则"方差"无法复核
            if r.get("rate_min") is None or r.get("rate_max") is None:
                errors.append(f"{tag}: replicate_count={rc} 但缺 rate_min/rate_max（方差不可查）")


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
        # 一份报告同时存 Easy 与 Hard：按榜单协议取对应字段。
        # 不看 protocol 会拿 Easy 的 success 去比 Hard 的条目，必然误报
        # （2026-11-24 预演实测）。
        proto = str(data.get("protocol", ""))
        if proto.startswith("hard"):
            rn = d.get("hard_n")
            rs = d.get("hard_success_count")
        else:
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
    """B2：同一 protocol 内不允许 shared 与 finetuned 混排（会被误读成一个排名）。

    确需同文件并列时，在顶层加 "ranked_separately": true 显式声明已分组。
    """
    wt = {r.get("weight_type") for r in data.get("entries", [])}
    if "shared" in wt and "finetuned" in wt:
        if data.get("ranked_separately") is True:
            warnings.append("shared 与 finetuned 混放，已声明 ranked_separately=true（需分别排名）")
        else:
            errors.append(
                "同榜单混有 shared 与 finetuned 且未声明 ranked_separately："
                "会被误读为一个排名，请拆分文件或加 \"ranked_separately\": true"
            )


def load_file(path: Path):
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{path.name} 非法 JSON: {e}")
        return None


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", help="只校验指定榜单文件（可多次；默认扫 leaderboard/leaderboard*.json）")
    args = ap.parse_args()

    if args.file:
        files = [Path(f) for f in args.file]
    else:
        files = sorted(f for f in ROOT.glob(LB_GLOB) if not f.name.endswith(".schema.json"))
    if not files:
        errors.append(f"没有找到任何榜单文件（{LB_GLOB}）")
        for e in errors:
            print("ERROR:", e)
        return 1
    rc = 0
    for f in files:
        try:
            shown = f.relative_to(ROOT)
        except ValueError:
            shown = f          # 预演时可指向仓外文件
        print(f"-- {f.name} ({shown})")
        data = load_file(f)
        if data is None:
            rc = 1
            continue
        check_required(data); check_schema(data); check_rows(data); check_reports(data); check_ranking_isolation(data)
        if errors:
            rc = 1
        else:
            print(f"   OK ({len(data.get('entries', []))} entries, protocol={data.get('protocol')})")
    # 附录目录：必须是 partial 且带 n_target，避免被当正式数
    for pf in sorted(ROOT.glob(PARTIAL_GLOB)):
        try:
            pd = json.loads(pf.read_text())
        except json.JSONDecodeError:
            errors.append(f"partial/{pf.name}: 非法 JSON")
            continue
        if pd.get("partial") is not True:
            errors.append(f"partial/{pf.name}: 缺 partial: true（附录文件必须显式标记）")
        if not pd.get("n_target"):
            errors.append(f"partial/{pf.name}: 缺 n_target（无法说明离满格差多少）")

    for w in warnings:
        print("WARN:", w)
    if errors:
        print(f"\nLEADERBOARD FAIL ({len(errors)} error(s)):")
        for e in errors:
            print(" -", e)
        return 1
    print(f"LEADERBOARD OK ({len(files)} file(s))")
    return rc


if __name__ == "__main__":
    sys.exit(main())
