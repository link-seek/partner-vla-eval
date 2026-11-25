---
title: R01：训练数据口径 → 成功率（V100 版，第一阶段汇报）
status: snapshot
nav_exclude: true
---

# R01：训练数据口径 → 成功率（V100 版，第一阶段汇报）

> 状态：**下一阶段立项**（2026-11-24 定）——方案已定；**S1 数据 5/5、S2 适配器已完成（2026-11-25）**，
> S3/S4 等 GPU 独占，**不进本次汇报**。
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
| S1 | 数据解包 + 格式/统计校验（5 task × 2 口径） | ✅ 2026-11-25 |
| S2 | ACT/DP serve 适配器 + 1 task smoke（链路通） | ✅ 2026-11-25（各 1/1） |
| S3 | 训练 20 个 ckpt（2 模型 × 2 口径 × 5 task，40k 步） | 3–4 天 |
| S4 | 评测 20 × 2 难度 × 50 ep（2000 ep） | 1.5–2 天 |
| S5 | 出表 + 写报告 | 0.5 天 |
| 合计 | | **6–7 天** |

## 10. 通过后（第二阶段，另开决策）

- 是否上 A30（`pi3.6xlarge.4`，cn-north-4，¥18.06/h）把 π0 那行补上（bf16，LoRA）
- 是否把 `cotrain_ckpt/` 里官方发布的 11 个模型 ckpt 纳入 L1 榜单（X_VLA / Pi_05 / starVLA / GalaxeaVLA …）

---

## 11. S1 数据就位（2026-11-25 实测）

`TASKS=click_bell,handover_block DATA_ROOT=/data/robotwin-train bash scripts/data/prepare_robotwin_data.sh`
补齐最后两个 task；现在 5/5：

| task | clean_50 | randomized_500 | 口径 A | 口径 B |
|---|---|---|---|---|
| adjust_bottle | 50 | 500 | 50 | 550 |
| click_bell | 50 | 500 | 50 | 550 |
| grab_roller | 50 | 500 | 50 | 550 |
| handover_block | 50 | 500 | 50 | 550 |
| place_phone_stand | 50 | 500 | 50 | 550 |

证据：`/data/robotwin-train/manifest.json`（脚本生成）+ 每 task `find -name '*.hdf5' | wc -l = 550`。

### 格式校验（2026-11-25，不只是数文件）

`python3 scripts/data/check_robotwin_data.py --root /data/robotwin-train --sample 5`（robotwin 镜像内跑）：

```
adjust_bottle clean_50 n=50 sample=5 OK T=140..153
...
[S1] 抽样 50 个文件，失败组 0
```

检查项：`joint_action/vector` 必须 (T,14)、左右臂 (T,6)、gripper (T,)、三路相机帧数 = T、
首帧 cv2 能解码、同一文件内 T 一致。**0 失败组**，可以进入 S3。

### 统计量（全量，非抽样）

`python3 scripts/data/robotwin_data_stats.py --root /data/robotwin-train --out .../stats.json`
对 2,750 个文件、约 38 万帧逐帧累计（不是抽样）：

| task | clean std_mean | randomized std_mean | 帧数（A / B） |
|---|---|---|---|
| adjust_bottle | 0.5479 | 0.5989 | 7,238 / 71,723 |
| click_bell | 0.4313 | 0.4264 | 3,905 / 39,013 |
| grab_roller | 0.5128 | 0.5551 | 4,778 / 48,321 |
| handover_block | 0.4375 | 0.4351 | 14,134 / 142,746 |
| place_phone_stand | 0.4422 | 0.4476 | 6,407 / 64,024 |

**0 个坏文件**（NaN/维度/空集都算坏）。A/B 各自独立统计，结果入库
`docs/data/raw/robotwin-train-stats-2026-11-25.json`，S3 训练时对得上。

注意：randomized 的 joint 方差不一定更大（它增加的是场景多样性，不是关节幅度），
所以不能拿 std 当"数据多样性"的代理指标。

注意：**不要用 `r01-prep.yml` 在评测期间补数据**——它最后一步会 `stop-ecs`，会把在跑的 B1/DP 一起关掉；
补数据直接跑脚本（不占 GPU、不关机）。

---

## 12. 训练产物与 serve 契约（2026-11-25 实测）

S3 训练 3–4 天后要立刻进 S4 评测，所以先确认"训练写出来的文件，serve 能不能直接吃"。

### ACT：兼容，不需要额外软链

官方 `policy/ACT/imitate_episodes.py` 末尾写：

| 文件 | 位置 | 用途 |
|---|---|---|
| `policy_last.ckpt` | line 419 | serve 的 fail-closed 守卫认这个名字 |
| `policy_epoch_<N>_seed_<S>.ckpt` | line 415 | 中间快照 |
| `dataset_stats.pkl` | line 193 | qpos 归一化（serve 自动读） |

结论：R01 的 ACT ckpt 放进 `ckpt_dir` 即可，`ckpt_file` 不用传，`act_ckpt.py` 的守卫会通过。

### DP：路径要等 S3 首次训练后确认

