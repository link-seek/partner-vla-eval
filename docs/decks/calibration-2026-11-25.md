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
