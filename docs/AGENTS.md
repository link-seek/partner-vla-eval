---
title: docs/ 目录规则（就近文档，本身不进站）
nav_exclude: true
status: living
---

# docs/ 目录规则

## 站点怎么构建

| 场景 | 方式 |
|---|---|
| 生产发布 | GitHub Pages，源 `main:/docs`，主题走 `remote_theme: just-the-docs` |
| CI 校验 | `docs/Gemfile` + `bundle exec jekyll build --strict_front_matter`（见 `lint.yml`） |
| 本地预览 | `cd docs && bundle install && bundle exec jekyll serve` |

CI 的构建步骤是**硬门禁**：front-matter 坏、Liquid 语法错、remote_theme 拉不到，PR 直接红。
`check_docs.py` 只负责字段与归属判定，**不能**替代构建。

## 每篇必须有的 front-matter

```yaml
---
title: 标题                # 必填
parent: 评测教程            # 进站页面：归属分组
# 或
nav_exclude: true          # 不进站（ADR / howto / internal / reports / archive）
status: snapshot           # reports 必填；ADR 用 Proposed|Accepted|Superseded|Deprecated
---
```

规则由 `scripts/gates/check_docs.py` 判定（详见 `CONTRIBUTING.md` 第六节）。

## 目录归属

| 目录 | 内容 | 进站 | 生命周期 |
|---|---|---|---|
| `tutorial/` | 教程/参考/原理 | ✅ | 随协议版本冻结 |
| `adr/` | 决策（编号 + 状态机） | ❌ | 接受后冻结 |
| `howto/` | 出事才看的手册 | ❌ | 跟着系统变 |
| `reports/` | 检视报告 | ❌ | `status: snapshot`，不再改 |
| `archive/` | 历史世代 | ❌ | 只读 |
| `data/` | 产物 JSON（第 1 类） | — | 按 `protocol_version` 冻结 |
| `decks/` | 汇报物 | ❌ | 交付物，留档 |

## 已迁移的目录

`docs/internal/` 已于 2026-11-25 拆解：决策 → `adr/`，手册 → `howto/`，过程/进度 → Discussion #1。
**不要重建 `internal/`**——它就是"内部稿漏进公开站"的来源。
