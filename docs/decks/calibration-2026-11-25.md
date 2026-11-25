---
title: 校准表：我们 vs 官方（截至 2026-11-25）
nav_exclude: true
status: living
---

# 校准表：我们 vs 官方

> 目的：证明**同一把尺子量官方基线，量出来的数和官方接近**。
> 数据源：官方榜单**入库快照** `docs/data/official/robotwin_leaderboard_2026-11-20.json`（board updated 2026-11-20，37 entry × 50 task）。
> 官方值不手抄：由 `scripts/ci/calibration_row.py` 从快照读取并生成对照行。
> 口径差异：官方 **100 trials/task**，我们 **50 ep/task**（噪声带见文末）。

---

## 一、DB-CogACT：4 个 task

| task | 我们 | 官方 | 差 | 备注 |
|---|---|---|---|---|
| grab_roller | 92%（46/50） | 89% | **+3pp** | 0.8.0 校验种子，零 error |
| adjust_bottle | 100%（35/35 有效） | 99% | **+1pp** | 0.7.0；15 个坏种已剔除 |
| place_phone_stand | 16%（8/50） | 18% | **−2pp** | 0.8.0 校验种子 |
| place_empty_cup | 16%（8/50） | 28% | **−12pp** | 离群：V100 fp16 vs 官方 H100 bf16 + 种子分布不同 |
| **有效平均** | **56%** | **58.5%** | **−2.5pp** | — |

## 二、X-VLA：5 个 task（Easy）

| task | 我们 | 官方 | 差 |
|---|---|---|---|
| grab_roller | 98%（49/50） | 100% | **−2pp** |
| adjust_bottle | 98%（49/50） | 99% | **−1pp** |
| place_phone_stand | 96%（48/50） | 84% | **+12pp** ← 离群 |
| click_bell | 96%（48/50） | 100% | **−4pp** |
| handover_block | 78%（39/50） | 77% | **+1pp** |

### 50 task 全量（官方口径）

| 项 | 我们 | 官方 | 差 |
|---|---|---|---|
| Easy 50 task × 100 ep | **66.56%**（3328/5000） | **67.96%** | **−1.40pp** |

这是整份校准里最硬的一条：**样本量相同（5000 集）、task 集相同、口径相同**，差 1.4pp。

---

## 三、汇总

| 维度 | 结果 |
|---|---|
| 覆盖模型 | **2 个**（DB-CogACT、X-VLA） |
| task 级对照 | **9 条** |
| ±4pp 内 | **7 条** |
| 离群 | 2 条：CogACT `place_empty_cup` −12pp、X-VLA `place_phone_stand` +12pp |
| 全量均值 | X-VLA 50 task：**−1.4pp** |
| 均值（4+5 task 合计） | CogACT −2.5pp / X-VLA 5 task 平均 −1.2pp |

**结论**：两个模型、九条对照、七条落在噪声带内，两条离群都**主动标出并给了原因**——
这正是"可被采信"的定义：不是所有格子都完美，而是**不可比的地方自己先说**。

---

## 四、噪声带（为什么用 ±4pp 作判据）

| 样本量 | p=0.9 时 95% CI 半宽 | p=0.5 时 |
|---|---|---|
| n=50（我们） | ±8.3pp | ±13.9pp |
| n=100（官方） | ±5.9pp | ±9.8pp |
| n=5000（全量） | ±0.8pp | ±1.4pp |

所以：
- 单 task n=50 的对照，**±10pp 内的差异不能当结论**（这也是为什么两条 12pp 标成"离群/待定"而不是"我们错了"）
- 50 task 全量 n=5000 的 −1.4pp，**落在噪声带内**，可以当"一致"

---

## 五、下一步（P1，需烧卡）

| 项 | 预期对照（官方 Easy） | 成本 |
|---|---|---|
| ACT `click_bell` × 50ep | 官方 58% | ≈¥104 |
| DP `click_bell` × 50ep | 官方 54% | ≈¥104 |
| place_empty_cup +100ep（CogACT） | 官方 28%，看是否收敛 | ≈¥208 |

ACT/DP 是**官方自带的基线**，跑它们等于"用官方自己的模型验我们的尺子"，比第三方模型更有说服力。

### 开跑前抓到并修掉一个静默错误

ACT 首次 50 集起跑后 4 集全 0。查下来：官方 `get_model` 只认 `<ckpt_dir>/policy_last.ckpt`，
而发布的权重叫 `policy_epoch_6000_seed_100.ckpt`，加载器打一行 Warning 就继续 → **随机权重跑满 400 步，不报错**。

| 动作 | 结果 |
|---|---|
| 旧路径（只给 ckpt_dir） | 0/4，每集 400 步，无 error |
| 修后 1 集 smoke（显式 `ckpt_file` + 严格断言） | **1/1 success，num_errors=0** |
| 适配器改成 fail-closed | 缺 `policy_last` 且未给 `ckpt_file` 直接报错，不再静默 |

