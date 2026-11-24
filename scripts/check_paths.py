#!/usr/bin/env python3
"""路径存在性门禁：文档/workflow 里反引号引用的仓内路径必须真实存在。

背景：README:30 曾引用 `scripts/upstream/run_sharded.sh`（文件早已不存在），
README:43 写 v0.7.0（实际 0.8.0），"四类 workflow"（实际 24 个）——这类漂移
没有任何检查能发现。本脚本把"引用可达"变成 lint 门禁。

规则：
  - 只检查反引号里、以已知顶层目录开头的路径（scripts/ configs/ docker/ docs/ leaderboard/ .github/）
  - 跳过 URL、以 * 结尾的 glob、明显是示例的（含 < > { } 或 $）
  - 允许清单：scripts/paths_allowlist.txt（一行一个 glob，支持 * 通配），
    用于"计划中/上游仓路径"这类合法的未来引用

用法：python3 scripts/check_paths.py
退出码：0 通过；1 有断链
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = ROOT / "scripts" / "paths_allowlist.txt"
TOP_DIRS = ("scripts/", "configs/", "docker/", "docs/", "leaderboard/", ".github/")

# 反引号内容；只取第一段（避免 `a/b: 说明` 这种）
PAT = re.compile(r"`([^`\n]+)`")
# 允许出现但不当路径的形态
SKIP_PAT = re.compile(r"(https?://|\*|<|>|\{|\}|\$|\s{2,}|\.\.\.|…)")


def load_allowlist() -> list[str]:
    if not ALLOWLIST.exists():
        return []
    out = []
    for line in ALLOWLIST.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def iter_files():
    yield from ROOT.glob("*.md")
    yield from (ROOT / "docs").rglob("*.md")
    yield from (ROOT / ".github" / "workflows").glob("*.yml")
    yield from (ROOT / ".github" / "workflows").glob("*.yaml")


def main() -> int:
    patterns = load_allowlist()
    broken: list[tuple[str, str, int]] = []
    checked = 0

    for f in iter_files():
        if not f.exists():
            continue
        rel = f.relative_to(ROOT)
        try:
            lines = f.read_text().splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, 1):
            for m in PAT.finditer(line):
                cand = m.group(1).strip()
                if not cand.startswith(TOP_DIRS):
                    continue
                if SKIP_PAT.search(cand):
                    continue
                cand = cand.rstrip("/").split(":")[0].strip()
                if not cand or cand in TOP_DIRS:
                    continue
                checked += 1
                if allowed(cand, patterns):
                    continue
                if not (ROOT / cand).exists():
                    broken.append((str(rel), cand, lineno))

    if broken:
        print(f"PATH-DRIFT ({len(broken)} broken reference(s) out of {checked}):")
        for f, p, ln in broken:
            print(f" - {f}:{ln}  ->  {p}")
        print("\n修法：改正路径，或在 scripts/paths_allowlist.txt 里登记（仅限计划中/上游仓路径）。")
        return 1

    print(f"PATHS OK ({checked} references checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
