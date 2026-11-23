---
title: 参考：口径映射
parent: 评测教程
nav_order: 8
---

# 参考：口径映射表

> 出 0 分先查这张。错了就是"跑满步数、零异常、全 0 分"。
> 相关：[15 条排障](./error-codes.md)、[精度断崖](../explanation/02-precision-cliff.md)。

## dtype 红线（V100）

| 模型 | 用什么 | 为什么 |
|---|---|---|
| X-VLA | 一律 fp32 | fp16 首推理即崩 `float vs Half bias`，LIBERO 三榜六轮 29/30 vs 0/30 一致；官方训练 `accelerate --mixed_precision bf16`，fp16 属数值越界；bf16 复刻待 H100 |
| DB-CogACT | fp16 | fp32 首个 forward 即 OOM（31GB，V100 单卡不可行） |
| 通用 | 跑分先报 dtype | fp16 不是 fp32 廉价版（指数位少 3 位）；0 分先查本表，不要先怀疑模型 |

## 口径映射

| 项 | 说明 | 错了会怎样 |
|---|---|---|
| `action_dim` | 14 关节 / 16 EE / 7 单臂 | 截断补零变垃圾动作 |
| `image_keys` | 相机名映射，各家不一样 | 看错相机，照样跑满步数 |
| `state_key` | 本体状态字段 | 首步 proprio 即错 |
| `chunk_size` | 和 benchmark 节拍对齐 | 越界或卡顿 |
| 权重路径 | 单仓直指 / 分头走本地子目录 | `HFValidationError` 起不来 |

## spec warning 读法

episode 起点刷 `Spec mismatch` = 口径错配预警，先停手对表，不要烧卡硬跑。

`action [ee_pose]: benchmark expects it but server doesn't declare it` 只是 advisory，
步数执行可照常（X-VLA EE 已验证）；真拦路的是 unknown kwarg（旧镜像，已退役）。
