# 01 业务与覆盖

> 版本：v1.0（2026-10-14）

## 给谁评

来评测的伙伴模型，只需交两样东西：权重地址 + 一个 serve 配置（见 06）。
我们不碰他们的训练代码，只跑分。

## 覆盖矩阵

| 能力 | 考场 | 参考模型 | 状态 |
|---|---|---|---|
| 单臂短程基线 | LIBERO | π0.5（LeRobot 桥） | ✅ smoke 1/1 |
| 单臂长程 | CALVIN | DB-CogACT | ✅ smoke 4/5 |
| 双臂基线 | RobotWin 2.0 | DB-CogACT（按 task 分头） | ✅ 4 轮出分 |
| 双臂长程通用 | DuoBench | 待定 | 🔲 规划位（11 task×100ep，星少，先 smoke） |
| 记忆专项 | RMBench | 待定 | 🔲 规划位（9 题，同 RobotWin 栈） |
| 双臂紧耦合前沿 | BiCoord | 待定 | 🔲 二期（harness 未接） |
| 真机 | — | — | 🔲 后放（SimplerEnv 等） |

## 为什么是这三件套先行

- LIBERO 最便宜，先证明 serve 链路本身正常。
- CALVIN 补长程（5 连任务），和 LIBERO 短任务互补。
- RobotWin 覆盖双臂（50 task，Easy+Hard）。
- 一个考场只回答一个问题，不追求单榜全能。
