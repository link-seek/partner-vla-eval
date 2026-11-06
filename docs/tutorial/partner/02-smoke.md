---
title: 伙伴 02：smoke
parent: 评测教程
nav_order: 4
---

# 伙伴 02：smoke（1 天内，通/不通）

> 目标：确认链路通、口径对齐；不通在这里打回，不烧全量卡钱。
> 时间：0.5~2 小时（含排队） ｜ 前置：01 的 yaml 已确认。
> 你将得到：通/不通 + spec 对齐摘要。

## 操作

我们按你交的 yaml 起 serve，跑 RobotWin 1 task × 1ep：B 用 `grab_roller`，C 用 `adjust_bottle`。只跑 RobotWin，不开其他榜。

输出两样：**通/不通 + spec 对齐摘要**。口径不对这里打回；通过后才进全量。摘要三行这样读：

1. `serve UP` + `smoke_exit=0`：serve 起来了，链路通了。
2. 日志里没有 `Spec mismatch`：口径对上了，可以烧卡。
3. 有 `Spec mismatch`：看它是 advisory 还是真拦路（见原理）。

## 检查点：不通的三种死法

| 现象 | 根因 | 下一步 |
|---|---|---|
| serve 起不来（`HFValidationError` / 401） | 路径三段式 / 权重无权限 | 回 01 补精确版本 + 开授权 |
| 跑满但全 0 分、零异常 | 口径错（EE 当关节喂等） | 按模板改 serve yaml，重跑 smoke |
| 全 ERROR 但 exit 0 | error 当数据 | 先看 errors 列；infra / 坏种子单列重跑 |

## 原理

* **warning 分级**：`action [ee_pose]: benchmark expects it but server doesn't declare it` 只是 advisory——实测照通（X-VLA EE 跑满 400 步零 ERROR）；真拦路的是 unknown kwarg 类错误和维度 / 相机 / chunk 错配。
* **smoke 为什么省钱**：smoke 只跑 1 task × 1ep，全量是 50 task；smoke 绿 = 权重、serve、口径、落盘四个变量一次对齐，全量只是加 task 和集数，不引入新变量。跳过 smoke 直接全量，口径错了就是全量的卡钱（单 task 3~7 小时）。

## 下一步

通过 → 进全量排期（[03-full-and-report.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/partner/03-full-and-report.md)，按 task 数串行）。
