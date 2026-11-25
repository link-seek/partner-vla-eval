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

# 从我们的 aggregate 直接生成校准行（不手抄）
python3 scripts/ci/calibration_row.py --entry sft:ACT --task click_bell \
    --aggregate /path/to/click_bell_aggregate.json
# → | click_bell | 58%（29/50） | 58% | **+0pp** |
```

`--band`（默认 4pp）之外的差异会标 `← 离群`；`--selftest` 有 13 项锚点断言，
已进 `scripts/gates/run_all.py` 的 `calibration` 门（快照被改坏会直接红）。

## 刷新流程

1. 抓最新 `robotwin_leaderboard.json`；
2. 存成 `robotwin_leaderboard_<updated>.json`（日期取 `board.updated`，不是抓取日）；
3. 改本文与 `scripts/ci/calibration_row.py` 的 `DEFAULT_SNAPSHOT`；
4. `python3 scripts/ci/calibration_row.py --selftest`（锚点变了就一起改断言，并说明原因）；
5. 提 PR。
