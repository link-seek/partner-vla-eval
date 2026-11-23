---
title: 变更记录
parent: 评测教程
nav_order: 10
---

# 变更记录

> 只记会影响读法/复现的变更；日常文字修订不进来。

## 2026-11-23

- **开关机不再依赖 hw21**：`start-ecs`/`stop-ecs` 迁到 GitHub 托管 runner（`power.yml`），密钥统一用 org 级 `PROD_HCLOUD_*`；hw21 只保留跳板用途（repair/ts-join）。
- **全量与 smoke 统一切 0002**（run 45174481686 首验通过）：runner 标签 `V100-0002`（org 级 `ecs-0002`），concurrency `gpu-ecs-0002-smoke`，power 调用显式 `server-id`；0001 冻结不动。
- **修全量两个真缺陷**：`bench_tag` 默认 `0.8.0` 是 stock 镜像、无 `/opt/patches/run_sharded.sh` → 跑到第 6 步才 127（#11 同因），默认改 `0.8.0-ee-slim` 并在拉镜像后预检；资产挂载改 `--mount` + 用「镜像内不存在」的 `objects/objaverse/list.json` 做探针，堵住 `-v` 静默空挂。
- **OBS 全量落盘结构**：`<obs_prefix>/robotwin-full/results/robotwin-<chunk>-x<ep>/`（含 `episodes/`、aggregate、sqlite、shard/serve 日志），smoke 仍在 `<obs_prefix>/robotwin-smoke/`。
- RobotWin smoke 复跑通过（run 45099674808）：三机自动开关、OBS 产物 11 个（含 2 个 mp4）。
- 文档校正：easy50 零分 task 5 个（原写 6）、grab_roller 90%（45/50，原写 92%）、place_empty_cup 14%（7/50，原写 16%）、EE OOM 2 例（原写 3/10）、步数 300（10-27 那轮 400）。

## 2026-11-16

- 运维篇收敛为三篇：01 系统/开跑/排障、02 开跑与收产物、03 镜像查版；补齐 `operator/`、`partner/` 目录落地页。

## 2026-11-04

- X-VLA EE easy50 跑完：50 tasks × 100ep，66.6%（3328/5000），零 error（run 41377057472）。

## 2026-10-27

- EE 16D 通路端到端成立：grab_roller 0/8，零 error，步数跑满（run 40471468752）。

## 2026-10-14

- 栈差异对照 A/D 组：镜像 0.7.0 vs 0.8.0（86% vs 92%）、盲种子 vs 校验种子（35/35 + 15 坏种）。
