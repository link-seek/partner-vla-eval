---
title: 官方榜单快照（RoboTwin 2.0 Leaderboard）
nav_exclude: true
status: living
---

# 官方榜单快照

`robotwin_leaderboard_2026-11-20.json` 是官方榜单的一次**只读快照**，用于两件事：

1. 校准表里的"官方值"不再手抄，全部从这份快照读；
2. 校准行生成器 `scripts/ci/calibration_row.py` 的官方数据源。

## 出处

| 项 | 值 |
|---|---|
| 数据源 | `https://robotwin-platform.github.io/data/robotwin_leaderboard.json` |
| 榜单页 | `https://robotwin-platform.github.io/leaderboard` |
| board updated | **2026-11-20**（快照自带字段） |
| 抓取日 | 2026-11-25 |
| 规模 | 37 个 entry × 50 个 task（Easy / Hard 各 50 列） |
| 大小 | 约 68 KB |

## 为什么入库快照而不是每次现抓

- 榜单会变；分数引用了哪一版必须能追。快照就是"官方值"的版本号。
- CI 与本地校验不该依赖外网（raw 链接国内也不稳）。
- 刷新是显式动作：换文件 + 改文件名日期 + 提 PR，历史留在 git。

## 怎么用

```bash
# 查官方值（对齐/核对用）
python3 scripts/ci/calibration_row.py --entry sft:ACT --task click_bell --official-only
# → ACT · click_bell · easy = 58% (board 2026-11-20)

# 官方值不在榜单里（如 DB-CogACT 的 28% 来自 Dexbotic）→ 显式覆盖 + 写出处
python3 scripts/ci/calibration_row.py --entry db-cogact --task place_empty_cup \
    --official-value 28 --official-source "Dexbotic 论文/官方 repo" --aggregate <agg.json>

# 从我们的 aggregate 直接生成校准行（不手抄）
python3 scripts/ci/calibration_row.py --entry sft:ACT --task click_bell \
    --aggregate /path/to/click_bell_aggregate.json
# → | click_bell | 58%（29/50） | 58% | **+0pp** |
```

生成器默认拒绝两类"看起来有数、其实无效"的 aggregate：不同种子数 < n（同一集重复跑）、
n < 10（区间太宽）；`--selftest` 有 17 项断言（含这两条），
已进 `scripts/gates/run_all.py` 的 `calibration` 门（快照被改坏会直接红）。

## 刷新流程

1. 抓最新 `robotwin_leaderboard.json`；
2. 存成 `robotwin_leaderboard_<updated>.json`（日期取 `board.updated`，不是抓取日）；
3. 改本文与 `scripts/ci/calibration_row.py` 的 `DEFAULT_SNAPSHOT`；
4. `python3 scripts/ci/calibration_row.py --selftest`（锚点变了就一起改断言，并说明原因）；
5. 提 PR。
