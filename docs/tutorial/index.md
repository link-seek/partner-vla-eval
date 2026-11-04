---
title: 评测教程
nav_order: 1
has_children: true
---

# 评测教程：从哪里开始

> 版本唯一真源：`docker/versions.yaml`（harness 全系 `0.8.0`）。本文只给路线，不钉版本号。

## 为什么要这么评（先看这段，再决定要不要往下读）

伙伴自测的分数互相不可比，三处不同：**训练口径**不同（per-suite 微调 vs 通用
单 checkpoint，RoboTwin 2.0 论文 §4.3 Table 3 里换训练口径相对差 30%（RDT 18.8%→24.8%，绝对 6pp））、**环境栈**不同（GPU/精度/镜像/种子，
栈差异对照里一动 6~97pp（镜像差 6pp，精度差 97pp））、**判分标尺**不同（各榜成功率/链长各说各话）。
横向评测就是把这三处全固定，只让模型变——这套教程的每一篇，都是在固定其中一处：
quickstart 证明尺子可信，01~03 交出可比的数，Hard 与训练固定是评测阶段的事。

## 为什么我们来做

1. **有需求**：伙伴选型要的是第三方可信分，不是论文数——无论别人做还是我们做，
最后都要有人做。需求在我们手里，所以只能是我们牵头。
2. **我们代表第三方客观**：不训模型、不卖模型，只出数。上游 leaderboard 只聚合
论文数、不独立验证（上游论文 Limitations 原话）。独立第三方 + 方法数据
全披露 + 可复现——这个生态位是空的，我们站上去。权威不是宣称来的，是 Hard 与
训练对照跑出来之后挣的，在那之前只谈独立，不谈权威。
3. **有能力**：V100 离线链路现成（执行）；栈差异对照、披露清单、排名规则（方法，
对照已补，清单与规则在跑）；harness contributor，能改尺子（#168 已合入上游主线，
#169 当天拿到维护者钥匙）——别人纯用遇到尺子 bug 只能绕（EE 通路断裂、SmolVLA
维度错位），我们修进去。路线对比（目标=多模型×多榜横向可比）：

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
 栈差异对照、披露清单。回答"这个配置下多少分"，**不回答"哪个基模强"**。
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
* **Explanation（懂）**：`explanation/` —— 栈差异对照、精度断崖、种子效应。有结论才进榜，主线一句话带过。

旧稿归档在 `old/`（只读，迁移映射见 `old/README.md`）。版本历史与口径偏离见 `changelog.md`（待写），正文不写版本号。
