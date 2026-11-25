---
title: ADR-0003 工具选型：优先用社区组件，上游不可用时才自建
status: Accepted
date: 2026-11-25
nav_exclude: true
---

## 背景

2026-11-25 一天内在同一类问题上栽了两次（`os` 未导入导致服务 500、`glob` 未导入导致门禁崩），
说明"靠人发现问题"本身不可靠。逐项查了现成组件，也对照了 `link-seek/docker-images` 与
`link-seek/infra` 的既有做法。

## 选项

| 问题 | 自建 | 社区组件 |
|---|---|---|
| 未定义名字 | 人眼 + 真跑 | ruff `F821` |
| shell 语法 | `bash -n` | shellcheck |
| YAML 规范 | 自写 parse | yamllint |
| 榜单结构 | 手写检查 | jsonschema |
| Wilson 区间 | 手写公式 | scipy `binomtest.proportion_ci` |
| 配置语义校验 | 自写 | `vla-eval test --validate`（上游） |
| workflow 语义 | 自写 | actionlint |

## 决定

**能用组件就用组件；上游的轮子实测跑不通时才自建，并记录原因。**

已采纳：ruff（F821）、shellcheck（`-S error`）、yamllint（relaxed）、jsonschema（榜单 schema）、
actionlint（`raven-actions/actionlint@v2.2.0`，pin 工具版 `1.7.12`）。
scipy **只用于校准**：Wilson 实现与 `binomtest.proportion_ci(method="wilson")` 逐位一致
（六组样本最大差 2.4e-6，来自取整），CI 仍只装 numpy。

## 后果

- **收益**：`os`/`glob` 这类缺陷在 CI 就被拦；YAML/文档格式不再靠自觉
- **代价**：门禁数量上升（已收敛为 `run_all.py` 单一入口，14 项）
- **明确没做**：trivy + SBOM（镜像对外分发前做）、GHCR 双推（适配器稳定后做）、renovate（pin > 10 再做）
- **触发重议**：某个组件开始产生大量误报，或上游提供官方校验入口

## 附：上游组件不可用的证据

`vla-eval test --validate` 曾被列为候选，实测两个坑堵死：
① 容器内没有 `docker` CLI，直接 skip；
② 把宿主 docker 挂进去后，内层 `vla-eval run` 不接收 `-c`，去读 `/etc/vla-eval.yaml` → `IsADirectoryError`。
