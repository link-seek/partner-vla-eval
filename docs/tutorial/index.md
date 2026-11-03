# 评测教程：从哪里开始

> 版本唯一真源：`docker/versions.yaml`（harness 全系 `0.8.0`）。本文只给路线，不钉版本号。

## 你是谁？走哪条路？

| 你是 | 目标 | 走法 | 时间 |
|---|---|---|---|
| 伙伴（来评测模型） | 交权重+配置，拿到分数 | `quickstart` → `partner/01-serve-yaml` → `02-smoke` → `03-full-and-report` | smoke 0.5~2h，全量 3~7h/task |
| 运维（开卡保链路） | 让 V100 离线跑起来 | `quickstart` → `operator/01-machines-ci` → `02-images` | 按需查，不必通读 |
| 复现者（对照分数） | 看懂一张分数怎么来的 | `quickstart` → `explanation/` → `reference/` | 30min |

三条路都从同一篇开始：`quickstart.md`（RobotWin smoke，grab_roller×1ep，只验链路不计分）。

## 核心概念（3 行，够用即走）

```text
serve（模型/GPU，WebSocket） ←→ benchmark（环境/CPU，Docker）
configs/serve-*.yaml：1 模型 1 个 ｜ configs/run-*.yaml：1 考场 1 组
```

* **考场**：一个 benchmark（环境+任务集+判分规则）。先行三件套：LIBERO（单臂短程，最便宜）→ CALVIN（单臂长程）→ RobotWin（双臂）。
* **smoke**：1 task×1ep，只验链路。**全量**：1 task×50ep（`test_num` 官方口径），计分。
* **分数各榜自己定**：harness 不发明分数，只透传各榜原生规则再平均。LIBERO / RobotWin 是单 ep 二值分（成或败）；CALVIN 是一个 ep = 5 连子任务，同时报 `success`（5/5 全对才算）+ `completed_subtasks`（0~5，部分分）。看分先确认是哪个指标。跨榜只并列展示，不加权总分。

## 覆盖矩阵（一张表）

| 能力 | 考场 | 参考模型 | 状态 |
|---|---|---|---|
| 双臂基线 | RobotWin 2.0 | DB-CogACT（按 task 分头） | smoke + 4 轮出分（见 `quickstart` 对照表） |
| 单臂短程基线 | LIBERO | π0.5（LeRobot 桥） | smoke 1/1 全绿（链路对照用） |
| 单臂长程 | CALVIN | DB-CogACT | smoke 4/5（5 sequences 全对，success 口径；链长另看） |
| 双臂长程 / 记忆 / 真机 | DuoBench / RMBench / 真机 | 待定 | 规划位，先 smoke，后放 |

## 文档地图（四分法）

* **Tutorial（学）**：`quickstart` + `partner/` —— 跟着跑，保证绿。
* **How-to（做）**：`operator/` —— 开机、打镜像、修 runner，按需查。
* **Reference（查）**：`reference/` —— 口径映射表、镜像 tag、15 条排障表。主线不展开，只给链接。
* **Explanation（懂）**：`explanation/` —— 栈差异 A-D、精度断崖、种子效应。有结论才进榜，主线一句话带过。

旧稿 `00~09/99` 原样保留，迁完再归档。版本历史与口径偏离见 `changelog.md`，正文不写版本号。
