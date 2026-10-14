# 02 技术架构

> 版本：v1.0（2026-10-14）。上游：`allenai/vla-evaluation-harness`，`vla-eval v0.7.0`
> （benchmark 镜像 0.8.0，见 03）。

## 总览

一次接入，多处复用：模型接一次（serve 配置），基准接一次（Docker 镜像 + run 配置），
交叉矩阵自己填满。官方原话：模型 benchmark 解耦，Docker 隔离依赖。

```
serve（模型/GPU，宿主） ←WebSocket/msgpack→ benchmark（环境/CPU，容器）
        ↑                                              ↑
  configs/serve-*.yaml                    configs/run-*.yaml
  1 模型 1 个                              1 考场 1 组
```

## 选型回指业务（每个选型支撑哪块业务）

| 选型 | 支撑业务 | 不选它的后果 |
|---|---|---|
| harness 统一执行 | 多模型×多榜单复用，不用每家重写评测 | 各维护一套私有 eval fork |
| RobotWin 2.0 | 双臂基线（50 task） | 双臂无尺子 |
| LIBERO | 单臂短程基线（最便宜） | 链路问题和模型问题分不清 |
| CALVIN | 单臂长程 | 长程能力没尺子 |
| serve/model 分离 | 伙伴只交配置+权重 | 要动人家训练代码 |
| Docker 按榜隔离 | robosuite/SAPIEN/Thor 装不到一起 | 依赖打架 |
| mean_success 透传 | 跨榜只并列展示，不造总分 | 榜单不可比还硬比 |

## 没选什么

- 真机（后放）、DuoBench/RMBench（规划位，先 smoke）、BiCoord（harness 未接，二期）。
