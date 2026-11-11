---
title: 精度断崖：fp16 首推理即崩
parent: 原理与案例
nav_order: 2
---

# 精度断崖：X-VLA fp16 在 V100 上 0/30，fp32 29/30

> 给复现者：同一套代码、同一权重、同一 task，只换推理精度，一边满分一边零分。
> 时间：10 分钟 ｜ 前置：`quickstart`。
> 你将得到：报错原文、两份报告、机理、复现方法。

## 现象（一句话）

X-VLA 在 LIBERO 上跑 fp16，每个 episode 死在第一个 action：10/10 ERROR，`mean_success` 为 null。
同 task 换 fp32：9/10，三榜（spatial/object/goal）合计 29/30。

## 证据

| 精度 | 报告 | 结果 |
|---|---|---|
| fp16 | [`x-vla_libero-spatial_fp16.json`](https://github.com/link-seek/partner-vla-eval/blob/main/docs/reports/x-vla_libero-spatial_fp16.json)（[run](https://github.com/link-seek/partner-vla-eval/actions/runs/38990222346)） | 0/10，全 ERROR：`首个 act 即崩 RuntimeError float vs Half` |
| fp32 | [`x-vla_libero-spatial_fp32.json`](https://github.com/link-seek/partner-vla-eval/blob/main/docs/reports/x-vla_libero-spatial_fp32.json)（[run](https://github.com/link-seek/partner-vla-eval/actions/runs/38981477153)） | 9/10，零 ERROR |
| fp32 整榜 | [`x-vla_libero-spatial50_fp32.json`](https://github.com/link-seek/partner-vla-eval/blob/main/docs/reports/x-vla_libero-spatial50_fp32.json)（[run](https://github.com/link-seek/partner-vla-eval/actions/runs/40552080571)） | 487/500 |

报错原文：

```
RuntimeError: Input type (float) and bias type (c10::Half) should be the same
```

## 机理

去噪头的 LayerNorm/大激活值在 fp16（5 位指数）下直接溢出。X-VLA 官方训练命令是
`accelerate --mixed_precision bf16`——正确推理精度是 bf16，fp16 推理属于数值越界，
不是性能降级。V100 无 bf16，所以 V100 上 X-VLA 一律 fp32。

另一面是显存墙：CogACT fp32 在 V100 上首个 forward 即 OOM（31GB），只能走 fp16
（见 [proposal-stack-effects.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/proposal-stack-effects.md) B2）。
精度和显存是同一枚硬币的两面，选哪边由模型+卡型共同决定，见下表：

| 模型 | V100 精度 | 原因 |
|---|---|---|
| X-VLA | fp32 | fp16 首推理即崩（本篇） |
| DB-CogACT | fp16 | fp32 首 forward 即 OOM 31GB |

## 复现者怎么复现/避坑

1. **先看 errors 列**：vla-eval 把 error 当数据，exit code 照样 0。0/30 全 ERROR 时看分会误判为模型不行——先看 `errors`，再看 `mean_success`。
2. **dtype 不是 yaml 字段**：serve 镜像构建时定（`Dockerfile.serve-xvla` DTYPE 构建参），写进报告备注，不写进 yaml。
3. **换卡重打基线**：H100 有 bf16，可复刻官方训练精度；V100 只能二选一。本篇数字只在 V100 上成立。

## 下一步

- EE 通路为什么能跑：[03-ee-action-path.md](./03-ee-action-path.html)。
- 栈差异全表：[proposal-stack-effects.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/proposal-stack-effects.md)。
