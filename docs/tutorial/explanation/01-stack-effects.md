---
title: 栈差异：分数里多少是栈造成的
parent: 原理与案例
nav_order: 1
---

# 栈差异：分数里多少是栈造成的？

> 给复现者：同一套评测代码，换栈（GPU / 精度 / 镜像 / 种子 / 分片 / 资产挂载）能差多少分？
> 时间：10 分钟 ｜ 前置：`quickstart`。
> 你将得到：一张 V100 实测的"旋钮×影响"表 + 披露清单——看别人的分时知道该问什么。

## 一句话

榜单可比性的前提是同栈；跨栈比较必须披露栈变量。下表每一格都是本仓 V100 实测，不是文献推演。

## 对照表（2026-10-14 ~ 11-04）

| # | 变量 | 水平 | 结果 | 结论 |
|---|---|---|---|---|
| A | benchmark 镜像 | 0.7.0 vs 0.8.0（同种子 grab_roller×50） | 43/50=86% vs 46/50=92% | 差 6pp，2σ 内，不搬分 |
| A2 | 资产内置 vs 外置挂载 | 同种子×50 | 46/50 vs 45/50 | 差 1ep，等价 |
| A3 | 烘焙 vs 原生 | stock vs slim×20 | 18/20 vs 18/20 | 差 0，自证清白 |
| B | 模型精度 | X-VLA fp32 vs fp16（LIBERO spatial/object/goal×10 同种子，6 轮） | 29/30 vs 0/30 | fp16 首推理即崩（float vs Half bias 算子错），跨 task 一致 |
| B2 | 精度 | CogACT fp32 vs fp16（V100） | fp32 首个 forward 即 OOM（31GB） | 单侧不可行本身即证据 |
| C | 分片 | 2 / 4 / 8 | 2 稳、4 慢、8 hang | 只动速度/稳定性 |
| D | 种子 | 盲种子 vs 校验种子 | 35/35 有效 + 15 坏种 vs 零 error；同集重跑 41 vs 46 | 种子集动 error 率；同集轮间差 ≈1.7σ（噪声） |
| E | 机器+精度 | V100 fp16 vs 官方 H100 bf16（place_empty_cup） | 16~20% vs 28% | 待定档，写进披露不硬判 |

补充：0.8.0 的 grab_roller 另有一轮 50ep 复测 45/50=90%（[报告](https://github.com/link-seek/partner-vla-eval/blob/main/docs/reports/cogact_robotwin-grab_roller-x50.json)），与 A 行 46/50 在 n=50 噪声带内一致。

## 怎么读这张表

* **动 6~97pp 的两处**：镜像差 6pp（A），精度差 97pp（B）——B 是"一边满分一边零分"的量级，不是性能波动。
* **只动速度/稳定性的**：分片（C）、资产挂载（A2）、烘焙方式（A3）。
* **动 error 率不动能力的**：种子集（D）。
* **跨机器**：V100 fp16 vs H100 bf16（E）落在待定档，披露但不硬判。

## Prior art（错开，各引各的）

- vla-eval 论文：审协议层（终止语义/归一化），声明固定种子 + 镜像——我们审的正是它固定的那些东西。
- VLATest：审环境扰动（光照/相机），580 卡时。我们不动环境，只动栈。
- VLA-Perf：跨 GPU 只谈速度不谈分数，还默认 BF16/FP16 可互换——B（29/30→0/30）至少在 X-VLA 上证伪后者。
- [2606.04233]：审榜单设计。REPLICA：真机跨场地。我们：仿真跨栈。

官方训练命令（2toinf/X-VLA README）为 `accelerate --mixed_precision bf16`：正确推理精度是 bf16，fp16 属数值越界；bf16 复刻待 H100。

## 披露清单

跨栈比较时至少披露：GPU / dtype / benchmark 镜像 tag（含 slim/补丁说明）/ serve 镜像 / 种子（bundled 还是盲）/ 分片 / 资产挂载。

方法论副产品：阴性对照（/tmp 盖资产秒崩）验证挂载生效；挂载 = 改镜像，版本化 + 差值单列。

## 下一步

* 精度为什么是断崖：[02-precision-cliff.md](./02-precision-cliff.md)。
* EE 通路怎么跑通：[03-ee-action-path.md](./03-ee-action-path.md)。
* 20D 怎么转 16D：[04-20d-to-16d.md](./04-20d-to-16d.md)。
