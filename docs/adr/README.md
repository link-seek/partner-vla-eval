---
title: ADR（决策记录）
nav_exclude: true
---

# ADR：只记"为什么这么定"，接受后冻结

> 来源：Python 的 PEP、Rust 的 RFC、Kubernetes 的 KEP 都是这个模式——**编号 + 状态机 + 冻结**。
> 决策文档的价值在于"当时为什么这么定"，所以它**不该被反复编辑**；要改就发新号。

## 规则

1. 编号递增，不复用：`ADR-0001-简短标题.md`
2. **接受后冻结**：不再改正文；后续变化写新 ADR，并在旧文头部标 `Superseded by ADR-XXXX`
3. 不进公开站点（`nav_exclude: true`）——它是内部历史，不是教程
4. 一个 ADR 只回答一个决定；背景、选项、结论、后果四段齐全

## 状态机

```
Proposed → Accepted → (Superseded | Deprecated)
```

## 模板

```markdown
---
title: ADR-0001 用 X 而不是 Y
status: Proposed        # Proposed | Accepted | Superseded | Deprecated
date: YYYY-MM-DD
nav_exclude: true
---

## 背景
要解决什么问题，约束是什么。

## 选项
A / B / C，各自的代价（要有数字或实测证据）。

## 决定
选了哪个，一句话说清。

## 后果
- 好处：
- 代价：
- 触发重议的条件：
```

## 现有决策的迁移

`docs/internal/` 里的决策类内容（如 `decisions-retention-partial-regression.md`）按此格式迁入并编号；
过程/进度类（整改计划、收口计划）**不进 ADR**，转 Discussion。
