# 07 开跑与判分

> 版本：v1.0（2026-10-14）

## smoke（必经）

1 task×1ep（CALVIN 用 5 sequences），验证：镜像/权重/serve-up/口径/落盘。
先 smoke 后全量，省卡钱。录像常开（1ep 体积小，出 0 分时亲眼看）。

## 全量（分块战役）

- RobotWin：1 task×50ep/轮（CogACT 一头一 task），`test_num` 官方口径。
- 分片：2 分片（4 分片以上抢单卡会 hang，见 08），serve 独占卡0、分片放卡1。
- 超时：自托管上限 5 天，chunk 设 1440（别信 6 小时，那是公有 runner 的）。
- 耗时参考：单 ep 2~10 分钟，一轮 3~7 小时。

## 最终报告模板（缺一项不算完整报告）

```json
{
  "model": "<模型名+权重地址>",
  "task": "<考场-任务>",
  "mean_success": 0.0,
  "n": 50,
  "errors": 0,
  "versions": {"harness": "v0.7.0", "benchmark_image": "<镜像:tag>"},
  "machine": "<GPU型号>",
  "seeds": "bundled/盲种子说明",
  "date": "YYYY-MM-DD",
  "artifacts": "<OBS/artifact 链接>"
}
```

## 伙伴之间怎么比（排名规则）

1. **同考场同种子同版本**：镜像 tag、test_num/种子集、harness 版本全 locked 才可比。
   我们的链路天然保证（配置钉版，见 05）。
2. **分榜排名，不合总分**：每个 task 一个榜；跨 task 看画像（各 task 分数并列），
   不造加权总分（权重一拍脑袋就失去公信）。
3. **差 10pp 以内判同档**：n=50 时噪声带约 ±6pp（p=0.2），2σ≈11pp。
   10pp 以内并列；10~15pp 标“待定”（加样本再判）；15pp 以上分档（S/A/B）。
   例：place_empty_cup 我们 16% vs 官称 28%（差 12pp）→ 待定，不硬判高下。
4. **error 口径一致**：坏种 error 剔除后再比有效成功率；剔除数也要公示。
5. **榜单四要素**：分数 + n + 版本日期 + **机器**（GPU型号+镜像tag），缺一个不上榜。
   同卡才可比：V100 的分数和 H100 的分数不上同一个榜；换卡重打基线，榜单按机器分组。

## 分数怎么读（92% 到底在说什么）

- `mean_success` = 成功 ep 数 / 总 ep 数。**二值分**：一个 ep 要么整单完成（1），
  要么 0，没有“完成一半给 0.5”。400 步没做出来和第一步就崩，都记 0。
- 和官称差多少算正常：±5pp 以内算对上（噪声+种子集差异）；
  差 10pp 以上先查口径（08 第 1 条），不要先怀疑模型。
- `error` ≠ `fail`：`fail` 是模型没做出来；`error` 是 infra/坏种子抛异常，
  不怪模型，单列。看分先看 errors，再看 mean。
- 跨榜不比大小：LIBERO 99% 和 RobotWin 16% 没有可比性，各榜难度和判分标尺不同，
  只并列展示（我们在总表里就是这么列的）。

## 判分记分

- harness 不发明分数：各榜原生规则 + `mean_success` 透传，跨榜只并列不加权。
- error 分类记法：模型失败（判 0 分）/ 坏种子 `UnStableError`（单列，不怪模型）/ infra 异常（重跑）。
- 归档：aggregate JSON + SQLite 进 artifact 与 OBS（`eval/<榜>-*/`），Discussion 记结论。
