---
title: 原理与案例
nav_order: 6
has_children: true
---

# 原理与案例：给复现者

> 给复现者：看懂一张分数怎么来的。时间：每篇 10 分钟 ｜ 前置：`quickstart`。
> 三篇都是 V100 实测 + 报告，有 run 链接；只回答"这个配置下多少分"，不回答"哪个基模强"。

## 三篇

| 篇 | 回答的问题 | 证据 |
|---|---|---|
| [02 精度断崖](./02-precision-cliff.html) | fp16 为什么 0/30，fp32 为什么 29/30 | fp16/fp32/spatial50 三份报告 |
| [03 EE 通路](./03-ee-action-path.html) | RobotWin EE 16D 怎么跑通（0/8 → 66.6%） | ee_grab_roller + easy50 两份报告 |
| [04 20D 转 16D](./04-20d-to-16d.html) | X-VLA 20D 输出怎么进 RoboTwin 16D | easy50 serve/run 配置 |

栈差异全表（镜像/分片/种子/机器）：[proposal-stack-effects.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/proposal-stack-effects.md)。
