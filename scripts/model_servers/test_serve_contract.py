#!/usr/bin/env python3
"""serve 配置与适配器签名的契约测试（零依赖、不需要 GPU、不需要 docker，进 lint）。

为什么要有：2026-11-25 一天之内在同一处栽了两次，两次都是**静默失败**——
  1) serve yaml 写成顶层 `server: {port: 8021}`，harness 只认 `args.port` / `--address`
     → 端口被忽略，去绑默认 8000，撞上别的容器：`OSError: address already in use`；
  2) yaml 的 `args.left_arm_dim` 没在 `__init__` 里声明
     → jsonargparse 报 `unrecognized arguments: --args.left_arm_dim=6`。
两者都只有在真跑、真占卡之后才暴露。而它们其实是**纯静态可判定**的：
  - 顶层键只有 script / args / docker / extends
  - args 的每个键必须是构造参数（harness 内省 __init__ 生成 --args.*）
所以用 AST + YAML 解析就能在提交前拦住。

规则来源：`vla-eval serve --help` 的原文
  "The config YAML must contain: script / args (passed to the server class __init__)"
  "jsonargparse maps args.* onto the class signature with full type validation"
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY_PY = ROOT / "scripts" / "model_servers" / "robotwin_policy.py"
SERVE_GLOB = "configs/model_servers/serve-robotwin-*.yaml"

ALLOWED_TOP = {"script", "args", "docker", "extends"}
IMAGE_SCRIPT_PREFIX = "/opt/serve/"     # 适配器必须烘进镜像，不能靠本地挂载（否则不可复现）

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


def init_kwargs(path: Path) -> set[str]:
    """取 RobotWinPolicy.__init__ 的显式参数名（含 keyword-only）。"""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "__init__":
                    a = fn.args
                    names = [x.arg for x in (a.posonlyargs + a.args + a.kwonlyargs)]
                    return {n for n in names if n != "self"}
    return set()


def load_yaml(p: Path) -> dict:
    return yaml.safe_load(p.read_text()) or {}


def main() -> int:
    print("[适配器签名]")
    kw = init_kwargs(POLICY_PY)
    check("能解析到 __init__ 参数", len(kw) > 10, f"只有 {len(kw)} 个")
    # 两个最容易漏的：DP 要它们算 action_dim；port 决定绑哪个端口
    for must in ("left_arm_dim", "right_arm_dim", "port", "policy", "task_name"):
        check(f"__init__ 声明了 {must}", must in kw)

    print("[serve yaml 契约]")
    # 只校验指向我们自建适配器的 yaml（robotwin_policy.py）。
    # serve-robotwin-cogact.yaml 走的是上游自带的 dexbotic/cogact.py，约定不同，不适用本规则。
    all_yamls = sorted(ROOT.glob(SERVE_GLOB))
    files = [f for f in all_yamls
             if Path(str(load_yaml(f).get("script") or "")).name == "robotwin_policy.py"]
    check("找到自建适配器的 serve yaml", len(files) >= 2,
          f"{len(files)} 份（全部匹配 {len(all_yamls)} 份）")
    for f in files:
        d = load_yaml(f)
        name = f.name
        top = set(d)
        bad_top = top - ALLOWED_TOP
        check(f"{name}: 无非法顶层键", not bad_top,
              f"多了 {sorted(bad_top)}（只允许 {sorted(ALLOWED_TOP)}；"
              "注意 server.port 不是合法键，端口走 args.port 或 --address）")
        check(f"{name}: 有 script", isinstance(d.get("script"), str))
        script = str(d.get("script") or "")
        check(f"{name}: script 指向镜像内路径", script.startswith(IMAGE_SCRIPT_PREFIX),
              f"实际 {script!r}（必须 {IMAGE_SCRIPT_PREFIX}… ，挂载的本地文件不可复现）")
        args = d.get("args") or {}
        unknown = set(args) - kw
        check(f"{name}: args 全部是构造参数", not unknown,
              f"未声明 {sorted(unknown)}（harness 会报 unrecognized arguments）")
        # 文件名与 policy 一致，避免 act/dp 抄串
        expect = "act" if "act" in name else ("dp" if "dp" in name else None)
        if expect:
            check(f"{name}: policy={expect}", args.get("policy") == expect, f"实际 {args.get('policy')!r}")

    print("[反例：这些必须被拦住]")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        bad1 = Path(td) / "b1.yaml"
        bad1.write_text(yaml.safe_dump({"script": "/opt/serve/robotwin_policy.py",
                                        "server": {"port": 8021}, "args": {"policy": "act"}}))
        d = load_yaml(bad1)
        check("顶层 server.port 被判为非法键", bool(set(d) - ALLOWED_TOP), str(sorted(d)))

        bad2 = Path(td) / "b2.yaml"
        bad2.write_text(yaml.safe_dump({"script": "/opt/serve/robotwin_policy.py",
                                        "args": {"policy": "dp", "bogus_arg": 1}}))
        d = load_yaml(bad2)
        check("未声明的 args.bogus_arg 被拦住", bool(set(d["args"]) - kw), str(sorted(d["args"])))

        bad3 = Path(td) / "b3.yaml"
        bad3.write_text(yaml.safe_dump({"script": "scripts/model_servers/robotwin_policy.py",
                                        "args": {"policy": "act"}}))
        d = load_yaml(bad3)
        check("相对 script 路径被拦住（不可复现）", not str(d["script"]).startswith(IMAGE_SCRIPT_PREFIX))

    if fails:
        print(f"\nFAILED: {len(fails)} -> {fails}")
        return 1
    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
