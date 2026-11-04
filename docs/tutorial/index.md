---
title: 评测教程
nav_order: 1
has_children: true
---

# 评测教程：从哪里开始

> 版本唯一真源：`docker/versions.yaml`（harness 全系 `0.8.0`）。本文只给路线，不钉版本号。

## 为什么要这么评（先看这段，再决定要不要往下读）

伙伴自测的分数互相不可比，三处不同：**训练口径**不同（per-suite 微调 vs 通用
单 checkpoint，Table 3 里一动 30pp）、**环境栈**不同（GPU/精度/镜像/种子，
A-D 对照里一动 6~92pp）、**判分标尺**不同（各榜成功率/链长各说各话）。
横向评测就是把这三处全固定，只让模型变——这套教程的每一篇，都是在固定其中一处：
quickstart 证明尺子可信，01~03 交出可比的数，Hard 与训练固定是评测阶段的事。

## 为什么我们来做

1. **上游缺方法论层**：harness 是尺子，协议/审计/披露三块是空白（论文自认各榜
 协议不统一，leaderboard 只聚合论文数、不独立验证）。我们补的正是这一层：
 A-D 栈差异对照、披露清单、同协议排名规则。
2. **我们是做伙伴生态的，这个需求躲不掉**：伙伴选型要的是第三方可信分，
 不是论文数——无论别人做还是我们做，最后都要有人做。需求在我们手里，
 所以只能是我们牵头。
3. **路线对比下来，harness 最优，而这套链路是我们搭的**（目标=多模型×多榜横向可比）：

| 方案 | 接入成本 | 可比性 | 复现成本 | 独立验证 |
|---|---|---|---|---|
| 各家私有 eval fork（现状） | O(N×M)，每家重写 | 无（口径各说各话） | 低（conda env 冲突） | 有，但互不认 |
| 官方原生逐家跑（XPolicyLab/`policy/`） | O(N×M) | 有（官方协议内） | 中（两个 conda env 自装） | 有 |
| 上游 leaderboard | 零（摘数） | 弱（只聚合，不验证） | — | 无 |
| VLATest / VLA-Perf 系 | 按其轴（环境扰动/速度） | 不答可比性问题 | 高（580 卡时级） | 有 |
| **harness + 自建方法论层（我们）** | **O(N+M)**，一次接入 | **披露清单+协议锁定** | **高（Docker 隔离，digest 即版本）** | **有（V100 自跑）** |

harness 在"横向可比"目标下最优，可比性方法论又恰好空白——而我们是 harness
代码仓的代码贡献者之一（#168 已合入上游主线，#169 当天拿到维护者钥匙，
Phase 2 数据已同步上游讨论），跟原作者有持续良好的互动。别人用这套方案搭环境
是纯用——遇到尺子本身的 bug（如 EE 通路断裂、SmolVLA 维度错位）只能绕；
我们能改，修进去（#168 就是一例）。方法论层由我们补，上游信得过数据，社区也认。

## 你是谁？走哪条路？

| 你是 | 目标 | 走法 | 时间 |
|---|---|---|---|
| 伙伴（来评测模型） | 有训好的模型要交，拿分数 | `quickstart` → `partner/01-serve-yaml` → `02-smoke` → `03-full-and-report` | smoke 0.5~2h，全量 3~7h/task |
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
* **分数各榜自己定**：harness 不发明分数，只透传各榜原生规则再平均。单次 run 内，
 LIBERO / RobotWin 是单 ep 二值平均；CALVIN 是一个 ep = 5 连子任务，同时报 `success`
 （5/5 全对才算）+ `completed_subtasks`（0~5，部分分）。看分先确认是哪个指标。
 跨榜只并列展示，不加权总分。
* **LIBERO 的 % 还依赖训练口径**：上游复现全是按 suite 出分（4 suites×10 tasks×50ep），
 且多为 per-suite 微调 checkpoint（OpenVLA 即 LoRA 分 suite 微调，单 checkpoint 跑不全四榜）。
 per-suite 微调与通用单 checkpoint 的 % 不可比——只看数字会把微调红利当成基模能力。
 比 LIBERO 必须同时对齐 checkpoint 与训练说明（见 `partner/01` 表单第 2/6 项）。

## 覆盖矩阵（一张表）

| 能力 | 考场 | 参考模型 | 状态 |
|---|---|---|---|
| 双臂基线 | RobotWin 2.0 | DB-CogACT（按 task 分头） | smoke + 4 轮出分（见 `quickstart` 对照表） |
| 单臂短程基线 | LIBERO | π0.5（LeRobot 桥） | smoke 1/1 全绿（链路对照用） |
| 单臂长程 | CALVIN | DB-CogACT | smoke 4/5（5 sequences 全对，success 口径；链长另看） |
| 双臂长程 / 记忆 / 真机 | DuoBench / RMBench / 真机 | 待定 | 规划位，先 smoke，后放 |

## 我们现在在哪一步（评价 vs 评测，必读以免误读分数）

* **评价（已完成）：跑出可信的分数**——链路跑通、三榜 smoke 全绿、RobotWin 四轮出分、
 栈差异 A-D 对照、披露清单。回答"这个配置下多少分"，**不回答"哪个基模强"**。
* **评测（未开始）：可比、可解释的基模比较**——固定数据和训练方式（如官方 §4.5 范式：
 单 task 50 demos 微调 → Easy/Hard 各 100 rollouts），横向比较伙伴基模在同训练
 口径下的成功率（官方 Table 3 范例）。这需要训练侧立项（数据+ recipe +算力，
 见 `old/99-audit.md` 第 5 条"另立项 finetune"），是新工程，不是本教程的范围。

没有阶段一，可比的阶段二不存在（口径一动几十分点）；但只有阶段一时，
任何"基模排名"式解读都是错的。

## 文档地图（四分法）

* **Tutorial（学）**：`quickstart` + `partner/` —— 跟着跑，保证绿。
* **How-to（做）**：`operator/` —— 开机、打镜像、修 runner，按需查。
* **Reference（查）**：`reference/` —— 口径映射表、镜像 tag、15 条排障表。主线不展开，只给链接。
* **Explanation（懂）**：`explanation/` —— 栈差异 A-D、精度断崖、种子效应。有结论才进榜，主线一句话带过。

旧稿归档在 `old/`（只读，迁移映射见 `old/README.md`）。版本历史与口径偏离见 `changelog.md`（待写），正文不写版本号。
