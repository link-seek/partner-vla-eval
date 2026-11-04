---
title: 伙伴 03：全量与报告
parent: 评测教程
nav_order: 5
---

# 伙伴 03：全量与报告（计分、出榜）

> 目标：拿到可上榜的分数和完整报告。
> 时间：3~7 小时/task（V100 单卡，串行累加） ｜ 前置：`02` smoke 通过。
> 你将得到：每个 task 的四列表分数 + 录像 + 官方口径对照说明。

## 操作

1. 排期（smoke 通过后自动进队列）：RobotWin 1 task×50ep/轮（CogACT 一头一 task），
 `test_num` 官方口径。分片默认 8（EE 默认 4：`fast_init=false` 全量 planner +
 SAPIEN 抢显存，8 分片 OOM）；生产切法 serve 独占卡 0、分片放卡 1。
 超时 chunk 10080（7 天；easy50 完整对照约 2~3 天）。
 耗时参考：单 ep 2~10 分钟；一轮（1 task×50ep，2 分片）3~7 小时。

2. 交付（按下表填，缺一项不算完整报告）：

```json
{
  "model": "<模型名+权重地址>",
  "task": "<考场-任务-条件>",
  "mean_success": 0.0,
  "hard_success": null,
  "gap": null,
  "steps_success": {"med": null, "mean": null},
  "n": 50,
  "errors": 0,
  "versions": {"harness": "v0.8.0", "benchmark_image": "<镜像:tag>"},
  "machine": "<GPU型号>",
  "seeds": "bundled/盲种子说明",
  "date": "YYYY-MM-DD",
  "artifacts": "<OBS 链接>"
}
```

跑分必报的披露清单（缺一个别比）：GPU / dtype / benchmark 镜像 tag
（含 slim/补丁说明）/ serve 镜像 / 种子（bundled 还是盲）/ 分片 / 资产挂载 /
checkpoint 与训练说明（权重精确版本 + 按 task 分头情况 + 微调口径）。

3. 到 OBS 收：`<obs_prefix>/<榜>-<smoke|full>/`（flat 打平）。
 dispatch 参数 `obs_prefix` 可自填（默认 `obs://so101-sim-pipeline/eval`），
 开跑前写探针校验，失败不烧卡。RobotWin smoke 强制录像；全量 `video=1` 打开。

## 检查点

- [ ] 报告 12 个字段全齐？`hard_success/gap` 暂空必须注明"Hard 待补"，不能删字段。
- [ ] 披露 8 项全齐？缺一个不上榜。
- [ ] `errors` 单列了？坏种剔除数公示了？先看 errors 再看 mean。
- [ ] 条件写进 task 身份了？easy/hard 不同条件不上同榜。

## 原理

* **分片只动速度不动分**（分片对照）：2 稳、4 慢、8 在单卡多 SAPIEN 上下文会 hang。
 分片是环境并行（共享同一 SQLite，`vla-eval export` 出 aggregate），不改变种子口径判分。
* **四列表**：Easy 成功率（现有）/ Hard 成功率（待补：`demo_randomized` run yaml，
 无代码改动）/ 落差 Easy−Hard（robustness 主指标：Pi0 grab_roller 96%→80%，
 DP 98%→0%，单列 Easy 会系统性高估）/ 成功集步数 med/mean（效率；现躺 note 里待转正）。
 排名主排序用 Hard，Easy 作基线，同分看步数。
* **排名四条**：①同协议才可比（镜像 tag、`test_num`/种子集、harness 版本、
 checkpoint 与训练口径全 locked；RobotWin 官方协议 §4.5：单 task 微调 50 demos →
 Easy/Hard 各 100 rollouts；我们现状 Easy×50ep，Hard 与训练数据披露待补）。
 ②分榜排名不合总分（多榜指标待接入后展开）。
 ③点估计排序区间分档（n=50 噪声带 ±6pp："10pp 同档，10~15pp 待定，15pp 以上分档"；
 place_empty_cup 16% vs 28% 差 12pp → 待定）。④error 口径一致 + 榜单四要素
 （分数 + n + 版本日期 + 机器；同卡才可比，换卡重打基线）。
* **分数怎么读**：`mean_success`（RobotWin）= 成功 ep / 总 ep，二值平均；
 和官称 ±5pp 算对上，差 10pp 先查口径（[08-troubleshooting.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/old/08-troubleshooting.md) 第 1 条）；
 跨榜不比大小。
* **训练口径是变量**：[官方 Table 3](https://arxiv.org/abs/2506.18088) 同一模型×三种训练口径并列比成功率——clean 微调
 几乎无提升，Rand 预训练 +30%。不同口径的分数只许并列，不许排名。
* **披露清单的来历**：每一项对应一张"旋钮×影响"对照表（[proposal-stack-effects.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/proposal-stack-effects.md)）：
 镜像对照（差 6pp 不搬分）、精度对照（29/30 vs 0/30 搬命）、分片对照（只动速度）、
 种子对照（盲 15 坏种 vs 校验零 error）、机器精度对照（待定档，只披露不硬判）。

## 下一步

* 栈差异对照的完整来龙去脉 → `explanation/`（待写）。
* 真正的基模评测（固定数据+训练方式横向比）→ 训练侧立项，不在本教程范围（见 [index.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/index.md) 评价 vs 评测）。
