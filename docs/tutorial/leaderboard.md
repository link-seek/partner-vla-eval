---
title: 基模榜单（进行中）
parent: 评测教程
nav_order: 3
---

# 基模榜单：同一考场，只让模型变

> 这一页回答一个教程前面没回答的问题：**哪个基模强**。
> 前置：`quickstart`（能跑一轮）+ `explanation/01-stack-effects`（知道栈会差多少分）。
> 状态：首批已出数（X-VLA Easy×50ep 5 task；CogACT Easy×50ep 按公开覆盖 3 task）；Hard 待补。

## 考场（固定这四项，缺一项就不进榜）

| 项 | 取值 |
|---|---|
| 数据/考场 | RobotWin 2.0 Easy，5 task：`grab_roller` / `adjust_bottle` / `place_phone_stand` / `click_bell` / `handover_block` |
| 集数与种子 | 每 task 50 ep，bundled seeds 从 100000 起（`skip_expert=false`），同 task 各模型用同一批种子 |
| 评测栈 | 同一镜像（`vla-eval-robotwin:0.8.0-ee-slim`）、同分片（8）、同机（V100-32GB×2，cn-north-4 内网） |
| 训练口径 | 用作者发布的 ckpt，**不自己重训**；dtype 按"能在 V100 上跑"的等价精度（bf16 → fp32 代替） |

**准入三条**（缺一条只能进"候选"，不能进表）：

1. ckpt 公开可下（HF / OBS 直链，能写进 `configs/registry/model-registry.json`）。
2. 训练口径可述：训练数据（哪 50 demos/多少 ep）、控制频率、动作空间（qpos 14D / EE 16D）至少能从作者文档或 ckpt 卡片确认。
3. 适配已验：本仓能起 serve 并跑通 1 task smoke（否则只是"能下载"）。

## 披露列（跨栈比较必看）

进表的每一行都必须带上：`ckpt` / `dtype`（V100 上实际跑的精度）/ `action_spec` / `seeds` / `episodes` / `date` / run 链接 / `errors`（ERROR 数）/
栈差异备注（如"官方在 A100 bf16，此处 V100 fp32 代替"）。缺披露的数只能自己看，不能对外引。

## 首批（2026-11 起）

| 模型 | ckpt | 动作 | 精度 | 覆盖 | 备注 |
|---|---|---|---|---|---|
| CogACT（DB-CogACT） | `Dexmal/robotwin-db-cogact/<task>` | qpos 14D | fp16 | **3/5 task** | 公开仓只发 4 个 task（含本考场外 1 个）；`click_bell` / `handover_block` 无公开 ckpt，按准入第 1 条不计入缺失，表中记 `—` |
| X-VLA | `2toINF/X-VLA-RoboTwin2` | EE 16D | fp32 | **5/5 task** | 单 ckpt 全 task；easy50 66.6%（5000ep）；本考场 5 task×50ep 已收齐：**233/250 = 93.2%**（95% CI [89.4, 95.7]），零 error |

**覆盖率差异是本次最需要披露的一条**：CogACT 是"一头一 task"，作者只发了 4 个头；X-VLA 是单 ckpt 通用。所以两者在本考场的可比格数不同（3 vs 5），**不能把 5 task 均值当同一口径比**。

### 逐 task 实取（Easy / demo_clean，每格 50 ep）

| task | X-VLA（run 45266034430） | CogACT（本轮 run 45188046221） | 差 | 同档判定（±7pp） |
|---|---|---|---|---|
| grab_roller | 49/50 = **98.0%** | 45/50 = **90.0%**（历史 run 40609758183） | +8.0pp | 跨档（X-VLA 高） |
| adjust_bottle | 49/50 = **98.0%** | 50/50 = **100%** | −2.0pp | 同档 |
| place_phone_stand | 48/50 = **96.0%** | 6/50 = **12.0%** | +84.0pp | 跨档（X-VLA 高） |
| click_bell | 48/50 = **96.0%** | — 无公开 ckpt | — | 不可比 |
| handover_block | 39/50 = **78.0%** | — 无公开 ckpt | — | 不可比 |

> **不给跨模型总分**：两边覆盖的 task 不同（X-VLA 5 格已收 / CogACT 3 格），且 `grab_roller` 取自不同 run，相加没有意义。
>
> **两轮差异已披露**：CogACT `place_phone_stand` 早前一轮 8/50=16%，本轮 6/50=12%，差 4pp 在 n=50 噪声带（±≈10pp）内，本轮为准。
>
> 95% Wilson 区间：X-VLA 5 task 合计 233/250 = 93.2%，[89.4%, 95.7%]；单 task n=50 约 ±5–11pp（handover_block 39/50 为 [64.8%, 87.2%]）。




首版就这两款（同考场、同栈、同种子）。下面这些**登记了但本轮不做**，列出来是为了说明“不是漏了”：

| 模型 | ckpt | 状态 | 原因 |
|---|---|---|---|
| ACT（官方基线） | `Avada11/RoboTwin-Model-AgileX-ACT` | dropped | `.ckpt + dataset_stats.pkl` 格式，要另写 ACT serve 适配器（本轮不做） |
| DP（官方基线） | `Avada11/RoboTwin-Model-AgileX-DP` | dropped | 同上 |
| π0 | `nextbig/pi0-robotwin-30fps-tasks5` | 候选（不可比） | 训练 task 清单/控制频率未披露 |

真源是 [`configs/registry/model-registry.json`](https://github.com/link-seek/partner-vla-eval/blob/main/configs/registry/model-registry.json)（这一页是它的可读视图）。

## 怎么跑一轮矩阵

Actions → `Model Matrix (base models x exam tasks)`：

```
models   = db-cogact
tasks    = grab_roller,adjust_bottle,place_phone_stand,click_bell,handover_block
episodes = 50   shards = 8   video = 0
```

派完就走：自动开机 → 逐模型逐 task 跑 → 产物进 `obs://<prefix>/leaderboard/<model>/<task>/` → 自动关机。
单模型 5 task×50ep 约 3–5h；多个模型按 concurrency 串行，不会抢同一张卡。

## 为什么现在才做这一步

跑出分数（评价）和比较基模（评测）差三样：模型维度、固定训练口径、可复现的榜单产物。
缺这三样时，任何"谁更强"的解读都是错的——栈一动就差几十分（见 `explanation/01`）。
现在补的是**前两样能自己控制的部分**（考场 + 栈 + 种子 + 披露），模型侧只用公开 ckpt；
没有公开 ckpt 的基模（如官方自训的 π0 原版）需要按 §4.5 自己 50 demos 微调，属训练侧立项，不在这条线上。
