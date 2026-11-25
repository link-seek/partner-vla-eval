---
title: R01：训练数据口径 → 成功率（V100 版，第一阶段汇报）
status: snapshot
nav_exclude: true
---

# R01：训练数据口径 → 成功率（V100 版，第一阶段汇报）

> 状态：**下一阶段立项**（2026-11-24 定）——方案已定，S2/S3/S4 未跑，**不进本次汇报**。
> 本次汇报只讲前四根柱子（执行/方法/保真/评价）+ 基模榜单 5a；微调轴 5b 在下一阶段交付。
> 目的：先说清"这个测试是怎么做的、我们的评测是怎么做的"；表跑出来后连同数字一起复核。
> 范围：只用现有 2×V100-32GB（0002），**不申请任何新算力**。A30 / A100 作为后续决策项，不在本报告。

## 1. 这张表要回答什么

不是"哪个模型强"，而是：**同一个基模，喂不同的训练数据，成功率差多少。**

对应官方做法：RoboTwin 2.0 论文 §4.3 / Table 4 的对照轴（同一基模 × 不同训练数据 → 成功率），
以及 §4.5 的评测协议（50 demos 训练 → Easy/Hard 各 100 rollouts，本文按 50 rollouts 计）。

## 2. 变量与固定量

| 类别 | 取值 |
|---|---|
| 唯一自变量 | 训练数据口径：**A = 仅 50 条 clean demos**；**B = 50 条 clean + 500 条 domain-randomized** |
| 基模 | ACT（官方 `policy/ACT`，80M 级）、DP（官方 `policy/DP`，50M 级） |
| 机器人本体 | aloha-agilex（14 维关节 + 三相机，与官方 benchmark 一致） |
| 考场 | 5 个 task：`grab_roller`、`adjust_bottle`、`place_phone_stand`、`click_bell`、`handover_block` |
| 评测难度 | Easy（`demo_clean`）与 Hard（`demo_randomized`）各 50 ep |
| 种子 | bundled expert seeds，从 100000 起；同 task 各条目不换种子 |
| 评测栈 | 本仓 vla-eval harness + `vla-eval-robotwin:0.8.0-ee-slim`；serve/env 分卡；V100 fp32 |
| 训练算力 | 2×V100-32GB，fp32（V100 无 bf16） |

## 3. 数据从哪来、怎么用

- 来源：`TianxingChen/RoboTwin2.0`（HF），按 task 分 zip：
  `dataset/<task>/aloha-agilex_clean_50.zip`（≈0.3GB/任务）、
  `dataset/<task>/aloha-agilex_randomized_500.zip`（≈5GB/任务）。
- 5 个 task 合计约 27GB；V100 经 `HF_ENDPOINT=hf-mirror.com` 直拉（与权重预热同一条路，不出境）。
- 口径 A：只解 clean_50；口径 B：clean_50 + randomized_500 一起解（共 550 条）。
- 数据统计量（mean/std）各自独立计算，不跨口径复用 —— 复用会引入口径污染。

## 4. 训练怎么跑（官方代码，官方超参）

| 项 | ACT | DP |
|---|---|---|
| 入口 | `policy/ACT/train.sh` → `imitate_episodes.py` | `policy/DP/train.sh` → `train.py` |
| 关键超参 | chunk 50 / hidden 512 / batch 8 / lr 1e-5 / kl 10 | 官方默认（`deploy_policy.yml` 同步） |
| epochs | **固定 40k 步**（见下） | 同 |
| seed | 0（固定） | 0 |

**为什么固定步数而不是固定 epoch**：官方默认 6000 epochs 是给 50 条数据定的。口径 B 有 550 条，
按 epoch 固定会让 B 的优化步数变成 A 的 11 倍，比的就不是"数据口径"而是"算力"。
所以两口径统一 **40k 优化步**（≈ ACT 6000 epochs@50 条 的步数量级），并在结论里明写：
本对照回答的是"同算力预算下，数据多样性 vs 重复次数哪个更值"。

## 5. 评测怎么跑（我们这一侧）

1. 训练产出的 ckpt 走 **serve 适配器**（`configs/model_servers/serve-robotwin-act.yaml` / `-dp.yaml`），
   由 `vla-eval serve` 起 WS 服务，暴露 `obs(三相机 + qpos14) → action chunk(14D)`。
2. 客户端跑本仓 `RoboTwinBenchmark`（`action_type: qpos`，`max_steps 300`，`send_state`），
   每 task 独立 chunk，50 ep，Easy/Hard 各一轮。
3. 产物：`aggregate.json`（mean_success / errors / 每 ep steps）+ 逐 ep json/jsonl，
   落 `obs://so101-sim-pipeline/eval/r01/<model>-<regime>/<task>/`。
4. 质量门槛：`errors > 0` 或 `Spec mismatch` 的条目不算数，重跑；步数跑满且全 0 的条目要单独看录像。

## 6. 表格长这样（待填）

| 基模 | 口径 | Easy（5 task） | Hard（5 task） | Hard−Easy | errors |
|---|---|---|---|---|---|
| ACT | A（50 clean） | — | — | — | — |
| ACT | B（50 clean + 500 rnd） | — | — | — | — |
| DP | A | — | — | — | — |
| DP | B | — | — | — | — |

每格还要有 per-task 明细（5 行），否则"均值"会被单个 task 带偏。

## 7. 已知限制（写进报告正文，不藏）

1. V100 只能 fp32：与论文的 A100/bf16 数字不完全可比，只做**口径间相对比较**。
2. 固定 40k 步而非 6000 epochs（理由见 §4）。
3. 单 embodiment（aloha-agilex）、单 seed 集；跨本体泛化不在本报告。
4. 50 rollouts（论文 100），噪声带更宽，差异小于 ±7pp 的不下结论。
5. RoboTwin 官方 ckpt（Avada11 系列）不在本报告：那是"作者训练口径"，作为 R02 的对照行。

## 8. 交付物

- 本文件 + 填好的表 + per-task 明细
- 每条 1 个 run 链接（GitHub Actions）+ OBS 路径
- 训练日志与 ckpt 摘要（步数、loss 末值、数据条数）

## 9. 时间线（2×V100，串行）

| 步骤 | 内容 | 估时 |
|---|---|---|
| S1 | 数据解包 + 格式/统计校验（5 task × 2 口径） | 0.5 天 |
| S2 | ACT/DP serve 适配器 + 1 task smoke（链路通） | 1 天 |
| S3 | 训练 20 个 ckpt（2 模型 × 2 口径 × 5 task，40k 步） | 3–4 天 |
| S4 | 评测 20 × 2 难度 × 50 ep（2000 ep） | 1.5–2 天 |
| S5 | 出表 + 写报告 | 0.5 天 |
| 合计 | | **6–7 天** |

## 10. 通过后（第二阶段，另开决策）

- 是否上 A30（`pi3.6xlarge.4`，cn-north-4，¥18.06/h）把 π0 那行补上（bf16，LoRA）
- 是否把 `cotrain_ckpt/` 里官方发布的 11 个模型 ckpt 纳入 L1 榜单（X_VLA / Pi_05 / starVLA / GalaxeaVLA …）
