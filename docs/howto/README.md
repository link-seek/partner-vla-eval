---
title: How-to（运维手册）
nav_exclude: true
---

# How-to：出事时照着做的手册

> 与教程的区别：教程教新人从头做一遍；how-to 只在**特定故障**时打开。
> 与 workflow 的区别：how-to 是**能力**（可以照着做），workflow 是**自动化**（点一下就做）。
> 一次性动作写进这里，不提交 workflow（见 `CONTRIBUTING.md` 第二节）。

## 已有

| 手册 | 场景 |
|---|---|
| `repair-runner.md` | V100 runner 装机 / agent 损坏（0002 双 agent、0001 单 agent） |
| `tailnet-join.md` | runner 重装后重新加入 tailnet（经 hw41 跳板，key 不落盘） |
| `act-dp-adapter-runbook.md` | ACT/DP 适配器首次 smoke（12 个坑） |
| `serve-yaml-onboarding.md` | serve yaml 编写/对接（上游讨论草稿） |
| `partner-onboarding-timing.md` | 伙伴接入要多久：交付物清单 + 机械实测 0.94s + 30 分钟拆解 + 4 个卡点 |
| `ops-entry.md` | **运维入口 ops.yml**：4 个 action 跑在哪个 runner、首次实证、3 个排错记录 |
| `obs-lifecycle.md` | OBS 桶生命周期核对/调整 |

## 写作要求

1. 开头写"**什么时候用这个**"和"**用错会怎样**"
2. 每条命令可复制粘贴，参数用 `<尖括号>` 标出
3. 写清验证步骤（怎么知道修好了）
4. 涉及凭证一律写 `$变量名`，不写值
