---
title: EE 通路：16D 端到端是怎么跑通的
parent: 原理与案例
nav_order: 3
---

# EE 通路：16D 端到端是怎么跑通的

> 给复现者：RobotWin 有两套动作口径（qpos 14D / EE 16D），EE 这条是 #168 修通的。
> 时间：10 分钟 ｜ 前置：`quickstart`。
> 你将得到：两次报告（0/8 验证通路 → 66.6% 出分）、口径对照、复现方法。

## 现象（一句话）

RobotWin benchmark 收两种动作：`action_type: qpos`（14D 关节）或 `action_type: ee`
（16D 末端位姿，双臂各 `[pos3, quat_wxyz4, gripper1]`，先左后右）。EE 口径下
CuRobo 规划每个 pose，所以 `fast_init` 自动关。

## 证据（两次）

| 时间 | 报告 | 结果 | 说明 |
|---|---|---|---|
| 10-27 | [`x-vla_robotwin-ee_grab_roller.json`](https://github.com/link-seek/partner-vla-eval/blob/main/docs/reports/x-vla_robotwin-ee_grab_roller.json)（[run](https://github.com/link-seek/partner-vla-eval/actions/runs/40471468752)） | 0/8，零 error，8 集各跑满 400 步 | 通路端到端成立；0 分是任务难，不是链路问题 |
| 11-04 | [`xvla_robotwin-easy50.json`](https://github.com/link-seek/partner-vla-eval/blob/main/docs/reports/xvla_robotwin-easy50.json)（[run](https://github.com/link-seek/partner-vla-eval/actions/runs/41377057472)） | 66.6%（3328/5000），零 error | 50 task × 100ep，可出分 |

## 机理

上游 [#168](https://github.com/allenai/vla-evaluation-harness/pull/168)（已合入主线）补了三件：

1. benchmark 侧：`action_type: ee` + `send_state`（16D 末端位姿进 obs）。
2. serve 侧：X-VLA 输出 20D EE6D → 转 16D（见 [04-20d-to-16d.md](./04-20d-to-16d.html)）。
3. run 侧：`max_steps: 300`、`render_every: 30`（chunk 开环跑，只在查询处渲染）。

口径错配必 0 分：EE 当关节喂，benchmark 硬截 `act[:14]`——400 步跑满全 0 分零异常。
smoke 遇到 `Spec mismatch` 直接打回，不让它烧卡（见排障表第 1 条）。

## 复现者怎么复现/避坑

1. **EE 配置三件套**：`action_type: ee` + `send_state: true` + `fast_init: false`
   （PPO 那套 `fast_init=true` 在 EE 下非法，IK 走 `plan_path`）。
2. **分片降到 4**：EE 全量 planner + SAPIEN 抢显存，8 分片 OOM（10-27 实测 3/10
   `env_start`）。qpos 保持 8。
3. **看步数**：EE 跑满 400 步零 error 但 0 分，先查口径（是不是截错了），再查任务难度。

## 下一步

- 20D 怎么转成 16D：[04-20d-to-16d.md](./04-20d-to-16d.html)。
- 精度为什么选 fp32：[02-precision-cliff.md](./02-precision-cliff.html)。
