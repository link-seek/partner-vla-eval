#!/usr/bin/env python3
"""配置契约门禁（把两个"一类问题"的检查合成一处，避免一个事故一个脚本）。

两类契约，都是 2026-11-25 真实栽过的：

A) task 清单不许硬编码
   事故：ci_robotwin_full.sh 默认含 stack_blocks_two、collect_matrix.sh 含 place_phone_stand，
   两份都"跑得通"所以没人发现，代价是报告里少一格/多一格 MISSING。
   规则：一行里出现 ≥3 个 exam.tasks 的 task 名即红；清单唯一真源是 registry.exam.tasks。

B) serve yaml 必须满足 harness 的接口
   事故 1：顶层 `server: {port: 8021}` 被静默忽略 → 去绑默认 8000，撞上别的容器。
   事故 2：`args.left_arm_dim` 未在 `__init__` 声明 → jsonargparse `unrecognized arguments`。
   规则：顶层键 ⊆ {script,args,docker,extends}；args 键 ⊆ __init__ 参数；script 必须是镜像内路径。

两者都不需要 GPU/docker，纯静态判定，进 lint。
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "configs" / "registry" / "model-registry.json"
POLICY_PY = ROOT / "scripts" / "model_servers" / "robotwin_policy.py"

SCAN_DIRS = ["scripts", ".github/workflows"]
SUFFIXES = {".sh", ".bash", ".yml", ".yaml", ".py"}
SELF_ALLOW = {ROOT / "scripts/gates/check_contracts.py", ROOT / "scripts/data/bench_config.py"}

SERVE_GLOB = "configs/model_servers/serve-robotwin-*.yaml"
ALLOWED_TOP = {"script", "args", "docker", "extends"}
IMAGE_SCRIPT_PREFIX = "/opt/serve/"

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


# ----------------------------------------------------------------- A) task 清单
def check_task_list() -> None:
    print("[A) task 清单不硬编码]")
    tasks = json.loads(REGISTRY.read_text())["exam"]["tasks"]
    check("exam.tasks 可读", len(tasks) >= 3, f"只有 {len(tasks)} 个")
    hits: list[str] = []
    for d in SCAN_DIRS:
        for f in sorted((ROOT / d).rglob("*")):
            if f.suffix not in SUFFIXES or not f.is_file() or f in SELF_ALLOW:
                continue
            try:
                lines = f.read_text(errors="ignore").splitlines()
            except OSError:
                continue
            for no, line in enumerate(lines, 1):
                n = sum(1 for t in tasks if re.search(rf"\b{re.escape(t)}\b", line))
                if n >= 3:
                    hits.append(f"{f.relative_to(ROOT)}:{no}（{n} 个 task 名）")
    check("没有硬编码的 task 清单", not hits,
          "；".join(hits[:3]) + ("…" if len(hits) > 3 else "") + " → 用 scripts/data/bench_config.py tasks")


# ----------------------------------------------------------------- B) serve 契约
def init_kwargs(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "__init__":
                    a = fn.args
                    return {x.arg for x in (a.posonlyargs + a.args + a.kwonlyargs)} - {"self"}
    return set()


def check_serve_contract() -> None:
    print("[B) serve yaml ↔ 适配器签名]")
    kw = init_kwargs(POLICY_PY)
    check("能解析 __init__ 参数", len(kw) > 10, f"只有 {len(kw)} 个")
    for must in ("left_arm_dim", "right_arm_dim", "port", "policy", "task_name"):
        check(f"__init__ 声明 {must}", must in kw)

    all_yamls = sorted(ROOT.glob(SERVE_GLOB))
    files = [f for f in all_yamls
             if Path(str((yaml.safe_load(f.read_text()) or {}).get("script") or "")).name == "robotwin_policy.py"]
    check("找到自建适配器的 serve yaml", len(files) >= 2,
          f"{len(files)} 份（共匹配 {len(all_yamls)} 份；cogact 走上游 script 约定，不适用本规则）")

    for f in files:
        d = yaml.safe_load(f.read_text()) or {}
        top_bad = set(d) - ALLOWED_TOP
        check(f"{f.name}: 顶层键合法", not top_bad,
              f"多了 {sorted(top_bad)}（server.port 不是合法键，端口走 args.port 或 --address）")
        script = str(d.get("script") or "")
        check(f"{f.name}: script 在镜像内", script.startswith(IMAGE_SCRIPT_PREFIX),
              f"{script!r}（挂载的本地文件不可复现）")
        args = d.get("args") or {}
        unknown = set(args) - kw
        check(f"{f.name}: args 都是构造参数", not unknown, f"未声明 {sorted(unknown)}")

    print("[B-反例：必须被拦住]")
    with tempfile.TemporaryDirectory() as td:
        cases = {
            "顶层 server.port": {"script": "/opt/serve/robotwin_policy.py",
                                 "server": {"port": 8021}, "args": {"policy": "act"}},
            "未声明 args": {"script": "/opt/serve/robotwin_policy.py",
                            "args": {"policy": "dp", "bogus_arg": 1}},
            "相对 script": {"script": "scripts/model_servers/robotwin_policy.py",
                            "args": {"policy": "act"}},
        }
        for name, data in cases.items():
            p = Path(td) / "x.yaml"
            p.write_text(yaml.safe_dump(data))
            d = yaml.safe_load(p.read_text())
            if name == "顶层 server.port":
                bad = bool(set(d) - ALLOWED_TOP)
            elif name == "未声明 args":
                bad = bool(set(d["args"]) - kw)
            else:
                bad = not str(d["script"]).startswith(IMAGE_SCRIPT_PREFIX)
            check(f"反例 {name} 被拦住", bad)


def main() -> int:
    check_task_list()
    print()
    check_serve_contract()
    if fails:
        print(f"\nCONTRACTS FAIL: {len(fails)} 项 -> {fails}")
        return 1
    print("\nCONTRACTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
