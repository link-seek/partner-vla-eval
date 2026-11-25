#!/usr/bin/env python3
"""镜像清单门禁（第 2 类：让"我们维护几个镜像"只有一个答案）。

背景（2026-11-25 实测）：
  10 个 Dockerfile / 15 个真实 SWR tag / registry 只记 6 条 —— 三套口径互不一致。
  原因不是疏忽，是结构性的：
    · 一个 Dockerfile 靠 build-arg/POLICY 出多个 tag（1→3）
    · 基座 tag 是 workflow 的**输入**，代码里写不死
    · 镜像推上去不会自己消失（代码删了 workflow，SWR 里还在）
  所以清单必须以镜像仓库为准，且由门禁保证"清单 ↔ 真源"一致。

模式：
  默认（静态）：清单自洽 + 与 model-registry 交叉校验，不需要网络/GPU
  --remote   ：逐个向 SWR 解析 digest 并比对（需要 docker + SWR 登录，在能访问 SWR 的机器上跑）

用法：
  python3 scripts/gates/check_images.py
  python3 scripts/gates/check_images.py --remote
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
IMAGES = ROOT / "configs" / "registry" / "image-registry.json"
MODELS = ROOT / "configs" / "registry" / "model-registry.json"
KINDS = {"bench", "serve", "tool"}
STATUSES = {"active", "retained"}
# retained = 历史版本，明确保留（不删），但不得被新结果引用
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

fails: list[str] = []
warns: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


def main() -> int:
    remote = "--remote" in sys.argv
    reg = json.loads(IMAGES.read_text())
    models = json.loads(MODELS.read_text())
    images = reg["images"]

    print(f"[清单] {len(images)} 个")
    refs = [i["ref"] for i in images]
    check("ref 不重复", len(refs) == len(set(refs)))
    check("声明数量与条目数一致", reg.get("count") == len(images))

    for i in images:
        r = i["ref"]
        check(f"{r}: digest 格式", bool(DIGEST_RE.match(i.get("digest", ""))), i.get("digest"))
        check(f"{r}: kind 合法", i.get("kind") in KINDS, i.get("kind"))
        check(f"{r}: status 合法", i.get("status") in STATUSES, i.get("status"))
        df = ROOT / i.get("dockerfile", "")
        check(f"{r}: Dockerfile 存在", df.exists(), str(df))
        wf = i.get("workflow")
        if wf:
            check(f"{r}: workflow 存在", (ROOT / wf).exists(), wf)
        if i.get("status") == "retained":
            check(f"{r}: retained 不得被模型引用", not i.get("used_by"), "retained 还被引用")

    print("[交叉校验] model-registry ↔ 镜像清单")
    by_ref = {i["ref"].split(":")[0] + ":" + i["ref"].split(":", 1)[1]: i for i in images}
    for key, m in models["models"].items():
        img = m.get("serve_image")
        dig = m.get("serve_image_digest")
        if not img:
            continue
        short = img.replace(reg["registry"] + "/", "")
        entry = by_ref.get(short)
        check(f"{key}: serve_image 在清单里", entry is not None, short)
        if entry and dig:
            check(f"{key}: digest 与清单一致", entry["digest"] == dig,
                  f"清单 {entry['digest'][:20]}… vs registry {dig[:20]}…")
        if entry and entry.get("mutable"):
            check(f"{key}: 不得引用可变 tag", False,
                  f"{short} 是 mutable（每次 push main 重打），身份必须以 sha tag 为准")

    bench_dig = (models.get("exam") or {}).get("bench_image_digest")
    bench = [i for i in images if i["kind"] == "bench" and i["status"] == "active"]
    check("exam.bench_image_digest 命中 active 基座", any(b["digest"] == bench_dig for b in bench),
          f"{bench_dig[:20] if bench_dig else None}…")
    check("active 基座只有一个", len(bench) == 1, f"{len(bench)} 个")

    print("[清单健康]")
    active = sum(1 for i in images if i["status"] == "active")
    retained = len(images) - active
    print(f"  active {active} / retained {retained} / mutable {sum(1 for i in images if i.get('mutable'))}")
    for i in images:
        if i["status"] == "retained":
            warns.append(f"{i['ref']} 标为 retained：明确保留（不删），禁止被新结果引用")

    if remote:
        print("[远端校验] 逐个向 SWR 解析 digest")
        for i in images:
            ref = f"{reg['registry']}/{i['ref']}"
            r = subprocess.run(
                ["docker", "buildx", "imagetools", "inspect", "--format", "{{.Manifest.Digest}}", ref],
                capture_output=True, text=True)
            got = (r.stdout or "").strip()
            if not got:
                check(f"{i['ref']}: 远端可解析", False, (r.stderr or "").strip()[:120])
                continue
            if got == i["digest"]:
                print(f"  ok   {i['ref']}: {got[:20]}…")
            elif i.get("mutable"):
                warns.append(f"{i['ref']} 是可变 tag：清单 {i['digest'][:16]}… ≠ 远端 {got[:16]}…（下次同步即可）")
            else:
                check(f"{i['ref']}: 远端 digest 一致", False,
                      f"清单 {i['digest'][:20]}… vs 远端 {got[:20]}…")

    for w in warns:
        print(f"  WARN {w}")
    if fails:
        print(f"\nIMAGES FAIL: {len(fails)} 项")
        return 1
    print(f"\nIMAGES OK（{len(images)} 个：active {active} / retained {retained}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
