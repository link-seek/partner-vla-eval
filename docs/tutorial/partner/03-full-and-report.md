# 伙伴 03：全量与报告（计分、出榜）

> 目标：拿到可上榜的分数和完整报告。
> 时间：3~7 小时/task（V100 单卡，串行累加） ｜ 前置：`02` smoke 通过 ｜
> 你将得到：每个 task 的 `mean_success` + 录像 + 官方口径对照说明。
> 读法：`操作`是排期与交付；`原理`是排名规则与分数读法（看不懂分就白跑了）。

## 操作：排期（smoke 通过后自动进队列）

* RobotWin：1 task×50ep/轮（CogACT 一头一 task），`test_num` 官方口径。
* 分片默认 8（EE 默认 4：`fast_init=false` 全量 planner + SAPIEN 抢显存，8 分片 OOM）。
  生产切法：serve 独占卡 0、分片放卡 1。
* 超时 chunk 10080（7 天；easy50 完整对照约 2~3 天）。
* 耗时参考：单 ep 2~10 分钟（成功短、失败跑满全程）；一轮（1 task×50ep，2 分片）3~7 小时。

> **原理·分片只动速度不动分**（实验 C）：2 稳、4 慢、8 在单卡多 SAPIEN 上下文会
> hang（watchdog 全杀）。分片是环境并行（`run_sharded.sh -n N` 共享同一 SQLite，
> 跑完 `vla-eval export` 出 aggregate），不改变种子、口径、判分，所以不动分。
> 上游论文另有 batch 并行（模型侧），我们 V100 单卡只用分片这一轴。

## 操作：交付（缺一项不算完整报告）

```json
{
  "model": "<模型名+权重地址>",
  "task": "<考场-任务>",
  "mean_success": 0.0,
  "n": 50,
  "errors": 0,
  "versions": {"harness": "v0.8.0", "benchmark_image": "<镜像:tag>"},
  "machine": "<GPU型号>",
  "seeds": "bundled/盲种子说明",
  "date": "YYYY-MM-DD",
  "artifacts": "<OBS/artifact 链接>"
}
```

跑分必报的披露清单（缺一个别比）：GPU / dtype / benchmark 镜像 tag（含 slim/补丁说明）
/ serve 镜像 / 种子（bundled 还是盲）/ 分片 / 资产挂载。

> **原理·为什么披露清单就是这 7 项**：每一项都对应一张"旋钮×影响"对照表
> （`docs/proposal-stack-effects.md`，V100 实测 10-14~16）：A 镜像版本（差 6pp，
> 2σ 内，不搬分）、B 精度（29/30 vs 0/30，搬命）、C 分片（只动速度）、
> D 种子（盲种子 15 坏种 vs 校验种子零 error）。动过分的东西必须披露，
> 没动过分的东西披露了证明清白。E（V100 fp16 vs 官方 H100 bf16）待定档：
> 只写进披露，不硬判，见 99。

## 原理：排名规则（四条）

1. **同协议才可比**：镜像 tag、`test_num`/种子集、harness 版本全 locked。我们的链路天然保证（配置钉版）。
2. **分榜排名，不合总分**：每个 task 一个榜；跨 task 看画像（并列），不造加权总分
 （权重一拍脑袋就失去公信）。CALVIN 主指标是平均链长（0~5，对齐上游论文 Table II），
  LIBERO/RobotWin 是成功率 %——指标不同，更不能加权。
3. **点估计排序，区间分档**：n=50 时噪声带约 ±6pp，"10pp 以内判同档；
 10~15pp 待定；15pp 以上分档"。例：place_empty_cup 我们 16% vs 官称 28%
 （差 12pp）→ 待定，不硬判高下。
4. **error 口径一致 + 榜单四要素**：坏种 error 剔除后比有效成功率，剔除数公示；
 分数 + n + 版本日期 + **机器**（GPU+dtype+镜像 tag），缺一个不上榜。
 同卡才可比，换卡重打基线，榜单按机器分组。

## 原理：分数怎么读

* `mean_success`（LIBERO/RobotWin）= 成功 ep 数 / 总 ep 数，二值平均。
* 和官称差 ±5pp 以内算对上（噪声+种子集差异）；差 10pp 以上先查口径（08 第 1 条）。
* `error` ≠ `fail`：`fail` 模型没做出来；`error` 是 infra/坏种子抛异常，单列。
 看分先看 errors，再看 mean。
* 跨榜不比大小：LIBERO 99% 和 RobotWin 16% 没有可比性，各榜难度和判分标尺不同。

判分记账：harness 不发明分数，各榜原生规则 + 透传汇总；error 分三类
（模型失败判 0 / 坏种子 `UnStableError` 单列 / infra 异常重跑）；aggregate JSON +
SQLite 进 artifact 与 OBS（`eval/<榜>-*/`），Discussion 记结论。
