---
title: ADR-0002 产物保留、partial 只进附录、回归先测确定性
status: Accepted
date: 2026-11-25
nav_exclude: true
---

## 背景

三个悬而未决的产物治理问题（原文实测数据见 git 历史 `docs/internal/decisions-retention-partial-regression.md@~1`）：

1. **recording sqlite 保留多久**：单 task 50 集约 3.1MB，一次活动约 62MB，`/data` 剩 400G，OBS 约 ¥0.006/月
2. **partial（n<50）进不进榜**：n=12 的 95% CI 约 ±27pp，n=50 约 ±8.3pp —— 不同 n 根本不可比
3. **回归测试频率**：前置未知是"同种子重跑是否逐集一致"

## 选项

| 决策 | 选项 | 代价 |
|---|---|---|
| sqlite | A 全留 / B 留 90 天 / C 只留 aggregate | A ≈¥0.006/月；C 失去救援与逐集复核 |
| partial | A 只进附录 / B 进榜标 n / C 丢弃 | B 一定有人拿 n=12 比 n=50 |
| 回归 | A 先花 ¥20 测确定性 / B 每月 50ep / D 每周 | B ¥105/月；D ¥420/月（过度） |

## 决定

- **sqlite 全留**（A）：它是唯一能重算 aggregate、逐集回查 `failure_detail`、崩溃后救援的载体；成本可忽略
- **partial 只进附录**（A）：榜单强制 `n == exam.episodes`，附录文件必须 `partial: true` + `n_target`
- **回归先做确定性实验**（A）：1 task × 3 集 × 3 轮同种子，再依结果定频率

## 后果

**已落地（可验证）**

- `RW_RESUME=1` 跳过清盘；`scripts/data/rescue_partial.sh` 实测从进行中的 sqlite 捞出 `8/12`
- `check_leaderboard` 两条门禁：`n != 50` 即红、附录缺 `partial/n_target` 即红（反例已验证）
- 附录样例 `leaderboard/partial/x-vla-robotwin2-hard-grab_roller.json`（真实数据 8/12）

**OBS 侧核实（2026-11-25，此前只是"决定"，这次是"验证"）**

| 项 | 实测 |
|---|---|
| 桶 | `obs://so101-sim-pipeline`（cn-north-4，standard，3457 对象 / 58.07GB） |
| 生命周期规则 | **只有一条**：`下载/` 前缀 7 天过期 |
| `eval/` 前缀 | **无任何规则 → 默认永久保留**；实测 167.77MB |
| 对象版本化 | 未启用（`versionId=null`，不会堆积旧版本） |
| 成本 | 167.77MB × ¥0.099/GB/月 ≈ **¥0.017/月** |

证据存档：`docs/adr/evidence/obs-lifecycle-2026-11-25.json`；
复核/调整方法：`docs/howto/obs-lifecycle.md`（含"`put` 是整份替换"的坑）。

**未完成（明确记着）**

- 确定性实验未跑（需 GPU 空闲窗口，与 A5 同批）；因此**回归频率仍未定**

**触发重议**：OBS 存储账单显著上升；或 partial 数据被对外误用。

**副产品（同批纠正）**：镜像 digest 必须是 **manifest digest**（`buildx imagetools inspect`），
早期误用 `config.digest` 导致 `FROM image@digest` 报 `unexpected media type`。
