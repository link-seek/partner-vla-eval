#!/usr/bin/env python3
"""文档入站门禁：保证"哪些页会出现在公开站点"是机械判定的。

背景（2026-11-25 实测）：54 篇 md 里 **10 篇没有 front-matter**（5 internal + 4 reports + 1 deck 计划），
just-the-docs 会把它们当作顶层页面塞进公开导航——内部整改计划、检视报告就这么暴露了。

规则（每条页面的归属必须显式）：
  1. 必须有 YAML front-matter，且有 `title`
  2. 必须三者之一：
     - `parent:`        属于某个导航分组（进站）
     - `nav_exclude: true` 不进站（内部/ADR/归档）
     - `has_children: true` 是分组首页（进站）
  3. 例外：`docs/index.md`（站点首页，无 parent 属正常）
  4. 站外目录（archive/adr/howto/internal/reports/decks）里的页面必须 `nav_exclude: true`

为什么不用"目录白名单"：目录会重组，显式字段不会。判据落在每一页上，才不会因为挪目录而失效。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
ROOT_PAGE = "docs/index.md"

# 这些目录的内容不进公开站（内部稿/归档/ADR/how-to）
OUT_OF_SITE = ["archive", "adr", "howto", "internal", "reports", "decks"]

fails: list[str] = []
warns: list[str] = []


def front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    pages = sorted(DOCS.rglob("*.md"))
    print(f"[扫描] {len(pages)} 篇")

    no_fm, no_title, no_owner, out_of_site_leak = [], [], [], []
    for p in pages:
        rel = str(p.relative_to(ROOT))
        fm = front_matter(p.read_text(errors="ignore"))
        if not fm:
            no_fm.append(rel)
            continue
        excluded_fm = fm.get("nav_exclude", "").lower() == "true"
        if not fm.get("title") and not excluded_fm:
            no_title.append(rel)   # 站外页不需要 title（不进导航）
        has_parent = bool(fm.get("parent"))
        excluded = fm.get("nav_exclude", "").lower() == "true"
        is_section = fm.get("has_children", "").lower() == "true"
        if not (has_parent or excluded or is_section or rel == ROOT_PAGE):
            no_owner.append(rel)

        in_oos = any(rel.startswith(f"docs/{d}/") for d in OUT_OF_SITE)
        if in_oos and not excluded:
            out_of_site_leak.append(rel)

    def report(name: str, items: list[str], hint: str) -> None:
        cond = not items
        print(f"  {'ok  ' if cond else 'FAIL'} {name} {'' if cond else str(items[:5]) + hint}")
        if not cond:
            fails.append(name)

    report("每篇都有 front-matter", no_fm, " → 加 title + (parent | nav_exclude)")
    report("进站页面都有 title", no_title, " → 进导航的页面必须有 title")
    report("每篇归属明确（parent / nav_exclude / has_children）", no_owner,
           " → 这 10 篇会直接进公开导航")
    report("站外目录必须 nav_exclude", out_of_site_leak, " → 内部稿会出现在公开站")

    # 站外的"根目录参考文档"必须是活的：被至少一篇其他文档引用，否则就是孤儿稿
    all_text = {p: p.read_text(errors="ignore") for p in pages}
    orphans = []
    for p in pages:
        rel = str(p.relative_to(ROOT))
        if not rel.startswith("docs/") or rel.count("/") != 1:
            continue          # 只看 docs/ 根下
        fm = front_matter(all_text[p])
        if not (fm.get("nav_exclude", "").lower() == "true"):
            continue
        name = p.name
        refs = sum(1 for q, t in all_text.items()
                   if q != p and (name in t or f"({name})" in t or f"]({name}" in t))
        if refs == 0:
            orphans.append(rel)
    report("docs/ 根下的站外参考文档都不是孤儿（被引用）", orphans,
           " → 没人引用就该归档或删除；有人引用就不许按日期清掉")

    # 站内页面的对账：parent 必须指向存在的分组 title
    titles = {front_matter(p.read_text(errors="ignore")).get("title") for p in pages}
    bad_parent = []
    for p in pages:
        fm = front_matter(p.read_text(errors="ignore"))
        par = fm.get("parent")
        if par and par not in titles:
            bad_parent.append(f"{p.relative_to(ROOT)}: parent={par!r}")
    report("parent 指向的分组存在", bad_parent, " → 分组标题拼错")

    for w in warns:
        print(f"  WARN {w}")
    if fails:
        print(f"\nDOCS FAIL: {len(fails)} 项")
        return 1
    insite = sum(1 for p in pages
                 if (front_matter(p.read_text(errors="ignore")).get("parent")
                     or front_matter(p.read_text(errors="ignore")).get("has_children", "").lower() == "true"
                     or str(p.relative_to(ROOT)) == ROOT_PAGE))
    print(f"\nDOCS OK（{len(pages)} 篇：进站 {insite} / 站外 {len(pages) - insite}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
