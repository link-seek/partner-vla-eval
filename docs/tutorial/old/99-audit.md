---
nav_exclude: true
---

# 99 审计报告

> 版本：v1.1（2026-11-03，A-D 收官；v1.0 见 2026-10-14）。诚实记录口径偏离与遗漏，对照 00 的表读。
> 无结论不进教程：E、X-VLA 上 RobotWin、瘦身/删 0.7.0/钉死全栈、easy50（进行中）仍 open，见 Discussion #3。

## 口径偏离（已接受）

| # | 偏离 | 影响 | 状态 |
|---|---|---|---|
| 1 | V100 全链 fp16（官方 bf16/H100） | place_empty_cup 16% vs 28%（约 2σ）嫌疑之一 | 接受，V100 无 bf16 原生支持；E 待定档，只披露不硬判 |
| 2 | adjust_bottle 用 0.7.0 盲种子（35/35 有效，15 坏种剔除） | 与官方验证种子集不同分布 | 接受，有效集 100%≈99%；D 已量化种子集效应（同集轮间 ≈1.7σ） |
| 3 | gripper 阈值 0.5（官方 client 0.7） | 同上嫌疑之二 | 待探（低优先级） |
| 4 | X-VLA 上 RobotWin 缺 EE 通路 | 总表缺 EE 系模型 | #166→#168 ready 待合；LIBERO fp32 已³榜出分（29/30），RobotWin EE 待上游合入 |
| 5 | 46 个 task 无公开权重 | 全量只覆盖 4/50 | 另立项（finetune）或等社区 |

## 本轮收官（A-D，2026-10-14~16，V100 实测）

- A：0.7.0 vs 0.8.0（43/50 vs 46/50，差 6pp，2σ 内，不搬分）。
- A2：资产内置 vs 外置（46/50 vs 45/50，差 1ep，等价）。
- A3：烘焙 vs 原生（18/20 vs 18/20，差 0）。
- B：X-VLA fp32 vs fp16（29/30 vs 0/30，首推理算子崩，跨 task 一致）。
- B2：CogACT fp32 OOM（31GB，单侧不可行即证据）。
- C：分片 2 稳/4 慢/8 hang（只动速度）。
- 详见 07 对照表 + `docs/proposal-stack-effects.md` + `docs/blog-precision-cliff.md`。

## 遗漏项

- LIBERO/CALVIN 只有 smoke，无全量（基线用途已满足）。
- DuoBench/RMBench/BiCoord 未跑（规划位/二期）。
- 真机未碰（后放）。

## 成本账（实测）

- 单 ep：2~10 分钟（成功短、失败跑满 400 步）。
- 一轮（1 task×50ep，2 分片）：3~7 小时。
- 镜像：robotwin 28.6GB（含 15GB 资产层）、serve 中等、verify 小。
- 跨洋：HF 下行 ~12MB/s；OBS 上传 ~60KB/s（path 式）/ ~7.7MB/s（virtual-host 式）。
