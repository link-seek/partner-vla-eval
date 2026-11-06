---
title: 伙伴 02：全量与报告
parent: 评测教程
nav_order: 4
---

# 伙伴 02：全量与报告（出分）

> 目标：拿到每个 task 的成功率和完整报告。
> 时间：按 task 数排期（单 task 3~7 小时，分片由我们排） ｜ 前置：smoke 通过。
> 你将得到：每 task 成功率 + 报告（n/errors/版本/机器/种子）+ 官方口径对照。

## 操作

smoke 通过后进全量队列，你不需要操作。全量按 task 跑，每个 task 50ep，跑完出报告。

报告字段：

| 字段 | 含义 |
|---|---|
| model | 模型名 + 权重地址 |
| task | 考场-任务-条件（Easy/Hard 分开记） |
| mean_success | 成功 ep / 总 ep |
| n | 总 ep 数（现状 50） |
| errors | 错误 ep 数；先看它，再看分数 |
| versions | harness 版本 + benchmark 镜像 tag |
| machine | GPU 型号 |
| seeds | bundled / 盲种子说明 |
| date | 跑测日期 |
| artifacts | 产物链接 |

Hard 成功率、Easy−Hard 落差、成功步数：现在没有，报告里标“待补”，不当 0 算。

随报告给的披露清单：GPU / dtype / benchmark 镜像 tag / serve 镜像 / 种子 / checkpoint 精确版本 + 按 task 分头 + 微调口径。

## 检查点

- [ ] 每个 task 的 `n` 和 `errors` 都在？先看 errors，再看 mean。
- [ ] Easy/Hard 条件写进 task 身份了？不同条件不混榜。
- [ ] 版本、机器、种子、checkpoint 精确版本齐全？
- [ ] Hard 没跑就写“待补”，不能当 0 分。

## 原理

* **分数怎么算**：RobotWin 的 `mean_success` = 成功 ep / 总 ep，二值平均；和官称（[Dexbotic 结果表](https://github.com/Dexmal/dexbotic#benchmark-results)）±5pp 算对上，差 10pp 先查口径。
* **为什么按 task 出、不合成总分**：task 之间难度和判分不同，跨 task/榜不可加；报告并列展示，不加权总分。
* **噪声**：n=50 的点估计有 ±6pp 噪声带——10pp 内同档，10~15pp 待定，15pp 以上才分档。
* **训练口径是变量**：同一模型换训练口径，成功率会变（官方 Table 3：RDT 18.8%→24.8%，相对 +30%，绝对 6pp）；不同口径只并列，不排名。
* **Easy 与 Hard**：官方 §4.5 是单 task 微调 50 demos → Easy/Hard 各 100 rollouts；我们现状 Easy×50ep，Hard 待补。只拿 Easy 解读会高估鲁棒性。
* **同卡才可比**：换 GPU 要重打基线；报告四要素——分数 + n + 版本日期 + 机器，缺一个不比。

## 报告样例

单 task 长这样（示例数据，非真实分数；Hard/步数没跑时置 `null`，不写 0）：

```json
{
  "model": "my-vla / hf:org/my-vla@3f2a1c9",
  "task": "robotwin-easy/grab_roller",
  "mean_success": 0.86,
  "n": 50,
  "errors": 0,
  "versions": {
    "harness": "0.8.0",
    "benchmark_image": "vla-eval-robotwin:0.8.0-ee-slim"
  },
  "machine": "V100 32GB",
  "seeds": "bundled（expert-checked，从 100000）",
  "date": "2026-11-06",
  "artifacts": "obs://<bucket>/<prefix>/robotwin-full/grab_roller/",
  "hard_success": null,
  "gap": null,
  "steps_success": {"med": null, "mean": null}
}
```

## 下一步

基模横向评测（固定数据 + 训练方式比强弱）不在本教程范围，见 [index.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/index.md) 的“评价 vs 评测”。