DP 的保存走 hydra workspace（`diffusion_policy/workspace/base_workspace.py` 的 `torch.save`），
而 serve 侧按 `<task>-<setting>-<num>-<seed>/<num>.ckpt` 拼路径。两者是否一致**尚未实测**，
S3 首次训练后必须先 `ls` 确认，再决定是否软链；不要等 20 个 ckpt 都训完才发现路径对不上。

---

## 13. S3 训练冒烟（2026-11-25，GPU0 实测 1 epoch）

在 6–7 天长跑前，用 click_bell clean_50 跑了一遍完整入口：数据转换 → 1 epoch 训练 → 产物检查。

### 三个前置条件（都踩过）

| # | 问题 | 现象 | 解法 |
|---|---|---|---|
| 1 | 训练镜像缺依赖 | `ModuleNotFoundError: einops`，换 DP 镜像后 `dm_control` | 构建期装：`docker/Dockerfile.robotwin-train`（`train deps OK`） |
| 2 | 原始数据布局 ≠ 训练布局 | `process_data.py` 找 `../../data/<task>/<config>/data/episode*.hdf5` | 软链 `aloha-agilex_clean_50` 到该路径，再跑 `process_data.py <task> <config> <num>` |
| 3 | DataLoader worker 崩 | `DataLoader worker (pid(s) 110) exited unexpectedly` | 训练容器加 `--ipc=host`（默认 64MB /dev/shm 不够） |

另外：镜像里的 `SIM_TASK_CONFIGS.json` 是 **0 字节**；`process_data.py` 会为每个 task 写入配置，所以每个训练容器都要先跑它（或挂载生成好的 JSON）。

### 实测输出

```
process_data: proccess 49 success!
number of parameters: 83.90M
Epoch 0: Train loss 53.67689 | Val loss 73.86844
ckpt:
  policy_last.ckpt          321M
  policy_best.ckpt          321M
  policy_epoch_0_seed_0.ckpt 321M
  policy_epoch_1_seed_0.ckpt 321M
  dataset_stats.pkl         5.7K
```

`policy_last.ckpt` + `dataset_stats.pkl` 与 serve 契约一致（第 12 节），可直接进 S4。

### 可重复入口（2026-11-25 干跑通过）

S3 不再靠手敲命令：`scripts/r01/s3_train_act.sh` 把五个前置条件都封进去
（训练镜像、`--ipc=host`、软链布局、`process_data`、40k 步换算、产物校验）。

```bash
# 干跑：1 epoch 验证链路
bash scripts/r01/s3_train_act.sh --task click_bell --regime clean_50 --epochs 1 --dry-run

# 正式：按 40k 步自动换算 epochs（50 集≈5714，550 集≈580）
bash scripts/r01/s3_train_act.sh --task click_bell --regime clean_50
```

干跑输出：`policy_last.ckpt` + `dataset_stats.pkl` + `run.json`（task/regime/episodes/epochs/seed）。

### 磁盘/时间估算

- 单 ckpt 321MB；一次训练至少留 5 个文件 ≈ 1.6GB → 20 个 ckpt ≈ **32GB**（`/data` 余 397GB，够）
- 1 epoch（50 集、7 batch）在本机约 1 分钟量级。

### 计时实测与预算影响（2026-11-25，GPU0）

3 epoch / 21 步实测（含模型初始化与 3 次验证）：**25 秒** → 约 **0.8–1.2 s/step**。

| 项 | 估算 |
|---|---|
| 单 ckpt（40k 步） | **9–13 小时** |
| 20 个 ckpt，单卡串行 | **7.5–11 天** |
| 20 个 ckpt，两卡并行 | **4–5.5 天**（但 S4 评测也要卡，不能全程并行） |
| 成本（¥32.87/h） | 单卡 **¥6000–8700**；两卡并行约 ¥6000–7000（含 S4） |

**结论**：原估"S3 3–4 天 / 总 6–7 天 / ¥5500"偏乐观。按实测吞吐，
S3 本身就可能吃掉 7.5–11 天（单卡）。

> **决定（2026-11-25）**：接受 **7.5–11 天 / ¥6000–8700**；**单卡串行**，不与评测抢卡。
> 启动条件：002 上无其他评测（place_empty 结束后）再开始 S3。

---

## 14. DP 训练冒烟与已知缺口（2026-11-25）

ACT 之外，DP 也做了一次 1 epoch 冒烟（`vla-robotwin-train-dp:dev`，click_bell clean_50）：

| 项 | 结果 |
|---|---|
| `process_data.py` → zarr | 50/50 ep 成功 |
| 训练 | 1 epoch / 29 batch，约 25s，loss ≈ 1.03 |
| 参数 | 8.56e7 |
| 缺依赖 | `wandb`（DP 镜像没有，构建期补：`docker/Dockerfile.robotwin-train-dp`） |
| **缺口** | **没产出 ckpt**：`checkpoint_every=300`、`save_last_ckpt=True`，保存触发/路径未确认 |

**结论**：DP 训练链路能跑，但"40k 步后 ckpt 落在哪"必须在 S3 首次正式训练时先确认，
再批量跑 10 个 DP ckpt。不要假设 serve 侧的 `<task>-<setting>-<num>/<num>.ckpt` 路径。