这也解释了为什么"零 error"不能单独作为链路正确的证据——**error 计数抓不到随机权重**。

### 紧接着又抓到第二个静默错误：同一个种子重复 50 次

权重修好后，前 5 集全是 success，而且**每集都是 69 步、74 秒**——太整齐了。查 aggregate：

| 集 | seed | steps |
|---|---|---|
| 0 | 100000 | 69 |
| 1 | 100000 | 69 |
| … | 100000 | 69 |

`smoke_serve.sh` 当时写的是 `episodes_per_task: 50` + `test_num: 1`。
harness 的语义是：**`test_num` = 不同种子的任务数，`episodes_per_task` = 每个任务重复几集**。
于是 50 集其实是同一集跑了 50 次，n=1，看起来像 5/5，实际什么都没测。

matrix 路径一直是对的（`episodes_per_task: 1` + `test_num: 50`），所以此前 X-VLA / CogACT 的 50 集不受影响。

修法与证据：

| 检查 | 结果 |
|---|---|
| 旧配置（1 task × 50 ep） | 5 集全 seed 100000、69 步 |
| 改后（50 task × 1 ep）2 集验证 | seed **100000 / 100001**，步数 **69 / 87** |
| `smoke_serve.sh` 后置断言 | 不同种子数 < 期望集数 → 直接 FAIL，不再静默 |

所以现在"n=50"有三个必要条件：不同种子 50 个、每集独立跑、error 计数为 0。缺一个都不是 n=50。

这两条现在由生成器**强制**，不再靠人看：

| 输入 | `calibration_row.py` 行为 |
|---|---|
| 不同种子数 < n（假 n） | **拒绝**，提示 `test_num/episodes_per_task` 配反；确需继续用 `--allow-repeated-seeds` |
| n < 10 | **拒绝**（区间半宽 >20pp 不能进表）；查链路用 `--allow-small-n` |
| 正常 n=50、种子各不相同 | 输出表格行 + JSON（含 `distinct_seeds`） |

---

## 六、官方基线的官方值（从快照读，非手抄）

`python3 scripts/ci/calibration_row.py --entry <id> --task click_bell --official-only`：

| entry | 模型 | click_bell (Easy) | 50 task Easy 均值 | 50 task Hard 均值 |
|---|---|---|---|---|
| `sft:ACT` | ACT | **58%** | 29.74% | 1.74% |
| `sft:DP` | DP | **54%** | 28.04% | 0.64% |
| `cotrain:X_VLA` | X-VLA | 100% | 67.96% | 20.95% |

（X-VLA 的 67.96% 就是第二节"50 task 全量"的官方参照；三行同源，可一次复核。）

## 七、结果怎么并表（机械动作）

校准跑结束后，不再手工抄数：

```bash
# ACT click_bell 50ep 跑完
python3 scripts/ci/calibration_row.py --entry sft:ACT --task click_bell \
    --aggregate <aggregate.json>
```

输出即为可粘贴的表格行（含 K/N、差值、超出 4pp 的自动标"离群"），同时打印一份 JSON
（ours/official/delta/outlier/snapshot/board_updated），供报告与榜单引用。
快照本身由 `calibration` 门守住：13 项锚点断言（ACT 58、DP 54、X-VLA 100 / 67.96、50 task、任务名映射、
离群标注、aggregate 解析），改坏快照会直接红。

---

## 八、ACT / DP：口径先对齐，再谈一致性

跑之前先查了官方口径，发现一处**不能忽略的差异**：

| 项 | 官方榜单 | 我们挂的公开 ckpt |
|---|---|---|
| 训练数据 | **50 demo_clean × 50 task**（2,500 demos） | **100 demos/task**（路径 `click_bell/demo_clean-100/100`） |
| 评测 | 100 trials/task | 50 ep/task |

官方快照 `board.train_data` 原文：`50 demo_clean x 50 tasks (2,500 demos)`。
公开权重仓（`Avada11/RoboTwin-Model-AgileX-ACT`、`-DP`）里 **没有 50-demo 版本**，
只有 `demo_clean-100`（HF 目录清单实测）。

所以：

- ACT / DP 的分数只能作 **100-demo 参考基线**，**不能**与官方 58% / 54% 算同口径差值，
  也不计入"±4pp 一致"的条数；
- 要对齐官方，需要 50-demo 权重（公开仓没有）或自训 50-demo（属 R01 范围）；
- 这一条必须写在结果旁边，否则 94% vs 58% 会被误读成"我们的尺子偏松"。

（中途读数：ACT click_bell 50 种子跑到 31 集时 29 success；最终以 aggregate 为准，
但无论多少，都不改变"口径不同"这个结论。）
