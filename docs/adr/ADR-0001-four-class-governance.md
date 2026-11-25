---
title: ADR-0001 四类治理：main 只放常驻能力
status: Accepted
date: 2026-11-25
nav_exclude: true
---

## 背景

治理前实测：54 篇文档、29 个脚本、28 个 workflow、15 个镜像 tag 混在一起，暴露三个具体问题：

1. **10 篇内部稿会出现在公开站点导航**（5 篇 internal + 4 篇 reports + 1 篇 deck 计划）
2. **7 个一次性 workflow**（诊断/探针/一次性修复）零可执行引用、30 天未动，却一直占着 Actions 目录
3. **镜像清单三套口径**：10 个 Dockerfile / 15 个真实 tag / registry 只记 6 条

同时仓库 `private: false`，但没有防泄漏门禁（无 gitleaks、无 `.env.example`、`.gitignore` 不忽略 `.env`）。

## 选项

| 方案 | 内容 | 代价 |
|---|---|---|
| A 拆两仓 | 文档仓 + 管线仓 | 版本要跨仓对齐；参数真源在 registry，拆开后两边会漂 |
| **B 单仓四类分区 + 分类门禁** | 产物/基础设施/文档/流程各自住址、生命周期、门禁 | 门禁变多；main 必须走 PR |
| C 只写文档靠自觉 | 无门禁 | 已验证会烂（现状就是） |

## 决定

选 **B**。核心四条：

1. **四类归属**：产物（OBS + 仓内索引）/ 基础设施（仓 + SWR）/ 文档（站点 / Discussion / ADR）/ 流程（CONTRIBUTING、模板、CODEOWNERS）
2. **main 只放常驻能力**：一次性动作在分支做完即删，不合并、不留痕
3. **基础设施登记制**：每个 workflow 必须登记 `kind ∈ {routine, rare}`；`one-off` 禁止进 main；靠参数引用的配置登记为 `option`，永不按时间删
4. **凭证与地址不进仓**：真值只在 Secrets 与目标机 `.env`；`gitleaks` 守门，机器地址走 repo variables

## 后果

- **好处**：文档站只剩公开面；一次性件在产生时被拦，不需要"到期清理"；分数与参数只有一个真源；main 有 PR + 三项检查（lint / actionlint / hygiene）
- **代价**：不能直推 main（已实测：`Repository rule violations ... must be made through a pull request`）；临时诊断要写成命令或 howto，不能点一下就跑
- **触发重议**：① 需要把管线转 private；② 出现第二位只维护文档、不碰管线的维护者；③ 四类里出现放不进去的东西（说明分类该改）
